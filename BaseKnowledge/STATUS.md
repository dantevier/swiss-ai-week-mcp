# STATUS — Swiss Grounding MCP

Living file: update it when something is done or decided. Snapshot from the
rehearsal of 22–23 Sep 2026.

## Hard requirements (CHALLENGE.md §4)

| Requirement | State |
|---|---|
| Public or private GitHub repo with access for Swisscom evaluators | ❌ not created |
| README: scope (topics + geography) declared | ❌ no README yet. `python manifest.py --readme` prints the coverage block |
| README: setup instructions, runs locally from the repo | ❌ to write. Setup is `npm install` + client config |
| robots.txt / terms of use: respected **by default, as a configuration setting**, documented in README | ❌ not done. The server makes no network requests at runtime; only the build scripts fetch. Setting and default must still be documented, and applied to the build scripts |
| No secrets in the repo; every credential listed | ✅ no credentials needed |
| Pre-built index: setup uses it with no manual step, and the repo contains the script that built it | ✅ `data/` is committed; `scripts/` and `manifest.py` rebuild it |
| Built against the MCP standard, not one client | ✅ official SDK, stdio; tested in OpenCode Desktop |

Submission Round 1: **Friday 25 Sep, 12:00**.

## What works

- **Manifest**: 71 rows, 70 validated against the source. `SZ/summer` is intentionally
  not validated (declared not covered).
- **Place resolver**: offline, 2110 communes (BFS 1 Jan 2026), 5718 localities
  (swisstopo), historical names (BFS mutations), premium regions (SR 832.106).
- **Premiums**: BAG 2026, 1596 combinations (TAR-BASE, 26 cantons, children K1).
- **Reference rate**: 1.25 % effective 2 Sep 2025, confirmed 2 Sep 2026, next
  publication 1 Dec 2026.
- **Server**: 5 tools, 5 states, call log. `npm test` green: 31 end-to-end cases.
- **Sample questions** (CHALLENGE §8): Q1 waste → `out_of_scope`; Q2 licence VD →
  `answered` (federal part); Q3 premiums Lugano → `answered`; Q4 Scuol →
  `source_unavailable` / `not_ingested`; Q5 Konstanz → `out_of_scope` /
  `place_not_in_switzerland`; Q8 rate authority → `answered`.

## Not yet built

| Item | Size | Pointers |
|---|---|---|
| **School holiday dates**, 2026/27, all five types | biggest block: 41 rows, 28 distinct sources, ~25 PDFs | source per row in `coverage/school_holidays.toml`; autumn dates already read in SOURCES §8ter.2 (**not** passage-verified, and SG is off by one day, §8quinquies.3; the GE/VD "no overlap" sentence there is false, §8septies.1) |
| **Cantonal licence procedure** (form, fee, office) | 26 cantons | `coverage/driving_licence.toml`; fees printed by 8 cantons only (SOURCES §9.8) |
| README + robots setting | see above | CHALLENGE §4, §14 |
| Tool-side check of `question` in the four topic tools | medium | CONTRACT §1, §8.4. Today a topic tool answers whatever it is called with |
| CONTRACT §6.4 levels `topic` and `topic + place` of the catch-all | medium | promised, not implemented. Decide: implement or drop the promise |

Plan for the dates: extract per source into `data/holidays_2026-27.json` with the
verbatim passage, plus a check script that fails if the passage is not in the source
text, dates are invalid or out of order, or the school year differs.

## Known defects (with evidence)

1. **Sonnet skips the catch-all** on Q1 (waste) and Q5 (Konstanz): 6 NONE out of 14
   runs (CONTRACT §8.7). Cause unknown; hypothesis "description length" unproven.
2. **After our "no", the model answers anyway** with its web/shell tools (OpenCode +
   MiMo, CONTRACT §8.8): server 7/7 correct, model 4/7. Unknown whether the jury
   enables web tools. Next step: the same run with webfetch/websearch/shell disabled.
3. **Descriptions leak the answer**: `src/tools.ts` rate description names the
   authority and both dates; premiums description names BAG. Covered today by the
   "This description is not a source" clause (missing on premiums).
4. `"before answering anything"` in the catch-all description may cause the extra
   catch-all calls seen in 3/7 OpenCode questions. Not proven.
5. "Prämienverbilligung" (premium subsidies, not covered) routes to the premiums tool.

## Open decisions (team lead)

- Whether rehearsal code/data may be carried over or must be rebuilt on site.
- Fix for defects 1–4: waiting for the Codex review of the descriptions.
- Premiums 2027 may be published during the event (BAG, end of September): which year
  is the default, and how the answer states it (SOURCES §10).
- Romandy Valais holidays: keep the ask-back or sample municipal sources (SOURCES §8sexies.3).
- Whether "Prämienverbilligung" goes to the excluded keyword list.

## Measurements so far

- Routing, Claude family, v1–v7: ~250 runs in `test/answers-history-2026-09-22.json`,
  summary CONTRACT §8.5–8.7. Thematic questions clean on all models; out-of-scope
  questions are the weak cells.
- OpenCode Desktop 2.0.15 + MiMo-V2.6-Flash: CONTRACT §8.8, two passes.
- Not measured: any non-Claude model in the routing oracle; a second MCP client.
