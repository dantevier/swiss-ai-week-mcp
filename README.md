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

Source data: `data/housing_knowledge.json` and `data/driving_licence/`. Run `uv run python scripts/import_housing.py --verify-sources` to refetch the BWO sources and check every housing passage. Set `HOUSING_DB_PATH` or `DRIVING_LICENCE_DB_PATH` when the database is elsewhere.

Run `uv run pytest -q` for local checks. Credentials belong in local environment variables or `.env`, never in the repository.
