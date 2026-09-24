"""Live school-holiday tool, with OpenHolidays responses mocked."""

import asyncio
from urllib.error import URLError

from src.mcp_boilerplate import school_holiday as holidays
from src.mcp_boilerplate.server import mcp
from src.mcp_boilerplate.tools.school_holiday_tools import swiss_school_holidays


def call(*args, **kwargs):
    return asyncio.run(swiss_school_holidays(*args, **kwargs))


def test_registration_and_invalid_arguments(monkeypatch):
    tool = asyncio.run(mcp.get_tool("swiss_school_holidays"))
    assert tool is not None
    assert "OpenHolidays" in tool.description
    assert all(
        name in tool.parameters["properties"]
        for name in ("canton", "school_year", "holiday_type", "municipality")
    )
    monkeypatch.setattr(
        holidays, "_fetch_json", lambda url: (_ for _ in ()).throw(AssertionError("network called"))
    )
    assert call("XX")["status"] == "invalid_input"
    assert call("ZH", school_year=2019)["status"] == "invalid_input"
    assert call("ZH", holiday_type=" ")["status"] == "invalid_input"
    assert call("ZH", municipality=" ")["status"] == "invalid_input"


def test_lookup_keeps_school_types_and_filters_name(monkeypatch):
    rows = [
        {
            "startDate": "2026-10-05",
            "endDate": "2026-10-17",
            "name": [
                {"language": "DE", "text": "Herbstferien"},
                {"language": "EN", "text": "Autumn holidays"},
            ],
            "subdivisions": [{"code": "CH-BE"}],
            "groups": [{"code": "CH-BE-VS"}],
        },
        {
            "startDate": "2026-10-05",
            "endDate": "2026-10-17",
            "name": [{"language": "EN", "text": "Autumn holidays"}],
            "subdivisions": [{"code": "CH-BE"}],
            "groups": [{"code": "CH-BE-MS"}],
        },
    ]
    urls = []

    def fetch(url):
        urls.append(url)
        return rows

    monkeypatch.setattr(holidays, "_fetch_json", fetch)
    result = call("BE", 2026, "autumn")
    assert result["status"] == "answered"
    assert result["school_year"] == "2026/27"
    assert (result["valid_from"], result["valid_to"]) == ("2026-08-01", "2027-07-31")
    assert result["scope"]["level"] == "canton"
    assert [h["school_types"] for h in result["holidays"]] == [["CH-BE-VS"], ["CH-BE-MS"]]
    assert all(h["scope"] == "canton" for h in result["holidays"])
    assert "subdivisionCode=CH-BE" in urls[0]
    assert result["source"]["license"] == "CC BY 4.0"
    assert call("BE", 2026, "summer")["status"] == "no_data"


def test_local_variation_needs_municipality_and_scopes_result(monkeypatch):
    row = {
        "startDate": "2026-10-10",
        "endDate": "2026-10-25",
        "name": [{"language": "EN", "text": "Autumn holidays"}],
        "subdivisions": [{"code": "CH-GR-ML"}],
        "groups": [{"code": "CH-GR-VS"}],
    }
    tree = [
        {
            "code": "CH-GR",
            "children": [
                {
                    "code": "CH-GR-ML",
                    "children": [
                        {"code": "CH-GR-ML-BR", "name": [{"language": "DE", "text": "Bregaglia"}]}
                    ],
                }
            ],
        }
    ]
    urls = []

    def fetch(url):
        urls.append(url)
        return tree if "/Subdivisions?" in url else [row]

    monkeypatch.setattr(holidays, "_fetch_json", fetch)
    assert call("GR", 2026)["status"] == "municipality_required"
    result = call("GR", 2026, municipality="Bregaglia")
    assert result["status"] == "answered"
    assert result["scope"] == {"level": "municipality", "code": "CH-GR-ML-BR", "name": "Bregaglia"}
    assert result["holidays"][0]["scope"] == "district"
    assert "subdivisionCode=CH-GR-ML-BR" in urls[-1]
    assert call("GR", 2026, municipality="Nowhere")["status"] == "invalid_input"


def test_upstream_failure_is_not_empty_result(monkeypatch):
    def fail(url):
        raise URLError("offline")

    monkeypatch.setattr(holidays, "_fetch_json", fail)
    result = call("BE", 2026)
    assert result["status"] == "source_unavailable"
    assert result["source"]["name"] == "OpenHolidays API"
