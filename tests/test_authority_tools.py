"""Live-rule parsing and official-source routing for the three authority tools."""

import asyncio

from mcp_swiss_info import customs, migration
from mcp_swiss_info import political_rights as political
from mcp_swiss_info.authority_pages import MainParagraphs
from mcp_swiss_info.server import mcp


def test_authority_tools_are_registered() -> None:
    for name in (
        "swiss_import_parcel_vat",
        "swiss_federal_political_rights",
        "swiss_residence_permit_guidance",
    ):
        assert asyncio.run(mcp.get_tool(name)) is not None


def test_parser_keeps_main_paragraphs_and_not_navigation() -> None:
    parser = MainParagraphs()
    parser.feed(
        "<nav><p>Not a rule</p></nav><h1>Official title</h1>"
        "<p>The <strong>reduced</strong> rate applies.</p>"
        "<script><p>Fake rate</p></script><footer><p>Other site</p></footer>"
    )
    assert parser.blocks == [
        ("h1", "Official title"),
        ("p", "The reduced rate applies."),
    ]


def test_customs_estimate_requires_current_rules_and_includes_shipping_and_duty(
    monkeypatch,
) -> None:
    page = {
        "blocks": [
            (
                "p",
                "Value added tax amounts to 8,1 % of the assessment basis. A reduced rate of 2.6 % applies for certain goods.",
            ),
            (
                "p",
                "Tax amounts of up to 5 Swiss francs are not levied. CHF 62 at 8,1 % or CHF 193 at 2.6 %.",
            ),
            (
                "p",
                "All costs up to the destination in Switzerland as well as import duties are added to the assessment basis.",
            ),
        ],
        "source_url": customs.SOURCE_URL,
        "fetched_at_utc": "now",
    }
    monkeypatch.setattr(customs, "fetch_page", lambda url, title: page)
    result = customs._estimate(100, 10, "standard", 2)
    assert result["assessment_basis_chf"] == 112
    assert result["estimated_vat_chf"] == 9.07
    assert result["carrier_clearance_fee_chf"] is None
    assert customs._estimate(100, 10, "reduced", 0)["estimated_vat_chf"] == 2.86
    assert "may change" in customs._estimate(100, 10, "standard", None)["collection_guidance"]
    assert customs._estimate(-1, 0, "standard", None)["status"] == "invalid_input"
    page["blocks"][0] = (
        "p",
        "Value added tax amounts to 9 % of the assessment basis. A reduced rate of 2.6 % applies.",
    )
    assert customs._estimate(100, 0, "standard", 0)["status"] == "source_unavailable"


def test_political_threshold_is_backed_by_matching_source_paragraph(monkeypatch) -> None:
    page = {
        "blocks": [
            ("p", "Sind innerhalb von 18 Monaten 100 000 gültige Unterschriften zusammengekommen."),
        ],
        "source_url": political.PAGES["initiative"][0],
        "fetched_at_utc": "now",
    }
    monkeypatch.setattr(political, "fetch_page", lambda url, title: page)
    result = political._rules("initiative")
    assert result["signatures_required"] == 100000
    assert result["collection_period_months"] == 18
    assert result["source_language"] == "de"
    page["blocks"][0] = (
        "p",
        "Sind innerhalb von 18 Monaten 120 000 gültige Unterschriften zusammengekommen.",
    )
    assert political._rules("initiative")["status"] == "source_unavailable"
    assert political._rules("cantonal_vote")["status"] == "invalid_input"


def test_migration_routes_by_group_and_never_infers_nationality(monkeypatch) -> None:
    def fetch(url, title):
        assert url == migration.PAGES["eu_efta"]["B"][0]
        assert title.startswith("B EU/EFTA")
        return {
            "blocks": [
                ("h1", title),
                ("p", "This permit is for EU/EFTA nationals employed for at least twelve months."),
                ("p", "Last modification 01.01.2022"),
            ],
            "source_url": url,
            "fetched_at_utc": "now",
        }

    monkeypatch.setattr(migration, "fetch_page", fetch)
    result = migration._guidance("eu_efta", "B")
    assert result["status"] == "answered"
    assert result["source_excerpts"] == [
        "This permit is for EU/EFTA nationals employed for at least twelve months."
    ]
    assert migration._guidance("third_country", "B")["status"] == "invalid_input"
