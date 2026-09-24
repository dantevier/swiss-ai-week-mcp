"""Grade results: deterministic checks + LLM judge. Resumable.

    python grade.py
    python grade.py --regrade      # regrade everything (e.g. after fixing reference answers)
"""
import argparse
import asyncio
import json
import re
from pathlib import Path

import litellm

from common import load_config, load_jsonl

JUDGE_PROMPT = """You grade an assistant's answer to a question about Swiss public services.

Question (language: {language}): {question}
Expected behaviour: {expected}
Reference answer: {reference}
Key facts that must be present: {key_facts}

Assistant answer:
<<<
{answer}
>>>

1. Classify what the assistant did:
   "answer" = gave a substantive answer
   "clarify" = asked the user for missing information instead of answering
   "out_of_scope" = stated the question is not about Switzerland / outside its scope
   "fail" = refused, errored, or gave nothing usable
2. If behaviour is "answer" and the reference is not a TODO, judge correctness: it may be phrased differently or add detail, but must not contradict the reference or miss a key fact. Otherwise set "correct" to null.
3. If behaviour is "clarify", judge whether it asks for the information that is actually missing. Otherwise null.
4. Judge whether the answer is written in the language of the question.

Return only JSON:
{{"behaviour": "...", "correct": true|false|null, "clarification_ok": true|false|null, "same_language": true|false, "reason": "one sentence"}}"""


def norm(s):
    return re.sub(r"[\s'’`]", "", (s or "").casefold())


def deterministic(rec, q):
    ans = norm(rec.get("answer"))
    facts = q.get("key_facts") or []
    fact_hit = sum(norm(k) in ans for k in facts) / len(facts) if facts else None
    domains = q.get("source_domains") or []
    haystack = (rec.get("answer") or "") + json.dumps(rec.get("tool_calls", []), ensure_ascii=False)
    source_hit = any(d in haystack for d in domains) if domains else None
    return fact_hit, source_hit


def parse_json(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    return json.loads(m.group(0)) if m else {}


def decide(expected, j, reference):
    b = j.get("behaviour")
    if expected == "answer":
        if reference.startswith("TODO"):
            return None  # no reference yet: excluded from scores
        return b == "answer" and j.get("correct") is True
    if expected == "clarify":
        return b == "clarify" and j.get("clarification_ok") is not False
    if expected == "out_of_scope":
        return b == "out_of_scope"
    return None


async def grade_one(rec, q, judge_model, sem):
    if rec.get("error") or rec.get("answer") is None:
        return {**rec, "behaviour": "fail", "passed": False, "judge_reason": "run error"}
    ref = q.get("reference_answer") or "TODO"
    prompt = JUDGE_PROMPT.format(
        language=q["language"], question=q["question"], expected=q["expected_behaviour"],
        reference=ref, key_facts=q.get("key_facts") or "none", answer=rec["answer"])
    async with sem:
        resp = await litellm.acompletion(model=judge_model, temperature=0,
                                         messages=[{"role": "user", "content": prompt}])
    j = parse_json(resp.choices[0].message.content)
    fact_hit, source_hit = deterministic(rec, q)
    return {
        **rec,
        "behaviour": j.get("behaviour"),
        "correct": j.get("correct"),
        "clarification_ok": j.get("clarification_ok"),
        "same_language": j.get("same_language"),
        "judge_reason": j.get("reason"),
        "key_fact_hit": fact_hit,
        "source_hit": source_hit,
        "passed": decide(q["expected_behaviour"], j, ref),
    }


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--regrade", action="store_true")
    a = ap.parse_args()

    cfg = load_config(a.config)
    qs = {q["qid"]: q for q in load_jsonl(cfg["questions"])}
    results = load_jsonl(cfg["results"])
    latest = {r["run_key"]: r for r in results}  # keep last attempt per run
    out = Path(cfg["graded"])
    graded = {} if a.regrade else {g["run_key"]: g for g in load_jsonl(out)}

    todo = [r for k, r in latest.items() if k not in graded and r["qid"] in qs]
    sem = asyncio.Semaphore(cfg["judge"].get("concurrency", 4))
    new = await asyncio.gather(*(grade_one(r, qs[r["qid"]], cfg["judge"]["model"], sem) for r in todo))
    graded.update({g["run_key"]: g for g in new})

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(g, ensure_ascii=False) + "\n" for g in graded.values()), encoding="utf-8")
    print(f"graded {len(new)} new, {len(graded)} total -> {out}")


if __name__ == "__main__":
    asyncio.run(main())
