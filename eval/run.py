"""Run every question against every (model x MCP set) and log answer, tool calls, latency, cost.

Resumable: already-completed runs (without error) are skipped.

    python run.py                          # everything
    python run.py --stage 1                # only stage-1 models
    python run.py --models myai-default --mcp-sets swiss-grounding
"""
import argparse
import asyncio
import getpass
import json
import re
import time
from contextlib import AsyncExitStack
from datetime import datetime, timezone
from pathlib import Path

import litellm
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

try:  # MCP Python SDK >= 2
    import httpx2
    from mcp.client.streamable_http import streamable_http_client

    async def open_http(stack, url, headers):
        client = await stack.enter_async_context(httpx2.AsyncClient(headers=headers))
        streams = await stack.enter_async_context(streamable_http_client(url, http_client=client))
        return streams[0], streams[1]
except ImportError:  # SDK 1.x
    from mcp.client.streamable_http import streamablehttp_client

    async def open_http(stack, url, headers):
        streams = await stack.enter_async_context(streamablehttp_client(url, headers=headers))
        return streams[0], streams[1]

from common import load_config, load_jsonl

litellm.drop_params = True
MAX_TOOL_RESULT_CHARS = 20_000


async def open_mcp(stack, cfg):
    if cfg["transport"] == "stdio":
        params = StdioServerParameters(command=cfg["command"], args=cfg.get("args", []), env=cfg.get("env"), cwd=cfg.get("cwd"))
        read, write = await stack.enter_async_context(stdio_client(params))
    else:
        read, write = await open_http(stack, cfg["url"], cfg.get("headers") or {})
    session = await stack.enter_async_context(ClientSession(read, write))
    await session.initialize()
    return session


def to_openai_tools(server, mcp_tools, tool_map):
    """Convert MCP tools to OpenAI function format (LiteLLM translates per provider)."""
    out = []
    for t in mcp_tools:
        name = re.sub(r"[^a-zA-Z0-9_-]", "_", f"{server}__{t.name}")[:64]
        tool_map[name] = (server, t.name)
        out.append({
            "type": "function",
            "function": {
                "name": name,
                "description": (t.description or "")[:1024],
                "parameters": (getattr(t, "input_schema", None) or getattr(t, "inputSchema", None)
                               or {"type": "object", "properties": {}}),
            },
        })
    return out


