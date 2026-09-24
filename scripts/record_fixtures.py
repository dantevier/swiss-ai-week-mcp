#!/usr/bin/env python3
"""Record raw upstream HTTP/SPARQL responses as test fixtures.

Idempotent: re-running overwrites the fixture files with a fresh capture and
only appends a PROVENANCE.md entry for a fixture that isn't already recorded
there (matched by filename), so repeated runs don't pile up duplicate notes.

Usage:
    uv run python scripts/record_fixtures.py lindas
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path

import httpx

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
PROVENANCE_PATH = FIXTURES_DIR / "PROVENANCE.md"
RECORD_DATE = "2026-09-24"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _append_provenance(entries: list[str]) -> None:
    """Replace any stale entry for each fixture (by filename) and append the
    fresh one, so re-running after a query-shape change updates the recorded
    query text and sha256 instead of leaving a stale duplicate or skipping
    the update entirely.
    """
    import re as _re

    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    existing = PROVENANCE_PATH.read_text(encoding="utf-8") if PROVENANCE_PATH.exists() else ""
    if not existing:
        existing = (
            "# Fixture provenance\n\n"
            "Raw upstream responses recorded for tests. Source URL, query/params, "
            "recording date, sha256 of the recorded file, and a note on personal "
            "data for every fixture. No personal data is recorded: Zefix carries "
            "only organisation-level register facts.\n"
        )
    for entry in entries:
        filename = entry.splitlines()[0].split("`")[1]
        # Drop a prior "- `filename` ... (until the next blank line)" block, if any.
        existing = _re.sub(
            rf"(?ms)^- `{_re.escape(filename)}`.*?(?:\n\n|\Z)",
            "",
            existing,
        )
    with PROVENANCE_PATH.open("w", encoding="utf-8") as f:
        f.write(existing.rstrip("\n") + "\n\n" + "\n".join(entries) + "\n")


async def record_lindas() -> None:
    # Imported lazily so `--help`-style misuse doesn't require the package
    # to be importable in every environment that might run this script.
    from mcp_boilerplate.config.settings import settings
    from mcp_boilerplate.zefix.sources import lindas

    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    entries: list[str] = []

    async def record(query: str, filename: str, note: str) -> None:
        path = FIXTURES_DIR / filename
        # A generous timeout: negative name searches on this endpoint have no
        # supporting index and can take ~19s for a true zero-hit scan
        # (measured live 2026-09-24 for "zzzzqqqq"), well past the
        # production lindas_timeout_s budget but fine for one-off recording.
        async with httpx.AsyncClient(
            timeout=45.0,
            headers={"Accept": "application/sparql-results+json", "User-Agent": settings.user_agent},
        ) as client:
            resp = await client.post(settings.lindas_endpoint, data={"query": query})
            resp.raise_for_status()
            body = resp.text
        path.write_text(body, encoding="utf-8")
        digest = _sha256(path)
        flat_query = " ".join(query.split())
        entries.append(
            f"- `{filename}`\n"
            f"  - source: `POST {settings.lindas_endpoint}`\n"
            f"  - query: `{flat_query}`\n"
            f"  - recorded: {RECORD_DATE}\n"
            f"  - sha256: `{digest}`\n"
            f"  - personal data: {note}\n"
        )
        print(f"wrote {path} ({len(body)} bytes)")

    uid_query = lindas._find_by_uid_query(lindas.escape_literal("CHE101654423"))
    await record(uid_query, "lindas_uid_hit.json", "none - one active company's public register facts (UID CHE101654423)")

    # search_by_name's stage 1 (legalName STRSTARTS) - representative of the
    # staged search pipeline's prefix-scan queries.
    prefix_query = lindas._search_prefix_query(
        lindas.escape_literal("swisscom"), "STRSTARTS", "schema:legalName", None, 10
    )
    await record(prefix_query, "lindas_search_prefix.json", "none - company/organisation facts only, no natural persons")

    empty_query = lindas._search_prefix_query(
        lindas.escape_literal("zzzzqqqq"), "STRSTARTS", "schema:legalName", None, 10
    )
    await record(empty_query, "lindas_search_empty.json", "none - empty result set")

    dm_query = lindas._dataset_modified_query()
    await record(dm_query, "lindas_dataset_modified.json", "none - dataset-level metadata only")

    _append_provenance(entries)


SOURCES = {"lindas": record_lindas}


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in SOURCES:
        print(f"usage: uv run python scripts/record_fixtures.py <{'|'.join(SOURCES)}>", file=sys.stderr)
        raise SystemExit(1)
    asyncio.run(SOURCES[sys.argv[1]]())


if __name__ == "__main__":
    main()
