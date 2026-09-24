"""
Tools module for the MCP Boilerplate server.

Import all tool modules to register them with the MCP server.
"""

# Import all tool modules - the decorators will register them automatically
from . import (
    bfs_tools,
    customs_tools,
    geo_tools,
    health_insurance_tools,
    migration_tools,
    opendata_tools,
    political_rights_tools,
    source_tools,
    weather_tools,
)

# Export the tool modules for potential external use
__all__ = [
    "bfs_tools",
    "customs_tools",
    "geo_tools",
    "health_insurance_tools",
    "migration_tools",
    "opendata_tools",
    "political_rights_tools",
    "source_tools",
    "weather_tools",
]
