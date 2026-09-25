"""Local forecasts and station observations from MeteoSwiss Open Data."""

import csv
import io
import json
import re
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

STAC = "https://data.geo.admin.ch/api/stac/v1/collections"
FORECAST_COLLECTION = "ch.meteoschweiz.ogd-local-forecasting"
STATION_COLLECTION = "ch.meteoschweiz.ogd-smn"
POINTS_URL = (
    "https://data.geo.admin.ch/ch.meteoschweiz.ogd-local-forecasting/"
    "ogd-local-forecasting_meta_point.csv"
)
MAX_DOWNLOAD = 40 * 1024 * 1024
SOURCE = "Source: MeteoSwiss"

# Name, parameter identifier, unit. The daily precipitation and temperatures
# refer to Swiss local calendar days; hourly timestamps are UTC interval ends.
FORECAST_FIELDS = {
    "daily": {
        "temperature_min_c": ("tre200pn", "°C"),
        "temperature_max_c": ("tre200px", "°C"),
        "precipitation_mm": ("rka150p0", "mm"),
    },
    "hourly": {
        "temperature_c": ("tre200h0", "°C"),
        "precipitation_mm": ("rre150h0", "mm"),
        "precipitation_probability_3h_pct": ("rp0003i0", "%"),
    },
}
OBSERVATION_FIELDS = {
    "10min": {
        "temperature_c": "tre200s0",
        "precipitation_mm": "rre150z0",
        "humidity_pct": "ure200s0",
        "wind_kmh": "fu3010z0",
        "gust_kmh": "fu3010z1",
        "pressure_hpa": "pp0qnhs0",
    },
    "hourly": {
        "temperature_c": "tre200h0",
        "precipitation_mm": "rre150h0",
        "humidity_pct": "ure200h0",
        "wind_kmh": "fu3010h0",
        "gust_kmh": "fu3010h1",
        "pressure_hpa": "pp0qnhh0",
    },
    "daily": {
        "temperature_c": "tre200d0",
        "temperature_min_c": "tre200dn",
        "temperature_max_c": "tre200dx",
        "precipitation_mm": "rka150d0",
        "humidity_pct": "ure200d0",
        "wind_kmh": "fu3010d0",
        "gust_kmh": "fu3010d1",
        "pressure_hpa": "pp0qnhd0",
    },
}


def _download(url: str) -> bytes:
    """Read an official file with a timeout and a hard size limit."""
    if not url.startswith("https://data.geo.admin.ch/"):
        raise ValueError("Unexpected MeteoSwiss data URL")
    with urlopen(
        Request(url, headers={"User-Agent": "swiss-ai-week-mcp/0.1"}), timeout=35
    ) as response:
        body = response.read(MAX_DOWNLOAD + 1)
    if len(body) > MAX_DOWNLOAD:
        raise ValueError("MeteoSwiss file exceeds the 40 MB download limit")
    return body


def _json(url: str) -> dict:
    return json.loads(_download(url))


def _csv_rows(url: str, encoding: str) -> csv.DictReader:
    return csv.DictReader(io.StringIO(_download(url).decode(encoding)), delimiter=";")


@lru_cache(maxsize=1)
def _points(csv_reader: Callable | None = None) -> list[dict[str, str]]:
    return list((csv_reader or _csv_rows)(POINTS_URL, "latin-1"))


def _forecast_item(json_reader: Callable | None = None, clock: Callable | None = None) -> dict:
    # A day's item already exists the previous day; fall back when it has not
    # yet appeared or if the date changes around midnight UTC.
    today = (clock or datetime.now)(UTC).date()
    for day in (today, today - timedelta(days=1)):
        url = f"{STAC}/{FORECAST_COLLECTION}/items/{day:%Y%m%d}-ch"
        try:
            return (json_reader or _json)(url)
        except HTTPError as exc:
            if exc.code != 404:
                raise
    raise ValueError("No current MeteoSwiss forecast item is available")


def _asset(item: dict, parameter: str) -> str:
    """Select the newest hourly run for the requested parameter."""
    assets = item["assets"]
    matches = [name for name in assets if name.endswith(f".{parameter}.csv")]
    if not matches:
        raise ValueError(f"Forecast parameter {parameter} is not published")
    return assets[max(matches)]["href"]


@lru_cache(maxsize=24)
def _forecast_values(
    url: str,
    point_id: str,
    point_type_id: str,
    parameter: str,
    csv_reader: Callable | None = None,
) -> dict[str, float | int | None]:
    """Keep only one point's values in memory, not the entire parameter file."""
    values: dict[str, float | int | None] = {}
    # Downloaded files have unique names per forecast run, so cached results
    # cannot accidentally serve values from a superseded run.
    for row in (csv_reader or _csv_rows)(url, "latin-1"):
        if row["point_id"] == point_id and row["point_type_id"] == point_type_id:
            values[row["Date"]] = _number(row.get(parameter))
    return values


