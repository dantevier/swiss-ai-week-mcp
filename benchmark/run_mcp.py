#!/usr/bin/env python3
"""Let a model answer the benchmark with the MCP tools, then score it.

    uv sync --extra bench
    python benchmark/run_mcp.py --per-area 2          # Claude if ANTHROPIC_API_KEY is set, else GPT with OPENAI_API_KEY
    python benchmark/run_mcp.py --model claude-opus-5 --per-area 2
    python benchmark/run_mcp.py --model gpt-5 --per-area 2
    python benchmark/run_mcp.py --model openrouter:swiss-ai/apertus-70b-instruct --per-area 2
    python benchmark/run_mcp.py --model ollama:qwen3 --topic-area 1 --limit 10
    python benchmark/run_mcp.py --model compat:my-model --base-url https://host/v1 --api-key-env MY_KEY

Add --no-mcp for a baseline without tools. Each run writes answers, tool-call
transcripts, the score report and its interpretation to benchmark/runs/<time>-<model>-<mcp|no-mcp>/;
the dashboard's Benchmark tab shows the latest one.

--model is "provider:model". A bare "claude-..." name means provider "anthropic",
a bare "gpt-..." or "o<digit>..." name means "openai".
API keys come from the environment, then from the project's .env file
(the dashboard's Settings page saves OPENAI_API_KEY and ANTHROPIC_API_KEY there). Providers and their key:
    anthropic   ANTHROPIC_API_KEY (or an `ant auth login` profile)
    openai      OPENAI_API_KEY
    openrouter  OPENROUTER_API_KEY
    ollama      none (local, http://localhost:11434/v1)
    compat      --api-key-env, with --base-url (any OpenAI-compatible endpoint)
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import datetime as dt
import json
import logging
import os
import random
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from interpret import interpret  # noqa: E402
from score import DEFAULT_DATA, load_questions  # noqa: E402

ENV_FILE = HERE.parent / ".env"

PROVIDERS = {
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "ollama": ("http://localhost:11434/v1", None),
    "compat": (None, None),
}
# Admin tools that change state or start servers; a benchmark answer should never need them.
EXCLUDED_TOOLS = re.compile(r"^(crawl_.*|open_dashboard|source_status)$")
MAX_TOOL_ROUNDS = 8
MAX_TOOL_RESULT_CHARS = 12_000  # get_source can return whole laws
TOPIC_TOOLS = {
    1: {"swiss_health_insurance_premiums", "swiss_geo_search", "swiss_geo_context"},
    3: {"swiss_housing_info"},
    6: {"swiss_residence_permit_guidance"},
    9: {"swiss_school_holidays"},
    11: {"get_driving_licence_exchange_info", "search_knowledge"},
    12: {"swiss_reference_interest_rate", "swiss_housing_info"},
    13: {"swiss_federal_political_rights"},
    14: {"company_info", "search_knowledge"},
    15: {"swiss_import_parcel_vat", "search_knowledge"},
    16: {"bfs_population", "opendata_search_datasets", "opendata_dataset", "swiss_geo_search", "swiss_geo_context"},
}

SYSTEM_PROMPT = """You answer questions from residents about Swiss public services and official data.
Answer in the language of the question. Be brief and give concrete figures, dates and deadlines.
Name the responsible authority and its website domain.
If the answer depends on information the user has not given (for example their municipality), ask for it instead of guessing.
If the question is not about Switzerland, say so and do not answer with Swiss information.
If you cannot find a reliable answer, say so instead of guessing."""
TOOLS_HINT = "\nUse the available tools to look up official sources before answering."


def system_prompt(mcp: McpTools | None) -> str:
    if mcp is None:
        return SYSTEM_PROMPT
    return SYSTEM_PROMPT + TOOLS_HINT + ("\n" + mcp.instructions if mcp.instructions else "")


# ---------- MCP ----------

class McpTools:
    """The server's tools, called in-process through a FastMCP client."""

    def __init__(self, client: Any, tools: list[Any], instructions: str = ""):
        self.client = client
        self.tools = [t for t in tools if not EXCLUDED_TOOLS.match(t.name)]
        self.instructions = instructions

    async def call(self, name: str, args: dict[str, Any]) -> tuple[str, bool]:
        try:
            result = await self.client.call_tool(name, args, raise_on_error=False)
        except Exception as e:  # unknown tool, bad arguments, transport error
            return f"Error: {e}", True
        text = "\n".join(getattr(block, "text", "") for block in result.content) or "(empty result)"
        if len(text) > MAX_TOOL_RESULT_CHARS:
            text = text[:MAX_TOOL_RESULT_CHARS] + f"\n[truncated, {len(text)} chars in total]"
        return text, bool(result.is_error)


