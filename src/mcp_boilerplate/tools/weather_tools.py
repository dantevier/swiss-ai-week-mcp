"""MeteoSwiss MCP tool registration."""

import asyncio

from .. import weather
from ..server import mcp

meteoswiss = weather.MeteoSwissWeather(
    weather.MeteoSwissData(csv_reader=weather._csv_rows, json_reader=weather._json)
)


@mcp.tool
async def swiss_weather_forecast(
    postal_code: str,
    granularity: str = "daily",
    periods: int = 3,
    point_id: str | None = None,
    metric: str = "temperature_c",
) -> dict:
    """Get MeteoSwiss local forecasts by Swiss postal code (not observations).

    Daily: 1–9 local calendar days of min/max temperature and precipitation.
    Hourly: 1–48 UTC hours; select one metric: temperature_c (default),
    precipitation_mm, or precipitation_probability_3h_pct. One hourly
    parameter file may be ~33 MB; only the selected metric is downloaded.
    Multiple points may share a postal code: retry with point_id from choices.
    Data: https://opendatadocs.meteoswiss.ch/e-forecast-data/e4-local-forecast-data
    """
    return await asyncio.to_thread(
        meteoswiss.forecast, postal_code, granularity, periods, point_id, metric
    )


@mcp.tool
async def swiss_weather_observations(
    station_id: str, granularity: str = "10min", on_date: str | None = None
) -> dict:
    """Get MeteoSwiss station measurements by three-letter station ID (e.g. BER).

    Granularity: 10min, hourly, daily. Omit on_date for latest measurement;
    supply YYYY-MM-DD for all readings that day, including historical dates.
    Measurements are at a station, not a postal-code forecast. All times UTC.
    Data: https://opendatadocs.meteoswiss.ch/a-data-groundbased/a1-automatic-weather-stations
    """
    return await asyncio.to_thread(meteoswiss.observations, station_id, granularity, on_date)
