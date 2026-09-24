"""MCP registration for live Swiss school holidays."""

from ..school_holiday import get_school_holidays
from ..server import mcp


@mcp.tool
async def swiss_school_holidays(
    canton: str,
    school_year: int | None = None,
    holiday_type: str | None = None,
    municipality: str | None = None,
) -> dict:
    """Fetch Swiss school holidays from OpenHolidays (CC BY 4.0; network required).

    canton: two-letter Swiss canton code (ZH) or ISO code (CH-ZH).
    school_year: starting year, e.g. 2026 means 2026/27; defaults to the
    current school year in Europe/Zurich (August 1 through July 31).
    holiday_type: optional case-insensitive name filter, e.g. summer or Sommerferien.
    municipality: optional exact municipality name or OpenHolidays subdivision code.
    Local variation requires a municipality; school types remain separate records.
    """
    return await get_school_holidays(canton, school_year, holiday_type, municipality)
