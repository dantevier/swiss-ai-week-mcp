"""Guided run: answer a few questions, then run + grade + report in one go.

    python start.py
    python start.py --dry-run          # show the generated config and commands, run nothing
    python start.py --skip-baseline    # do not also run the model without the MCP server

Asks for: (1) the model to test and its access, (2) the MCP server to test.
Secrets are passed to the child processes through environment variables and never written to disk.
"""
import argparse
import getpass
import os
import shlex
import subprocess
import sys
from pathlib import Path

import yaml

import import_benchmark as bench
from common import load_jsonl

HERE = Path(__file__).resolve().parent
GENERATED = HERE / ".wizard-config.yaml"  # gitignored, holds no secrets
QUESTIONS = HERE / ".wizard-questions.jsonl"  # gitignored
PROVIDER_KEYS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "mistral": "MISTRAL_API_KEY"}


def ask(prompt, default=None):
    suffix = f" [{default}]" if default else ""
    while True:
        v = input(f"{prompt}{suffix}: ").strip()
        if v:
            return v
        if default is not None:
            return default


def choose(prompt, options):
    print(prompt)
    for i, (_, label) in enumerate(options, 1):
        print(f"  {i}) {label}")
    while True:
        v = input("> ").strip()
        if v.isdigit() and 1 <= int(v) <= len(options):
            return options[int(v) - 1][0]


def ask_model(env):
    print("\n== 1. Model to test ==")
    model = ask("Model, LiteLLM string (e.g. anthropic/claude-haiku-4-5-20251001, openai/gpt-4.1, mistral/mistral-large-latest)")
    base = input("API base URL (blank = provider default, needed for OpenAI-compatible endpoints like Swisscom myAI): ").strip()
    provider_env = PROVIDER_KEYS.get(model.split("/")[0])
    params = {}
    if base:
        params["api_base"] = base
    if base or not provider_env or not os.environ.get(provider_env):
        key = getpass.getpass("API key (hidden; blank = use provider env var): ")
        if key:
            env["EVAL_MODEL_API_KEY"] = key
            params["api_key"] = "${EVAL_MODEL_API_KEY}"
    entry = {"id": model.split("/")[-1], "model": model}
    if params:
        entry["params"] = params
    return entry


def ask_server(cfg, env):
    print("\n== 2. MCP server to test ==")
    kind = choose("How does the server run?", [
        ("typescript", "TypeScript, started locally (stdio)"),
        ("fastmcp", "Python / FastMCP, started locally (stdio)"),
        ("http", "Already running at a URL (streamable HTTP)"),
    ])
    if kind == "http":
        env["SWISS_MCP_URL"] = ask("Server URL (e.g. https://host/mcp)")
        token = getpass.getpass("Bearer token (hidden; blank = no auth): ")
        server = {"transport": "http", "url": "${SWISS_MCP_URL}"}
        if token:
            env["SWISS_MCP_TOKEN"] = token
            server["headers"] = {"Authorization": "Bearer ${SWISS_MCP_TOKEN}"}
        return "http", server
    preset = dict(cfg["mcp_servers"][kind])
    cmd = shlex.split(ask("Start command", " ".join([preset["command"], *preset.get("args", [])])), posix=os.name != "nt")
    preset["command"], preset["args"] = cmd[0], cmd[1:]
    default_cwd = preset.get("cwd", ".")
    preset["cwd"] = ask("Working directory, relative to eval/", default_cwd)
    if preset["cwd"] == ".":
        preset.pop("cwd")
    return kind, preset


def ask_topics(cfg, verified_only, max_per_topic):
    sets = {str(x["id"]): x for x in cfg["question_sets"]}
    print("\n== 3. Question set ==")
    for k, x in sets.items():
        print(f"  {k}) {x['name']}")
    default = "1" if "1" in sets else next(iter(sets))
    pick = ask("Set", default)
    qset = sets.get(pick, sets[default])
    if qset["source"] == "benchmark":
        qs = bench.load(verified_only)
    else:
        qs = load_jsonl(HERE / qset["file"])
        if not qs:
            raise SystemExit(f"{qset['file']} has no questions.")
    print("\n== 4. Topics to test ==")
    labels = {int(k): v for k, v in cfg["topics"].items()}
    counts = bench.topic_counts(qs, labels)
    for t, label, n in counts:
        print(f"  {t:>2}  {label:<36} {n} questions")
    raw = input("Topic numbers, comma-separated (Enter = all): ").strip()
    topics = {int(x) for x in raw.replace(" ", "").split(",") if x.isdigit()} or None
    chosen = bench.select(qs, topics, max_per_topic)
    if not chosen:
        raise SystemExit("No questions for that selection.")
    bench.write(chosen, QUESTIONS)
    langs = {}
    for q in chosen:
        langs[q["language"]] = langs.get(q["language"], 0) + 1
    print(f"  {len(chosen)} questions selected, by language: {langs}")
    print("  Note: the languages are NOT equivalent (different questions, not translations), so compare languages with care.")
    return len(chosen)


def ask_judge(cfg, env):
    print("\n== Judge (grades the answers) ==")
    model = ask("Judge model, press Enter to keep", cfg["judge"]["model"])
    provider_env = PROVIDER_KEYS.get(model.split("/")[0])
    if provider_env and not os.environ.get(provider_env) and not env.get(provider_env):
        key = getpass.getpass(f"{provider_env} (hidden): ")
        if key:
            env[provider_env] = key
    elif not provider_env:
        print(f"  Make sure the API key env var for '{model}' is set.")
    return model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--seed-questions", action="store_true", help="use eval/questions.jsonl instead of the benchmark")
    ap.add_argument("--verified-only", action="store_true", help="benchmark: only the 32 hand-checked questions")
    ap.add_argument("--max-per-topic", type=int, help="benchmark: sample at most N questions per topic (cuts cost)")
    ap.add_argument("--skip-baseline", action="store_true", help="do not run the no-MCP baseline")
    a = ap.parse_args()

    cfg = yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))
    env = dict(os.environ)
    model = ask_model(env)
    name, server = ask_server(cfg, env)
    n_questions = None
    if not a.seed_questions:
        n_questions = ask_topics(cfg, a.verified_only, a.max_per_topic)
        cfg["questions"] = QUESTIONS.name
    judge = ask_judge(cfg, env)

    cfg["models"] = [model]
    cfg["mcp_servers"] = {name: server}
    cfg["mcp_sets"] = {name: [name]} if a.skip_baseline else {"no-mcp": [], name: [name]}
    cfg["judge"]["model"] = judge
    GENERATED.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")

    if n_questions:
        n_sets = len(cfg["mcp_sets"])
        print(f"\n{n_questions} questions x {n_sets} conditions = {n_questions * n_sets} model runs, plus the same number of judge calls.")
        if not a.dry_run and input("Continue? [Y/n]: ").strip().lower() in ("n", "no"):
            raise SystemExit("Cancelled.")
    steps = [["run.py"], ["grade.py"], ["report.py"]]
    print(f"\nConfig written to {GENERATED.name} (no secrets). Steps: run -> grade -> report.")
    if a.dry_run:
        print(GENERATED.read_text(encoding="utf-8"))
        return
    for step in steps:
        cmd = [sys.executable, step[0], "--config", GENERATED.name]
        print(f"\n$ {' '.join(cmd)}")
        if subprocess.run(cmd, cwd=HERE, env=env).returncode:
            raise SystemExit(f"{step[0]} failed, stopping. Fix the problem and rerun: finished work is kept and skipped.")
    print("\nDone. Open eval/reports/report.html")


if __name__ == "__main__":
    main()
