"""Offline checks for scripts/import_housing.py (no network)."""

import importlib.util
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("import_housing", ROOT / "scripts" / "import_housing.py")
import_housing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(import_housing)

P0_P1_KEYS = {
    "reference_rate:2026-09-01", "reference_rate:method", "rent_adjustment:quarter_point",
    "rent_adjustment:large_change", "rent_adjustment:contract_basis",
    "rent_adjustment:request_reduction", "rent_adjustment:increase_form",
    "rent_adjustment:other_factors", "rent_adjustment:contest_increase",
    "rent_adjustment:exceptions", "jurisdiction:tenancy", "deposit:residential",
    "handover:incoming", "utilities:advance_settlement", "defects:notification",
    "alterations:permission", "termination:tenant", "termination:landlord", "handover:outgoing",
}
GUIDE_KEYS = {
    "deposit:residential", "handover:incoming", "utilities:advance_settlement", "defects:notification",
    "alterations:permission", "termination:tenant", "termination:landlord", "handover:outgoing",
}
EXPECTED_KEYS = {"it": P0_P1_KEYS, "de": P0_P1_KEYS, "fr": P0_P1_KEYS, "rm": GUIDE_KEYS}


def rows(database: Path, where: str = "is_current = 1") -> list[sqlite3.Row]:
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(f"SELECT * FROM housing_knowledge WHERE {where}").fetchall()


def test_import_rows_values_and_citations(tmp_path):
    database = tmp_path / "housing.sqlite3"
    assert import_housing.import_rows(database) == 65

    current = rows(database)
    for language, keys in EXPECTED_KEYS.items():
        assert {row["item_key"] for row in current if row["language"] == language} == keys
    seed = import_housing.load_seed()
    fetched = {source["url"]: source["fetched_at"] for source in seed["sources"].values()}
    for row in current:
        assert row["source_url"].startswith("https://www.bwo.admin.ch/")
        assert row["source_passage"] and row["source_locator"]
        assert row["scraped_at"] == fetched[row["source_url"]]  # never invented
        assert json.loads(row["conditions_json"])
    # Language variants share the canonical structured facts.
    canonical = {row["item_key"]: row["data_json"] for row in current if row["language"] == "it"}
    assert all(row["data_json"] == canonical[row["item_key"]] for row in current)

    rate = next(row for row in current if (row["item_key"], row["language"]) == ("reference_rate:2026-09-01", "it"))
    assert json.loads(rate["data_json"]) == {
        "reference_rate_bp": 125,
        "average_rate_bp": 131,
        "average_rate_as_of": "2026-06-30",
        "value_unchanged_since": "2025-09-02",
        "next_publication_on": "2026-12-01",
        "official_publication_frequency": "quarterly",
    }
    assert (rate["published_on"], rate["effective_from"], rate["applicability_verified"]) == ("2026-09-01", "2026-09-02", 1)
    assert "1,31 %" in rate["source_passage"] and "2 settembre 2026" in rate["source_passage"]

    deposit = next(row for row in current if (row["item_key"], row["language"]) == ("deposit:residential", "it"))
    assert json.loads(deposit["data_json"])["max_monthly_rents"] == 3
    assert "commerciali" in json.loads(deposit["conditions_json"])["tenancy_type"]


def test_reimport_is_idempotent_and_corrections_add_revision(tmp_path, monkeypatch):
    database = tmp_path / "housing.sqlite3"
    import_housing.import_rows(database)
    import_housing.import_rows(database)
    assert len(rows(database, "1 = 1")) == 65

    seed = import_housing.load_seed()
    seed["records"][0]["summary"] += " (corretto)"
    monkeypatch.setattr(import_housing, "load_seed", lambda: seed)
    import_housing.import_rows(database)

    history = rows(database, "item_key = 'reference_rate:2026-09-01' AND language = 'it' ORDER BY revision")
    assert [(row["revision"], row["is_current"]) for row in history] == [(1, 0), (2, 1)]
    assert len(rows(database)) == 65


def test_variant_must_match_source_language():
    seed = import_housing.load_seed()
    variant = next(record for record in seed["records"] if record["language"] == "de")
    variant["source"] = "S01"
    try:
        import_housing.build_rows(seed)
    except ValueError as error:
        assert "language differs" in str(error)
    else:
        raise AssertionError("mismatched source language accepted")


def test_unverified_source_is_rejected():
    seed = import_housing.load_seed()
    seed["sources"]["S01"]["fetched_at"] = None
    try:
        import_housing.build_rows(seed)
    except ValueError as error:
        assert "never verified" in str(error)
    else:
        raise AssertionError("unverified source accepted")
