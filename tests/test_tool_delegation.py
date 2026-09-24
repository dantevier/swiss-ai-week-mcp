"""MCP entry points keep their arguments while delegating to implementations."""

import asyncio
from datetime import UTC, datetime

import pytest

from mcp_boilerplate import (
    bfs,
    customs,
    driving_licence,
    geodata,
    health_insurance,
    housing,
    migration,
    opendata_catalog,
    political_rights,
    weather,
)
from mcp_boilerplate.source_access import SourceAccess
from mcp_boilerplate.tools import (
    bfs_tools,
    customs_tools,
    driving_licence_tools,
    geo_tools,
    health_insurance_tools,
    housing_tools,
    migration_tools,
    opendata_tools,
    political_rights_tools,
    source_tools,
    weather_tools,
)


@pytest.mark.parametrize(
    ("tool", "service", "method", "args"),
    [
        (
            weather_tools.swiss_weather_forecast,
            weather.MeteoSwissWeather,
            "forecast",
            ("1201", "hourly", 2, None, "temperature_c"),
        ),
        (
            weather_tools.swiss_weather_observations,
            weather.MeteoSwissWeather,
            "observations",
            ("BER", "10min", None),
        ),
        (
            bfs_tools.bfs_population,
            bfs.BFSStatistics,
            "population",
            ("BE", 2024, 2025, "permanent", "total"),
        ),
        (
            opendata_tools.opendata_search_datasets,
            opendata_catalog.OpenDataCatalog,
            "search",
            ("weather", 5, "en"),
        ),
        (
            opendata_tools.opendata_dataset,
            opendata_catalog.OpenDataCatalog,
            "dataset",
            ("example", "en", 20),
        ),
        (geo_tools.swiss_geo_search, geodata.SwissGeodata, "search", ("Bern", 5)),
        (geo_tools.swiss_geo_context, geodata.SwissGeodata, "context", (46.9, 7.4)),
        (
            customs_tools.swiss_import_parcel_vat,
            customs.Customs,
            "estimate_vat",
            (100, 10, "standard", 0),
        ),
        (
            political_rights_tools.swiss_federal_political_rights,
            political_rights.PoliticalRights,
            "rules",
            ("referendum",),
        ),
        (
            migration_tools.swiss_residence_permit_guidance,
            migration.Migration,
            "guidance",
            ("eu_efta", "B"),
        ),
    ],
)
def test_entry_point_delegates_without_calling_network(
    monkeypatch, tool, service, method, args
) -> None:
    expected = {"status": "answered", "arguments": args}

    def implementation(self, *received):
        assert received == args
        return expected

    monkeypatch.setattr(service, method, implementation)
    assert asyncio.run(tool(*args)) == expected


def test_injected_catalog_and_geo_requesters_are_used_by_tools(monkeypatch) -> None:
    calls = []

    def catalogue_request(url):
        calls.append(url)
        return {
            "success": True,
            "result": {
                "count": 1,
                "results": [{"name": "sample", "title": {"en": "Sample"}, "resources": []}],
            },
        }

    def geo_request(url):
        calls.append(url)
        return {
            "results": [
                {"attrs": {"label": "<b>Bern</b>", "origin": "gg25", "lat": 46.9, "lon": 7.4}}
            ]
        }

    monkeypatch.setattr(
        opendata_tools, "catalog", opendata_catalog.OpenDataCatalog(catalogue_request)
    )
    monkeypatch.setattr(geo_tools, "geodata", geodata.SwissGeodata(geo_request))
    assert (
        asyncio.run(opendata_tools.opendata_search_datasets("sample"))["datasets"][0]["id"]
        == "sample"
    )
    assert asyncio.run(geo_tools.swiss_geo_search("Bern"))["locations"][0]["name"] == "Bern"
    assert len(calls) == 2


def test_injected_authority_fetcher_is_used_by_tool(monkeypatch) -> None:
    urls = []

    def fetch(url, title):
        urls.append(url)
        return {
            "blocks": [
                ("h1", title),
                ("p", "An EU/EFTA B permit applies to long-term residence in Switzerland."),
                ("p", "Last modification 01.01.2022"),
            ],
            "source_url": url,
            "fetched_at_utc": "now",
        }

    monkeypatch.setattr(migration_tools, "migration", migration.Migration(fetch))
    result = asyncio.run(migration_tools.swiss_residence_permit_guidance("eu_efta", "B"))
    assert result["source_excerpts"] == [
        "An EU/EFTA B permit applies to long-term residence in Switzerland."
    ]
    assert urls == [migration.PAGES["eu_efta"]["B"][0]]


