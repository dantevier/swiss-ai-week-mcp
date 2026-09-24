"""
Tools module for the MCP Boilerplate server.

Import all tool modules to register them with the MCP server. Only
`company_info` is registered (docs/prd-zefix-company-info.md S6): the
boilerplate demo tools (math, text, utility, tax) stay on disk, unregistered,
so the jury sees a single, well-grounded tool.
"""

from . import company_info

__all__ = ["company_info"]
