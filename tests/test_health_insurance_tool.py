"""Behavior and registration checks for the CSV-backed premium lookup."""

import asyncio

from src.mcp_swiss_info.server import mcp
from src.mcp_swiss_info.tools.health_insurance_tools import swiss_health_insurance_premiums


def test_tool_is_registered_with_source_and_validity_description() -> None:
    tool = asyncio.run(mcp.get_tool("swiss_health_insurance_premiums"))
    assert tool is not None
    assert "priminfo.admin.ch" in tool.description.lower()
    assert "Valid ONLY for 2026; INVALID for 2027" in tool.description
    assert "BFS" in tool.description


def test_premium_lookup_returns_both_accident_options() -> None:
    result = swiss_health_insurance_premiums(26, 1, 2500)
    assert result["status"] == "answered"
    assert result["year"] == 2026
    assert result["municipality"] == "Aeugst am Albis"
    assert result["premiums"][0] == {
        "accident_cover": "excluded",
        "minimum_premium": "300.9",
        "insurer": "Sanitas",
        "model": "TelMed (Compact One)",
        "source_url": "https://kvgmapper26.github.io/maps/map-AKL-ERW-OHN-UNF-FRA-2500.html",
    }
    assert result["premiums"][1]["accident_cover"] == "included"
    assert result["premiums"][1]["minimum_premium"] == "317.4"
    assert swiss_health_insurance_premiums(25, 1, 300)["age_group"] == "young_19_25"


def test_missing_and_invalid_inputs() -> None:
    assert swiss_health_insurance_premiums(26, 2391, 2500)["status"] == "no_data"
    assert swiss_health_insurance_premiums(26, 99999, 2500)["status"] == "not_found"
    assert swiss_health_insurance_premiums(18, 1, 2500)["status"] == "invalid_input"
    assert swiss_health_insurance_premiums(26, 1, 100)["status"] == "invalid_input"