def test_injected_weather_clients_serve_both_queries(monkeypatch) -> None:
    stamp = datetime(2026, 9, 24, 18, tzinfo=UTC)
    observed = "https://data.geo.admin.ch/obs.csv"
    forecast = "https://data.geo.admin.ch/forecast.csv"

    def read_csv(url, encoding):
        if url == weather.POINTS_URL:
            return iter(
                [
                    {
                        "point_id": "120100",
                        "point_type_id": "2",
                        "postal_code": "1201",
                        "point_name": "Genève",
                        "point_coordinates_wgs84_lat": "46.2",
                        "point_coordinates_wgs84_lon": "6.1",
                    }
                ]
            )
        if url == forecast:
            return iter(
                [
                    {
                        "point_id": "120100",
                        "point_type_id": "2",
                        "Date": "202609241800",
                        "tre200h0": "15.5",
                    }
                ]
            )
        assert url == observed
        return iter(
            [
                {
                    "station_abbr": "BER",
                    "reference_timestamp": "24.09.2026 18:00",
                    "tre200s0": "13.4",
                }
            ]
        )

    def read_json(url):
        if weather.FORECAST_COLLECTION in url:
            return {
                "id": "run",
                "properties": {"updated": "now"},
                "assets": {"vnut12.lssw.202609241700.tre200h0.csv": {"href": forecast}},
            }
        return {
            "properties": {"title": "Bern (BER)"},
            "assets": {"ogd-smn_ber_t_now.csv": {"href": observed}},
        }

    data = weather.MeteoSwissData(read_csv, read_json, lambda tz: stamp.replace(hour=17, tzinfo=tz))
    monkeypatch.setattr(weather_tools, "meteoswiss", weather.MeteoSwissWeather(data))
    result = asyncio.run(weather_tools.swiss_weather_forecast("1201", "hourly", 1))
    assert result["values"] == [{"valid_time_utc": stamp.isoformat(), "temperature_c": 15.5}]
    result = asyncio.run(weather_tools.swiss_weather_observations("BER"))
    assert result["values"][0]["temperature_c"] == 13.4


@pytest.mark.parametrize(
    ("tool", "service", "method", "args"),
    [
        (
            housing_tools.swiss_reference_interest_rate,
            housing.Housing,
            "reference_interest_rate",
            ("2026-10-15", "de"),
        ),
        (housing_tools.swiss_housing_info, housing.Housing, "info", ("deposit", "de", None, 2)),
        (
            driving_licence_tools.get_driving_licence_exchange_info,
            driving_licence.DrivingLicence,
            "exchange_info",
            ("ZH", "fee"),
        ),
        (
            health_insurance_tools.swiss_health_insurance_premiums,
            health_insurance.HealthInsurance,
            "premiums",
            (26, 1, 2500),
        ),
    ],
)
def test_database_tool_wrappers_delegate_to_injected_services(
    monkeypatch, tool, service, method, args
):
    expected = {"status": "answered", "arguments": args}

    def implementation(self, *received):
        assert received == args
        return expected

    monkeypatch.setattr(service, method, implementation)
    assert tool(*args) == expected


def test_source_tool_wrappers_use_injected_dependencies(monkeypatch):
    calls = []

    class FakeCrawler:
        async def crawl(self, level, source):
            calls.append((level, source))
            return {"level": level, "source": source}

    class FakeKnowledge:
        async def search(self, query, limit):
            calls.append((query, limit))
            return {"query": query}

        def get(self, level, source):
            calls.append((level, source))
            return {"source": source}

    service = SourceAccess(
        FakeCrawler, FakeKnowledge, lambda: {"status": "ok"}, lambda: "http://localhost/"
    )
    monkeypatch.setattr(source_tools, "sources", service)
    assert asyncio.run(source_tools.crawl_federal_sources("sample")) == {
        "level": "federal",
        "source": "sample",
    }
    assert asyncio.run(source_tools.search_knowledge("rent", 2)) == {"query": "rent"}
    assert source_tools.get_source("federal", "sample") == {"source": "sample"}
    assert source_tools.source_status() == {"status": "ok"}
    assert source_tools.open_dashboard() == {"url": "http://localhost/"}
    assert calls == [("federal", "sample"), ("rent", 2), ("federal", "sample")]
