"""Swiss place search and current administrative context from map.geo.admin.ch."""

import asyncio
import html
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

from ..server import mcp
from ._public_api import request_json, unavailable

GEO_API = "https://api3.geo.admin.ch/rest/services/ech/"
MUNICIPALITY = "ch.swisstopo.swissboundaries3d-gemeinde-flaeche.fill"
CANTON = "ch.swisstopo.swissboundaries3d-kanton-flaeche.fill"
POSTAL = "ch.swisstopo-vd.ortschaftenverzeichnis_plz"


def _search_locations(query: str, limit: int) -> dict:
    if not query.strip() or len(query) > 100 or len(query.split()) > 10 or not 1 <= limit <= 10:
        return {
            "status": "invalid_input",
            "message": "Use 1–10 words (up to 100 characters) and limit 1–10.",
        }
    url = (
        GEO_API
        + "SearchServer?"
        + urlencode({"searchText": query.strip(), "type": "locations", "limit": limit, "sr": 4326})
    )
    try:
        results = request_json(url)["results"]
        return {
            "status": "answered" if results else "no_data",
            "locations": [
                {
                    "name": html.unescape(re.sub(r"<[^>]+>", "", item["attrs"].get("label", ""))),
                    "type": item["attrs"].get("origin"),
                    "latitude": item["attrs"].get("lat"),
                    "longitude": item["attrs"].get("lon"),
                }
                for item in results
            ],
            "source_url": url,
            "source": "swisstopo / geo.admin.ch",
            "note": "Results may be places, ZIP areas or addresses; use coordinates with swiss_geo_context for administrative boundaries.",
        }
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as exc:
        return unavailable(exc)


def _context(latitude: float, longitude: float) -> dict:
    if not 45 <= latitude <= 48.5 or not 5.5 <= longitude <= 11:
        return {
            "status": "invalid_input",
            "message": "Use WGS84 coordinates within Switzerland (latitude, longitude).",
        }
    url = (
        GEO_API
        + "MapServer/identify?"
        + urlencode(
            {
                "geometry": f"{longitude},{latitude}",
                "geometryType": "esriGeometryPoint",
                "layers": f"all:{MUNICIPALITY},{CANTON},{POSTAL}",
                "sr": 4326,
                "tolerance": 0,
                "returnGeometry": "false",
                "limit": 200,
            }
        )
    )
    try:
        results = request_json(url)["results"]
        current = next(
            (
                r["attributes"]
                for r in results
                if r["layerBodId"] == MUNICIPALITY
                and r["attributes"].get("is_current_jahr") is True
            ),
            None,
        )
        canton = next((r["attributes"] for r in results if r["layerBodId"] == CANTON), None)
        postals = [r["attributes"] for r in results if r["layerBodId"] == POSTAL]
        return {
            "status": "answered" if current or canton or postals else "no_data",
            "latitude": latitude,
            "longitude": longitude,
            "municipality": (
                {
                    "name": current.get("gemname"),
                    "bfs_number": current.get("gde_nr"),
                    "boundary_year": current.get("jahr"),
                }
                if current
                else None
            ),
            "canton": ({"code": canton.get("ak"), "name": canton.get("name")} if canton else None),
            "postal_areas": [
                {"postal_code": str(p["plz"]), "name": p.get("langtext")} for p in postals
            ],
            "source_url": url,
            "map_url": "https://map.geo.admin.ch/#/map?"
            + urlencode(
                {
                    "lang": "en",
                    "swisssearch": f"{longitude},{latitude}",
                    "swisssearch_autoselect": "true",
                }
            ),
            "source": "swisstopo / geo.admin.ch",
            "note": "Boundaries are based on the current-year feature; postal areas and municipalities do not always coincide.",
        }
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as exc:
        return unavailable(exc)


@mcp.tool
async def swiss_geo_search(query: str, limit: int = 5) -> dict:
    """Search Swiss addresses, ZIP codes, municipalities and place names.

    Returns WGS84 coordinates for follow-up spatial queries.
    API: https://api3.geo.admin.ch/rest/services/ech/SearchServer
    """
    return await asyncio.to_thread(_search_locations, query, limit)


@mcp.tool
async def swiss_geo_context(latitude: float, longitude: float) -> dict:
    """Look up the current Swiss municipality (BFS code), canton and postal area at a WGS84 point.

    Coordinates can come from swiss_geo_search. Historical municipality
    boundaries are excluded. API: https://api3.geo.admin.ch/rest/services/ech/MapServer/identify
    """
    return await asyncio.to_thread(_context, latitude, longitude)
