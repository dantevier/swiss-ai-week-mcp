# Swiss AI Week MCP

Three MCP tools crawl a reviewed starter set of Swiss public sources: `crawl_federal_sources`, `crawl_cantonal_sources`, and `crawl_municipal_sources`.

## Run

```sh
uv sync --all-extras --dev
```

Set `CRAWLORA_API_KEY` in your environment or a local `.env` file, then run `uv run python -m mcp_boilerplate.main`. Restart Codex after changing this MCP server's code or configuration.

## Crawl

Each tool accepts at most one of `source` or `url`:

- `source` is a registered short name, or `all`. Omitting both arguments also crawls all sources for that level.
- `url` is a pasted HTTPS webpage or PDF address on an official host already registered for that level. Other hosts are rejected. Pasted URLs are returned directly and are not saved as snapshots.

Registered sources are in [`src/mcp_boilerplate/sources.py`](src/mcp_boilerplate/sources.py). Federal names: `health_insurance_premiums`, `premium_regions_2026`, `reference_interest_rate`, `reference_interest_rate_law`, `foreign_driving_licence_law`. Cantonal names: `gr_school_holidays_2026_27`, `vd_school_holidays_2023_31`, `ti_school_holidays_2026_27`, `zh_school_holidays`. Municipal names: `scuol_waste`, `bern_arrival`, `st_gallen_school_holidays`, `lausanne_arrival`.

Named crawls save JSON snapshots under `data/<level>_sources/`. HTML pages use Crawlora; PDFs are downloaded and text-extracted locally. A single-source crawl returns its extracted text; an `all` crawl returns a per-source summary. These are starter sets, not complete coverage of every canton or municipality.

Run `uv run pytest -q` to check the crawler and MCP tool registration.