# ---------- providers ----------

class AnthropicAgent:
    def __init__(self, model: str):
        import anthropic

        self.anthropic = anthropic
        self.client = anthropic.AsyncAnthropic()
        self.model = model

    async def answer(self, question: str, mcp: McpTools | None, log: list) -> str:
        tools = [
            {"name": t.name, "description": t.description or "", "input_schema": t.input_schema}
            for t in (mcp.tools if mcp else [])
        ]
        system = system_prompt(mcp)
        messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
        for _ in range(MAX_TOOL_ROUNDS + 1):
            kwargs = {"tools": tools} if tools else {}
            response = await self.client.messages.create(
                model=self.model, max_tokens=16000, system=system, messages=messages, **kwargs
            )
            if response.stop_reason == "refusal":
                log.append({"refusal": getattr(response.stop_details, "category", None)})
                return ""
            calls = [b for b in response.content if b.type == "tool_use"]
            if response.stop_reason != "tool_use" or not calls:
                return "".join(b.text for b in response.content if b.type == "text").strip()
            messages.append({"role": "assistant", "content": response.content})
            results = []
            for call in calls:
                text, is_error = await mcp.call(call.name, call.input)
                log.append({"tool": call.name, "args": call.input, "error": is_error, "result": text})
                results.append({"type": "tool_result", "tool_use_id": call.id, "content": text, "is_error": is_error})
            messages.append({"role": "user", "content": results})
        return ""  # still calling tools after MAX_TOOL_ROUNDS


class OpenAICompatAgent:
    def __init__(self, model: str, base_url: str, api_key: str, require_tool: bool = False):
        import openai

        self.client = openai.AsyncOpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.require_tool = require_tool

    async def answer(self, question: str, mcp: McpTools | None, log: list) -> str:
        tools = [
            {"type": "function",
             "function": {"name": t.name, "description": t.description or "", "parameters": t.input_schema}}
            for t in (mcp.tools if mcp else [])
        ]
        system = system_prompt(mcp)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ]
        for round_idx in range(MAX_TOOL_ROUNDS + 1):
            kwargs = {"tools": tools} if tools else {}
            if round_idx == 0 and tools and self.require_tool:
                kwargs["tool_choice"] = "required"
            response = await self.client.chat.completions.create(model=self.model, messages=messages, **kwargs)
            message = response.choices[0].message
            if not message.tool_calls:
                return (message.content or "").strip()
            messages.append(message.model_dump(exclude_none=True))
            for call in message.tool_calls:
                try:
                    args = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError as e:
                    text, is_error = f"Error: arguments are not valid JSON: {e}", True
                else:
                    text, is_error = await mcp.call(call.function.name, args)
                log.append({"tool": call.function.name, "args": call.function.arguments, "error": is_error,
                            "result": text})
                messages.append({"role": "tool", "tool_call_id": call.id, "content": text})
        return ""


