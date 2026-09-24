#!/usr/bin/env python3
"""Build the offline Swiss places and 2026 premiums database.

Network access is build-time only. Runtime code should open
``data/swiss_places_premiums_2026.sqlite`` read-only and never fetch these sources again.

The selected reusable datasets are:

* all current Swiss municipalities and cantons from the BFS municipality register;
* municipality mutations since 2015, including historical place aliases;
* municipality-to-premium-region assignments from SR 832.106;
* the complete BAG 2026 Swiss health-insurance premium table and catchments;
* grounded facts already verified in benchmark/data/qa.jsonl.

Standard library only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import re
import sqlite3
import unicodedata
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = ROOT / ".cache" / "knowledge"
DEFAULT_OUTPUT = ROOT / "data" / "swiss_places_premiums_2026.sqlite"
QA_PATH = ROOT / "benchmark" / "data" / "qa.jsonl"
USER_AGENT = "swiss-grounding-mcp/0.1 (Swiss AI Weeks; offline data builder)"
REGISTER_DATE = "24-09-2026"
BUILD_DATE = "2026-09-24"

SOURCES = {
    "bag_premiums_2026": {
        "authority": "Federal Office of Public Health (BAG)",
        "title": "Health insurance premiums 2026 archive",
        "url": (
            "https://opendata.bagnet.ch/?r=/download&path="
            "L1ByYWVtaWVuL0FyY2hpdl9QcmFlbWllbl8yMDI2LnppcA%3D%3D"
        ),
        "landing_url": "https://opendata.swiss/en/dataset/health-insurance-premiums",
        "cache_name": "premiums.zip",
        "effective_from": "2026-01-01",
        "valid_until": "2026-12-31",
    },
    "fedlex_premium_regions_2026": {
        "authority": "Federal Department of Home Affairs / Fedlex",
        "title": "SR 832.106 Annex 1, premium regions, consolidated 2026-01-01",
        "url": (
            "https://www.fedlex.admin.ch/filestore/fedlex.data.admin.ch/eli/"
            "cc/2022/184/20260101/de/html/"
            "fedlex-data-admin-ch-eli-cc-2022-184-20260101-de-html.html"
        ),
        "landing_url": "https://www.fedlex.admin.ch/eli/cc/2022/184/de",
        "cache_name": "regions.html",
        "effective_from": "2026-01-01",
        "valid_until": "2026-12-31",
    },
    "bfs_commune_snapshot": {
        "authority": "Federal Statistical Office (BFS)",
        "title": f"Official municipality register snapshot, {REGISTER_DATE}",
        "url": (
            "https://www.agvchapp.bfs.admin.ch/api/communes/"
            f"snapshot?date={REGISTER_DATE}"
        ),
        "landing_url": "https://www.agvchapp.bfs.admin.ch/en/communes/query",
        "cache_name": "communes.csv",
        "effective_from": "2026-09-24",
        "valid_until": "",
    },
    "bfs_commune_levels": {
        "authority": "Federal Statistical Office (BFS)",
        "title": f"Official municipality levels, {REGISTER_DATE}",
        "url": (
            "https://www.agvchapp.bfs.admin.ch/api/communes/"
            f"levels?date={REGISTER_DATE}"
        ),
        "landing_url": "https://www.agvchapp.bfs.admin.ch/en/communes/query",
        "cache_name": "levels.csv",
        "effective_from": "2026-09-24",
        "valid_until": "",
    },
    "bfs_commune_mutations": {
        "authority": "Federal Statistical Office (BFS)",
        "title": "Official municipality mutations, 2015-01-01 to 2026-09-24",
        "url": (
            "https://www.agvchapp.bfs.admin.ch/api/communes/mutations?"
            "startPeriod=01-01-2015&endPeriod=24-09-2026&"
            "includeTerritoryExchange=false"
        ),
        "landing_url": "https://www.agvchapp.bfs.admin.ch/en/communes/mutations",
        "cache_name": "mutations.csv",
        "effective_from": "2015-01-01",
        "valid_until": "",
    },
}

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE sources (
    source_id TEXT PRIMARY KEY,
    authority TEXT NOT NULL,
    title TEXT NOT NULL,
    source_url TEXT NOT NULL,
    landing_url TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    effective_from TEXT,
    valid_until TEXT,
    sha256 TEXT NOT NULL
);

CREATE TABLE cantons (
    code TEXT PRIMARY KEY,
    bfs_code INTEGER NOT NULL UNIQUE,
    name TEXT NOT NULL
);

CREATE TABLE communes (
    bfs_code INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    canton TEXT NOT NULL REFERENCES cantons(code),
    language_region INTEGER,
    premium_region INTEGER NOT NULL,
    premium_region_basis TEXT NOT NULL,
    register_date TEXT NOT NULL,
    source_order INTEGER NOT NULL UNIQUE
);

CREATE TABLE place_aliases (
    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    bfs_code INTEGER NOT NULL REFERENCES communes(bfs_code),
    alias_type TEXT NOT NULL CHECK(alias_type IN ('current', 'historical')),
    mutation_date TEXT,
    PRIMARY KEY (normalized_alias, bfs_code, alias_type)
);

CREATE TABLE municipality_mutations (
    mutation_number INTEGER NOT NULL,
    mutation_date TEXT NOT NULL,
    initial_historical_code INTEGER NOT NULL,
    initial_bfs_code INTEGER NOT NULL,
    initial_name TEXT NOT NULL,
    initial_parent_name TEXT,
    initial_step INTEGER,
    terminal_historical_code INTEGER NOT NULL,
    terminal_bfs_code INTEGER NOT NULL,
    terminal_name TEXT NOT NULL,
    terminal_parent_name TEXT,
    terminal_step INTEGER,
    PRIMARY KEY (mutation_number, initial_historical_code, terminal_historical_code)
);

CREATE TABLE premium_offers (
    id INTEGER PRIMARY KEY,
    insurer_id INTEGER NOT NULL,
    canton TEXT NOT NULL,
    sovereign_area TEXT NOT NULL,
    business_year INTEGER NOT NULL,
    survey_year INTEGER NOT NULL,
    premium_region INTEGER NOT NULL,
    age_class TEXT NOT NULL,
    accident_included INTEGER NOT NULL CHECK(accident_included IN (0, 1)),
    tariff_code TEXT NOT NULL,
    tariff_type TEXT NOT NULL,
    age_subgroup TEXT,
    franchise_level TEXT NOT NULL,
    deductible_chf INTEGER NOT NULL,
    monthly_premium_rappen INTEGER NOT NULL,
    is_base_p INTEGER NOT NULL,
    is_base_f INTEGER NOT NULL,
    tariff_name TEXT,
    is_offered_in_region INTEGER NOT NULL CHECK(is_offered_in_region IN (0, 1))
);

CREATE TABLE premium_catchments (
    insurer_id INTEGER NOT NULL,
    canton TEXT NOT NULL,
    sovereign_area TEXT NOT NULL,
    business_year INTEGER NOT NULL,
    survey_year INTEGER NOT NULL,
    premium_region INTEGER NOT NULL,
    tariff_code TEXT NOT NULL,
    tariff_type TEXT NOT NULL,
    hmo_id TEXT,
    restricted INTEGER NOT NULL CHECK(restricted IN (0, 1)),
    municipality_bfs_codes TEXT,
    PRIMARY KEY (
        insurer_id, canton, premium_region, tariff_code, tariff_type,
        hmo_id, municipality_bfs_codes
    )
);

CREATE TABLE grounded_facts (
    fact_id TEXT PRIMARY KEY,
    topic_area INTEGER NOT NULL,
    topic TEXT NOT NULL,
    jurisdiction_level TEXT NOT NULL,
    expected_behavior TEXT NOT NULL,
    reference_answer TEXT NOT NULL,
    authority TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_domains_json TEXT NOT NULL,
    evidence TEXT NOT NULL,
    verified_at TEXT NOT NULL,
    verified_by TEXT NOT NULL,
    valid_until TEXT,
    checks_json TEXT NOT NULL
);

CREATE INDEX idx_communes_normalized_name ON communes(normalized_name);
CREATE INDEX idx_aliases_name ON place_aliases(normalized_alias);
CREATE INDEX idx_aliases_bfs ON place_aliases(bfs_code);
CREATE INDEX idx_mutations_initial_name ON municipality_mutations(initial_name);
CREATE INDEX idx_mutations_terminal_code ON municipality_mutations(terminal_bfs_code);
CREATE INDEX idx_premium_lookup ON premium_offers(
    canton, premium_region, business_year, age_class, deductible_chf,
    accident_included, tariff_type, is_offered_in_region, monthly_premium_rappen
);
CREATE INDEX idx_premium_insurer ON premium_offers(insurer_id);
CREATE INDEX idx_facts_topic ON grounded_facts(topic_area, topic);
"""


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def base_commune_name(value: str) -> str:
    return re.sub(r"\s*\([A-Z]{2}\)$", "", value).strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(source: dict[str, str], cache_dir: Path, offline: bool) -> Path:
    target = cache_dir / source["cache_name"]
    if target.exists():
        return target
    if offline:
        raise SystemExit(f"offline build: missing cached source {target}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(source["url"], headers={"User-Agent": USER_AGENT})
    temporary = target.with_suffix(target.suffix + ".part")
    with urllib.request.urlopen(request, timeout=300) as response:
        temporary.write_bytes(response.read())
    temporary.replace(target)
    return target


def csv_file(path: Path, delimiter: str = ",") -> list[dict[str, str]]:
    return list(
        csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig")), delimiter=delimiter)
    )


def csv_from_zip(path: Path, member: str, delimiter: str) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        member_name = next(name for name in archive.namelist() if name.endswith(member))
        text = archive.read(member_name).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text), delimiter=delimiter))


