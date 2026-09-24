"""Local dashboard for the data sources behind the MCP tools.

Run with: uv run python -m mcp_boilerplate.dashboard
"""

from .server import app, ensure_running, main

__all__ = ["app", "ensure_running", "main"]
