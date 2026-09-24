#!/usr/bin/env python3
"""Score an assistant's answers against the Swiss public-sector Q&A benchmark.

1. Write a blank answers file, one line per question:
       python benchmark/score.py --template runs/my-answers.jsonl
2. Fill in each "answer" with what the assistant replied (by hand, or from a script).
3. Score it:
       python benchmark/score.py runs/my-answers.jsonl

Optional: --judge-prompts FILE writes one grading prompt per answer for an LLM judge.
Standard library only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_DATA = [HERE / "data" / "qa.jsonl", HERE / "data" / "generated.jsonl"]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as e:
                    raise SystemExit(f"{path}:{line_no}: invalid JSON: {e}") from e
    return rows


def load_questions(paths: list[Path]) -> list[dict[str, Any]]:
    rows = [row for path in paths if path.exists() for row in read_jsonl(path)]
    seen = set()
    for row in rows:
        if row["id"] in seen:
            raise SystemExit(f"duplicate id: {row['id']}")
        seen.add(row["id"])
        for group in ("must_include", "must_not_include", "ask_for"):
            for item in row[group]:
                try:
                    re.compile(item["pattern"])
                except re.error as e:
                    raise SystemExit(f"{row['id']}: bad regex in {group}: {e}") from e
    return rows


def is_stale(row: dict[str, Any], today: dt.date) -> bool:
    until = row.get("valid_until")
    return bool(until) and dt.date.fromisoformat(until) < today


def score_answer(row: dict[str, Any], answer: str) -> list[str]:
    """Return the reasons the answer fails; empty means it passes the automatic checks."""
    if not answer.strip():
        return ["no answer"]
    problems = []
    for item in row["must_include"]:
        if not re.search(item["pattern"], answer):
            problems.append(f"missing: {item['fact']}")
    for item in row["must_not_include"]:
        match = re.search(item["pattern"], answer)
        if match:
            problems.append(f"{item['reason']} (matched {match.group(0)!r})")
    if row["expected_behavior"] == "ask_back":
        if "?" not in answer:
            problems.append("should ask the user a question")
        for item in row["ask_for"]:
            if not re.search(item["pattern"], answer):
                problems.append(f"does not ask for: {item['info']}")
    return problems


def cites_authority(row: dict[str, Any], answer: str) -> bool | None:
    domains = row.get("source_domains") or []
    if not domains:
        return None
    return any(d.lower() in answer.lower() for d in domains)


JUDGE_TEMPLATE = """You are grading an AI assistant's answer to a question about Swiss public services.

Question ({lang}): {question}

Expected behaviour: {behavior}
Reference answer: {reference}
Verified source ({authority}): {source_url}
Supporting passage: {evidence}
Common errors to penalise: {errors}

Assistant's answer:
<<<
{answer}
>>>