def load_env_file(path: Path = ENV_FILE) -> None:
    """Fill in API keys from the project's .env without overriding the real environment."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and not line.lstrip().startswith("#") and key.strip() not in os.environ:
            os.environ[key.strip()] = value.strip()


DEFAULT_MODELS = [("ANTHROPIC_API_KEY", "claude-opus-5"), ("OPENAI_API_KEY", "gpt-5")]


def default_model() -> str:
    """Pick a model from whichever API key is set: Anthropic first, then OpenAI."""
    for key, model in DEFAULT_MODELS:
        if os.environ.get(key):
            return model
    raise SystemExit("No API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY (environment, .env, or the "
                     "dashboard's Settings page), or pass --model, e.g. ollama:qwen3 for a local model.")


def split_model(spec: str) -> tuple[str, str]:
    provider, _, model = spec.partition(":")
    if model:
        return provider, model
    if spec.startswith("claude"):
        return "anthropic", spec
    if re.match(r"(gpt-|o\d)", spec):
        return "openai", spec
    raise SystemExit(f"--model {spec!r} needs a provider, e.g. openai:{spec} or ollama:{spec}")


def make_agent(args: argparse.Namespace):
    provider, model = split_model(args.model)
    if provider == "anthropic":
        return AnthropicAgent(model)
    if provider not in PROVIDERS:
        raise SystemExit(f"unknown provider in --model {args.model!r}; use one of: anthropic, {', '.join(PROVIDERS)}")
    base_url, key_env = PROVIDERS[provider]
    base_url = args.base_url or base_url
    key_env = args.api_key_env or key_env
    if not base_url:
        raise SystemExit("--base-url is required for provider 'compat'")
    api_key = os.environ.get(key_env) if key_env else "not-needed"
    if not api_key:
        raise SystemExit(f"set {key_env} for provider {provider!r}")
    return OpenAICompatAgent(model, base_url, api_key, args.require_tool)


# ---------- run ----------

def pick_questions(args: argparse.Namespace) -> list[dict[str, Any]]:
    rows = load_questions(args.data)
    if args.topic_area:
        rows = [r for r in rows if int(r["topic_area"]) == args.topic_area]
    if args.per_area:
        by_area = collections.defaultdict(list)
        for r in rows:
            by_area[int(r["topic_area"])].append(r)
        rng = random.Random(args.seed)
        rows = [r for area in sorted(by_area) for r in rng.sample(by_area[area], min(args.per_area, len(by_area[area])))]
    return rows[: args.limit] if args.limit else rows


async def run(args: argparse.Namespace, questions: list[dict[str, Any]], out: Path) -> int:
    agent = make_agent(args)
    semaphore = asyncio.Semaphore(args.concurrency)
    done = 0

    async def one(row, mcp):
        nonlocal done
        log: list = []
        scoped_mcp = mcp
        if mcp and args.relevant_tools:
            names = TOPIC_TOOLS[int(row["topic_area"])]
            scoped_mcp = McpTools(mcp.client, [t for t in mcp.tools if t.name in names], mcp.instructions)
        async with semaphore:
            try:
                answer = await agent.answer(row["question"], scoped_mcp, log)
            except Exception as e:  # keep the run going; the item scores as "no answer"
                answer, log = "", log + [{"error": f"{type(e).__name__}: {e}"}]
        done += 1
        error = next((x["error"] for x in log if isinstance(x.get("error"), str)), None)
        status = f"FAILED {error}" if error else f"{len([x for x in log if 'tool' in x])} tool calls"
        print(f"[{done}/{len(questions)}] {row['id']}: {status}", file=sys.stderr)
        return {"id": row["id"], "question": row["question"], "answer": answer, "trace": log}

    if args.no_mcp:
        results = await asyncio.gather(*(one(r, None) for r in questions))
    else:
        from fastmcp import Client

        from mcp_swiss_info.server import mcp as server

        async with Client(server) as client:
            mcp = McpTools(client, await client.list_tools(), server.instructions or "")
            print(f"MCP tools: {', '.join(t.name for t in mcp.tools)}", file=sys.stderr)
            results = await asyncio.gather(*(one(r, mcp) for r in questions))

    with (out / "answers.jsonl").open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps({k: r[k] for k in ("id", "question", "answer")}, ensure_ascii=False) + "\n")
    with (out / "traces.jsonl").open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps({"id": r["id"], "trace": r["trace"]}, ensure_ascii=False) + "\n")
    failed = sum(any(isinstance(x.get("error"), str) for x in r["trace"]) for r in results)
    if failed:
        print(f"\nWARNING: {failed}/{len(results)} questions failed with an API error, see traces.jsonl", file=sys.stderr)
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", help='"provider:model", e.g. claude-opus-5, gpt-5, ollama:qwen3 '
                        "(default: claude-opus-5 if ANTHROPIC_API_KEY is set, else gpt-5 if OPENAI_API_KEY is set)")
    parser.add_argument("--no-mcp", action="store_true", help="baseline: answer without tools")
    parser.add_argument("--require-tool", action="store_true", help="require one tool call on the first OpenAI-compatible MCP request")
    parser.add_argument("--relevant-tools", action="store_true", help="offer only the tools for each covered benchmark topic")
    parser.add_argument("--data", type=Path, nargs="+", default=DEFAULT_DATA, help="question files (default as score.py)")
    parser.add_argument("--topic-area", type=int, choices=range(1, 17), help="only this topic area (1-16)")
    parser.add_argument("--per-area", type=int, help="sample N questions per topic area")
    parser.add_argument("--limit", type=int, help="stop after N questions")
    parser.add_argument("--seed", type=int, default=7, help="sampling seed, same seed = same questions (default 7)")
    parser.add_argument("--concurrency", type=int, default=4, help="questions answered in parallel (default 4)")
    parser.add_argument("--base-url", help="API base URL, overrides the provider default")
    parser.add_argument("--api-key-env", help="environment variable holding the API key")
    args = parser.parse_args()

    load_env_file()
    args.model = args.model or default_model()
    provider, _ = split_model(args.model)
    questions = pick_questions(args)
    if not questions:
        parser.error("no questions selected")
    if args.relevant_tools and any(int(q["topic_area"]) not in TOPIC_TOOLS for q in questions):
        parser.error("--relevant-tools requires questions only from covered topics")
    slug = re.sub(r"[^A-Za-z0-9.-]+", "_", args.model)
    out = HERE / "runs" / f"{dt.datetime.now():%Y%m%d-%H%M%S}-{slug}-{'no-mcp' if args.no_mcp else 'mcp'}"
    out.mkdir(parents=True)
    # Score only the selected questions, so a sample is not counted against unanswered ones.
    with (out / "questions.jsonl").open("w", encoding="utf-8") as f:
        for r in questions:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    logging.getLogger("mcp_swiss_info").setLevel(logging.WARNING)
    print(f"{len(questions)} questions, model {args.model}, {'no MCP' if args.no_mcp else 'with MCP'} -> {out}", file=sys.stderr)
    meta = {"model": args.model, "provider": provider, "mcp": not args.no_mcp, "require_tool": args.require_tool,
            "relevant_tools": args.relevant_tools,
            "questions": len(questions),
            "seed": args.seed, "per_area": args.per_area, "topic_area": args.topic_area,
            "started": dt.datetime.now().astimezone().isoformat(timespec="seconds")}
    meta["api_errors"] = asyncio.run(run(args, questions, out))
    meta["finished"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    (out / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")

    report = subprocess.run(
        [sys.executable, str(HERE / "score.py"), str(out / "answers.jsonl"), "--data", str(out / "questions.jsonl"),
         "--out", str(out / "results.jsonl"), "--judge-prompts", str(out / "judge_prompts.jsonl")],
        capture_output=True, text=True, encoding="utf-8",
    )
    text = report.stdout + report.stderr + interpret(out) + "\n"
    (out / "report.txt").write_text(text, encoding="utf-8")
    print(text)
    print(f"Saved to {out}\nOpen the dashboard's Benchmark tab to browse this run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
