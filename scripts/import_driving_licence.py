"""Import driving-licence coverage entries from TOML into the local SQLite DB."""

import argparse
import json
import sqlite3
import tomllib
from contextlib import closing
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "driving_licence" / "driving_licence.toml"
TRANSLATIONS = ROOT / "data" / "driving_licence" / "driving_licence.en.toml"
SCHEMA = (
    ROOT
    / "src"
    / "mcp_boilerplate"
    / "storage"
    / "migrations"
    / "001_driving_licence_sources.sql"
)
FACT_SCHEMA = ROOT / "src" / "mcp_boilerplate" / "storage" / "migrations" / "002_driving_licence_facts.sql"
FACT_SOURCE = ROOT / "data" / "driving_licence" / "driving_licence_facts.json"
DEFAULT_DATABASE = ROOT / "var" / "swissproject.sqlite3"
THEME = "driving_licence_exchange"
COLUMNS = (
    "jurisdiction",
    "subtopic",
    "resolution_level",
    "on_missing_place",
    "authority",
    "authority_level",
    "source_url",
    "landing_url",
    "source_status",
    "validated_at",
    "legal_basis",
    "notes",
)
REQUIRED_COLUMNS = set(COLUMNS) - {"landing_url", "validated_at", "legal_basis"}
FACT_COLUMNS = (
    "fact_key", "fact_type", "description_en", "source_url", "validated_at",
    "amount_min_rappen", "amount_max_rappen", "fee_code", "fee_model",
    "period_value", "period_unit", "period_anchor", "deadline_code",
    "requirement_code", "requirement_kind", "requirement_effect",
)
CONDITION_FIELDS = {
    "category", "category_group", "country_group", "issuing_country", "professional_use",
    "control_drive", "years_since_entry", "regular_driving",
    "licence_age_years", "licence_language", "applicant_status", "theory_test",
    "max_consecutive_abroad_months", "first_application", "licence_acquired_after_entry",
    "has_qualification_certificate", "waive_categories",
}
CONDITION_OPERATORS = {"eq", "gt", "gte", "lt", "lte"}


def load_rows() -> list[dict[str, str | None]]:
    with SOURCE.open("rb") as source_file:
        entries = tomllib.load(source_file)["entry"]
    with TRANSLATIONS.open("rb") as translations_file:
        translated_notes = tomllib.load(translations_file)["translations"]

    if not entries:
        raise ValueError(f"No entries found in {SOURCE}")

    rows: list[dict[str, str | None]] = []
    seen: set[tuple[str, str]] = set()
    used_translations: set[tuple[str, str]] = set()
    for entry in entries:
        if entry.get("theme") != THEME:
            raise ValueError(f"Unexpected theme: {entry.get('theme')!r}")
        missing = sorted(column for column in REQUIRED_COLUMNS if not entry.get(column))
        if missing:
            raise ValueError(f"{entry.get('jurisdiction', '?')}: missing {', '.join(missing)}")
        if entry.get("validated_at"):
            date.fromisoformat(entry["validated_at"])

        key = (entry["jurisdiction"], entry["subtopic"])
        if key in seen:
            raise ValueError(f"Duplicate jurisdiction/subtopic: {key}")
        seen.add(key)
        translation = translated_notes.get(key[0], {}).get(key[1])
        if not translation:
            raise ValueError(f"Missing English notes for {key}")
        used_translations.add(key)
        rows.append(
            {
                column: translation if column == "notes" else entry.get(column)
                for column in COLUMNS
            }
        )

    expected_translations = {
        (jurisdiction, subtopic)
        for jurisdiction, topics in translated_notes.items()
        for subtopic in topics
    }
    if expected_translations != used_translations:
        raise ValueError("English translations do not match the TOML coverage entries")

    return rows


