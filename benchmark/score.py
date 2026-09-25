#!/usr/bin/env python3
"""Score an assistant's answers against the Swiss public-sector Q&A benchmark.

1. Write a blank answers file, one line per question:
       python benchmark/score.py --template runs/my-answers.jsonl
2. Fill in each "answer" with what the assistant replied (by hand, or from a script).
3. Score it:
       python benchmark/score.py runs/my-answers.jsonl

Optional: --judge-prompts FILE writes one grading prompt per answer for an LLM judge.
Optional: --judgements FILE reads those LLM grades (verdict plus 0-2 scores) and reports a quality score.
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
from urllib.parse import urlparse

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


def links_to_source_domain(row: dict[str, Any], answer: str) -> bool | None:
    """Check whether an answer contains a URL on one of the listed source domains."""
    domains = [d.lower().lstrip(".") for d in row.get("source_domains") or []]
    if not domains:
        return None
    for raw_url in re.findall(r"https?://[^\s<>\"']+", answer):
        host = (urlparse(raw_url.rstrip(".,;:!?)]}")).hostname or "").lower()
        if any(host == domain or host.endswith("." + domain) for domain in domains):
            return True
    return False


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
- Factual accuracy: all material claims match the reference; penalise contradictions and unsupported specifics.
- Evidence support: the answer's claims are directly supported by the supplied passage/source, not merely accompanied by a source name.
- Completeness: it includes the key answer and required qualifications, limits, dates, or jurisdiction.
- Clarity: it is understandable, direct, and appropriately scoped; do not reward verbosity.
- For "ask_back", full factual accuracy requires asking for the missing information and not guessing.
- For "not_switzerland", full factual accuracy requires identifying the non-Swiss jurisdiction and not substituting a Swiss answer.
For each dimension assign 0 (poor), 1 (partly meets), or 2 (strong). Be conservative: an answer can be correct but poorly supported or incomplete.
Reply with JSON only: {{"verdict": "correct" | "partial" | "incorrect", "scores": {{"factual_accuracy": 0|1|2, "evidence_support": 0|1|2, "completeness": 0|1|2, "clarity": 0|1|2}}, "reason": "<one concise sentence>"}}"""

QUALITY_DIMENSIONS = ("factual_accuracy", "evidence_support", "completeness", "clarity")


def load_judgements(path: Path, valid_ids: set[str]) -> dict[str, dict[str, Any]]:
    """Read and validate optional judge JSONL; invalid rows are reported and skipped."""
    judgements: dict[str, dict[str, Any]] = {}
    for line_no, item in enumerate(read_jsonl(path), 1):
        question_id = item.get("id")
        if question_id not in valid_ids:
            print(f"warning: judgement line {line_no} has unknown id {question_id!r}; ignored", file=sys.stderr)
            continue
        if question_id in judgements:
            print(f"warning: duplicate judgement for {question_id!r}; keeping first", file=sys.stderr)
            continue
        scores = item.get("scores") or {}
        if item.get("verdict") not in {"correct", "partial", "incorrect"}:
            print(f"warning: judgement for {question_id!r} has invalid verdict; ignored", file=sys.stderr)
            continue
        if any(
            not isinstance(scores.get(dim), int)
            or isinstance(scores.get(dim), bool)
            or scores[dim] not in (0, 1, 2)
            for dim in QUALITY_DIMENSIONS
        ):
            print(
                f"warning: judgement for {question_id!r} needs integer 0-2 scores for {', '.join(QUALITY_DIMENSIONS)}; ignored",
                file=sys.stderr,
            )
            continue
        total = sum(scores[dim] for dim in QUALITY_DIMENSIONS)
        judgements[question_id] = {
            "verdict": item["verdict"],
            "scores": {dim: scores[dim] for dim in QUALITY_DIMENSIONS},
            "total": total,
            "reason": str(item.get("reason") or ""),
        }
    return judgements