def _number(value: str | None) -> float | int | None:
    if value is None or value.strip() in ("", "-"):
        return None
    number = float(value)
    return int(number) if number.is_integer() else number


def _failure(exc: Exception) -> dict:
    if isinstance(exc, (HTTPError, URLError, TimeoutError, OSError)):
        return {
            "status": "source_unavailable",
            "message": "MeteoSwiss data could not be retrieved.",
        }
    return {"status": "source_unavailable", "message": str(exc)}


def _forecast(
    postal_code: str,
    granularity: str,
    periods: int,
    point_id: str | None,
    metric: str,
    points_loader: Callable | None = None,
    item_loader: Callable | None = None,
    values_loader: Callable | None = None,
    clock: Callable | None = None,
) -> dict:
    if not re.fullmatch(r"\d{4}", postal_code):
        return {
            "status": "invalid_input",
            "message": "postal_code must be a four-digit Swiss postal code (string).",
        }
    if granularity not in FORECAST_FIELDS or not 1 <= periods <= (
        9 if granularity == "daily" else 48
    ):
        return {
            "status": "invalid_input",
            "message": "granularity must be daily (periods 1–9) or hourly (periods 1–48).",
        }
    if granularity == "hourly" and metric not in FORECAST_FIELDS["hourly"]:
        return {
            "status": "invalid_input",
            "message": "Hourly metric must be temperature_c, precipitation_mm or precipitation_probability_3h_pct.",
        }
    try:
        matches = [
            p
            for p in (points_loader or _points)()
            if p["point_type_id"] == "2" and p["postal_code"] == postal_code
        ]
        if not matches:
            return {
                "status": "not_found",
                "message": "Postal code not in the MeteoSwiss forecast point list.",
            }
        if point_id is not None:
            matches = [p for p in matches if p["point_id"] == point_id]
            if not matches:
                return {
                    "status": "not_found",
                    "message": "point_id not found for this postal code.",
                }
        if len(matches) > 1:
            return {
                "status": "ambiguous_location",
                "message": "Specify point_id to select a location.",
                "choices": [
                    {
                        "point_id": p["point_id"],
                        "name": p["point_name"],
                        "latitude": p["point_coordinates_wgs84_lat"],
                        "longitude": p["point_coordinates_wgs84_lon"],
                    }
                    for p in matches
                ],
            }
        point = matches[0]
        item = (item_loader or _forecast_item)()
        # An hourly parameter CSV covers every forecast point and can reach
        # 33 MB. Fetch one requested metric instead of three ~30 MB files.
        fields = (
            FORECAST_FIELDS["daily"]
            if granularity == "daily"
            else {metric: FORECAST_FIELDS["hourly"][metric]}
        )
        urls = {name: _asset(item, parameter) for name, (parameter, _) in fields.items()}
        series = {
            name: (values_loader or _forecast_values)(
                urls[name], point["point_id"], point["point_type_id"], parameter
            )
            for name, (parameter, _) in fields.items()
        }
        now = (clock or datetime.now)(UTC)
        if granularity == "daily":
            # Daily p0/pn/px parameters use local Swiss calendar days.
            from zoneinfo import ZoneInfo

            today = now.astimezone(ZoneInfo("Europe/Zurich")).date()
            timestamps = [
                (today + timedelta(days=i)).strftime("%Y%m%d0000") for i in range(periods)
            ]
        else:
            start = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            timestamps = [
                (start + timedelta(hours=i)).strftime("%Y%m%d%H%M") for i in range(periods)
            ]
        rows = []
        for stamp in timestamps:
            values = {name: series[name].get(stamp) for name in fields}
            if any(stamp in series[name] for name in fields):
                rows.append(
                    {
                        "valid_date" if granularity == "daily" else "valid_time_utc": (
                            stamp[:4] + "-" + stamp[4:6] + "-" + stamp[6:8]
                            if granularity == "daily"
                            else datetime.strptime(stamp, "%Y%m%d%H%M")
                            .replace(tzinfo=UTC)
                            .isoformat()
                        ),
                        **values,
                    }
                )
        return {
            "status": "answered" if rows else "no_data",
            "location": {
                "postal_code": postal_code,
                "point_id": point["point_id"],
                "name": point["point_name"],
                "latitude": point["point_coordinates_wgs84_lat"],
                "longitude": point["point_coordinates_wgs84_lon"],
            },
            "granularity": granularity,
            "units": {name: unit for name, (_, unit) in fields.items()},
            "values": rows,
            "forecast_item": item["id"],
            "forecast_updated_utc": item["properties"].get("updated"),
            "source_urls": urls,
            "attribution": SOURCE,
            "note": (
                "Daily dates are Swiss local calendar days (Europe/Zurich)."
                if granularity == "daily"
                else "Hourly timestamps are UTC interval ends; precipitation probability covers the preceding 3 hours."
            ),
        }
    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
        ValueError,
        KeyError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        return _failure(exc)