def premium_region_number(value: str) -> int:
    match = re.search(r"(\d+)$", value)
    if not match:
        raise ValueError(f"invalid premium region: {value!r}")
    return int(match.group(1))


def money_rappen(value: str) -> int:
    return int(Decimal(value) * 100)


def parse_fedlex_regions(path: Path) -> dict[int, int]:
    document = path.read_text(encoding="utf-8")
    if "no-script-warning" in document:
        raise SystemExit("Fedlex returned the JavaScript shell, not the consolidated law")
    regions: dict[int, int] = {}
    for row in re.findall(r"<tr>(.*?)</tr>", document, re.S):
        cells = [
            re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", cell))).strip()
            for cell in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        ]
        if len(cells) == 3 and cells[0].isdigit() and cells[2].isdigit():
            regions[int(cells[0])] = int(cells[2])
    if len(regions) < 1400:
        raise SystemExit(f"Fedlex region parse is unexpectedly small: {len(regions)} rows")
    return regions


def resolve_successor(
    mutation: dict[str, str],
    successors: dict[int, dict[str, str]],
    current_codes: set[int],
) -> int | None:
    step = mutation
    seen: set[int] = set()
    while True:
        terminal_code = int(step["TerminalCode"])
        if terminal_code in current_codes:
            return terminal_code
        historical = int(step["TerminalHistoricalCode"])
        if historical in seen or historical not in successors:
            return None
        seen.add(historical)
        step = successors[historical]


