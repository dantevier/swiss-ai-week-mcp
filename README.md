# Swiss AI Week MCP

A Python/FastMCP server with a local SQLite knowledge base of 13 reviewed Swiss authority pages. The starter coverage spans five federal, four cantonal, and four local or regional sources; it is not complete Swiss coverage.

## Run

Install dependencies with `uv sync --all-extras --dev`, then start the stdio server:

```sh
uv run python -m mcp_boilerplate.main
```

The package includes a database built from fresh crawls. On first use, the server copies it to `~/.swiss-ai-week-mcp/knowledge.sqlite3`. Later starts preserve that writable copy. Set `KNOWLEDGE_DB_PATH` to use another location. Restart your MCP client after changing server code or configuration.

## Retrieve saved knowledge

- `search_knowledge(query, limit=5)` returns relevant passages, source URLs, authority names, crawl times, and any failed-refresh time. The limit must be 1–10.
- `get_source(level, source)` returns the complete saved page and metadata. Levels are `federal`, `cantonal`, and `municipal`; names are in [the approved source list](src/mcp_boilerplate/sources.py).

Search uses OpenAI `text-embedding-3-small` for semantic ranking. Set `OPENAI_API_KEY` in the environment or a local `.env` file for live semantic queries. If the embedding API is unavailable, search returns locally ranked keyword matches with `method: "keyword_fallback"`. The key is never stored in SQLite. Saved pages retain their source language.

## Refresh sources

Set both `CRAWLORA_API_KEY` and `OPENAI_API_KEY` before refreshing. The three `crawl_*_sources(source=None)` MCP tools refresh one approved source by name or every source at that authority level. They accept no pasted URLs. HTML and JSON normally use Crawlora, with direct retrieval of an approved URL if Crawlora is unavailable; PDFs are downloaded and text-extracted locally. A refresh must return successful content, the expected approved URL, and a source-specific topic phrase. Only then are its page and passages replaced. A failure preserves the previous version and records its time.

The shipped seed contains all 13 sources. MCP crawl tools update the writable local database; they do not change the packaged seed or import the older JSON snapshots. The `scuol_waste` entry uses the responsible regional authority linked by Scuol, since Scuol's own page blocks direct retrieval.

## Housing and driving licence facts

These tools read `var/swissproject.sqlite3`, which is not in Git. Build it from the reviewed data in `data/` before starting the server:

```sh
uv run python scripts/import_housing.py
uv run python scripts/import_driving_licence.py
```

- `swiss_reference_interest_rate(as_of=None, language="it")` returns the BWO mortgage reference rate publication in force on `as_of`. It does not answer dates before 2 September 2026 or from the next announced publication on.
- `swiss_housing_info(question=None, language="it", topic=None, limit=5)` returns BWO renting guidance (rent adjustments, deposit, termination, defects and more) in Italian, German, French or Romansh. Romansh covers the eight guide topics only. Each result includes a verbatim passage, source URL, locator and conditions.
- `get_driving_licence_exchange_info(canton="CH", fact_type="all")` returns documented fees, deadlines and requirements for exchanging a foreign licence. `CH` returns federal rules; a canton code adds cantonal facts. A missing fee or requirement means unknown, not free or waived.

Architecture, data model and test questions: [docs/housing_and_driving_licence.md](docs/housing_and_driving_licence.md). Source data: `data/housing_knowledge.json` and `data/driving_licence/`. Run `uv run python scripts/import_housing.py --verify-sources` to refetch the BWO sources and check every housing passage. Set `HOUSING_DB_PATH` or `DRIVING_LICENCE_DB_PATH` when the database is elsewhere.

Run `uv run pytest -q` for local checks. Credentials belong in local environment variables or `.env`, never in the repository.

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
