"""BFS statistics MCP tool registration."""

import asyncio

from ..bfs import BFSStatistics
from ..public_api import request_json
from ..server import mcp

statistics = BFSStatistics(requester=request_json)


@mcp.tool
async def bfs_population(
    canton: str = "CH",
    start_year: int | None = None,
    end_year: int | None = None,
    population_type: str = "permanent",
    sex: str = "total",
) -> dict:
    """Get official FSO/BFS annual population for Switzerland or a canton.

    canton: CH or a two-letter canton code (e.g. BE, GE). Defaults to the
    latest published year. Specify start_year/end_year for up to ten years.
    Population type: permanent or non_permanent. Sex: total, male, female.
    Data: https://www.pxweb.bfs.admin.ch/api/v1/en/px-x-0103010000_101/px-x-0103010000_101.px
    """
    return await asyncio.to_thread(
        statistics.population, canton, start_year, end_year, population_type, sex
    )