def _station_asset(
    item: dict,
    station: str,
    granularity: str,
    when: date | None,
    clock: Callable | None = None,
) -> str | None:
    code = {"10min": "t", "hourly": "h", "daily": "d"}[granularity]
    assets = item["assets"]
    prefix = f"ogd-smn_{station.lower()}_{code}_"
    today = (clock or datetime.now)(UTC).date()
    if when is None or when == today and granularity != "daily":
        suffix = "recent.csv" if granularity == "daily" else "now.csv"
        name = prefix + suffix
    elif when.year == today.year:
        name = prefix + "recent.csv"
    else:
        historic = [k for k in assets if k.startswith(prefix + "historical")]
        name = next(
            (
                k
                for k in historic
                if (range_match := re.search(r"(\d{4})-(\d{4})\.csv$", k))
                and int(range_match[1]) <= when.year <= int(range_match[2])
            ),
            None,
        )
        if name is None and code == "d":
            name = prefix + "historical.csv"
    return assets.get(name, {}).get("href") if name else None


def _observations(
    station_id: str,
    granularity: str,
    on_date: str | None,
    json_reader: Callable | None = None,
    csv_reader: Callable | None = None,
    clock: Callable | None = None,
) -> dict:
    if not re.fullmatch(r"[A-Za-z]{3}", station_id):
        return {
            "status": "invalid_input",
            "message": "station_id must be a three-letter MeteoSwiss station code (e.g. BER).",
        }
    if granularity not in OBSERVATION_FIELDS:
        return {
            "status": "invalid_input",
            "message": "granularity must be 10min, hourly, or daily.",
        }
    try:
        when = date.fromisoformat(on_date) if on_date is not None else None
    except ValueError:
        return {"status": "invalid_input", "message": "on_date must be an ISO date (YYYY-MM-DD)."}
    if when and when > (clock or datetime.now)(UTC).date():
        return {"status": "invalid_input", "message": "on_date cannot be in the future."}
    station = station_id.upper()
    try:
        item = (json_reader or _json)(f"{STAC}/{STATION_COLLECTION}/items/{station.lower()}")
        url = _station_asset(item, station, granularity, when, clock)
        if not url:
            return {
                "status": "no_data",
                "message": "No file for this station, date and granularity.",
            }
        fields = OBSERVATION_FIELDS[granularity]
        rows = []
        for row in (csv_reader or _csv_rows)(url, "cp1252"):
            if row["station_abbr"] != station:
                continue
            timestamp = datetime.strptime(row["reference_timestamp"], "%d.%m.%Y %H:%M").replace(
                tzinfo=UTC
            )
            if when and timestamp.date() != when:
                continue
            rows.append(
                {
                    "time_utc": timestamp.isoformat(),
                    **{name: _number(row.get(parameter)) for name, parameter in fields.items()},
                }
            )
        if when is None:
            rows = rows[-1:]
        return {
            "status": "answered" if rows else "no_data",
            "station_id": station,
            "station_name": item["properties"].get("title"),
            "granularity": granularity,
            "values": rows,
            "source_url": url,
            "attribution": SOURCE,
            "note": (
                "UTC daily dates refer to the start of the aggregation interval; precipitation is for 00:00–24:00 UTC."
                if granularity == "daily"
                else "UTC timestamps refer to the end of the observation interval."
            ),
        }
    except HTTPError as exc:
        if exc.code == 404:
            return {"status": "not_found", "message": "MeteoSwiss station code not found."}
        return _failure(exc)
    except (URLError, TimeoutError, OSError, ValueError, KeyError, UnicodeError) as exc:
        return _failure(exc)


class MeteoSwissData:
    """Injectable MeteoSwiss transport and clock, shared by both queries."""

    def __init__(
        self,
        csv_reader: Callable = _csv_rows,
        json_reader: Callable = _json,
        clock: Callable = datetime.now,
    ) -> None:
        self.csv_reader = csv_reader
        self.json_reader = json_reader
        self.clock = clock

    def points(self) -> list[dict[str, str]]:
        return _points(self.csv_reader)

    def forecast_item(self) -> dict:
        return _forecast_item(self.json_reader, self.clock)

    def forecast_values(
        self, url: str, point_id: str, point_type_id: str, parameter: str
    ) -> dict[str, float | int | None]:
        return _forecast_values(url, point_id, point_type_id, parameter, self.csv_reader)


class MeteoSwissWeather:
    """Look up published forecasts and station observations."""

    def __init__(self, data: MeteoSwissData) -> None:
        self.data = data

    def forecast(
        self, postal_code: str, granularity: str, periods: int, point_id: str | None, metric: str
    ) -> dict:
        return _forecast(
            postal_code,
            granularity,
            periods,
            point_id,
            metric,
            self.data.points,
            self.data.forecast_item,
            self.data.forecast_values,
            self.data.clock,
        )

    def observations(self, station_id: str, granularity: str, on_date: str | None) -> dict:
        return _observations(
            station_id,
            granularity,
            on_date,
            self.data.json_reader,
            self.data.csv_reader,
            self.data.clock,
        )
