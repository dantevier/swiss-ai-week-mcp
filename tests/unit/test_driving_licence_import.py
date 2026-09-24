"""Offline checks for scripts/import_driving_licence.py (no network)."""

import importlib.util
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "import_driving_licence", ROOT / "scripts" / "import_driving_licence.py"
)
import_driving_licence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(import_driving_licence)

CANTONS = {
    "AG", "AI", "AR", "BE", "BL", "BS", "FR", "GE", "GL", "GR", "JU", "LU", "NE",
    "NW", "OW", "SG", "SH", "SO", "SZ", "TG", "TI", "UR", "VD", "VS", "ZG", "ZH",
}


def count(database: Path, table: str) -> int:
    with closing(sqlite3.connect(database)) as db:
        return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_import_covers_ch_and_all_cantons(tmp_path):
    database = tmp_path / "dl.sqlite3"
    sources, facts = import_driving_licence.import_rows(database)
    assert (sources, facts) == (27, count(database, "driving_licence_facts"))
    with closing(sqlite3.connect(database)) as db:
        jurisdictions = {row[0] for row in db.execute("SELECT jurisdiction FROM driving_licence_sources")}
        assert jurisdictions == CANTONS | {"CH"}
        # Every source and fact is traceable to an HTTPS URL and a validation date.
        assert not db.execute(
            "SELECT 1 FROM driving_licence_facts WHERE source_url NOT LIKE 'https://%' OR validated_at IS NULL"
        ).fetchone()
        assert not db.execute("SELECT 1 FROM driving_licence_sources WHERE validated_at IS NULL").fetchone()


def test_reimport_is_idempotent_and_keeps_manual_facts(tmp_path):
    database = tmp_path / "dl.sqlite3"
    import_driving_licence.import_rows(database)
    totals = [count(database, table) for table in (
        "driving_licence_sources", "driving_licence_facts",
        "driving_licence_fact_conditions", "driving_licence_country_groups",
    )]
    with closing(sqlite3.connect(database)) as db, db:
        db.execute(
            "INSERT INTO driving_licence_facts (source_id, fact_key, fact_type, description_en, source_url, "
            "origin, requirement_code, requirement_kind, requirement_effect) "
            "SELECT id, 'manual_note', 'requirement', 'Manual entry.', 'https://example.org', 'manual', "
            "'manual_note', 'document', 'recommended' FROM driving_licence_sources WHERE jurisdiction = 'ZH'"
        )
    import_driving_licence.import_rows(database)
    assert count(database, "driving_licence_facts") == totals[1] + 1
    assert [count(database, table) for table in (
        "driving_licence_sources", "driving_licence_fact_conditions", "driving_licence_country_groups",
    )] == [totals[0], totals[2], totals[3]]


def test_invalid_fact_is_rejected(tmp_path, monkeypatch):
    seed = json.loads(import_driving_licence.FACT_SOURCE.read_text(encoding="utf-8"))
    seed["facts"][0]["fact_type"] = "price"
    broken = tmp_path / "facts.json"
    broken.write_text(json.dumps(seed), encoding="utf-8")
    monkeypatch.setattr(import_driving_licence, "FACT_SOURCE", broken)
    with pytest.raises(ValueError, match="Invalid fact type"):
        import_driving_licence.load_facts(import_driving_licence.load_rows())
