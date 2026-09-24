# External portfolio evaluation — `malkreide/swiss-public-data-mcp`

> Verified 2026-09-24 against the index repo (HEAD `2680363`) and six member repos cloned
> and smoke-tested: `swiss-holidays-mcp`, `bag-health-mcp`, `swiss-housing-mcp`,
> `swiss-snb-mcp`, `fedlex-mcp`, `swisstopo-mcp`. `termdat-mcp` was installed from PyPI.
> Requirements: [CHALLENGE.md](CHALLENGE.md) · Source research: [SOURCES.md](SOURCES.md)

## 1. Verdict

- **D1 — It does not solve the challenge.** The repo is a catalogue: `portfolio.json`,
  44 MCP-registry drafts, doc-generation scripts. No server code. The 42 servers live in
  separate repos under `github.com/malkreide/`, and none covers the citizen-service topics
  in the jury's sample questions.
- **D2 — Not a fork base. A selective pattern donor.** Two code fragments and one place
  resolver are worth porting (§5). The thin-client design of the portfolio conflicts with
  our fat-server design and with the evidence the jury grades on.

## 2. What the portfolio is

| Fact | Value |
|---|---|
| Owner | Hayal Oezkan, single maintainer, Claude co-authored commits |
| Licence | MIT (index, termdat-mcp, and the six cloned servers) |
| Servers | 42 active, 2 archived; all thin read-only clients over official or aggregator APIs |
| Stack | official `mcp` SDK 2.x (`MCPServer`), stdio + Streamable HTTP, Pydantic v2, httpx, `uvx` install from PyPI |
| Quality claim | "100% audited" = self-audit with the author's own `mcp-audit-skill` (120 checks). Repo-grounded, not independent |
| Activity | index: 130 commits, 62 in Aug 2026, 2 in Sep 2026. `portfolio.json.last_checked` = 2026-08-18 |
| Install check | `uvx termdat-mcp` answers JSON-RPC `initialize` over stdio in under 2 s |
| Design statement | README: "No server hosts, mirrors, or re-publishes data: each one is a thin, read-only client for a public endpoint" |

## 3. Source × availability matrix

Rows follow CHALLENGE.md §7 plus two infrastructure sources. "Official serving" is from
SOURCES.md verifications and the smoke tests. "Not verified" where neither checked.

Portfolio column: ✅ covered by a malkreide server · 🟡 server exists but wrong scope or
wrong authority · ❌ nothing.

