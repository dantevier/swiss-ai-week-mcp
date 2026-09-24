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
  - config_name: generated_full
    data_files: data/generated_full.jsonl
  - config_name: area_01_health_insurance_premiums
    data_files: data/generated_by_sector/area-01-health-insurance-premiums.jsonl
  - config_name: area_02_taxes_and_duties
    data_files: data/generated_by_sector/area-02-taxes-and-duties.jsonl
  - config_name: area_03_law_and_regulations
    data_files: data/generated_by_sector/area-03-law-and-regulations.jsonl
  - config_name: area_04_waste_and_recycling
    data_files: data/generated_by_sector/area-04-waste-and-recycling.jsonl
  - config_name: area_05_residence_and_civil_status
    data_files: data/generated_by_sector/area-05-residence-and-civil-status.jsonl
  - config_name: area_06_migration
    data_files: data/generated_by_sector/area-06-migration.jsonl
  - config_name: area_07_social_insurance_and_pensions
    data_files: data/generated_by_sector/area-07-social-insurance-and-pensions.jsonl
  - config_name: area_08_work_and_unemployment
    data_files: data/generated_by_sector/area-08-work-and-unemployment.jsonl
  - config_name: area_09_schools_and_education
    data_files: data/generated_by_sector/area-09-schools-and-education.jsonl
  - config_name: area_10_public_transport
    data_files: data/generated_by_sector/area-10-public-transport.jsonl
  - config_name: area_11_road_traffic_and_licences
    data_files: data/generated_by_sector/area-11-road-traffic-and-licences.jsonl
  - config_name: area_12_housing_and_rental
    data_files: data/generated_by_sector/area-12-housing-and-rental.jsonl
  - config_name: area_13_voting_and_political_rights
    data_files: data/generated_by_sector/area-13-voting-and-political-rights.jsonl
  - config_name: area_14_companies_and_vat
    data_files: data/generated_by_sector/area-14-companies-and-vat.jsonl
  - config_name: area_15_customs
    data_files: data/generated_by_sector/area-15-customs.jsonl
  - config_name: area_16_statistics_and_open_data
    data_files: data/generated_by_sector/area-16-statistics-and-open-data.jsonl
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

## Dataset configurations

| config | items | how the answers were obtained |
|---|---|---|
| `verified` (`data/qa.jsonl`) | 35 | checked against the responsible authority's page; all 16 briefing topic areas |
| `generated` (`data/generated.jsonl`) | 160 | balanced suite: exactly 10 cases for each of the 16 topic areas; some lower-data areas use question framings from verified facts |
| `generated_full` (`data/generated_full.jsonl`) | 904 | complete data-derived corpus plus 34 context variants; intentionally uneven, retained for broader place-level stress tests |

The full corpus's 870 data-derived items come from `../data/swiss_places_premiums_2026.sqlite`.
That reusable runtime database was built from the BAG health insurance premiums
2026 (217,472 rows), SR 832.106 Annex 1 (premium region per municipality, version
in force on 1 Jan 2026, from the Fedlex filestore), and the BFS register of
municipalities (snapshot and mutations since 2015). Each such item quotes the data
rows its answer came from in `evidence`. The 34 `gen-context-*` items are wrappers
around verified benchmark seeds and retain their original evidence. The balanced
suite samples the full corpus first, then adds question-framing variants of verified
items where a sector has fewer than 10 cases.

| kind | n | what it tests |
|---|---|---|
| `gen-premium-*` | 360 | cheapest 2026 premium for a municipality, age group, deductible, accident cover and model; every canton and premium region |
| `gen-region-*` | 80 | premium region of a municipality |
| `gen-canton-*` | 150 | canton of a small municipality with a unique name |
| `gen-merger-*` | 150 | "I am moving to X" where X was merged away since 2015: the answer is today's municipality (`outdated`) |
| `gen-samename-*` | 35 | a municipality name that exists in several cantons with different premiums: the assistant must ask which one (`ask_back`) |
| `gen-foreign-*` | 87 | premium, registration and school-holiday questions about 29 towns in Germany, France, Italy, Austria and Liechtenstein (`not_switzerland`) |
| `gen-askback-*` | 8 | premium questions with no place given |
| `gen-context-*` | 34 | one language-matched request-context variant for each non-Romansh verified item; keeps the original answer, evidence, and scoring checks |
| `gen-balanced-*` | varies | additional language-matched question framings used only where needed to reach 10 generated cases in a topic area; reuses a verified fact and carries `source_item_id` / `fact_cluster_id` |

