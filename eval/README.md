# Evaluation harness

Compares models x MCP servers on Swiss public-service questions and reports pass % per topic, language, level and expected behaviour. Independent of the server code: own `requirements.txt`, own `.env`.

## What it is
A test bench for the MCP server. It asks the same questions to several LLMs, with and without the server's tools, then an LLM judge grades each answer against a reference. The report shows pass % per model, topic, language, level and expected behaviour, so you can see whether the server actually helps and where it fails.

- `run.py` asks the questions and records answers and tool calls. It needs model API keys.
- `grade.py` has a judge model (default `anthropic/claude-opus-5-5`, needs `ANTHROPIC_API_KEY`) decide pass/fail. Key-fact and source hits are recorded but do not decide the result.
- `report.py` builds the HTML/Excel/CSV report.

## Quick start (guided)
    python start.py

It asks (1) which model to test, its API base URL and key, and (2) which MCP server: TypeScript or FastMCP started locally (start command and folder), or an already running server (URL and token). It also confirms the judge model. Then it asks which question set and which topics to test (see below), shows how many runs that means, and runs, grades and builds the report in one go, including a no-MCP baseline (`--skip-baseline` to drop it). Keys are typed hidden and only passed to the child processes; the generated `.wizard-config.yaml` holds no secrets. `python start.py --dry-run` shows the config without running anything.

## Question sets and topics
`start.py` offers the sets listed under `question_sets` in `config.yaml`:
1. **Swiss benchmark** (default): the 902 questions in `benchmark/data/` (32 hand-verified, 870 generated from official open data), converted on the fly by `import_benchmark.py`. Mapping: `ask_back` -> `clarify`, `not_switzerland` -> `out_of_scope`, foreign items -> topic 0. The benchmark's required facts, forbidden content and typical errors are appended to the reference answer for the judge. Questions past their `valid_until` date are skipped.
2. **Own questions**: `eval/questions.jsonl`. Add your own lines there (fields below); add more sets in `config.yaml` if needed.

You then pick topics by number (Enter = all). Options: `--max-per-topic N` (random, fixed-seed sample, cuts cost), `--verified-only` (the 32 hand-checked benchmark questions), `--seed-questions` (skip the prompt, use `questions.jsonl`). `python import_benchmark.py --list` shows the topic counts; it can also write a file directly (`--topics 1,4 --out ...`).

**Attention: the languages are not equivalent.** Benchmark questions are not translations of each other, so `group_id` is just each question's own id and the by-language results compare different questions, not the same question in different languages.
- 574 questions are German, 247 French, 80 Italian and 1 Romansh.
- Generated items use the language of the municipality (Romansh-speaking municipalities get German questions).
- Topic mix differs by language, and 514 of 902 questions are about health insurance premiums, so a language gap may just reflect the topic or question type.
- Reference answers are in English. Read language differences as indications, and use the same question in several languages (one `group_id`) in your own set if you need a clean comparison.

## What needs to be changed before a real run
| # | Where | What | Status |
|---|---|---|---|
| 1 | `config.yaml` `mcp_servers.typescript` | Set the real start command (default `node dist/index.js` is a guess), build the server first | open |
| 2 | `config.yaml` `models` | Replace `REPLACE_WITH_MODEL_NAME` (`gpt`) and `REPLACE_WITH_MYAI_MODEL_NAME` (`myai-default`); check the myAI endpoint is OpenAI-compatible | open |
| 3 | `.env` (from `.env.example`) | Add API keys: provider keys, `MYAI_API_BASE`/`MYAI_API_KEY`, and `SWISS_MCP_URL`/`SWISS_MCP_TOKEN` if using the `remote` set. Or enter the model at run time with `--ask` | open |
| 4 | `config.yaml` `judge.model` | Keep one judge for all runs, ideally not a model under test. Changing it means `python grade.py --regrade` | decide |
| 5 | `questions.jsonl` (own set) | Optional now that the benchmark is set 1. To use your own: fill the `TODO` references (verified against the sources, never guessed) and translate questions into de/fr/it/rm/en under one `group_id`. Only 2 of the 5 seeds are scored today | optional |
| 6 | `config.yaml` `topics`, `languages` | Adjust labels if the scope differs | optional |

Always pass `--mcp-sets`; without it every set is started and the ones not set up fail.

