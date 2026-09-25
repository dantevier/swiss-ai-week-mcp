"""Behavior of the SQLite-backed BWO/UFAB housing tools, on a DB built from the seed."""

import asyncio
import importlib.util
from pathlib import Path

import pytest

from src.mcp_swiss_info.config.settings import settings
from src.mcp_swiss_info.server import mcp
from src.mcp_swiss_info.tools.housing_tools import (
    swiss_housing_info,
    swiss_reference_interest_rate,
)

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("import_housing", ROOT / "scripts" / "import_housing.py")
import_housing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(import_housing)


@pytest.fixture(autouse=True)
def housing_db(tmp_path, monkeypatch):
    database = tmp_path / "housing.sqlite3"
    import_housing.import_rows(database)
    monkeypatch.setattr(settings, "housing_db_path", str(database))


def test_tools_are_registered_with_scope_in_description() -> None:
    rate = asyncio.run(mcp.get_tool("swiss_reference_interest_rate"))
    info = asyncio.run(mcp.get_tool("swiss_housing_info"))
    assert "never ask for a canton" in rate.description
    assert "not forecast" in rate.description
    assert "Not covered" in info.description


def test_rate_in_force_with_all_dates() -> None:
    result = swiss_reference_interest_rate("2026-10-15")
    assert result["status"] == "answered"
    assert (result["reference_rate_bp"], result["average_rate_bp"]) == (125, 131)
    assert (result["reference_rate_percent"], result["average_rate_percent"]) == ("1.25", "1.31")
    assert result["published_on"] == "2026-09-01"
    assert result["effective_from"] == "2026-09-02"
    assert result["value_unchanged_since"] == "2025-09-02"
    assert result["average_rate_as_of"] == "2026-06-30"
    assert result["next_publication_on"] == "2026-12-01"
    assert result["evidence"]["source"]["url"] == "https://www.bwo.admin.ch/it/newnsb/Ozmbl-Ca5Ee4"
    assert result["evidence"]["scraped_at"].endswith("Z")


def test_rate_languages_and_fallback() -> None:
    german = swiss_reference_interest_rate("2026-10-15", "de")["evidence"]
    assert german["source"]["language"] == "de" and "1,31 Prozent" in german["source"]["passage"]
    assert "language_fallback" not in german
    romansh = swiss_reference_interest_rate("2026-10-15", "rm")
    assert romansh["reference_rate_bp"] == 125
    assert romansh["evidence"]["source"]["language"] == "it"
    assert "language_fallback" in romansh["evidence"]


def test_rate_outside_coverage_is_not_answered() -> None:
    before = swiss_reference_interest_rate("2026-09-01")
    assert before["status"] == "no_match" and before["coverage"]["from"] == "2026-09-02"
    assert swiss_reference_interest_rate("2099-01-01")["status"] == "no_match"
    assert swiss_reference_interest_rate("01.10.2026")["status"] == "invalid_input"


def test_housing_info_matches_question_language() -> None:
    german = swiss_housing_info("Wie hoch darf die Kaution maximal sein?", "de")
    top = german["results"][0]
    assert (top["item_key"], top["source"]["language"]) == ("deposit:residential", "de")
    assert top["data"]["max_monthly_rents"] == 3
    assert "Geschäftsräume" in top["conditions"]["tenancy_type"]

    italian = swiss_housing_info("entro quanti giorni posso contestare un aumento dell'affitto?")
    assert "rent_adjustment:contest_increase" in [item["item_key"] for item in italian["results"]]

    romansh = swiss_housing_info("cauziun deposit", "rm")["results"][0]
    assert (romansh["item_key"], romansh["source"]["language"]) == ("deposit:residential", "rm")


@pytest.mark.parametrize(
    ("question", "language", "expected"),
    [
        ("Entro quando devo disdire l'appartamento e in che forma?", "it", "termination:tenant"),
        ("Se il tasso scende di 0,25 punti quanto si riduce l'affitto?", "it", "rent_adjustment:quarter_point"),
        ("Wie hoch darf die Mietkaution sein?", "de", "deposit:residential"),
        ("Wie kündige ich meine Wohnung?", "de", "termination:tenant"),
        ("Combien de jours pour contester une hausse de loyer ?", "fr", "rent_adjustment:contest_increase"),
        ("Quant po esser la cauziun?", "rm", "deposit:residential"),
        ("Posso dipingere le pareti?", "it", "alterations:permission"),
        ("Chi paga se si rompe il tubo della doccia?", "it", "defects:notification"),
        ("Le spese accessorie in acconto vanno conteggiate ogni anno?", "it", "utilities:advance_settlement"),
    ],
)
def test_housing_info_ranks_expected_item_first(question, language, expected) -> None:
    assert swiss_housing_info(question, language)["results"][0]["item_key"] == expected


@pytest.mark.parametrize(
    ("question", "expected_prefix"),
    [
        ("How high can the rent deposit be?", "deposit:residential"),
        ("How do I terminate my lease?", "termination:"),
        ("Can I paint the walls of my flat?", "alterations:permission"),
        ("How many days to contest a rent increase?", "rent_adjustment:contest_increase"),
        ("Who pays when something breaks in my apartment?", "defects:notification"),
    ],
)
def test_english_question_matches_through_keywords(question, expected_prefix) -> None:
    # The calling model often translates the question into English; passages are not in English.
    top = swiss_housing_info(question, "de")["results"][0]
    assert top["item_key"].startswith(expected_prefix)
    assert top["source"]["language"] == "de"


def test_lexically_ambiguous_question_keeps_expected_item_in_top_two() -> None:
    # The tenant passage also says the lease "peut être résilié ... par le propriétaire".
    results = swiss_housing_info("Le propriétaire peut-il résilier mon bail ?", "fr", limit=2)["results"]
    assert "termination:landlord" in [item["item_key"] for item in results]


def test_conciliation_address_is_out_of_scope_but_deadline_is_answered() -> None:
    for question, language in [
        ("Dov'è l'autorità di conciliazione a Lugano?", "it"),
        ("Wo ist die Schlichtungsbehörde in Bern?", "de"),
        ("Où est l'autorité de conciliation à Genève ?", "fr"),
    ]:
        assert swiss_housing_info(question, language)["status"] == "out_of_scope"
    deadline = swiss_housing_info("Entro quanti giorni devo rivolgermi all'autorità di conciliazione?")
    assert deadline["status"] == "answered"


def test_housing_info_topic_and_fallback() -> None:
    result = swiss_housing_info(topic="rent_adjustment", language="rm", limit=10)
    assert result["status"] == "answered"
    assert {item["source"]["language"] for item in result["results"]} == {"it"}
    assert all("language_fallback" in item for item in result["results"])
    assert len(swiss_housing_info(topic="termination", language="fr")["results"]) == 2


def test_housing_info_scope_and_input_errors() -> None:
    assert swiss_housing_info("Serve il modulo per la pigione iniziale a Zurigo?")["status"] == "out_of_scope"
    assert swiss_housing_info("Adresse der Schlichtungsbehörde in Bern?", "de")["status"] == "out_of_scope"
    assert swiss_housing_info()["status"] == "need_info"
    assert swiss_housing_info("xyzzy qwrtp")["status"] == "no_match"
    assert swiss_housing_info("cauzione", limit=0)["status"] == "invalid_input"
    assert swiss_housing_info(topic="mortgage")["status"] == "invalid_input"


def test_missing_database(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "housing_db_path", str(tmp_path / "missing.sqlite3"))
    assert swiss_reference_interest_rate()["status"] == "source_unavailable"
    assert swiss_housing_info("cauzione")["status"] == "source_unavailable"
