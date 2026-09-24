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
