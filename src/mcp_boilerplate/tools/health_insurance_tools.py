"""Offline lookup of 2026 health insurance premiums from the exported CSV."""

import csv
from functools import lru_cache
from pathlib import Path

from ..server import mcp

CSV_PATH = Path(__file__).resolve().parents[3] / "data" / "kvg_minimum_premiums_2026.csv"
FRANCHISES = {300, 500, 1000, 1500, 2000, 2500}


@lru_cache(maxsize=1)
def _premiums() -> dict[tuple[str, int, int], dict[str, dict[str, str]]]:
    """Load the CSV once, keyed by age group, Swiss BFS municipality code, franchise."""
    index: dict[tuple[str, int, int], dict[str, dict[str, str]]] = {}
    with CSV_PATH.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            if row["year"] != "2026":
                continue
            key = (row["age_group"], int(row["bfs_number"]), int(row["deductible_chf"]))
            index.setdefault(key, {})[row["accident_cover"]] = row
    return index


@mcp.tool
def swiss_health_insurance_premiums(
    age: int, municipality_code: int, franchise: int
) -> dict:
    """Look up 2026 Swiss basic health insurance minimum premiums.

    Premium reference: Priminfo (https://www.priminfo.admin.ch/de/praemien).
    Values were extracted from the KVG26 mapper into the local CSV, not fetched
    directly from Priminfo. Valid ONLY for 2026; INVALID for 2027 and later.
    age: completed years (19–25 young, 26+ adult); municipality_code: Swiss
    BFS municipality number, NOT a postal code/PLZ/CAP; franchise: annual
    deductible in CHF (300, 500, 1000, 1500, 2000 or 2500).
    Returns both with-accident and without-accident premium options.
    """
    if age < 19:
        return {"status": "invalid_input", "message": "Only ages 19 and older are in this CSV."}
    if franchise not in FRANCHISES:
        return {"status": "invalid_input", "message": "Unsupported franchise; use 300, 500, 1000, 1500, 2000 or 2500."}
    if municipality_code <= 0:
        return {"status": "invalid_input", "message": "municipality_code must be a positive Swiss BFS number, not a postal code."}

    group = "young_19_25" if age <= 25 else "adult_26_plus"
    try:
        options = _premiums().get((group, municipality_code, franchise))
    except OSError:
        return {"status": "source_unavailable", "message": "The 2026 premium CSV is unavailable."}
    if not options:
        return {"status": "not_found", "message": "Swiss BFS municipality code not found in the 2026 CSV (postal codes are not supported)."}

    first = next(iter(options.values()))
    results = []
    for cover in ("excluded", "included"):
        row = options.get(cover)
        if row and row["minimum_premium"]:
            results.append({
                "accident_cover": cover,
                "minimum_premium": row["minimum_premium"],
                "insurer": row["best_insurer"],
                "model": row["best_model"],
                "source_url": row["source_url"],
            })

    return {
        "status": "answered" if results else "no_data",
        "year": 2026,
        "municipality": first["municipality"],
        "municipality_code": municipality_code,
        "age_group": group,
        "franchise_chf": franchise,
        "premiums": results,
        "official_reference": "https://www.priminfo.admin.ch/de/praemien",
        "message": "2026 only; not valid for 2027. Amounts are as shown on the source map.",
    }
