"""Source-specific, bounded public-data queries and tool registration."""

import asyncio

from mcp_swiss_info import bfs
from mcp_swiss_info import geodata as geo
from mcp_swiss_info import opendata_catalog as catalog
from mcp_swiss_info.server import mcp


def test_public_data_tools_are_registered() -> None:
    for name in (
        "bfs_population",
        "opendata_search_datasets",
        "opendata_dataset",
        "swiss_geo_search",
        "swiss_geo_context",
    ):
        assert asyncio.run(mcp.get_tool(name)) is not None


def test_bfs_query_selects_one_canton_and_explicit_totals(monkeypatch) -> None:
    variables = [
        {"code": code, "values": values, "valueTexts": labels}
        for code, values, labels in (
            ("Jahr", ["2024", "2025"], ["2024", "2025"]),
            ("Kanton", ["8100", "BE"], ["Switzerland", "Bern"]),
            ("Bevölkerungstyp", ["1", "2"], ["Permanent", "Non-permanent"]),
            ("Anwesenheitsbewilligung", ["-99999"], ["Total"]),
            ("Geschlecht", ["-99999", "1", "2"], ["Total", "Male", "Female"]),
            ("Altersklasse", ["-99999"], ["Total"]),
            ("Staatsangehörigkeit", ["-99999"], ["Total"]),
        )
    ]

    def request(url, payload=None, timeout=35):
        assert url == bfs.TABLE_URL
        if payload is None:
            return {"title": "Population", "variables": variables}
        assert timeout == 75
        selection = {q["code"]: q["selection"]["values"] for q in payload["query"]}
        assert selection == {
            "Jahr": ["2024", "2025"],
            "Kanton": ["BE"],
            "Bevölkerungstyp": ["1"],
            "Anwesenheitsbewilligung": ["-99999"],
            "Geschlecht": ["2"],
            "Altersklasse": ["-99999"],
            "Staatsangehörigkeit": ["-99999"],
        }
        return {
            "data": [
                {"key": ["2024", "BE"], "values": ["500"]},
                {"key": ["2025", "BE"], "values": ["501"]},
            ]
        }

    monkeypatch.setattr(bfs, "request_json", request)
    result = bfs._population("be", 2024, 2025, "permanent", "female")
    assert result["values"] == [
        {"year": 2024, "population": 500},
        {"year": 2025, "population": 501},
    ]
    assert result["canton_name"] == "Bern"


def test_catalogue_paginates_resources_and_preserves_rights(monkeypatch) -> None:
    dataset = {
        "name": "example",
        "title": {"en": "Example"},
        "publisher": {"name": {"en": "FSO"}},
        "resources": [
            {
                "title": {"en": f"year {i}"},
                "format": "CSV",
                "url": f"https://publisher.example/{i}.csv",
                "rights": "cc-by",
            }
            for i in range(25)
        ],
    }
    monkeypatch.setattr(catalog, "request_json", lambda url: {"success": True, "result": dataset})
    result = catalog._dataset("example", "en", 20)
    assert result["status"] == "answered"
    assert result["dataset"]["resource_count"] == 25
    assert len(result["dataset"]["resources"]) == 5
    assert result["dataset"]["resources"][0]["url"] == "https://publisher.example/20.csv"
    assert result["dataset"]["resources"][0]["rights"] == "cc-by"
    assert result["dataset"]["has_more_resources"] is False
    assert catalog._dataset("https://evil.example", "en", 0)["status"] == "invalid_input"


def test_catalogue_search_returns_metadata_not_raw_resources(monkeypatch) -> None:
    def request(url):
        assert "rows=2" in url
        return {
            "success": True,
            "result": {
                "count": 7,
                "results": [
                    {
                        "name": "first",
                        "title": {"en": "First"},
                        "resources": [{"url": "https://publisher.example/file.csv"}],
                    }
                ],
            },
        }

    monkeypatch.setattr(catalog, "request_json", request)
    result = catalog._search("train stations", 2, "en")
    assert result["status"] == "answered"
    assert result["total_matches"] == 7
    assert "resources" not in result["datasets"][0]
    assert result["datasets"][0]["resource_count"] == 1


def test_geo_context_ignores_historical_boundaries(monkeypatch) -> None:
    def request(url):
        assert "tolerance=0" in url and "sr=4326" in url
        return {
            "results": [
                {
                    "layerBodId": geo.MUNICIPALITY,
                    "attributes": {"gemname": "Old Bern", "gde_nr": 7700, "is_current_jahr": False},
                },
                {
                    "layerBodId": geo.MUNICIPALITY,
                    "attributes": {
                        "gemname": "Bern",
                        "gde_nr": 351,
                        "jahr": 2026,
                        "is_current_jahr": True,
                    },
                },
                {"layerBodId": geo.CANTON, "attributes": {"ak": "BE", "name": "Bern"}},
                {"layerBodId": geo.POSTAL, "attributes": {"plz": 3011, "langtext": "Bern"}},
            ]
        }

    monkeypatch.setattr(geo, "request_json", request)
    result = geo._context(46.948, 7.4474)
    assert result["municipality"] == {"name": "Bern", "bfs_number": 351, "boundary_year": 2026}
    assert result["postal_areas"] == [{"postal_code": "3011", "name": "Bern"}]
    assert result["map_url"].startswith("https://map.geo.admin.ch/#/map?")
    assert geo._context(0, 0)["status"] == "invalid_input"


def test_geo_search_is_bounded(monkeypatch) -> None:
    monkeypatch.setattr(
        geo,
        "request_json",
        lambda url: {
            "results": [
                {"attrs": {"label": "<b>Genève</b>", "origin": "gg25", "lat": 46.2, "lon": 6.1}}
            ]
        },
    )
    result = geo._search_locations("Genève", 1)
    assert result["locations"] == [
        {"name": "Genève", "type": "gg25", "latitude": 46.2, "longitude": 6.1}
    ]
    assert geo._search_locations("Genève", 11)["status"] == "invalid_input"