## Pipeline
1. `questions.jsonl`: dev set (5 seed questions; TODO references stay excluded from scores until filled in)
2. `python run.py`: every model x MCP set x question, logs answer + tool calls to `results/results.jsonl`
3. `python grade.py`: deterministic checks + LLM judge to `results/graded.jsonl`
4. `python report.py`: `reports/report.html` (heatmaps), `report.xlsx`, `topic_language_long.csv`

All steps are resumable. Rerun after adding questions or models and only the new work is done.

## Setup (from `eval/`)
    python -m venv .venv && .venv\Scripts\activate      # or source .venv/bin/activate
    pip install -r requirements.txt
    pip install -e ..                                    # server deps (fastmcp, ...) so the stdio server can start
    cp .env.example .env                                 # fill in keys, then load it (see .env.example)

Run order:

    python run.py --stage 1     # external models first
    python run.py --stage 2     # Swisscom myAI models last
    python grade.py && python report.py

`make eval-run | eval-run-myai | eval-grade | eval-report` do the same.

Run a single model against the server only:

    python run.py --models claude-haiku-4-5 --mcp-sets fastmcp      # or: typescript | remote | no-mcp

## Choosing the server
`config.yaml` has three presets under `mcp_servers`, each exposed as an MCP set; pick one with `--mcp-sets`:
- `fastmcp`: the Python FastMCP server in this repo over stdio (`python -m mcp_boilerplate.main`; currently 21 tools, including `compute_swiss_tax`). With `uv` installed you can use the repo's own command, `uv run --frozen python -m mcp_boilerplate.main` from the repo root (see `.mcp.json`).
- `typescript`: for a TypeScript server outside this repo: `node dist/index.js` over stdio, run from the repo root (`cwd: ..`). Build first, and edit `command`/`args` to match the TypeScript server's entry point (or `npx tsx src/index.ts`).
- `remote`: streamable HTTP at `SWISS_MCP_URL` with `Authorization: Bearer SWISS_MCP_TOKEN`.

Server dependencies live outside this harness: the Python server needs `pip install -e ..`, the TypeScript server needs `npm install`.
Tool names are exposed to models as `<server>__<tool>`, sanitized to `[a-zA-Z0-9_-]` and capped at 64 chars; `run.py` maps them back to the real tool name (unless two names collide after sanitizing).

## Choosing the model and access
Configured models (`config.yaml`, keys from env vars) run with `--stage` / `--models`. To enter a model at run time instead:

    python run.py --ask --mcp-sets typescript                      # prompts for model, API base, API key (hidden)
    python run.py --model-name openai/gpt-4.1 --mcp-sets fastmcp   # key from OPENAI_API_KEY
    python run.py --model-name openai/my-model --api-base https://host/v1 --api-key ... --mcp-sets remote

`--model-name` uses a LiteLLM string (`provider/model`). Blank key = the provider's usual env var. Models in `config.yaml` that still say `REPLACE_WITH_...` stop the run with a message.
Ad-hoc runs are logged under the model name's last segment, so grade and report work unchanged. Note that `--api-key` on the command line ends up in shell history; prefer `--ask` or env vars.

## Question fields
| field | values |
|---|---|
| qid, group_id | group_id links the same question across languages |
| topic | 1-16, 0 = not about Switzerland |
| language | de, fr, it, rm, en |
| level | federal, cantonal, municipal, none |
| expected_behaviour | answer, clarify, out_of_scope |
| reference_answer | starts with TODO = excluded from scores until filled |
| key_facts | strings that must appear (amounts, dates, deadlines) |
| source_domains | e.g. priminfo.admin.ch, checked in answer + tool calls |
| valid_as_of | date the reference was verified |

## Building the dev set
- Write each question once, then translate it into all 5 languages under one `group_id`. Differences between languages then measure language, not question difficulty.
- Target 5+ questions per topic x language cell. Cells below `min_n_per_cell` are faded in the report.
- Include clarify and out_of_scope cases in every language, roughly 10% each.
- Re-verify time-sensitive references (premiums, holidays, fees) and update `valid_as_of`, then `python grade.py --regrade`.

## Scoring
- answer: judge says correct vs reference
- clarify: asked for the actually missing info
- out_of_scope: said it is not about Switzerland
- Also reported: answered in the question's language, key-fact hit rate, source hit, tool calls, latency, cost
