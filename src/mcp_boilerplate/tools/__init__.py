"""
Tools module for the MCP Boilerplate server.

Import all tool modules to register them with the MCP server. Registered:
`company_info` (docs/prd-zefix-company-info.md), the Swiss commercial
register / SHAB grounding tool; `health_insurance_tools` / `source_tools`,
the reviewed-source knowledge base and its crawl tools; and the public-data
tools (`bfs_tools`, `customs_tools`, `geo_tools`, `migration_tools`,
`opendata_tools`, `political_rights_tools`, `weather_tools`).
The generic boilerplate demo tools (math, text, utility, tax) stay on
disk, unregistered, so the jury sees only well-grounded, Swiss-specific
tools.
"""

from . import (
    bfs_tools,
    company_info,
    customs_tools,
    geo_tools,
    health_insurance_tools,
    migration_tools,
    opendata_tools,
    political_rights_tools,
    source_tools,
    weather_tools,
)

__all__ = [
    "bfs_tools",
    "company_info",
    "customs_tools",
    "geo_tools",
    "health_insurance_tools",
    "migration_tools",
    "opendata_tools",
    "political_rights_tools",
    "source_tools",
    "weather_tools",
]