| # | Source to crawl (responsible authority) | Level | Sample Q | Portfolio | Official data serving | Third-party aggregator (not authoritative) | Auth | Effort |
|---|---|---|---|---|---|---|---|---|
| 1 | BAG premiums: `opendata.bagnet.ch/Praemien/Prämien_CH.csv` via opendata.swiss | Federal | Q3 | ❌ (`bag-health-mcp` = disease surveillance) | CSV/XLSX/ZIP, updated 2026-09-11, all query dimensions as columns | priminfo.admin.ch is official but an HTML calculator; comparis etc. | none | Low |
| 2 | 26 cantonal tax administrations (ti.ch …) | Cantonal | – | ❌ | HTML/PDF/calculators, 26 systems | ESTV calculator (federal, not the responsible canton) | none | Very high |
| 3 | Fedlex (VZV art. 42, VMWG art. 12a) | Federal | Q2, Q8 | 🟡 `fedlex-mcp`: metadata + link only, no article text | SPARQL JOLux + HTML consolidated text, ELI, date-addressable | none needed | none | Medium |
| 4 | Municipal waste calendars (lausanne.ch, consortia) | Municipal | Q1 | ❌ | HTML/PDF/ICS per municipality; vendor platforms Trennio, Sammelkalender, A-Region | Localcities (Swisscom Directories) | none | High per municipality |
| 5 | Residents' offices (bern.ch, lausanne.ch) | Municipal | Q7 | ❌ | HTML only | ch.ch (official portal, maps responsibility, is not the authority) | none | Medium per municipality |
| 6 | SEM sem.admin.ch + cantonal migration offices | Federal/cantonal | – | ❌ | HTML/PDF | ch.ch | none | Medium |
| 7 | AHV/IV information centre ahv-iv.ch (legally mandated) | Semi-official | – | ❌ | HTML/PDF mementos | – | none | Medium |
| 8 | SECO: arbeit.swiss (procedures), amstat.ch (statistics) | Federal | – | 🟡 `seco-labor-mcp`: AMSTAT statistics only, no procedures | AMSTAT API; arbeit.swiss HTML | – | none | Medium |
| 9 | School calendars: 26 cantonal education depts, or municipality (GR per-municipality PDF, ZH delegated, BE two calendars) | Cantonal/municipal | Q4, Q6 | 🟡 `swiss-holidays-mcp`: OpenHolidays feed, canton granularity, no authority URL; `zh-education-mcp`: ZH statistics only | Mostly PDF; open data only BS, BL, SZ (SZ self-declares non-binding), ICS SG city | openholidaysapi.org, schulferien.org, feiertagskalender.ch, Localcities | none | High |
| 10 | opentransportdata.swiss (FOT mandate) | Semi-official | – | ✅ `swiss-transport-mcp`, `swiss-road-mobility-mcp`, `sbb-opendata-mcp` | OJP 2.0 XML, GTFS-RT | – | API key (server key handling not verified) | Medium |
| 11 | 26 Strassenverkehrsämter + ASTRA Weisung + VZV; asa.ch address list; gr.ch form in Romansh | Cantonal + federal | Q2 | ❌ (`swiss-road-mobility-mcp` = GBFS, EV charging) | HTML/PDF; 27 rows validated in SOURCES.md §9 on 2026-09-23 | asa.ch is the association directory | none | Low for us |
| 12 | BWO bwo.admin.ch/referenzzinssatz | Federal | Q8 | ❌ (`swiss-housing-mcp` = GWR register; `swiss-snb-mcp` = SNB policy rate, wrong rate) | HTML only, no CKAN dataset, quarterly, four dates per value | – | none | Very low |
| 13 | BK bk.admin.ch; VoteInfo JSON (BFS/BK) | Federal | – | 🟡 `swiss-democracy-mcp` uses Swissvotes (Uni Bern, academic); `parlament-mcp` is official Curia Vista | VoteInfo JSON via CKAN/S3 | Swissvotes | none | Low |
| 14 | Zefix | Federal | – | ✅ `register-mcp` | REST JSON, Basic auth on free account (HTTP 401 without) | – | credential | Low + credential |
| 15 | BAZG bazg.admin.ch, Tares | Federal | – | ❌ | HTML | – | none | Medium |
| 16 | BFS PxWeb, opendata.swiss CKAN, geo.admin.ch, MeteoSwiss | Federal | – | ✅ `swiss-statistics-mcp`, `swisstopo-mcp`, `meteoswiss-mcp`, `lindas-mcp`, `i14y-mcp` | JSON APIs, no auth | – | none | Low |
| G | Place resolver: api3.geo.admin.ch SearchServer, swissBOUNDARIES, OpenPLZ | Infra | all local Qs | ✅ `swisstopo-mcp` `find_commune`, `municipality_at`, `lookup_postal_code` | JSON, sub-second | – | none | Very low |
| C | Open-data catalogue opendata.swiss CKAN | Infra | – | ❌ in this portfolio (`pipeworx-io/mcp-opendata-swiss` exists elsewhere) | CKAN JSON; 403 without User-Agent | – | none | Very low |

Totals: sample questions 0/8 fully covered, 2 partial (Q4, Q6, wrong authority), 5 not
at all, 1 out of scope by design (Q5). Topic areas 5/16 covered, 2 partial, 9 none.

## 4. Findings and risks by source

**1 BAG premiums**
- F4 `bag-health-mcp` has zero hits for premium, priminfo, franchise, OKP. Wrong domain despite the name.
- F11 The official CSV is the cleanest source in the challenge. Building it ourselves is cheaper than adapting anything in the portfolio.
- R6 Premium region is a per-municipality legal assignment. The place resolver (row G) must sit in front of the CSV lookup.

**3 Fedlex**
- F5 `fedlex-mcp` returns ordinance title, status, entry-into-force date and ELI link. No article text. Fails the citation-support case for VZV art. 42 and VMWG art. 12a.
- F12 Its `handle_error` and `no_match_hint` functions and the `match_type` field (`src/fedlex_mcp/server.py:279-295`, `500-556`) are the best reusable code in the portfolio for our `source_unavailable` and `no_match` states.
- R4 Live SPARQL on every call, no cache, 1.3 s per call. No fallback during a jury run.
- R7 Article extraction must be built by us either way; SOURCES.md §3.2d-bis records the Fedlex HTML shell trap.

**4 Waste · 5 Residents' offices · 6 SEM · 7 AHV/IV · 15 BAZG**
- F1, F2 Nothing in the portfolio. HTML-only municipal or federal pages with no API. The thin-client model cannot cover them by design (F8).
- R8 Localcities is the tempting waste shortcut and belongs to Swisscom Directories. It is an aggregator; the review checklist excludes it. Not even as a fallback.
- R3 Three of the five uncovered sample questions sit in these rows.

**9 School calendars**
- F3 `swiss-holidays-mcp` returned correct autumn 2026 dates for Bern (19.09–11.10) and Scuol (10.10–25.10) in live tests, verified against bern.ch and scoula-scuol.ch. It cites only the fixed string "Data: OpenHolidays API … Unofficial aggregation". No authority URL, passage or effective date. Canton-code input only. Languages DE/FR/IT/EN, no Romansh.
- F13 OpenHolidays records carry district codes for GR (`CH-GR-EB` for Scuol). The municipality-to-district join needs two tool calls and is undocumented.
- R1 Any answer citing OpenHolidays is ungrounded under the "publisher responsible for the matter" rule, even when numerically correct.
- R2 Silent staleness. Only a fetch timestamp is surfaced.
- R9 Legal-status trap. SZ open data self-declares non-binding, AR publishes indicative dates, BL excludes one Gymnasium. Machine-readable does not mean citable. Lookup from the dataset, cite the binding PDF.