Regenerate, for example after the BAG publishes new premiums:

```bash
python scripts/build_knowledge_db.py       # network at build time; writes data/swiss_places_premiums_2026.sqlite
python benchmark/build/generate.py         # offline; writes balanced generated.jsonl, generated_full.jsonl, and sector files
```

The database builder stops if Fedlex returns its JavaScript shell instead of the
law text or if any current municipality cannot be assigned a premium region.
The benchmark generator stops if its self-check fails: Lugano, adult, CHF 2,500
deductible, no accident cover must give CHF 449.90, the figure verified by hand.
The same seed, database, and verified QA seeds give byte-identical output. The
balanced `generated_by_sector/area-NN-*.jsonl` files each contain exactly 10 cases
and partition the balanced generated set by topic area. Use these files or
`--data benchmark/data/generated.jsonl` for an even sector comparison. The separate
`generated_full_by_sector/` files retain the larger, uneven corpus. Framing variants
exercise prompt wording and answer the same underlying fact; use `fact_cluster_id`
to avoid treating them as independent factual evidence. Romansh variants are omitted
until a fluent reviewer can verify them.
Data-derived items whose answer a regex
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

`score.py` reads both files by default. Use `--data` to select a sector file or `--topic-area N` to filter a combined run. For example:

```bash
python benchmark/score.py --template runs/transport.jsonl --data benchmark/data/generated_by_sector/area-10-public-transport.jsonl
python benchmark/score.py runs/transport.jsonl --data benchmark/data/generated_by_sector/area-10-public-transport.jsonl
python benchmark/score.py --template runs/taxes.jsonl --topic-area 2
```

An item passes when every `must_include` pattern matches, no `must_not_include` pattern matches, and, for `ask_back`, the answer contains a question and every `ask_for` pattern matches. Results are broken down by expected behaviour, failure mode, language and topic area. The share of answers that name the responsible authority's domain is reported separately.

The patterns accept German, French, Italian and English wording, but a regex cannot judge nuance. `--judge-prompts` writes one grading prompt per answer, containing the reference answer, the evidence and the common errors, for an LLM judge. Use both, and read the failures.

To compare an assistant with and without your MCP server, collect two answer files for the same questions and score each.

## Freshness

Swiss facts change: rates on 1 January, the reference interest rate every quarter, school calendars every year. Items past `valid_until` are skipped automatically; use `--today YYYY-MM-DD` to simulate a date, or `--include-stale` to score them anyway. Re-verify an expired item against its `source_url`, then update `evidence`, `verified_at` and `valid_until`.

## Coverage and limits

- The balanced generated set has exactly 10 questions per area (160 total). Combined with all 35 verified items, the `all` config has 195 rows and is not exactly balanced by area.
- The full generated corpus has 904 items and remains heavily weighted toward premiums (514/904). Use it for broad stress testing, not equal-weight sector comparisons.
- Several areas have only one to four underlying verified facts. Their balanced files contain distinct language-matched question framings but share `fact_cluster_id`; they provide wording robustness, not 10 independent facts. More source research is needed for broad factual coverage in those areas.
- Romansh phrasing variants are omitted until a fluent reviewer can verify them.
- The reference answers are in English; the questions are in the national languages.
- Every verified fact was checked against the official page on 2026-09-24, except `premiums-lugano-it`, which comes from team research on 2026-09-21 against the BAG premium data.
- Premium items ask for the lowest premium "offered" in the region. For alternative models the generator requires the insurer to list the region in `Einzugsgebiete.csv`; the standard model is offered everywhere. In 2026 no offer is restricted to specific municipalities.
- Five verified seed items (`sample: true`) reuse published sample questions; their generated context variants keep that flag. Filter by `sample` or deduplicate by `source_item_id` when reporting an unseen-question score.

## Contributing an item

Take the fact from the responsible authority's own page, never from memory or a secondary site. Copy the supporting sentence into `evidence`, set `valid_until` when the fact is time-bound, and check that your patterns accept a correct answer and reject the typical wrong one. Then run `python benchmark/score.py --template /tmp/t.jsonl`, which loads the data and fails on duplicate ids or invalid regexes.

## License

CC BY 4.0. The evidence passages are short quotations from official Swiss government websites and open government data, each attributed by `source_url`.