def build_database(output: Path, cache_dir: Path, offline: bool) -> dict[str, int]:
    paths = {
        source_id: fetch(source, cache_dir, offline)
        for source_id, source in SOURCES.items()
    }
    premium_rows = csv_from_zip(paths["bag_premiums_2026"], "Prämien_CH.csv", ",")
    catchment_rows = csv_from_zip(
        paths["bag_premiums_2026"], "Einzugsgebiete.csv", ";"
    )
    snapshot_rows = csv_file(paths["bfs_commune_snapshot"])
    level_rows = csv_file(paths["bfs_commune_levels"])
    mutation_rows = csv_file(paths["bfs_commune_mutations"])
    fedlex_regions = parse_fedlex_regions(paths["fedlex_premium_regions_2026"])

    cantons = {
        int(row["BfsCode"]): (row["ShortName"], row["Name"])
        for row in snapshot_rows
        if row["Level"] == "1"
    }
    communes = {
        int(row["BfsCode"]): row
        for row in level_rows
    }
    current_codes = set(communes)

    premium_regions_by_canton: dict[str, set[int]] = defaultdict(set)
    for row in premium_rows:
        premium_regions_by_canton[row["Kanton"]].add(
            premium_region_number(row["Region"])
        )

    old_regions_by_terminal: dict[int, set[int]] = defaultdict(set)
    for row in mutation_rows:
        old_code = int(row["InitialCode"])
        terminal_code = int(row["TerminalCode"])
        if old_code in fedlex_regions:
            old_regions_by_terminal[terminal_code].add(fedlex_regions[old_code])

    region_assignments: dict[int, tuple[int, str]] = {}
    for bfs_code, row in communes.items():
        canton = cantons[int(row["CantonId"])][0]
        available = premium_regions_by_canton[canton]
        if available == {0}:
            region_assignments[bfs_code] = (0, "single-region canton in BAG data")
        elif bfs_code in fedlex_regions:
            region_assignments[bfs_code] = (
                fedlex_regions[bfs_code],
                "SR 832.106 Annex 1",
            )
        elif len(old_regions_by_terminal[bfs_code]) == 1:
            region_assignments[bfs_code] = (
                next(iter(old_regions_by_terminal[bfs_code])),
                "SR 832.106 Art. 3 via predecessor municipality",
            )

    missing_regions = sorted(current_codes - region_assignments.keys())
    if missing_regions:
        details = ", ".join(f"{code} {communes[code]['Name']}" for code in missing_regions)
        raise SystemExit(f"no premium-region assignment for: {details}")

    catchment_keys = {
        (
            int(row["Versicherer"]),
            row["Kanton"],
            premium_region_number(row["Region"]),
            row["Tarif"],
        )
        for row in catchment_rows
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    connection = sqlite3.connect(temporary)
    try:
        connection.executescript(SCHEMA)
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            [
                ("schema_version", "1"),
                ("built_at", BUILD_DATE),
                ("register_date", "2026-09-24"),
                ("runtime_network_required", "false"),
                ("description", "Offline commune register, historical names, and 2026 health-insurance premiums"),
            ],
        )
        for source_id, source in SOURCES.items():
            connection.execute(
                """
                INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    source["authority"],
                    source["title"],
                    source["url"],
                    source["landing_url"],
                    BUILD_DATE,
                    source["effective_from"],
                    source["valid_until"] or None,
                    sha256(paths[source_id]),
                ),
            )

        connection.executemany(
            "INSERT INTO cantons(code, bfs_code, name) VALUES (?, ?, ?)",
            sorted((code, bfs, name) for bfs, (code, name) in cantons.items()),
        )
        commune_records = []
        for source_order, (bfs_code, row) in enumerate(communes.items()):
            canton = cantons[int(row["CantonId"])][0]
            region, basis = region_assignments[bfs_code]
            commune_records.append(
                (
                    bfs_code,
                    row["Name"],
                    normalized(row["Name"]),
                    canton,
                    int(row["SPRGEB2020"]) if row["SPRGEB2020"] else None,
                    region,
                    basis,
                    "2026-09-24",
                    source_order,
                )
            )
        connection.executemany(
            "INSERT INTO communes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            commune_records,
        )
        current_aliases = []
        for bfs, row in communes.items():
            full_name = row["Name"]
            short_name = base_commune_name(full_name)
            names = [full_name] if short_name == full_name else [full_name, short_name]
            current_aliases.extend(
                (name, normalized(name), bfs)
                for name in names
            )
        connection.executemany(
            """
            INSERT INTO place_aliases(
                alias, normalized_alias, bfs_code, alias_type, mutation_date
            ) VALUES (?, ?, ?, 'current', NULL)
            """,
            current_aliases,
        )

        mutation_records = []
        for row in mutation_rows:
            mutation_records.append(
                (
                    int(row["MutationNumber"]),
                    date.fromisoformat(
                        "-".join(reversed(row["MutationDate"].split(".")))
                    ).isoformat(),
                    int(row["InitialHistoricalCode"]),
                    int(row["InitialCode"]),
                    row["InitialName"],
                    row["InitialParentName"],
                    int(row["InitialStep"]) if row["InitialStep"] else None,
                    int(row["TerminalHistoricalCode"]),
                    int(row["TerminalCode"]),
                    row["TerminalName"],
                    row["TerminalParentName"],
                    int(row["TerminalStep"]) if row["TerminalStep"] else None,
                )
            )
        connection.executemany(
            "INSERT INTO municipality_mutations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            mutation_records,
        )

        successors = {
            int(row["InitialHistoricalCode"]): row
            for row in mutation_rows
        }
        historical_aliases: dict[tuple[str, int], tuple[str, str, int, str, str]] = {}
        for row in mutation_rows:
            successor = resolve_successor(row, successors, current_codes)
            if successor is None:
                continue
            key = (normalized(row["InitialName"]), successor)
            historical_aliases[key] = (
                row["InitialName"],
                key[0],
                successor,
                "historical",
                date.fromisoformat(
                    "-".join(reversed(row["MutationDate"].split(".")))
                ).isoformat(),
            )
        connection.executemany(
            """
            INSERT OR IGNORE INTO place_aliases(
                alias, normalized_alias, bfs_code, alias_type, mutation_date
            ) VALUES (?, ?, ?, ?, ?)
            """,
            historical_aliases.values(),
        )

        catchment_records = []
        for row in catchment_rows:
            catchment_records.append(
                (
                    int(row["Versicherer"]),
                    row["Kanton"],
                    row["Hoheitsgebiet"],
                    int(row["Geschäftsjahr"]),
                    int(row["Erhebungsjahr"]),
                    premium_region_number(row["Region"]),
                    row["Tarif"],
                    row["Tariftyp"],
                    row["HMO-ID"],
                    int(row["Eingeschränkt"] == "J"),
                    row["Gemeinden-BFS"],
                )
            )
        connection.executemany(
            "INSERT INTO premium_catchments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            catchment_records,
        )

        premium_records = []
        for row in premium_rows:
            insurer = int(row["Versicherer"])
            region = premium_region_number(row["Region"])
            offered = row["Tariftyp"] == "TAR-BASE" or (
                insurer,
                row["Kanton"],
                region,
                row["Tarif"],
            ) in catchment_keys
            premium_records.append(
                (
                    insurer,
                    row["Kanton"],
                    row["Hoheitsgebiet"],
                    int(row["Geschäftsjahr"]),
                    int(row["Erhebungsjahr"]),
                    region,
                    row["Altersklasse"],
                    int(row["Unfalleinschluss"] == "MIT-UNF"),
                    row["Tarif"],
                    row["Tariftyp"],
                    row["Altersuntergruppe"],
                    row["Franchisestufe"],
                    int(row["Franchise"].removeprefix("FRA-")),
                    money_rappen(row["Prämie"]),
                    int(row["isBaseP"]),
                    int(row["isBaseF"]),
                    row["Tarifbezeichnung"],
                    int(offered),
                )
            )
        connection.executemany(
            """
            INSERT INTO premium_offers(
                insurer_id, canton, sovereign_area, business_year, survey_year,
                premium_region, age_class, accident_included, tariff_code,
                tariff_type, age_subgroup, franchise_level, deductible_chf,
                monthly_premium_rappen, is_base_p, is_base_f, tariff_name,
                is_offered_in_region
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            premium_records,
        )

        fact_count = 0
        if QA_PATH.exists():
            with QA_PATH.open(encoding="utf-8") as stream:
                for line in stream:
                    item = json.loads(line)
                    if item["expected_behavior"] != "answer":
                        continue
                    checks = {
                        "must_include": item["must_include"],
                        "must_not_include": item["must_not_include"],
                    }
                    connection.execute(
                        """
                        INSERT INTO grounded_facts VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                        )
                        """,
                        (
                            item["id"],
                            item["topic_area"],
                            item["topic"],
                            item["level"],
                            item["expected_behavior"],
                            item["reference_answer"],
                            item["authority"],
                            item["source_url"],
                            json.dumps(item["source_domains"], ensure_ascii=False),
                            item["evidence"],
                            item["verified_at"],
                            item["verified_by"],
                            item["valid_until"],
                            json.dumps(checks, ensure_ascii=False),
                        ),
                    )
                    fact_count += 1

        connection.commit()
        alias_count = connection.execute(
            "SELECT count(*) FROM place_aliases"
        ).fetchone()[0]
        connection.execute("ANALYZE")
        connection.execute("VACUUM")
    finally:
        connection.close()
    temporary.replace(output)
    checksum_path = output.with_suffix(".sha256")
    checksum_path.write_text(
        f"{sha256(output)}  {output.name}\n",
        encoding="utf-8",
        newline="\n",  # sha256sum -c rejects CRLF
    )
    return {
        "cantons": len(cantons),
        "communes": len(communes),
        "place_aliases": alias_count,
        "mutations": len(mutation_rows),
        "premium_offers": len(premium_rows),
        "premium_catchments": len(catchment_rows),
        "grounded_facts": fact_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="use cached downloads only; fail instead of accessing the network",
    )
    args = parser.parse_args()
    counts = build_database(args.output, args.cache_dir, args.offline)
    print(f"wrote {args.output} ({args.output.stat().st_size / 1024 / 1024:.1f} MiB)")
    for table, count in counts.items():
        print(f"  {table}: {count:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
