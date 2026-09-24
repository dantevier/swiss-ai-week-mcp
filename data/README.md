# Offline Swiss places and 2026 premiums

`swiss_places_premiums_2026.sqlite` holds reusable, deterministic lookups for
municipalities and 2026 health-insurance premiums. It is not a dump of all Swiss
public-sector websites. The MCP server and the benchmark can query this file
without network access.

## Included data

The database contains complete snapshots of the selected structured domains:

| Table | Contents | Official source |
|---|---|---|
| `cantons` | all 26 cantons | BFS municipality register |
| `communes` | all 2,110 municipalities on 24 September 2026, language region and 2026 health-insurance premium region | BFS + Fedlex SR 832.106 |
| `place_aliases` | current municipality names and historical names resolvable to today's municipality | BFS |
| `municipality_mutations` | all 519 mutation rows from 1 January 2015 through 24 September 2026 | BFS |
| `premium_offers` | all 217,472 rows of the BAG 2026 Swiss premium file, including children, young adults, adults, every deductible, accident setting and tariff | BAG |
| `premium_catchments` | all 3,939 insurer/tariff/region availability rows | BAG |
| `grounded_facts` | 27 answerable, hand-verified facts from `benchmark/data/qa.jsonl`, with authority, URL, evidence and dates (the questions are not copied) | authority shown per row |
| `sources` | source URLs, retrieval date, validity dates and SHA-256 of every raw structured source | BAG, BFS, Fedlex |

The database deliberately does **not** claim complete Swiss public-sector coverage.
It is complete only for the selected snapshots above. School calendars, public
transport, all legislation and all municipal services are not yet bulk datasets in
this store.

## Build once, query offline

```bash
# First build downloads official sources into .cache/knowledge, then writes SQLite.
python scripts/build_knowledge_db.py

# Rebuild without any network access when the files are already cached.
python scripts/build_knowledge_db.py --offline

# Inspect the database.
python scripts/query_knowledge.py stats
python scripts/query_knowledge.py sources
python scripts/query_knowledge.py place Lugano
python scripts/query_knowledge.py place Bagnes
python scripts/query_knowledge.py premium Lugano --age adult --deductible 2500
python scripts/query_knowledge.py fact vat-standard-rate-de
```

The query command opens SQLite with `mode=ro`. It never accesses the network.
Python's standard library is sufficient.

## Runtime use

Open the database once when the MCP server starts:

```python
from pathlib import Path
import sqlite3

path = Path("data/swiss_places_premiums_2026.sqlite").resolve()
db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
db.row_factory = sqlite3.Row
```

Do not use `benchmark/data/*.jsonl` as the runtime knowledge database. Those files are
test cases. `benchmark/build/generate.py` now reads this SQLite database, ensuring that
evaluation and runtime use the same facts.

## Freshness

- Premiums and premium regions are valid for 2026 and expire on 31 December 2026.
- Municipality data is a dated snapshot (24 September 2026).
- `grounded_facts.valid_until` identifies facts that require scheduled re-verification.
- Refreshing is a build/deployment operation, never part of answering a user request.

Raw downloads remain in `.cache/knowledge/` and are intentionally not committed. The
database records each raw file's SHA-256 in `sources`, so a build can be audited.
`swiss_places_premiums_2026.sha256` contains the checksum of the final database artifact.