def print_quality_score(rows, results) -> None:
    judged = [r for r in rows if results[r["id"]].get("quality_scores") is not None]
    if not judged:
        return

    def show(label, subset):
        if not subset:
            return
        avg = sum(results[r["id"]]["quality_total"] for r in subset) / len(subset)
        print(f"  {label}: {avg:.2f}/8 across {len(subset)} judged item(s)")
        for dim in QUALITY_DIMENSIONS:
            value = sum(results[r["id"]]["quality_scores"][dim] for r in subset) / len(subset)
            print(f"    {dim.replace('_', ' '):<20} {value:.2f}/2")

    print("\nquality score (optional rubric judge; 0-8, higher is better)")
    show("question weighted", judged)
    clusters: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    areas: dict[str, dict[tuple[int, str], list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in judged:
        cluster_id = str(row.get("fact_cluster_id") or row.get("source_item_id") or row["id"])
        key = (int(row["topic_area"]), cluster_id)
        clusters[key].append(row)
        areas[f"{key[0]:02d} {row['topic']}"][key].append(row)
    cluster_means = [
        sum(results[r["id"]]["quality_total"] for r in items) / len(items) for items in clusters.values()
    ]
    print(
        f"  cluster weighted: {sum(cluster_means) / len(cluster_means):.2f}/8 across {len(cluster_means)} judged fact cluster(s)"
    )
    for dim in QUALITY_DIMENSIONS:
        means = [
            sum(results[r["id"]]["quality_scores"][dim] for r in items) / len(items)
            for items in clusters.values()
        ]
        print(f"    {dim.replace('_', ' '):<20} {sum(means) / len(means):.2f}/2")
    verdicts = defaultdict(int)
    for row in judged:
        verdicts[results[row["id"]]["judge_verdict"]] += 1
    print(
        "  judge verdicts: "
        + ", ".join(f"{k}={verdicts[k]}" for k in ("correct", "partial", "incorrect"))
    )
    print("  by area (cluster-weighted quality, /8)")
    for area, area_clusters in sorted(areas.items()):
        means = [
            sum(results[r["id"]]["quality_total"] for r in items) / len(items)
            for items in area_clusters.values()
        ]
        print(f"    {area:<32} {sum(means) / len(means):.2f}/8 over {len(means)} cluster(s)")


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


def print_cluster_score(rows, results) -> None:
    """Count each fact once; a cluster passes only when all its framings pass."""
    clusters: dict[tuple[int, str], list[bool]] = defaultdict(list)
    by_area: dict[str, dict[tuple[int, str], list[bool]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        cluster_id = str(row.get("fact_cluster_id") or row.get("source_item_id") or row["id"])
        key = (int(row["topic_area"]), cluster_id)
        passed = results[row["id"]]["passed"]
        clusters[key].append(passed)
        by_area[f"{key[0]:02d} {row['topic']}"][key].append(passed)

    passed_clusters = sum(all(values) for values in clusters.values())
    total_clusters = len(clusters)
    if not total_clusters:
        print("\nfact-cluster score: no questions to score")
        return
    print(f"\nfact-cluster score (all framings must pass): {passed_clusters}/{total_clusters} "
          f"({100 * passed_clusters / total_clusters:.0f}%)")
    print("  by topic area (passed clusters / distinct clusters)")
    for area, area_clusters in sorted(by_area.items()):
        values = [all(items) for items in area_clusters.values()]
        passed = sum(values)
        print(f"  {area:<32} {passed:>3}/{len(values):<3} {100 * passed / len(values):5.0f}%")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("answers", nargs="?", type=Path, help="JSONL with {\"id\", \"answer\"} per line")
    parser.add_argument("--data", type=Path, nargs="+", default=DEFAULT_DATA,
                        help="question files (default: data/qa.jsonl data/generated.jsonl)")
    parser.add_argument("--topic-area", type=int, choices=range(1, 17),
                        help="score only one challenge topic area (1-16)")
    parser.add_argument("--template", type=Path, help="write a blank answers file and exit")
    parser.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today(),
                        help="date used to skip expired questions (default: today)")
    parser.add_argument("--include-stale", action="store_true", help="also score questions past valid_until")
    parser.add_argument("--out", type=Path, help="write per-question results as JSONL")
    parser.add_argument("--show-all", action="store_true", help="print every failure, not only the first 40")
    parser.add_argument("--judge-prompts", type=Path, help="write one LLM-judge prompt per answer as JSONL")
    parser.add_argument(
        "--judgements",
        type=Path,
        help="read LLM-judge JSONL {id, verdict, scores, reason} and report a 0-8 quality score",
    )
    args = parser.parse_args()

    questions = load_questions(args.data)
    if args.topic_area is not None:
        questions = [row for row in questions if int(row["topic_area"]) == args.topic_area]
        if not questions:
            parser.error(f"no questions found for topic area {args.topic_area}")

    if args.template:
        args.template.parent.mkdir(parents=True, exist_ok=True)
        with args.template.open("w", encoding="utf-8") as f:
            for row in questions:
                f.write(json.dumps({"id": row["id"],
                                    "fact_cluster_id": row.get("fact_cluster_id") or row.get("source_item_id") or row["id"],
                                    "question": row["question"], "answer": ""},
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
            "fact_cluster_id": row.get("fact_cluster_id") or row.get("source_item_id") or row["id"],
            "passed": not problems,
            "problems": problems,
            "cites_authority": cites_authority(row, answer),
            "links_to_source_domain": links_to_source_domain(row, answer),
            "answer": answer,
        }

    judgements = load_judgements(args.judgements, {r["id"] for r in rows}) if args.judgements else {}
    for row in rows:
        judgement = judgements.get(row["id"])
        if judgement:
            results[row["id"]].update({
                "judge_verdict": judgement["verdict"],
                "quality_scores": judgement["scores"],
                "quality_total": judgement["total"],
                "judge_reason": judgement["reason"],
            })

    print_table("item source", rows, results, lambda r: "generated" if r["id"].startswith("gen-") else "hand-verified")
    print_table("expected behaviour", rows, results, lambda r: r["expected_behavior"])
    print_table("failure mode tested", rows, results, lambda r: r["failure_mode"])
    print_table("language", rows, results, lambda r: r["lang"])
    print_table("topic area (briefing numbering)", rows, results, lambda r: f"{r['topic_area']:>2} {r['topic']}")
    print_cluster_score(rows, results)
    print_quality_score(rows, results)

    cited = [r["cites_authority"] for r in results.values() if r["cites_authority"] is not None and r["answer"]]
    if cited:
        print(f"\ncites the responsible authority's domain: {sum(cited)}/{len(cited)}")
    linked = [r["links_to_source_domain"] for r in results.values() if r["links_to_source_domain"] is not None and r["answer"]]
    if linked:
        print(f"links to an official source URL: {sum(linked)}/{len(linked)}")

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