Grade only against the reference and the passage, not your own knowledge.
- "answer": correct if the key facts match and nothing contradicts the reference.
- "ask_back": correct only if it asks for the missing information and does not guess.
- "not_switzerland": correct only if it says the question is not about Switzerland and does not substitute a Swiss answer.
Reply with JSON only: {{"verdict": "correct" | "partial" | "incorrect", "reason": "<one sentence>"}}"""


def judge_prompt(row: dict[str, Any], answer: str) -> str:
    return JUDGE_TEMPLATE.format(
        lang=row["lang"],
        question=row["question"],
        behavior=row["expected_behavior"],
        reference=row["reference_answer"],
        authority=row["authority"],
        source_url=row.get("source_url") or "n/a",
        evidence=row["evidence"],
        errors="; ".join(row["common_errors"]) or "none listed",
        answer=answer,
    )


def print_table(title: str, rows, results, key) -> None:
    buckets: dict[str, list[bool]] = defaultdict(list)
    for row in rows:
        buckets[str(key(row))].append(results[row["id"]]["passed"])
    print(f"\n{title}")
    for name in sorted(buckets, key=lambda k: (len(k), k)):
        values = buckets[name]
        print(f"  {name:<24} {sum(values):>3}/{len(values):<3} {100 * sum(values) / len(values):5.0f}%")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("answers", nargs="?", type=Path, help="JSONL with {\"id\", \"answer\"} per line")
    parser.add_argument("--data", type=Path, nargs="+", default=DEFAULT_DATA,
                        help="question files (default: data/qa.jsonl data/generated.jsonl)")
    parser.add_argument("--template", type=Path, help="write a blank answers file and exit")
    parser.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today(),
                        help="date used to skip expired questions (default: today)")
    parser.add_argument("--include-stale", action="store_true", help="also score questions past valid_until")
    parser.add_argument("--out", type=Path, help="write per-question results as JSONL")
    parser.add_argument("--show-all", action="store_true", help="print every failure, not only the first 40")
    parser.add_argument("--judge-prompts", type=Path, help="write one LLM-judge prompt per answer as JSONL")
    args = parser.parse_args()

    questions = load_questions(args.data)

    if args.template:
        args.template.parent.mkdir(parents=True, exist_ok=True)
        with args.template.open("w", encoding="utf-8") as f:
            for row in questions:
                f.write(json.dumps({"id": row["id"], "question": row["question"], "answer": ""},
                                   ensure_ascii=False) + "\n")
        print(f"wrote {len(questions)} questions to {args.template}")
        return 0
    if not args.answers:
        parser.error("give an answers file, or --template to create one")

    stale = [] if args.include_stale else [r for r in questions if is_stale(r, args.today)]
    rows = [r for r in questions if r not in stale]
    answers = {a["id"]: a.get("answer") or "" for a in read_jsonl(args.answers)}
    unknown = sorted(set(answers) - {r["id"] for r in questions})
    if unknown:
        print(f"warning: answers for unknown ids ignored: {', '.join(unknown)}", file=sys.stderr)
    if stale:
        print(f"skipped {len(stale)} expired questions: {', '.join(r['id'] for r in stale)}", file=sys.stderr)

    results = {}
    for row in rows:
        answer = answers.get(row["id"], "")
        problems = score_answer(row, answer)
        results[row["id"]] = {
            "id": row["id"],
            "passed": not problems,
            "problems": problems,
            "cites_authority": cites_authority(row, answer),
            "answer": answer,
        }

    print_table("item source", rows, results, lambda r: "generated" if r["id"].startswith("gen-") else "hand-verified")
    print_table("expected behaviour", rows, results, lambda r: r["expected_behavior"])
    print_table("failure mode tested", rows, results, lambda r: r["failure_mode"])
    print_table("language", rows, results, lambda r: r["lang"])
    print_table("topic area (briefing numbering)", rows, results, lambda r: f"{r['topic_area']:>2} {r['topic']}")

    cited = [r["cites_authority"] for r in results.values() if r["cites_authority"] is not None and r["answer"]]
    if cited:
        print(f"\ncites the responsible authority's domain: {sum(cited)}/{len(cited)}")

    failed = [r for r in results.values() if not r["passed"]]
    if failed:
        shown = failed if args.show_all else failed[:40]
        more = "" if len(shown) == len(failed) else f", first {len(shown)} shown; --show-all or --out for the rest"
        print(f"\nfailures ({len(failed)}{more})")
        for r in shown:
            print(f"  {r['id']}")
            for p in r["problems"]:
                print(f"    - {p}")
    passed = len(rows) - len(failed)
    print(f"\ntotal {passed}/{len(rows)} ({100 * passed / len(rows):.0f}%)")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as f:
            for r in results.values():
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    if args.judge_prompts:
        args.judge_prompts.parent.mkdir(parents=True, exist_ok=True)
        by_id = {r["id"]: r for r in rows}
        with args.judge_prompts.open("w", encoding="utf-8") as f:
            for r in results.values():
                if r["answer"]:
                    f.write(json.dumps({"id": r["id"], "prompt": judge_prompt(by_id[r["id"]], r["answer"])},
                                       ensure_ascii=False) + "\n")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
