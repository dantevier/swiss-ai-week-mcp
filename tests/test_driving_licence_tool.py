"""Behavior of the SQLite-backed driving licence exchange tool, on a DB built from the seed."""

import asyncio
import importlib.util
from pathlib import Path

import pytest

from src.mcp_swiss_info.config.settings import settings
from src.mcp_swiss_info.server import mcp
from src.mcp_swiss_info.tools.driving_licence_tools import get_driving_licence_exchange_info

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "import_driving_licence", ROOT / "scripts" / "import_driving_licence.py"
)
import_driving_licence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(import_driving_licence)


@pytest.fixture(autouse=True)
def driving_licence_db(tmp_path, monkeypatch):
    database = tmp_path / "driving_licence.sqlite3"
    import_driving_licence.import_rows(database)
    monkeypatch.setattr(settings, "driving_licence_db_path", str(database))


def _facts(result: dict) -> dict[str, dict]:
    return {fact["fact_key"]: fact for fact in result["facts"]}


def test_tool_is_registered() -> None:
    tool = asyncio.run(mcp.get_tool("get_driving_licence_exchange_info"))
    assert "driving licence" in tool.description
    assert "A missing fact does not mean that a fee" in tool.description


def test_federal_rules_only_for_ch() -> None:
    result = get_driving_licence_exchange_info("CH")
    assert result["status"] == "answered"
    assert {fact["rule_jurisdiction"] for fact in result["facts"]} == {"CH"}
    deadline = _facts(result)["exchange_after_residence"]
    assert (deadline["period_value"], deadline["period_unit"], deadline["period_anchor"]) == (12, "months", "residence_start")
    assert deadline["source_url"].startswith("https://")


def test_canton_returns_federal_and_cantonal_facts() -> None:
    result = get_driving_licence_exchange_info("gr")
    assert result["jurisdiction"] == "GR"
    assert {fact["rule_jurisdiction"] for fact in result["facts"]} == {"CH", "GR"}
    fee = _facts(result)["exchange"]
    assert (fee["amount_min_chf"], fee["amount_max_chf"], fee["fee_model"]) == ("80.00", "80.00", "bundle")


def test_fee_ranges_components_and_conversions() -> None:
    zh = _facts(get_driving_licence_exchange_info("ZH", "fee"))
    assert zh["exchange_application_review"]["amount_min_chf"] == "50.00"
    assert zh["control_drive_light"]["fee_model"] == "component"
    vd = _facts(get_driving_licence_exchange_info("VD", "fee"))
    assert (vd["control_drive"]["amount_min_chf"], vd["control_drive"]["amount_max_chf"]) == ("130.00", "190.00")
    ju = _facts(get_driving_licence_exchange_info("JU", "fee"))
    assert ju["exchange_without_exam"]["amount_min_chf"] == "225.75"


def test_fact_type_filter_and_conditions() -> None:
    result = get_driving_licence_exchange_info("GR", "requirement")
    assert {fact["fact_type"] for fact in result["facts"]} == {"requirement"}
    assert any(fact["conditions"] for fact in result["facts"])
    assert "Missing facts mean unknown" in result["interpretation"]
    assert get_driving_licence_exchange_info("CH", "fee")["status"] == "no_data"


def test_invalid_input_and_missing_database(monkeypatch, tmp_path) -> None:
    assert get_driving_licence_exchange_info("Zurich")["status"] == "invalid_input"
    assert get_driving_licence_exchange_info("XX")["status"] == "invalid_input"
    assert get_driving_licence_exchange_info("ZH", "cost")["status"] == "invalid_input"
    monkeypatch.setattr(settings, "driving_licence_db_path", str(tmp_path / "missing.sqlite3"))
    assert get_driving_licence_exchange_info("ZH")["status"] == "source_unavailable"
