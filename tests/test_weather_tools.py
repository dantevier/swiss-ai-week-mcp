"""MeteoSwiss tool registration and bounded, location-specific lookups."""

import asyncio
from datetime import UTC, datetime, timedelta

from mcp_boilerplate import weather
from mcp_boilerplate.server import mcp


def test_tools_are_registered() -> None:
    for name in ("swiss_weather_forecast", "swiss_weather_observations"):
        tool = asyncio.run(mcp.get_tool(name))
        assert tool is not None
        assert "opendatadocs.meteoswiss.ch" in tool.description


def test_forecast_requires_specific_point_when_postal_code_is_shared(monkeypatch) -> None:
    monkeypatch.setattr(
        weather,
        "_points",
        lambda: [
            {
                "postal_code": "1945",
                "point_type_id": "2",
                "point_id": str(i),
                "point_name": name,
                "point_coordinates_wgs84_lat": "46.1",
                "point_coordinates_wgs84_lon": "7.1",
            }
            for i, name in ((1, "A"), (2, "B"))
        ],
    )
    result = weather._forecast("1945", "daily", 1, None, "temperature_c")
    assert result["status"] == "ambiguous_location"
    assert [p["point_id"] for p in result["choices"]] == ["1", "2"]
    assert weather._forecast("1945", "hourly", 1, "3", "temperature_c")["status"] == "not_found"


def test_forecast_selects_latest_run_and_filters_point(monkeypatch) -> None:
    now = datetime.now(UTC)
    hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    timestamp = hour.strftime("%Y%m%d%H%M")
    monkeypatch.setattr(
        weather,
        "_points",
        lambda: [
            {
                "postal_code": "1201",
                "point_type_id": "2",
                "point_id": "120100",
                "point_name": "Genève",
                "point_coordinates_wgs84_lat": "46.2",
                "point_coordinates_wgs84_lon": "6.1",
            }
        ],
    )
    older = "https://data.geo.admin.ch/old.csv"
    latest = "https://data.geo.admin.ch/new.csv"
    monkeypatch.setattr(
        weather,
        "_forecast_item",
        lambda: {
            "id": "run",
            "properties": {"updated": "today"},
            "assets": {
                "vnut12.lssw.202609241000.tre200h0.csv": {"href": older},
                "vnut12.lssw.202609241100.tre200h0.csv": {"href": latest},
            },
        },
    )

    def fake_rows(url, encoding):
        assert url == latest
        return iter(
            [
                {"point_id": "other", "point_type_id": "2", "Date": timestamp, "tre200h0": "77"},
                {"point_id": "120100", "point_type_id": "1", "Date": timestamp, "tre200h0": "88"},
                {"point_id": "120100", "point_type_id": "2", "Date": timestamp, "tre200h0": "12.5"},
            ]
        )

    monkeypatch.setattr(weather, "_csv_rows", fake_rows)
    weather._forecast_values.cache_clear()
    result = weather._forecast("1201", "hourly", 1, None, "temperature_c")
    assert result["status"] == "answered"
    assert result["values"] == [{"valid_time_utc": hour.isoformat(), "temperature_c": 12.5}]
    assert result["source_urls"] == {"temperature_c": latest}
    assert result["attribution"] == "Source: MeteoSwiss"


def test_observation_selects_historical_decade_and_returns_only_requested_date(monkeypatch) -> None:
    chosen = "https://data.geo.admin.ch/historical.csv"
    monkeypatch.setattr(
        weather,
        "_json",
        lambda url: {
            "properties": {"title": "Bern (BER)"},
            "assets": {
                "ogd-smn_ber_h_historical_2010-2019.csv": {"href": chosen},
                "ogd-smn_ber_h_historical_2020-2029.csv": {
                    "href": "https://data.geo.admin.ch/wrong.csv"
                },
            },
        },
    )

    def fake_rows(url, encoding):
        assert url == chosen
        assert encoding == "cp1252"
        return iter(
            [
                {
                    "station_abbr": "BER",
                    "reference_timestamp": "31.12.2018 23:00",
                    "tre200h0": "10",
                },
                {
                    "station_abbr": "BER",
                    "reference_timestamp": "01.01.2019 00:00",
                    "tre200h0": "",
                    "rre150h0": "0.2",
                },
                {
                    "station_abbr": "OTHER",
                    "reference_timestamp": "01.01.2019 00:00",
                    "tre200h0": "30",
                },
            ]
        )

    monkeypatch.setattr(weather, "_csv_rows", fake_rows)
    result = weather._observations("ber", "hourly", "2019-01-01")
    assert result["status"] == "answered"
    assert result["source_url"] == chosen
    assert result["values"] == [
        {
            "time_utc": "2019-01-01T00:00:00+00:00",
            "temperature_c": None,
            "precipitation_mm": 0.2,
            "humidity_pct": None,
            "wind_kmh": None,
            "gust_kmh": None,
            "pressure_hpa": None,
        }
    ]


def test_invalid_inputs_do_not_download(monkeypatch) -> None:
    monkeypatch.setattr(
        weather, "_download", lambda url: (_ for _ in ()).throw(AssertionError("downloaded"))
    )
    assert weather._forecast("300", "daily", 1, None, "temperature_c")["status"] == "invalid_input"
    assert weather._forecast("1201", "hourly", 1, None, "bad")["status"] == "invalid_input"
    assert weather._observations("BAD!", "10min", None)["status"] == "invalid_input"
    assert weather._observations("BER", "daily", "tomorrow")["status"] == "invalid_input"
