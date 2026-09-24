"""Convert benchmark/data/*.jsonl into the eval question format, optionally for selected topics only.

    python import_benchmark.py                               # all topics -> questions.benchmark.jsonl
    python import_benchmark.py --topics 1,4,0 --max-per-topic 20
    python import_benchmark.py --verified-only               # the 32 hand-checked questions only
    python import_benchmark.py --list                        # topics with question counts

Mapping: ask_back -> clarify, not_switzerland -> out_of_scope, level foreign -> none, foreign items -> topic 0.
The benchmark's must_include / must_not_include / common_errors are appended to reference_answer for the judge.
Questions past their valid_until date are skipped.
"""
import argparse
import datetime as dt
import json
import random
from collections import Counter
from pathlib import Path

from common import load_config, load_jsonl

BENCH = Path(__file__).resolve().parent.parent / "benchmark" / "data"
BEHAVIOUR = {"answer": "answer", "ask_back": "clarify", "not_switzerland": "out_of_scope"}


def convert(r):
    foreign = r["level"] == "foreign" or r["expected_behavior"] == "not_switzerland"
    ref = r["reference_answer"]
    if r.get("must_include"):
        ref += " Must include: " + "; ".join(m["fact"] for m in r["must_include"]) + "."
    if r.get("ask_for"):
        ref += " Must ask for: " + "; ".join(a["info"] for a in r["ask_for"]) + "."
    if r.get("must_not_include"):
        ref += " Must not include: " + "; ".join(m.get("fact", str(m)) for m in r["must_not_include"]) + "."
    if r.get("common_errors"):
        ref += " Typical wrong answers: " + "; ".join(r["common_errors"]) + "."
    return {
        "qid": r["id"], "group_id": r["id"],  # no cross-language groups: every question is its own group
        "topic": 0 if foreign else r["topic_area"], "language": r["lang"],
        "level": "none" if r["level"] == "foreign" else r["level"],
        "expected_behaviour": BEHAVIOUR[r["expected_behavior"]],
        "question": r["question"], "reference_answer": ref, "key_facts": [],
        "source_domains": r.get("source_domains") or [], "valid_as_of": r.get("verified_at"),
    }


def load(verified_only=False, today=None):
    today = today or dt.date.today().isoformat()
    files = ["qa.jsonl"] if verified_only else ["qa.jsonl", "generated.jsonl"]
    rows = [r for f in files for r in load_jsonl(BENCH / f)]
    return [convert(r) for r in rows if not (r.get("valid_until") and r["valid_until"] < today)]


def select(qs, topics=None, max_per_topic=None):
    if topics is not None:
        qs = [q for q in qs if q["topic"] in topics]
    if max_per_topic:
        rng, out = random.Random(0), []
        for t in sorted({q["topic"] for q in qs}):
            group = [q for q in qs if q["topic"] == t]
            out += rng.sample(group, min(max_per_topic, len(group)))
        qs = out
    return qs


def topic_counts(qs, labels):
    c = Counter(q["topic"] for q in qs)
    return [(t, labels.get(t, str(t)), n) for t, n in sorted(c.items())]


def write(qs, path):
    Path(path).write_text("".join(json.dumps(q, ensure_ascii=False) + "\n" for q in qs), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--topics", help="comma-separated topic numbers (0 = not about Switzerland); default all")
    ap.add_argument("--max-per-topic", type=int, help="random sample (fixed seed) of at most N questions per topic")
    ap.add_argument("--verified-only", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--out", default="questions.benchmark.jsonl")
    a = ap.parse_args()
    labels = {int(k): v for k, v in load_config(a.config)["topics"].items()}
    qs = load(a.verified_only)
    if a.list:
        for t, label, n in topic_counts(qs, labels):
            print(f"{t:>2}  {label:<36} {n}")
        return
    topics = {int(t) for t in a.topics.split(",")} if a.topics else None
    qs = select(qs, topics, a.max_per_topic)
    write(qs, a.out)
    langs = Counter(q["language"] for q in qs)
    print(f"{len(qs)} questions -> {a.out}  languages: {dict(langs)}")


if __name__ == "__main__":
    main()
