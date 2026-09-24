# Swiss AI Week MCP

An MCP server that grounds questions about Switzerland in two complementary,
independent mechanisms: a live lookup against the federal commercial register
(Zefix) via LINDAS, with SHAB/cantonal gazette citations, and a local SQLite
knowledge base of 13 reviewed Swiss authority pages (health insurance
premiums, the reference mortgage rate, foreign driving-licence exchange,
school holidays, waste collection, and municipal arrival registration). A
third, narrower tool answers 2026 basic health-insurance premium questions
directly from a precomputed table. Also known by its MCP server name,
`mcp-swiss-info`, in client configuration.

Team: Roberto Cerrone, Edoardo Diana, Alberto Minetti, Vincent Van Loo, Victor
Bonilla, Jesus Sebastian, Jiaqi Yu.

## Install

Requires [uv](https://docs.astral.sh/uv/). From a clone of this repo, in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

It installs dependencies, asks for the two API keys (optional, saved to the git-ignored `.env`), and registers the server in whichever of Claude Code, Codex and opencode it finds. Restart the harness afterwards. Use `-Yes` to skip prompts (keys are then read from `$env:CRAWLORA_API_KEY` and `$env:OPENAI_API_KEY`), and `-Uninstall` to remove the server from every harness.

Manual equivalent for Claude Code: `claude mcp add --scope user mcp-swiss-info -- uv run --directory <path-to-this-repo> python -m mcp_boilerplate.main`.

## Check data freshness

Ask the assistant "how fresh is your data?" (tool `source_status`), or "open the dashboard" (tool `open_dashboard`) for a local page at http://127.0.0.1:8765 with each source's last refresh, failures, and a Refresh button. Outside a harness: `make dashboard`. Sources older than 30 days show as outdated (`STALE_AFTER_DAYS` to change).

## Scope

Covered:

- **Companies and the commercial register**: Swiss companies in the federal
  commercial register index (Zefix) and their SHAB/cantonal gazette
  publications. Federal level, all 26 cantons. Languages: German, French,
  Italian, English; Romansh questions are answered in German with a note.
- **13 reviewed authority pages**, federal, cantonal, and municipal (full
  list under [Data sources](#data-sources)): health insurance premiums and
  premium regions, the reference mortgage rate and its ordinance, and
  foreign driving-licence exchange law (federal); school holidays for
  Graubünden, Vaud, Ticino, and Zürich (cantonal); waste collection, arrival
  registration, and school holidays for Scuol, Bern, Lausanne, and St.
  Gallen (municipal). Pages are saved and searched in their source language
  (mostly German, some French and Italian); nothing is translated.
- **2026 basic health-insurance minimum premiums**, looked up by age group,
  Swiss BFS municipality number, and deductible, from a precomputed table —
  not the knowledge base above; see [Data sources](#data-sources) for the
  distinction.

Not covered: natural persons (board members, signatories), VAT status,
cantonal register extracts, or statistics and lists over the commercial
register; any Swiss topic outside the 13 reviewed pages and the premium
table above (this is a starter set, not complete Swiss coverage); anything
outside Switzerland.

## Tools

### Commercial register: `company_info`

One tool, no mandatory parameters. Omitting both `name` and `uid` returns
`need_info` asking for a company name — a mandatory field would push that
failure into client-side schema validation, where the calling LLM cannot see
it.

| Parameter | Type | Default | Purpose |
|---|---|---|---|
| `question` | `str \| None` | `None` | The user's question verbatim; used to self-detect wrong-topic, person, jurisdiction, and analytics questions |
| `name` | `str \| None` | `None` | Company name or name prefix |
| `uid` | `str \| None` | `None` | `CHE-xxx.xxx.xxx`; dots and hyphens optional |
| `canton` | `str \| None` | `None` | Two-letter canton code, narrows disambiguation |
| `language` | `str` | `"de"` | `de \| fr \| it \| en`; `rm` maps to `de` |
| `include_publications` | `bool` | `True` | Attach recent gazette publications for the resolved company |
| `max_publications` | `int` | `5` | 1–20 |

Response states:

- `answered` — company resolved, with citation, authority, and effective date.
- `need_info` — the name was ambiguous or missing; the tool asks for exactly one of UID, canton, or seat, with up to 5 candidates.
- `no_match` — no company found at the primary source (and, when a UID was given, no deletion publication either).
- `out_of_scope` — the question is about persons, a non-Swiss jurisdiction, register-wide analytics, or an unrelated topic.
- `source_unavailable` — a source the answer depends on could not be reached; the tool never falls back to a cached or stale record.

Example (`answered`, abbreviated):

```json
{
  "status": "answered",
  "answer": "Swisscom (Schweiz) AG ist eine aktive Aktiengesellschaft mit Sitz in Ittigen (BE).",
  "company": {
    "name": "Swisscom (Schweiz) AG",
    "uid": "CHE-101.654.423",
    "legal_form": "Aktiengesellschaft",
    "seat": "Ittigen",
    "canton": "BE",
    "address": {"street": "Alte Tiefenaustrasse 6", "zip": "3050", "city": "Bern"},
    "status": "ACTIVE"
  },
  "publications": [
    {"date": "2026-06-12", "registry_office": "Handelsregisteramt des Kantons Bern", "rubric": "HR", "source_url": "https://amtsblattportal.ch/..."}
  ],
  "citation": {
    "authority": "Eidgenössisches Amt für das Handelsregister (EHRA), Bundesamt für Justiz",
    "source_url": "https://register.ld.admin.ch/zefix/company/415941",
    "cantonal_excerpt_url": "https://be.chregister.ch/cr-portal/auszug/...",
    "effective_from": "2026-06-12",
    "dataset_modified": "2026-09-23",
    "source_status": "indicative"
  },
  "notes": "Zefix ist nicht rechtsverbindlich. Massgebend sind der beglaubigte Handelsregisterauszug des Kantons und die SHAB-Publikation."
}
```

The full field list, including `need_info`, `no_match`, `out_of_scope`, and
`source_unavailable` shapes, is in `docs/prd-zefix-company-info.md` §5.3.

### Health insurance premium lookup: `swiss_health_insurance_premiums`

`swiss_health_insurance_premiums(age, municipality_code, franchise)` is an
offline lookup over a precomputed CSV, separate from the knowledge base
below. `age` is completed years (19–25 counts as "young", 26+ as "adult");
`municipality_code` is the Swiss BFS municipality number, not a postal code;
`franchise` is the annual deductible in CHF (300, 500, 1000, 1500, 2000, or
2500). It returns both with- and without-accident-cover minimum premium
options, each naming the cheapest insurer and model. States: `answered`,
`no_data` (valid lookup, nothing on file), `invalid_input` (bad age,
franchise, or municipality code), `source_unavailable` (the CSV could not be
read). Valid only for premium year 2026; the tool says so in its own
description and response.

### Knowledge base: `search_knowledge`, `get_source`, `crawl_*_sources`

- `search_knowledge(query, limit=5)` returns relevant passages, source URLs,
  authority names, crawl times, and any failed-refresh time. The limit must
  be 1–10. Search uses OpenAI `text-embedding-3-small` for semantic ranking;
  if the embedding API is unavailable, it returns locally ranked keyword
  matches (SQLite FTS5) with `method: "keyword_fallback"`.
- `get_source(level, source)` returns the complete saved page and metadata.
  Levels are `federal`, `cantonal`, and `municipal`; names are in
  [the approved source list](src/mcp_boilerplate/sources.py).
- `crawl_federal_sources`, `crawl_cantonal_sources`, `crawl_municipal_sources`
  (each `source: str | None = None`) refresh one approved source by name, or
  every source at that authority level. They accept no pasted URLs. HTML and
  JSON normally use Crawlora, with a direct fetch of the same approved URL if
  Crawlora is unavailable or fails; PDFs are always downloaded and
  text-extracted locally. A refresh must return successful content, the
  expected approved URL, and a source-specific topic phrase before it
  replaces the saved page and passages; a failure preserves the previous
  version and records its time.

The shipped seed database contains all 13 sources. Crawl tools update the
writable local database only; they never change the packaged seed.


## MeteoSwiss weather

The weather tools download MeteoSwiss Open Data files from `data.geo.admin.ch` and return only the requested point or station and time period. No API key is needed. Times are UTC unless specified otherwise; missing measurements are returned as `null`. Results include source URLs and the required “Source: MeteoSwiss” attribution.

- `swiss_weather_forecast(postal_code, granularity="daily", periods=3, point_id=None, metric="temperature_c")`: forecasts for a **four-digit postal code**, up to nine Swiss local calendar days (daily min/max temperature and precipitation), or up to 48 future UTC hours. For hourly forecasts, choose **one** `metric`: `temperature_c`, `precipitation_mm`, or `precipitation_probability_3h_pct` (the probability refers to a three-hour interval). Hourly files can be ~33 MB each, so this downloads only the selected parameter. When a postal code has several forecast points, the result lists point IDs; supply `point_id` to disambiguate.
- `swiss_weather_observations(station_id, granularity="10min", on_date=None)`: actual measurements at a **three-letter MeteoSwiss station** such as `BER` (Bern/Zollikofen). Available granularities are `10min`, `hourly`, and `daily`. Omit `on_date` for the latest published value, or set an ISO date like `2026-09-23` for every available measurement on that UTC date. Historical dates are supported when MeteoSwiss publishes a matching station file. Daily precipitation covers 00:00–24:00 UTC.

Forecasts are for postal-code points; observations are measurements at stations and are not interchangeable. Both tools fetch official files on demand; repeated forecasts of the same point and run are cached in memory. See the [forecast](https://opendatadocs.meteoswiss.ch/e-forecast-data/e4-local-forecast-data), [station](https://opendatadocs.meteoswiss.ch/a-data-groundbased/a1-automatic-weather-stations) and [data format](https://opendatadocs.meteoswiss.ch/general/download) documentation.

## Swiss statistics, open-data catalogue and map

These tools query the official public APIs on demand; no API key is needed. They limit returned results and include source links.

- `bfs_population(canton="CH", start_year=None, end_year=None, population_type="permanent", sex="total")` gets the [FSO/BFS PxWeb population table](https://www.pxweb.bfs.admin.ch/api/v1/en/px-x-0103010000_101/px-x-0103010000_101.px). Use `CH` or a canton abbreviation such as `BE`, `GE`; optionally select up to ten available years and permanent/non-permanent population or male/female totals. The default is the latest **published annual** figure, not a live headcount. The tool selects totals for permit, age, and citizenship to avoid double-counting.
- `opendata_search_datasets(query, limit=5, language="en")` searches the [opendata.swiss catalogue](https://handbook.opendata.swiss/en/content/nutzen/api-nutzen.html) by topic. It returns concise metadata and dataset IDs (limit 1–10).
- `opendata_dataset(dataset_id, language="en", resource_start=0)` returns one dataset’s metadata and up to 20 publisher-hosted resource links with their formats and rights. Set `resource_start=20` to fetch the next page of links. These catalogue tools do not treat a dataset description as the actual data.
- `swiss_geo_search(query, limit=5)` searches [map.geo.admin.ch locations](https://docs.geo.admin.ch/access-data/search.html) for addresses, ZIP areas and place names, returning coordinates in WGS84.
- `swiss_geo_context(latitude, longitude)` identifies the **current** municipality and its BFS code, canton, and postal area at a WGS84 coordinate using [geo.admin.ch identify](https://docs.geo.admin.ch/access-data/identify-features.html), plus a link to the map. Search results supply coordinates; municipal boundaries and postal areas need not match.

## Customs, federal political rights and migration

These three tools fetch the selected authority page at query time and return its URL, fetch time and the relevant source paragraphs. They use a fixed list of official pages rather than accepting arbitrary URLs. No credentials are required.

- `swiss_import_parcel_vat(goods_value_chf, shipping_chf=0, vat_rate="standard", customs_duty_chf=None)` estimates import VAT for an **online purchase delivered to Switzerland** using [BAZG/FOCBS parcel rules](https://www.bazg.admin.ch/en/receipt-of-letters-and-parcels). Supply the price excluding separately stated foreign VAT; shipping and any known customs duty are included in the VAT basis. Choose `standard` (8.1%) or `reduced` (2.6%) only when the goods qualify. BAZG says import VAT up to CHF 5 is not levied. The tool does not calculate tariffs, excise, or carrier clearance charges and does not apply the private-gift exemption; when customs duty is unknown its VAT estimate can change.
- `swiss_federal_political_rights(topic)` reads [Federal Chancellery (BK/FCh) rules](https://www.bk.admin.ch/de/politische-rechte) for `initiative`, `referendum`, `national_council`, `petition` or `federal_vote`. Initiative and referendum results include signature requirements and collection periods; election results describe the federal National Council rules. Excerpts are returned in the German of the BK source. `federal_vote` covers the federal ballot-setting process, not a list of confirmed voting dates.
- `swiss_residence_permit_guidance(group, topic="residence")` retrieves [SEM residence information](https://www.sem.admin.ch/sem/en/home/themen/aufenthalt.html). Use `eu_efta` with `residence`, `L`, `B`, `C` or `G`; `third_country` with `residence`, `work`, `L_B_C`, `F`, `N` or `S`; and `uk` with `residence` for the distinct UK rules. `L_B_C` describes biometric card issuance, not eligibility. Results are sourced guidance, while cantonal migration offices decide individual applications.

## Data sources

Two different things share the word "source" here, and they don't overlap:
`src/mcp_boilerplate/zefix/sources/` holds the **live API clients**
(`LindasClient`, `ZefixClient`, `GazetteClient`) that `company_info` calls
fresh on every request and stores nothing; `src/mcp_boilerplate/sources.py`
is the **registry of reviewed authorities** — pages the crawler and
`get_source` are restricted to, in `SOURCES`, and the four API endpoints
`company_info` is allowed to call, in `API_SOURCES` (used for the egress
allow-list). Nothing in `SOURCES` is fetched until a `crawl_*_sources` call
asks for it, and the result is saved, not proxied.

### Commercial register (`zefix/sources/`)

| Source | Endpoint | Auth | Licence / terms | Contributes |
|---|---|---|---|---|
| LINDAS (primary) | `lindas.admin.ch/query` | none | "Open use. Must provide the source." (`dcterms:rights` on the FOJ Zefix dataset) | Identity, legal form, seat, address, purpose. Updated daily. |
| Zefix web endpoint | `www.zefix.admin.ch/ZefixREST/api/v1` | none | Undocumented, no published terms | Enrichment only: status, SHAB date, cantonal excerpt link. Off by default. |
| Zefix PublicREST | `www.zefix.admin.ch/ZefixPublicREST/api/v1` | Basic Auth, free registration via `zefix@bj.admin.ch` | Documented (OpenAPI) | Same enrichment fields, used automatically once credentials are set. |
| Amtsblattportal | `amtsblattportal.ch/api/v1` | none | Portal GTC | UID-scoped SHAB/cantonal gazette publications. |

LINDAS is always used and is the only source required for an `answered`
result; the two Zefix backends and the gazette are enrichment whose failure
degrades fields but never removes the answer (except branch 3b, where a UID
resolves nowhere on LINDAS and the gazette alone can settle existence — see
the PRD).

### Reviewed knowledge-base sources (`sources.py`)

| Level | Source id | Authority | Publishes |
|---|---|---|---|
| Federal | `health_insurance_premiums` | Federal Office of Public Health (BAG), via opendata.swiss | 2026 basic-insurance premium archive package |
| Federal | `premium_regions_2026` | Federal Department of Home Affairs (FDHA), via Fedlex | Premium-region assignment ordinance |
| Federal | `reference_interest_rate` | Federal Office for Housing (BWO) | Current mortgage reference interest rate |
| Federal | `reference_interest_rate_law` | Swiss Confederation (Fedlex) | Ordinance on rent and lease of residential/business premises |
| Federal | `foreign_driving_licence_law` | Swiss Confederation (Fedlex) | Traffic admission ordinance (foreign licence exchange) |
| Cantonal | `gr_school_holidays_2026_27` | Canton of Graubünden | School holiday calendar 2026/27 |
| Cantonal | `vd_school_holidays_2023_31` | Canton of Vaud | School holiday calendar 2023–2031 |
| Cantonal | `ti_school_holidays_2026_27` | Canton of Ticino | School holiday calendar 2026/27 |
| Cantonal | `zh_school_holidays` | Canton of Zürich | School holidays |
| Municipal | `scuol_waste` | Region Engiadina Bassa / Val Müstair | Waste collection (Scuol's own page blocks direct retrieval, so the responsible regional authority's page is used instead) |
| Municipal | `bern_arrival` | City of Bern | Arrival, move, and departure registration |
| Municipal | `st_gallen_school_holidays` | City of St. Gallen | School year and holidays |
| Municipal | `lausanne_arrival` | City of Lausanne | Residents' registration office brochure |

**Health-insurance premium table** (`swiss_health_insurance_premiums`):
built by `scripts/build_kvg_premiums.py` from the [KVG26
mapper](https://kvgmapper26.github.io/)'s published GeoJSON into
`data/kvg_minimum_premiums_2026.csv` — extracted, not scraped live, and
cross-referenced against [Priminfo](https://www.priminfo.admin.ch/de/praemien)
without being fetched from it directly. A separate artifact from the
`health_insurance_premiums` knowledge-base entry above, which saves a
descriptive BAG page, not a queryable table.

## Compliance

### Commercial register

`RESPECT_ROBOTS_TXT` defaults to `true` — a configuration setting, not
hardcoded behavior, so it can be switched for testing.

- `true` (default): the undocumented Zefix web endpoint is not called;
  `enrichment_status` is `"policy_robots"` and the answer loses live `status`,
  `shabDate`, and the cantonal excerpt link. LINDAS and the gazette API are
  used regardless — a published SPARQL endpoint and an API with its own GTC
  are not crawl targets.
- `false`: the Zefix web endpoint is also called for enrichment.
- Setting `ZEFIX_USERNAME`/`ZEFIX_PASSWORD` switches enrichment to the
  documented PublicREST API under either setting — the credential grant is
  the ToS acceptance.

`zefix.admin.ch` and `amtsblattportal.ch` publish `robots.txt` with
`Disallow: /` for crawlers. This server does not crawl either site: it makes
one individual, user-triggered request per tool call against a published API
endpoint, in response to a specific question, never an unattended traversal
of pages.

Outbound requests are further restricted by an egress allow-list enforced on
every request (including redirects). The allow-list is derived from
`API_SOURCES` in `src/mcp_boilerplate/sources.py`: `lindas.admin.ch`,
`register.ld.admin.ch`, `www.zefix.admin.ch`, `amtsblattportal.ch`.

### Knowledge base

The crawler has no `RESPECT_ROBOTS_TXT`-equivalent setting; it is compliant
by construction instead. `check_url()` in `src/mcp_boilerplate/crawler.py`
rejects any URL — including a redirect target — that is not exactly one of
the 13 URLs in `sources.py`; `crawl_*_sources` and `get_source` take a
source name, never a URL, so no tool call can reach an arbitrary or
user-supplied page. Direct and PDF fetches identify themselves with a fixed
`User-Agent: swiss-ai-week-mcp/0.1`. Each of the 13 URLs was reviewed by
hand before being added; the code itself does not parse `robots.txt`.

## Credentials

Per source:

- `company_info`: none required. LINDAS, the Zefix web endpoint, and the
  Amtsblattportal API are all keyless. Optional: `ZEFIX_USERNAME` /
  `ZEFIX_PASSWORD` for the documented ZefixPublicREST API (register for free
  by emailing `zefix@bj.admin.ch`); without them, enrichment falls back to
  the undocumented web endpoint, gated by `RESPECT_ROBOTS_TXT` above.
- `swiss_health_insurance_premiums`: none. It reads a file shipped in the
  repo.
- `search_knowledge` / `get_source`: none required. `OPENAI_API_KEY`
  upgrades `search_knowledge` from keyword to semantic ranking; without it,
  search still works via keyword fallback. The key is never stored in
  SQLite.
- `crawl_*_sources`: `OPENAI_API_KEY` is required — a refresh embeds its new
  passages, and that step fails without the key (the previous saved version
  is kept, and the failure is recorded). `CRAWLORA_API_KEY` is optional: when
  unset, or when Crawlora fails, HTML/JSON refreshes fall back automatically
  to a direct fetch of the same approved URL; PDFs are always fetched
  directly regardless of this key.

Zero secrets are committed to this repository. Put credentials in a local
`.env` file, which is gitignored (`git check-ignore .env` confirms this).

## Run locally

```bash
uv sync
uv run python -m mcp_boilerplate.main            # stdio transport (default)
```

`uv sync --all-extras` additionally installs the `dev` group (pytest, respx,
ruff, mypy, ...), needed to run the test suite below.

SSE transport, for web/HTTP integration:

```bash
make run-sse
# equivalent to:
uv run python -m mcp_boilerplate.main --transport sse --port 8000
```

On first use, the knowledge-base tools copy the packaged seed database to
`~/.swiss-ai-week-mcp/knowledge.sqlite3`; later starts reuse that writable
copy. Set `KNOWLEDGE_DB_PATH` to use another location. Restart your MCP
client after changing server code or configuration.

### Client configuration

Claude Desktop / Claude Code (`.mcp.json`):

```json
{
  "mcpServers": {
    "mcp-swiss-info": {
      "command": "uv",
      "args": ["run", "--frozen", "python", "-m", "mcp_boilerplate.main"]
    }
  }
}
```

Codex (`.codex/config.toml`):

```toml
[mcp_servers.mcp-swiss-info]
command = "uv"
args = ["run", "--frozen", "python", "-m", "mcp_boilerplate.main"]
```

OpenCode (`opencode.json`):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "mcp-swiss-info": {
      "type": "local",
      "command": ["uv", "run", "--frozen", "python", "-m", "mcp_boilerplate.main"],
      "enabled": true
    }
  }
}
```

## Tests

```bash
uv run pytest -q                                    # offline, covers both grounding paths and the premium lookup
uv run pytest -m live                               # hits real upstream endpoints, run manually before submission
uv run python scripts/record_fixtures.py lindas     # refresh LINDAS fixtures
uv run python scripts/build_kvg_premiums.py --year 2027   # regenerate the premium CSV for a new year
```

`test_company_info.py` (injected fakes from `conftest.py`) and
`test_company_info_registration.py` cover the `company_info` state machine
and MCP registration; `test_sources.py` covers the API-source registry and
egress allow-list; `test_zefix_sources_lindas.py`,
`test_zefix_sources_zefix.py`, and `test_zefix_sources_gazette.py` cover the
`zefix/sources/` clients; `test_live.py` hits real upstream endpoints.
`test_crawler.py` covers the knowledge base offline, with fake fetchers and a
fake embedder; `test_health_insurance_tool.py` and `test_kvg_export.py` cover
the premium lookup and its CSV export.

## Honesty and prompt-injection stance

Every string returned by an upstream source is treated as data, never as
instructions. The `company_info` tool forwards only company name, purpose,
and address as free text in its answer. Gazette full text (`content`) and
SHAB message bodies (`shabPub[].message`) are read by no code path in this
server and are never returned. The server never answers `company_info` from
a cache: every result reflects a live call made during that request, or an
explicit `source_unavailable`. The knowledge base is the deliberate
exception to "never cache": it exists to answer from saved, dated pages, and
every result carries the page's `crawled_at` (and any `refresh_failed_at`)
so staleness is visible rather than hidden.

## Attribution

Company data: Zefix, Federal Office of Justice / EHRA, via LINDAS
(lindas.admin.ch). Not legally binding; the cantonal commercial register
extract is authoritative. Official notices: SHAB via amtsblattportal.ch; the
signed PDF is the binding version.

Parts of `src/mcp_boilerplate/zefix/sources` are vendored from
`malkreide/register-mcp`, MIT, Copyright (c) 2026 Hayal Oezkan; see
`src/mcp_boilerplate/zefix/sources/LICENSE-register-mcp`.

Knowledge-base pages are attributed inline by every `search_knowledge` and
`get_source` result (`authority`, `url`) — see the
[reviewed-source table](#reviewed-knowledge-base-sources-sourcespy) above.
Semantic ranking uses OpenAI's `text-embedding-3-small`; the premium table
is extracted from the community-run KVG26 mapper, cross-referenced against
Priminfo.

## Limitations

Commercial register:

- LINDAS is updated daily and can lag the register by up to one day.
- Dissolved companies are absent from the LINDAS graph; when a UID is known,
  the tool infers `DELETED` from a matching gazette deletion publication.
  Without a UID, a dissolved company simply returns `no_match`.
- Name search is exact, then prefix, then substring matching, not fuzzy. An
  exact registered name or a UID answers in well under a second. A name that
  matches nothing exhausts the 15 second LINDAS budget and returns
  `source_unavailable` with `error_class: "timeout_scan"` and a sentence asking
  for the UID, because LINDAS has no full-text index.
- One UID can have several registered seats (UBS AG: Basel and Zürich). The
  tool shows one seat and lists the others in `assumptions`.

Knowledge base and premium lookup:

- 13 sources is a starter set, not complete Swiss coverage; a question
  outside them, or outside the 2026 premium table, gets `no_data` /
  `not_found` or no useful search results, not a guess.
- Semantic search degrades to keyword (FTS5/bm25) matching whenever
  `OPENAI_API_KEY` is unset or the embeddings call fails; results stay
  restricted to the approved sources, but ranking quality is lower.
- The premium table is frozen to 2026; the tool returns `invalid_input`/
  `no_data` rather than an outdated figure once a new premium year applies,
  and a fresh CSV has to be regenerated and shipped, not auto-refreshed.
