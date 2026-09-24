#!/usr/bin/env python3
"""Query the local Swiss public-sector knowledge database.

Examples:

    python scripts/query_knowledge.py stats
    python scripts/query_knowledge.py place Lugano
    python scripts/query_knowledge.py place Bagnes
    python scripts/query_knowledge.py premium Lugano --age adult --deductible 2500
    python scripts/query_knowledge.py fact vat-standard-rate-de

The database is opened read-only. This command never accesses the network.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "swiss_public_data.sqlite"
AGE_CLASSES = {
    "child": "AKL-KIN",
    "young-adult": "AKL-JUG",
    "adult": "AKL-ERW",
}


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def connect(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise SystemExit(
            f"database not found: {path}\n"
            "Build it with: python scripts/build_knowledge_db.py"
        )
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def emit(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def places(connection: sqlite3.Connection, name: str) -> list[dict]:
    rows = connection.execute(
        """
        SELECT
            a.alias AS matched_name,
            a.alias_type,
            a.mutation_date,
            c.bfs_code,
            c.name,
            c.canton,
            c.language_region,
            c.premium_region,
            c.premium_region_basis
        FROM place_aliases AS a
        JOIN communes AS c ON c.bfs_code = a.bfs_code
        WHERE a.normalized_alias = ?
        ORDER BY a.alias_type, c.canton, c.name
        """,
        (normalized(name),),
    ).fetchall()
    return [dict(row) for row in rows]


def command_stats(connection: sqlite3.Connection) -> None:
    tables = (
        "sources",
        "cantons",
        "communes",
        "place_aliases",
        "municipality_mutations",
        "premium_offers",
        "premium_catchments",
        "grounded_facts",
    )
    counts = {
        table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in tables
    }
    metadata = dict(connection.execute("SELECT key, value FROM metadata"))
    emit({"metadata": metadata, "rows": counts})


def command_place(connection: sqlite3.Connection, name: str) -> None:
    matches = places(connection, name)
    if not matches:
        emit({"state": "not_found", "query": name, "matches": []})
        return
    emit(
        {
            "state": "ambiguous" if len(matches) > 1 else "found",
            "query": name,
            "matches": matches,
        }
    )


def command_premium(connection: sqlite3.Connection, args: argparse.Namespace) -> None:
    matches = places(connection, args.place)
    unique = {(row["bfs_code"], row["name"]): row for row in matches}
    if not unique:
        emit({"state": "place_not_found", "place": args.place})
        return
    if len(unique) != 1:
        emit(
            {
                "state": "need_info",
                "reason": "place name matches more than one municipality",
                "matches": list(unique.values()),
            }
        )
        return
    place = next(iter(unique.values()))
    conditions = [
        "canton = ?",
        "premium_region = ?",
        "business_year = ?",
        "age_class = ?",
        "deductible_chf = ?",
        "accident_included = ?",
        "is_offered_in_region = 1",
    ]
    parameters: list[object] = [
        place["canton"],
        place["premium_region"],
        args.year,
        AGE_CLASSES[args.age],
        args.deductible,
        int(args.accident),
    ]
    if args.standard:
        conditions.append("tariff_type = 'TAR-BASE'")
    row = connection.execute(
        f"""
        SELECT
            insurer_id, tariff_code, tariff_type, tariff_name,
            monthly_premium_rappen
        FROM premium_offers
        WHERE {' AND '.join(conditions)}
        ORDER BY monthly_premium_rappen, insurer_id, tariff_code
        LIMIT 1
        """,
        parameters,
    ).fetchone()
    if row is None:
        emit({"state": "not_found", "place": place, "parameters": vars(args)})
        return
    result = dict(row)
    result["monthly_premium_chf"] = result.pop("monthly_premium_rappen") / 100
    emit(
        {
            "state": "answered",
            "place": place,
            "year": args.year,
            "age": args.age,
            "deductible_chf": args.deductible,
            "accident_included": args.accident,
            "standard_model_only": args.standard,
            "cheapest_offer": result,
            "source_ids": [
                "bag_premiums_2026",
                "fedlex_premium_regions_2026",
                "bfs_commune_levels",
            ],
        }
    )


def command_fact(connection: sqlite3.Connection, fact_id: str) -> None:
    row = connection.execute(
        "SELECT * FROM grounded_facts WHERE fact_id = ?", (fact_id,)
    ).fetchone()
    if row is None:
        emit({"state": "not_found", "fact_id": fact_id})
        return
    result = dict(row)
    result["source_domains"] = json.loads(result.pop("source_domains_json"))
    result["checks"] = json.loads(result.pop("checks_json"))
    emit({"state": "answered", "fact": result})


def command_sources(connection: sqlite3.Connection) -> None:
    emit([dict(row) for row in connection.execute("SELECT * FROM sources ORDER BY source_id")])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("stats")
    subparsers.add_parser("sources")
    place_parser = subparsers.add_parser("place")
    place_parser.add_argument("name")
    premium_parser = subparsers.add_parser("premium")
    premium_parser.add_argument("place")
    premium_parser.add_argument("--year", type=int, default=2026)
    premium_parser.add_argument("--age", choices=AGE_CLASSES, default="adult")
    premium_parser.add_argument(
        "--deductible",
        type=int,
        choices=(0, 100, 200, 300, 400, 500, 600, 1000, 1500, 2000, 2500),
        default=2500,
    )
    premium_parser.add_argument("--accident", action="store_true")
    premium_parser.add_argument("--standard", action="store_true")
    fact_parser = subparsers.add_parser("fact")
    fact_parser.add_argument("fact_id")
    args = parser.parse_args()

    with connect(args.db) as connection:
        if args.command == "stats":
            command_stats(connection)
        elif args.command == "sources":
            command_sources(connection)
        elif args.command == "place":
            command_place(connection, args.name)
        elif args.command == "premium":
            command_premium(connection, args)
        elif args.command == "fact":
            command_fact(connection, args.fact_id)
        else:
            parser.error(f"unknown command: {args.command}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
