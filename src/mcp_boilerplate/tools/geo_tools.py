"""Swiss map and administrative-boundary MCP tool registration."""

import asyncio

from ..geodata import SwissGeodata
from ..public_api import request_json
from ..server import mcp

geodata = SwissGeodata(requester=request_json)


@mcp.tool
async def swiss_geo_search(query: str, limit: int = 5) -> dict:
    """Search Swiss addresses, ZIP codes, municipalities and place names.

    Returns WGS84 coordinates for follow-up spatial queries.
    API: https://api3.geo.admin.ch/rest/services/ech/SearchServer
    """
    return await asyncio.to_thread(geodata.search, query, limit)


@mcp.tool
async def swiss_geo_context(latitude: float, longitude: float) -> dict:
    """Look up the current Swiss municipality (BFS code), canton and postal area at a WGS84 point.

    Coordinates can come from swiss_geo_search. Historical municipality
    boundaries are excluded. API: https://api3.geo.admin.ch/rest/services/ech/MapServer/identify
    """
    return await asyncio.to_thread(geodata.context, latitude, longitude)
