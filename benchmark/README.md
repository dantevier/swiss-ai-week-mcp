---
license: cc-by-4.0
language:
  - de
  - fr
  - it
  - rm
pretty_name: Swiss Public Services Grounding QA
size_categories:
  - n<1K
task_categories:
  - question-answering
tags:
  - switzerland
  - public-sector
  - grounding
  - mcp
  - multilingual
configs:
  - config_name: all
    data_files:
      - data/qa.jsonl
      - data/generated.jsonl
    default: true
  - config_name: verified
    data_files: data/qa.jsonl
  - config_name: generated
    data_files: data/generated.jsonl
---

# Swiss Public Services Grounding QA

Questions people ask about Swiss public services, each with a verified answer, the official source, and the verbatim passage that supports it. The questions cover federal, cantonal and municipal rules in German, French, Italian and Romansh.

It tests whether an assistant (an LLM on its own, or an LLM connected to an MCP server such as one built for the [Swiss Grounding MCP challenge](https://zh.ai-weeks.ch/challenges/swiss-grounding-mcp)) answers correctly and honestly. The questions are built around the four ways assistants typically fail on Swiss questions:

| failure mode | example |
|---|---|
| `wrong_jurisdiction` | Gives a national answer where the rule depends on the canton or municipality, or asks for a location that does not change the answer |
| `outdated` | Gives the VAT rate, pension amount or customs allowance of an earlier year |
| `invisible_data` | The answer exists only on a cantonal or municipal website that general models rarely know |
| `foreign_confusion` | Answers a question about Konstanz or Austria as if it were Swiss, or applies German or Italian rules |

## Two parts

| config | items | how the answers were obtained |
|---|---|---|
| `verified` (`data/qa.jsonl`) | 32 | checked by hand against the responsible authority's page; 15 of the 16 briefing topic areas |
| `generated` (`data/generated.jsonl`) | 870 | computed by `build/generate.py` from the offline official-data database; ids start with `gen-` |

The generated items come from `../data/swiss_places_premiums_2026.sqlite`. That reusable
runtime database was built from the BAG health insurance premiums 2026 (217,472
rows), SR 832.106 Annex 1 (premium region per municipality, version in force on
1 Jan 2026, from the Fedlex filestore), and the BFS register of municipalities
(snapshot and mutations since 2015). Each item quotes the data rows its answer
came from in `evidence`.

| kind | n | what it tests |
|---|---|---|
| `gen-premium-*` | 360 | cheapest 2026 premium for a municipality, age group, deductible, accident cover and model; every canton and premium region |
| `gen-region-*` | 80 | premium region of a municipality |
| `gen-canton-*` | 150 | canton of a small municipality with a unique name |
| `gen-merger-*` | 150 | "I am moving to X" where X was merged away since 2015: the answer is today's municipality (`outdated`) |
| `gen-samename-*` | 35 | a municipality name that exists in several cantons with different premiums: the assistant must ask which one (`ask_back`) |
| `gen-foreign-*` | 87 | premium, registration and school-holiday questions about 29 towns in Germany, France, Italy, Austria and Liechtenstein (`not_switzerland`) |
| `gen-askback-*` | 8 | premium questions with no place given |

Regenerate, for example after the BAG publishes new premiums:

```bash
python scripts/build_knowledge_db.py       # network at build time; writes data/swiss_places_premiums_2026.sqlite
python benchmark/build/generate.py         # offline; writes benchmark/data/generated.jsonl
```

The database builder stops if Fedlex returns its JavaScript shell instead of the
law text or if any current municipality cannot be assigned a premium region.
The benchmark generator stops if its self-check fails: Lugano, adult, CHF 2,500
deductible, no accident cover must give CHF 449.90, the figure verified by hand.
The same seed and database give byte-identical output. Items whose answer a regex
cannot separate from the typical wrong answer are left out, for example mergers
where the new name is part of the old one (Bad Zurzach became Zurzach).

## Expected behaviour

Every question has one `expected_behavior`:

- `answer`: the question can be answered; the answer must contain the verified facts.
- `ask_back`: key information is missing (usually the municipality) and it changes the answer. The assistant must ask for it rather than guess.
- `not_switzerland`: the question is about another country. The assistant must say so rather than substitute a Swiss answer.

## Fields

| field | meaning |
|---|---|
| `id` | stable identifier |
| `sample` | `true` if the wording reuses one of the challenge's published sample questions |
| `lang` | language of the question: `de`, `fr`, `it`, `rm` |
| `topic_area`, `topic` | the 16 topic areas of the challenge briefing (1 premiums … 16 statistics) |
| `level` | `federal`, `cantonal`, `municipal` or `foreign` |
| `failure_mode` | which failure mode the question probes |
| `question` | the user question |
| `expected_behavior` | `answer`, `ask_back` or `not_switzerland` |
| `reference_answer` | verified answer, in English |
| `must_include` | facts the answer must contain, each with a regex |
| `must_not_include` | content that is wrong wherever it appears, each with a regex |
| `ask_for` | for `ask_back`: what the assistant must ask for, with a regex |
| `common_errors` | typical wrong answers, for human or LLM judges |
| `authority`, `source_url`, `source_domains` | the responsible authority and its official page |
| `evidence` | verbatim passage from the source that supports the answer |
| `verified_at`, `verified_by` | when and by whom the fact was checked |
| `valid_until` | date after which the fact may change and the item must be re-verified (empty if not time-bound) |

## Scoring

`score.py` needs only the Python standard library.

```bash
# 1. blank answers file with every question
python benchmark/score.py --template runs/my-assistant.jsonl
# 2. fill in each "answer" with the assistant's reply
# 3. score it
python benchmark/score.py runs/my-assistant.jsonl --out runs/results.jsonl --judge-prompts runs/judge.jsonl
```

`score.py` reads both files by default; use `--data benchmark/data/qa.jsonl` to score one part only. An item passes when every `must_include` pattern matches, no `must_not_include` pattern matches, and, for `ask_back`, the answer contains a question and every `ask_for` pattern matches. Results are broken down by expected behaviour, failure mode, language and topic area. The share of answers that name the responsible authority's domain is reported separately.

The patterns accept German, French, Italian and English wording, but a regex cannot judge nuance. `--judge-prompts` writes one grading prompt per answer, containing the reference answer, the evidence and the common errors, for an LLM judge. Use both, and read the failures.

To compare an assistant with and without your MCP server, collect two answer files for the same questions and score each.

## Freshness

Swiss facts change: rates on 1 January, the reference interest rate every quarter, school calendars every year. Items past `valid_until` are skipped automatically; use `--today YYYY-MM-DD` to simulate a date, or `--include-stale` to score them anyway. Re-verify an expired item against its `source_url`, then update `evidence`, `verified_at` and `valid_until`.

## Coverage and limits

- 902 items: 573 German, 248 French, 80 Italian, 1 Romansh. Generated items use the language of the municipality; Romansh-speaking municipalities get German questions.
- The generated part covers only premiums, municipalities and foreign towns, so it is heavy on topic area 1. The other areas rely on the 32 verified items. Area 10 (public transport) has no items yet.
- The reference answers are in English; the questions are in the national languages.
- Every verified fact was checked against the official page on 2026-09-24, except `premiums-lugano-it`, which comes from team research on 2026-09-21 against the BAG premium data.
- Premium items ask for the lowest premium "offered" in the region. For alternative models the generator requires the insurer to list the region in `Einzugsgebiete.csv`; the standard model is offered everywhere. In 2026 no offer is restricted to specific municipalities.
- Five items (`sample: true`) reuse the wording of the challenge's published sample questions. Report them separately if you want a score on unseen questions only.

## Contributing an item

Take the fact from the responsible authority's own page, never from memory or a secondary site. Copy the supporting sentence into `evidence`, set `valid_until` when the fact is time-bound, and check that your patterns accept a correct answer and reject the typical wrong one. Then run `python benchmark/score.py --template /tmp/t.jsonl`, which loads the data and fails on duplicate ids or invalid regexes.

## License

CC BY 4.0. The evidence passages are short quotations from official Swiss government websites and open government data, each attributed by `source_url`.
