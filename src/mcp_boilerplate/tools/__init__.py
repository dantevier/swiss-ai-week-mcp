"""
Tools module for the MCP Boilerplate server.

Import all tool modules to register them with the MCP server. Registered:
`company_info` (docs/prd-zefix-company-info.md), the Swiss commercial
register / SHAB grounding tool, and `health_insurance_tools` /
`source_tools`, the reviewed-source knowledge base and its crawl tools.
The generic boilerplate demo tools (math, text, utility, tax) stay on
disk, unregistered, so the jury sees only well-grounded, Swiss-specific
tools.
"""

from . import company_info, health_insurance_tools, source_tools

__all__ = ["company_info", "health_insurance_tools", "source_tools"]
