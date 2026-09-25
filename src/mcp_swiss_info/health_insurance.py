"""Offline lookup of 2026 health insurance premiums from the exported CSV."""

import csv
from functools import lru_cache
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "kvg_minimum_premiums_2026.csv"
FRANCHISES = {300, 500, 1000, 1500, 2000, 2500}


@lru_cache(maxsize=1)
def _premiums(path: Path) -> dict[tuple[str, int, int], dict[str, dict[str, str]]]:
    """Load the CSV once, keyed by age group, Swiss BFS municipality code, franchise."""
    index: dict[tuple[str, int, int], dict[str, dict[str, str]]] = {}
    with path.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            if row["year"] != "2026":
                continue
            key = (row["age_group"], int(row["bfs_number"]), int(row["deductible_chf"]))
            index.setdefault(key, {})[row["accident_cover"]] = row
    return index


def _lookup(age: int, municipality_code: int, franchise: int, path: Path) -> dict:
    """Read a 2026 premium from the injected CSV and validate the lookup."""
    if age < 19:
        return {"status": "invalid_input", "message": "Only ages 19 and older are in this CSV."}
    if franchise not in FRANCHISES:
        return {
            "status": "invalid_input",
            "message": "Unsupported franchise; use 300, 500, 1000, 1500, 2000 or 2500.",
        }
    if municipality_code <= 0:
        return {
            "status": "invalid_input",
            "message": "municipality_code must be a positive Swiss BFS number, not a postal code.",
        }

    group = "young_19_25" if age <= 25 else "adult_26_plus"
    try:
        options = _premiums(path).get((group, municipality_code, franchise))
    except OSError:
        return {"status": "source_unavailable", "message": "The 2026 premium CSV is unavailable."}
    if not options:
        return {
            "status": "not_found",
            "message": "Swiss BFS municipality code not found in the 2026 CSV (postal codes are not supported).",
        }

    first = next(iter(options.values()))
    results = []
    for cover in ("excluded", "included"):
        row = options.get(cover)
        if row and row["minimum_premium"]:
            results.append(
                {
                    "accident_cover": cover,
                    "minimum_premium": row["minimum_premium"],
                    "insurer": row["best_insurer"],
                    "model": row["best_model"],
                    "source_url": row["source_url"],
                }
            )

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


class HealthInsurance:
    """Premium lookups with an injectable CSV location."""

    def __init__(self, csv_path: Path):
        self.csv_path = csv_path

    def premiums(self, age: int, municipality_code: int, franchise: int) -> dict:
        return _lookup(age, municipality_code, franchise, self.csv_path)
