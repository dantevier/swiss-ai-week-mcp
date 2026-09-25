#!/usr/bin/env python3
"""Explain a benchmark run: why items failed, how the tools were used, and what to fix.

    python benchmark/interpret.py                      # latest run in benchmark/runs/
    python benchmark/interpret.py benchmark/runs/DIR   # a given run

Reads questions.jsonl, results.jsonl, traces.jsonl and meta.json from the run folder,
writes summary.json (used by the dashboard's Benchmark tab) and prints the interpretation.
Standard library only.
"""

from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"

# Answers that say the information could not be found, in the benchmark's languages.
DECLINED = re.compile(
    r"(?i)keine (offizielle )?quelle|nicht (verlässlich|gefunden|verfügbar)|je n'ai pas|pas de source"
    r"|ne (peux|trouve) pas|non dispongo|non ho trovato|non posso|could ?n[o']t find|no (official )?source"
    r"|not (available|found)|cannot (confirm|find)|unable to (find|confirm)"
)

# Benchmark patterns are written to check answers; some are as short as \b19\b or \bC\b and would match
# almost any long tool output. A pattern that matches this neutral text is too generic to count as evidence.
GENERIC_PROBE = " ".join(map(str, range(1, 32))) + " " + " ".join("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + " 2025 2026"

# Failure causes, in the order they are checked. (label, what it means / what to do)
CAUSES = {
    "api_error": ("API error", "The model call failed. Check the API key, model name and rate limits in traces.jsonl."),
    "no_answer": ("No final answer", "The model refused or was still calling tools after the round limit."),
    "wrong_claim": ("Wrong fact stated", "The answer contains a known wrong fact. If the answer is actually right, "
                    "the benchmark's must_not_include pattern is too broad."),
    "guessed": ("Guessed instead of asking", "Information was missing (e.g. the municipality) and the model answered "
                "anyway. Tell the model to ask back, or make the tool return a 'which place?' hint."),
    "no_tools": ("Answered without tools", "The model never called the MCP. Improve tool names and descriptions."),
    "found_not_used": ("Fact probably in a tool result, answer missed it", "Every missing fact matches the tool "
                       "output: likely a reading or ranking problem, not missing data. Check the evidence snippet, "
                       "since a pattern can also match unrelated text."),
    "declined": ("Said it could not find it", "Coverage gap: add an official source or a tool for this topic."),
    "not_in_mcp": ("Incomplete, fact never returned by a tool", "Coverage gap or wrong tool: no tool output contained "
                   "the expected fact."),
    "incomplete": ("Incomplete answer", "Without tools the model did not know the expected fact."),
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def latest_run(runs: Path = RUNS) -> Path | None:
    folders = sorted(p for p in runs.glob("*") if (p / "results.jsonl").exists()) if runs.exists() else []
    return folders[-1] if folders else None


def tool_evidence(missing: list[dict[str, Any]], tool_text: str) -> list[str]:
    """Snippets showing every missing fact in the tool output; empty unless all of them are there."""
    snippets = []
    for item in missing:
        match = None if re.search(item["pattern"], GENERIC_PROBE) else re.search(item["pattern"], tool_text)
        if not match:
            return []
        context = tool_text[max(0, match.start() - 80):match.end() + 80].replace("\\n", " ")  # JSON-escaped
        context = re.sub(r"\s+", " ", context)
        snippets.append(f"{item['fact']}: ...{context}...")
    return snippets


def classify(row: dict[str, Any], result: dict[str, Any], trace: list[dict[str, Any]],
             with_mcp: bool) -> tuple[str, list[str]]:
    """The failure cause, plus evidence snippets when the tools had the missing facts."""
    answer = result.get("answer") or ""
    if any(isinstance(step.get("error"), str) for step in trace):
        return "api_error", []
    if not answer.strip():
        return "no_answer", []
    if any(re.search(item["pattern"], answer) for item in row["must_not_include"]):
        return "wrong_claim", []
    if row["expected_behavior"] == "ask_back":
        return "guessed", []
    calls = [step for step in trace if "tool" in step]
    if with_mcp and not calls:
        return "no_tools", []
    missing = [item for item in row["must_include"] if not re.search(item["pattern"], answer)]
    evidence = tool_evidence(missing, "\n".join(step.get("result", "") for step in calls)) if with_mcp else []
    if missing and evidence:
        return "found_not_used", evidence
    if DECLINED.search(answer):
        return "declined", []
    return ("not_in_mcp" if with_mcp else "incomplete"), []


def rate(rows: list[dict[str, Any]], passed: dict[str, bool], key) -> list[dict[str, Any]]:
    buckets: dict[str, list[bool]] = collections.defaultdict(list)
    for row in rows:
        buckets[key(row)].append(passed[row["id"]])
    return [{"name": name, "passed": sum(v), "total": len(v)} for name, v in sorted(buckets.items())]


def summarize(run: Path) -> dict[str, Any]:
    meta = json.loads((run / "meta.json").read_text(encoding="utf-8")) if (run / "meta.json").exists() else {}
    with_mcp = meta.get("mcp", True)
    rows = {r["id"]: r for r in read_jsonl(run / "questions.jsonl")}
    results = {r["id"]: r for r in read_jsonl(run / "results.jsonl")}
    traces = {t["id"]: t["trace"] for t in read_jsonl(run / "traces.jsonl")}
    scored = [rows[i] for i in results if i in rows]  # stale questions are skipped by score.py
    passed = {i: r["passed"] for i, r in results.items()}

    questions, causes = [], collections.defaultdict(list)
    for row in scored:
        result, trace = results[row["id"]], traces.get(row["id"], [])
        cause, evidence = (None, []) if result["passed"] else classify(row, result, trace, with_mcp)
        if cause:
            causes[cause].append(row["id"])
        calls = [step for step in trace if "tool" in step]
        questions.append({
            "id": row["id"], "question": row["question"], "topic": f"{row['topic_area']} {row['topic']}",
            "expected_behavior": row["expected_behavior"], "passed": result["passed"], "cause": cause,
            "problems": result["problems"], "answer": result.get("answer") or "", "evidence": evidence,
            "tools": [step["tool"] for step in calls],
        })

    tool_calls: dict[str, dict[str, Any]] = {}
    for trace in traces.values():
        for step in trace:
            if "tool" not in step:
                continue
            stats = tool_calls.setdefault(step["tool"], {"tool": step["tool"], "calls": 0, "errors": 0, "empty": 0,
                                                         "example_error": None})
            stats["calls"] += 1
            if step.get("error"):
                stats["errors"] += 1
                stats["example_error"] = stats["example_error"] or step.get("result", "")[:300]
            elif '"results":[]' in step.get("result", "").replace(" ", ""):
                stats["empty"] += 1

    total, ok = len(scored), sum(passed[r["id"]] for r in scored)
    summary = {
        "run": run.name,
        "meta": meta,
        "total": total,
        "passed": ok,
        "by_behavior": rate(scored, passed, lambda r: r["expected_behavior"]),
        "by_topic": rate(scored, passed, lambda r: f"{int(r['topic_area']):>2} {r['topic']}"),
        "causes": [{"cause": c, "label": CAUSES[c][0], "advice": CAUSES[c][1], "count": len(causes[c]),
                    "examples": causes[c]} for c in CAUSES if causes.get(c)],
        "tools": sorted(tool_calls.values(), key=lambda t: -t["calls"]),
        "questions": questions,
    }
    summary["headline"] = headline(summary)
    summary["next_steps"] = next_steps(summary)
    return summary


def headline(s: dict[str, Any]) -> list[str]:
    meta, total, ok = s["meta"], s["total"], s["passed"]
    if not total:
        return ["No scored questions in this run."]
    mode = "with the MCP tools" if meta.get("mcp", True) else "WITHOUT tools (baseline)"
    lines = [f"{meta.get('model', '?')} answered {total} questions {mode}: {ok}/{total} passed "
             f"({100 * ok / total:.0f}%)."]
    strong = [t["name"].strip() for t in s["by_topic"] if t["passed"] == t["total"]]
    weak = sorted((t for t in s["by_topic"] if t["total"] >= 2), key=lambda t: t["passed"] / t["total"])[:3]
    if strong:
        lines.append(f"Fully correct topics: {', '.join(strong)}.")
    if weak and weak[0]["passed"] < weak[0]["total"]:
        lines.append("Weakest topics: " + ", ".join(f"{t['name'].strip()} ({t['passed']}/{t['total']})" for t in weak) + ".")
    if s["tools"]:
        n_calls = sum(t["calls"] for t in s["tools"])
        lines.append(f"Tool use: {n_calls} calls, {n_calls / total:.1f} per question.")
    return lines


def next_steps(s: dict[str, Any]) -> list[str]:
    by = {c["cause"]: c["count"] for c in s["causes"]}
    gaps = by.get("declined", 0) + by.get("not_in_mcp", 0)
    todo = []
    if by.get("api_error"):
        todo.append("Fix the API errors first; those items were never really answered.")
    if gaps:
        gap_topics = collections.Counter(q["topic"] for q in s["questions"] if q["cause"] in ("declined", "not_in_mcp"))
        todo.append(f"Close coverage gaps ({gaps} items), mainly: "
                    + ", ".join(f"{t} ({n})" for t, n in gap_topics.most_common(4)) + ".")
    if by.get("found_not_used"):
        todo.append(f"Check retrieval ({by['found_not_used']} failed answers probably had the fact in a tool result; "
                    "see the evidence): better search ranking, shorter and more relevant passages.")
    if by.get("no_tools"):
        todo.append(f"{by['no_tools']} answers used no tool: make tool descriptions match the questions.")
    if by.get("guessed"):
        todo.append(f"{by['guessed']} answers guessed instead of asking for missing details.")
    if by.get("wrong_claim"):
        todo.append(f"Review {by['wrong_claim']} answers flagged as wrong; if they are right, fix the benchmark pattern.")
    for t in s["tools"]:
        if t["example_error"]:
            todo.append(f"{t['errors']} {t['tool']} calls failed, e.g.: {t['example_error'].splitlines()[0][:160]}")
    if not s["meta"].get("mcp", True):
        todo.append("This is a baseline: run the same --model and --seed with the MCP to see what the tools add.")
    return todo or ["Nothing: every question passed."]


def render(s: dict[str, Any]) -> str:
    lines = ["", "=" * 70, "INTERPRETATION", "=" * 70, *s["headline"]]
    if s["causes"]:
        lines += ["", f"Why the {s['total'] - s['passed']} failures happened:"]
        for c in s["causes"]:
            examples = ", ".join(c["examples"][:3]) + (" ..." if c["count"] > 3 else "")
            lines += [f"  {c['count']:>3}  {c['label']}", f"       {c['advice']}", f"       e.g. {examples}"]
    if s["tools"]:
        lines += ["", "Tool calls:"]
        for t in s["tools"]:
            extra = [f"{t['errors']} errors"] * bool(t["errors"]) + [f"{t['empty']} empty results"] * bool(t["empty"])
            lines.append(f"  {t['calls']:>4}  {t['tool']}" + (f"  ({', '.join(extra)})" if extra else ""))
    lines += ["", "What to do next:", *(f"  - {t}" for t in s["next_steps"])]
    return "\n".join(lines)


def interpret(run: Path) -> str:
    summary = summarize(run)
    (run / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return render(summary)


def main() -> int:
    run = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_run()
    if not run or not (run / "results.jsonl").exists():
        raise SystemExit("no run found; give a run folder that contains results.jsonl")
    print(interpret(run))
    return 0


if __name__ == "__main__":
    sys.exit(main())