**10 Public transport**
- F14 Three servers, the portfolio's strongest area. Not smoke-tested by us.
- R10 OJP requires an API key. Key handling in the servers is not verified. A key costs operability points.

**11 Driving licence exchange**
- F1 Nothing in the portfolio.
- F15 The team already validated 27 cantonal rows plus the federal VZV line. The portfolio adds nothing here.

**12 BWO reference rate**
- F4 `swiss-housing-mcp` is the GWR building register. `swiss-snb-mcp` exposes the SNB policy rate and SARON.
- R11 An LLM given `swiss-snb-mcp` will answer Q8 with the SNB Leitzins. The server has no disclaimer separating it from the BWO rate. Do not connect it.
- F16 One HTML page, quarterly, four dates per value. A curated JSON with the verbatim passage and gültig-ab date is specified in SOURCES.md §3.2f.

**13 Voting**
- F17 `swiss-democracy-mcp` reads Swissvotes, an academic database. `parlament-mcp` reads official Curia Vista OData. Only the second is authoritative.

**14 Zefix**
- F18 `register-mcp` works against the official REST API with a free-account credential.
- R12 One credential to deliver through the organizers' secure channel and to list in the README. The challenge rewards keyless servers.

**16 Statistics, geodata, weather**
- F19 Five servers, all official JSON APIs, no auth. Real breadth if wanted. No sample question touches this row.
- R2 (efficiency) Each added server adds tools the LLM must choose between.

**G Place resolver**
- F6 `swisstopo_find_commune` resolved Scuol and Lausanne (BFS 5586, VD) and returned an honest empty result for Konstanz, sub-second, no key.
- R5 `swisstopo_geocode` returns a Swiss hamlet "Konstanz (LU) - Rothenburg". Only `find_commune` or `municipality_at` is safe as the out-of-scope gate.
- R13 SOURCES.md §3.1b found live fuzzy search resolving the wrong municipality and chose an offline resolver over all 2110 communes. That decision holds. Use the malkreide code as reference, not as a live dependency.

**C Open-data catalogue**
- F20 Not in this portfolio. CKAN returns 403 without a User-Agent. Relevant only to the premiums download script.

**Cross-cutting**
- F7 The robots.txt / terms-of-use toggle is missing in every server inspected. The portfolio never needed it: every server hits an API, not a website.
- R3 We must build that toggle ourselves for rows 4, 5, 6, 7, 9, 11, 12, 15, which are all HTML or PDF crawls.
- F8 The portfolio returns what the upstream API returns. Supporting passage, effective date and the five states are our layer regardless of which sources we take.
- F9 "Production ready, 100% audited" is self-certification. Substantive but not independent.
- F10 Engineering quality is high: structured envelope with `source`, `license`, `match_type`, `provenance`, `retrieved_at` per record; fixture-vs-live test split; CI with version-sync check; DNS pinning; egress allow-list.

## 5. What to take

| Code | Action | From |
|---|---|---|
| A1 | Port the response envelope and the honest-failure pair into our FastMCP server | `swisstopo-mcp/src/swisstopo_mcp/models.py` (`ToolResponse`, `LICENSE_BY_SOURCE`); `fedlex-mcp/src/fedlex_mcp/server.py:500-556` |
| A2 | Use the OpenPLZ / swissBOUNDARIES lookups as reference for our offline resolver; gate out-of-scope on an empty commune match, never on geocode | `swisstopo-mcp/src/swisstopo_mcp/openplz.py:285-320` |
| A3 | OpenHolidays only as a consistency check against curated authority URLs, never as the cited source | `swiss-holidays-mcp` |
| A4 | Keep the MIT copyright notice with any copied file | all repos |
| A5 | Copy the fixture-vs-live test split: `pytest -m "not live"` in CI, weekly live run classified into infra failure / contract break / pass | `swisstopo-mcp/.github/workflows`, `scripts/classify_live_run.py` |

Do not connect any malkreide server alongside ours during the jury run: R1, R2, R11 and
F7 all apply, and every extra server adds tools to the client's selection problem.

## 6. Other Swiss MCP servers not evaluated

SOURCES.md §5 lists `JayTheSkier/fedlex-connector`, `vikramgorla/mcp-swiss`,
`pipeworx-io/mcp-opendata-swiss`. Same reading applies until checked: thin wrappers on
structured APIs, none addressing jurisdiction resolution, passage extraction or ask-back.