def load_facts(rows: list[dict[str, str | None]]) -> tuple[list[dict], dict[str, list[str]]]:
    seed = json.loads(FACT_SOURCE.read_text(encoding="utf-8"))
    facts = seed["facts"]
    country_groups = seed["country_groups"]
    sources = {(row["jurisdiction"], row["subtopic"]): row for row in rows}
    seen: set[tuple[str, str]] = set()
    for fact in facts:
        unexpected = set(fact) - set(FACT_COLUMNS) - {"jurisdiction", "conditions"}
        if unexpected:
            raise ValueError(f"Unknown fact fields: {sorted(unexpected)}")
        jurisdiction = fact["jurisdiction"]
        subtopic = "deadline_and_exams" if jurisdiction == "CH" else "procedure"
        source = sources.get((jurisdiction, subtopic))
        if source is None:
            raise ValueError(f"No source row for fact {fact['fact_key']}")
        key = (jurisdiction, fact["fact_key"])
        if key in seen:
            raise ValueError(f"Duplicate fact: {key}")
        seen.add(key)
        fact.setdefault("source_url", source["source_url"])
        fact.setdefault("validated_at", source["validated_at"])
        if fact["fact_type"] not in {"fee", "deadline", "requirement"}:
            raise ValueError(f"Invalid fact type: {key}")
        if not fact.get("fact_key") or not fact.get("description_en") or not fact["source_url"].startswith("https://"):
            raise ValueError(f"Missing description or HTTPS source: {key}")
        if fact["fact_type"] == "fee":
            if not all(field in fact for field in ("amount_min_rappen", "amount_max_rappen", "fee_code", "fee_model")):
                raise ValueError(f"Incomplete fee: {key}")
        elif fact["fact_type"] == "deadline":
            if not all(field in fact for field in ("period_value", "period_unit", "period_anchor", "deadline_code")):
                raise ValueError(f"Incomplete deadline: {key}")
        elif not all(field in fact for field in ("requirement_code", "requirement_kind", "requirement_effect")):
            raise ValueError(f"Incomplete requirement: {key}")
        for condition in fact.get("conditions", []):
            if condition["field"] not in CONDITION_FIELDS or condition.get("operator", "eq") not in CONDITION_OPERATORS:
                raise ValueError(f"Invalid condition: {key}: {condition}")
            values = condition["value"] if isinstance(condition["value"], list) else [condition["value"]]
            if not values or any(str(value) == "" for value in values):
                raise ValueError(f"Empty condition: {key}")
            if condition.get("operator", "eq") != "eq" and (len(values) != 1 or not str(values[0]).isdigit()):
                raise ValueError(f"Comparison needs one numeric value: {key}")
    for group_code, members in country_groups.items():
        if not members or len(set(members)) != len(members) or any(len(member) != 2 or not member.isupper() for member in members):
            raise ValueError(f"Invalid country group: {group_code}")
    return facts, country_groups


def import_rows(database: Path) -> tuple[int, int]:
    rows = load_rows()
    facts, country_groups = load_facts(rows)
    database.parent.mkdir(parents=True, exist_ok=True)

    column_names = ", ".join(COLUMNS)
    placeholders = ", ".join(f":{column}" for column in COLUMNS)
    updates = ", ".join(
        f"{column} = excluded.{column}"
        for column in COLUMNS
        if column not in {"jurisdiction", "subtopic"}
    )
    statement = (
        f"INSERT INTO driving_licence_sources ({column_names}) "
        f"VALUES ({placeholders}) "
        f"ON CONFLICT(jurisdiction, subtopic) DO UPDATE SET {updates}"
    )

    with closing(sqlite3.connect(database)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        connection.executescript(FACT_SCHEMA.read_text(encoding="utf-8"))
        with connection:
            connection.executemany(statement, rows)
            connection.execute("DELETE FROM driving_licence_country_groups WHERE origin = 'seed'")
            connection.executemany(
                "INSERT OR IGNORE INTO driving_licence_country_groups "
                "(group_code, country_code) VALUES (?, ?)",
                [(group_code, country_code) for group_code, members in country_groups.items() for country_code in members],
            )
            source_ids = {
                jurisdiction: source_id
                for source_id, jurisdiction in connection.execute(
                    "SELECT id, jurisdiction FROM driving_licence_sources"
                )
            }
            existing = {
                (source_id, fact_key): (fact_id, origin)
                for fact_id, source_id, fact_key, origin in connection.execute(
                    "SELECT id, source_id, fact_key, origin FROM driving_licence_facts"
                )
            }
            imported_keys: set[tuple[int, str]] = set()
            for fact in facts:
                source_id = source_ids[fact["jurisdiction"]]
                key = (source_id, fact["fact_key"])
                imported_keys.add(key)
                values = {column: fact.get(column) for column in FACT_COLUMNS}
                values["source_id"] = source_id
                if key in existing:
                    fact_id, origin = existing[key]
                    if origin != "seed":
                        raise ValueError(f"Seed fact conflicts with manually entered fact: {key}")
                    assignment = ", ".join(f"{column} = :{column}" for column in FACT_COLUMNS)
                    connection.execute(
                        f"UPDATE driving_licence_facts SET {assignment} WHERE id = :id",
                        {**values, "id": fact_id},
                    )
                    connection.execute(
                        "DELETE FROM driving_licence_fact_conditions WHERE fact_id = ?",
                        (fact_id,),
                    )
                else:
                    names = ("source_id", *FACT_COLUMNS)
                    connection.execute(
                        f"INSERT INTO driving_licence_facts ({', '.join(names)}) "
                        f"VALUES ({', '.join(':' + name for name in names)})",
                        values,
                    )
                    fact_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
                for condition in fact.get("conditions", []):
                    values = condition["value"] if isinstance(condition["value"], list) else [condition["value"]]
                    connection.executemany(
                        "INSERT INTO driving_licence_fact_conditions (fact_id, field, operator, value) "
                        "VALUES (?, ?, ?, ?)",
                        [(fact_id, condition["field"], condition.get("operator", "eq"), str(value)) for value in values],
                    )
            for key, (fact_id, origin) in existing.items():
                if origin == "seed" and key not in imported_keys:
                    connection.execute("DELETE FROM driving_licence_facts WHERE id = ?", (fact_id,))

    return len(rows), len(facts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE,
        help=f"SQLite file (default: {DEFAULT_DATABASE})",
    )
    args = parser.parse_args()
    sources, facts = import_rows(args.database)
    print(f"Imported {sources} sources and {facts} facts into {args.database.resolve()}")


if __name__ == "__main__":
    main()
