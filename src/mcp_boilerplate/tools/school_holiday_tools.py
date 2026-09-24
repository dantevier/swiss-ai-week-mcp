"""MCP registration for live Swiss school holidays."""

from fastmcp.tools import ToolResult

from ..school_holiday import SchoolHolidayService
from ..server import mcp


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True})
async def swiss_school_holidays(
    canton: str,
    school_year: int | None = None,
    holiday_type: str | None = None,
    municipality: str | None = None,
) -> ToolResult:
    """Fetch Swiss school holidays from OpenHolidays (CC BY 4.0; network required).

    canton: two-letter Swiss canton code (ZH) or ISO code (CH-ZH).
    school_year: starting year, e.g. 2026 means 2026/27; defaults to the
    current school year in Europe/Zurich (August 1 through July 31).
    holiday_type: optional case-insensitive name filter, e.g. summer or Sommerferien.
    municipality: optional exact municipality name or OpenHolidays subdivision code.
    Use for Swiss school holidays, not public or bank holidays.
    Local variation requires a municipality; school types remain separate records.
    """
    service = SchoolHolidayService()
    result = await service.get(canton, school_year, holiday_type, municipality)
    return ToolResult(content=service.format_result(result), structured_content=result)
