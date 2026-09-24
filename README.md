# Swiss AI Week MCP

A Python/FastMCP server with a local SQLite knowledge base of 13 reviewed Swiss authority pages. The starter coverage spans five federal, four cantonal, and four local or regional sources; it is not complete Swiss coverage.

## Install

Requires [uv](https://docs.astral.sh/uv/). From a clone of this repo:

```sh
uv run python scripts/setup.py      # or: make setup
```

It installs dependencies, asks for the two API keys (optional, saved to the git-ignored `.env`), and registers the server in whichever of Claude Code, Codex and opencode it finds. Restart the harness afterwards. Use `--yes` to skip prompts.

Manual equivalent for Claude Code: `claude mcp add --scope user mcp-swiss-info -- uv run --directory <path-to-this-repo> python -m mcp_boilerplate.main`.

## Check data freshness

Ask the assistant "how fresh is your data?" (tool `source_status`), or "open the dashboard" (tool `open_dashboard`) for a local page at http://127.0.0.1:8765 with each source's last refresh, failures, and a Refresh button. Outside a harness: `make dashboard`. Sources older than 30 days show as outdated (`STALE_AFTER_DAYS` to change).

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