async def answer(model_cfg, system_prompt, sessions, tools, tool_map, question, max_turns):
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": question}]
    calls, usage, cost = [], {"prompt_tokens": 0, "completion_tokens": 0}, 0.0

    for _ in range(max_turns):
        kwargs = {"model": model_cfg["model"], "messages": messages, **model_cfg.get("params", {})}
        if tools:
            kwargs["tools"] = tools
        resp = await litellm.acompletion(**kwargs)

        if getattr(resp, "usage", None):
            usage["prompt_tokens"] += resp.usage.prompt_tokens or 0
            usage["completion_tokens"] += resp.usage.completion_tokens or 0
        try:
            cost += litellm.completion_cost(completion_response=resp) or 0.0
        except Exception:
            pass  # unknown pricing (e.g. custom endpoints)

        msg = resp.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None)
        if not tool_calls:
            return msg.content or "", calls, usage, cost

        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in tool_calls
            ],
        })
        for tc in tool_calls:
            server, tool = tool_map.get(tc.function.name, (None, tc.function.name))
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            try:
                res = await sessions[server].call_tool(tool, args)
                text = "\n".join(getattr(c, "text", "") for c in getattr(res, "content", []) or []) or "(empty result)"
                if getattr(res, "is_error", None) or getattr(res, "isError", None):
                    text = "TOOL ERROR: " + text
            except Exception as e:
                text = f"TOOL ERROR: {e!r}"
            calls.append({"server": server, "tool": tool, "args": args, "result_preview": text[:1000]})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": text[:MAX_TOOL_RESULT_CHARS]})

    return "[max tool turns reached without final answer]", calls, usage, cost


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--models", nargs="*", help="model ids to run")
    ap.add_argument("--mcp-sets", nargs="*", help="MCP set names to run")
    ap.add_argument("--stage", type=int, help="only models with this stage")
    ap.add_argument("--model-name", help="ad-hoc model, LiteLLM string, e.g. openai/gpt-4.1 or mistral/mistral-large-latest")
    ap.add_argument("--api-base", help="ad-hoc model: API base URL (OpenAI-compatible endpoints)")
    ap.add_argument("--api-key", help="ad-hoc model: API key (omit to use the provider env var)")
    ap.add_argument("--ask", action="store_true", help="prompt for model name, API base and API key")
    a = ap.parse_args()

    cfg = load_config(a.config)
    questions = load_jsonl(cfg["questions"])
    out = Path(cfg["results"])
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {r["run_key"] for r in load_jsonl(out) if not r.get("error")}

    if a.ask:
        a.model_name = a.model_name or input("Model (LiteLLM string, e.g. openai/gpt-4.1): ").strip()
        a.api_base = a.api_base or input("API base URL (blank = provider default): ").strip() or None
        a.api_key = a.api_key or getpass.getpass("API key (blank = use provider env var): ") or None
    if a.model_name:  # ad-hoc model replaces the configured list
        params = {k: v for k, v in (("api_base", a.api_base), ("api_key", a.api_key)) if v}
        models = [{"id": a.model_name.split("/")[-1], "model": a.model_name, "params": params}]
    else:
        models = [m for m in cfg["models"]
                  if (not a.models or m["id"] in a.models) and (a.stage is None or m.get("stage") == a.stage)]
        for m in models:
            if "REPLACE_WITH" in m["model"]:
                raise SystemExit(f"Model '{m['id']}' still has a placeholder name in config.yaml. "
                                 "Edit it, or run with --model-name / --ask.")
    mcp_sets = {k: v for k, v in cfg["mcp_sets"].items() if not a.mcp_sets or k in a.mcp_sets}
    sem = asyncio.Semaphore(cfg.get("concurrency", 4))
    lock = asyncio.Lock()

    with out.open("a", encoding="utf-8") as f:
        for set_name, server_names in mcp_sets.items():
            async with AsyncExitStack() as stack:
                sessions, tools, tool_map = {}, [], {}
                for s in server_names:
                    sessions[s] = await open_mcp(stack, cfg["mcp_servers"][s])
                    tools += to_openai_tools(s, (await sessions[s].list_tools()).tools, tool_map)
                print(f"[{set_name}] {len(tools)} tools loaded")

                async def job(m, q, rep, key):
                    async with sem:
                        t0 = time.time()
                        err = None
                        try:
                            ans, calls, usage, cost = await answer(
                                m, cfg["system_prompt"], sessions, tools, tool_map,
                                q["question"], cfg.get("max_tool_turns", 8))
                        except Exception as e:
                            ans, calls, usage, cost, err = None, [], {}, None, repr(e)
                        rec = {
                            "run_key": key, "model_id": m["id"], "mcp_set": set_name, "repeat": rep,
                            **{k: q.get(k) for k in ("qid", "group_id", "topic", "language", "level",
                                                     "expected_behaviour", "question")},
                            "answer": ans, "tool_calls": calls, "n_tool_calls": len(calls),
                            "latency_s": round(time.time() - t0, 2),
                            "prompt_tokens": usage.get("prompt_tokens"),
                            "completion_tokens": usage.get("completion_tokens"),
                            "cost_usd": cost, "error": err,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    async with lock:
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        f.flush()
                    print(f"  {'ERR' if err else 'ok '} {m['id']:<20} {q['qid']:<10} {rec['latency_s']}s"
                          + (f"  {err[:120]}" if err else ""))

                jobs = []
                for m in models:
                    for q in questions:
                        for rep in range(cfg.get("repeats", 1)):
                            key = f"{m['id']}|{set_name}|{q['qid']}|{rep}"
                            if key not in done:
                                jobs.append(job(m, q, rep, key))
                await asyncio.gather(*jobs)


if __name__ == "__main__":
    asyncio.run(main())
