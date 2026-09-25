"""Crawl approved Swiss sources and retrieve saved evidence."""

from ..crawler import Crawler
from ..dashboard import ensure_running
from ..dashboard.status import get_status
from ..knowledge import KnowledgeBase
from ..server import mcp
from ..source_access import SourceAccess

sources = SourceAccess(Crawler, KnowledgeBase, get_status, ensure_running)


@mcp.tool
async def crawl_federal_sources(source: str | None = None) -> dict:
    """Refresh one approved federal source, or all federal sources."""
    return await sources.crawl("federal", source)


@mcp.tool
async def crawl_cantonal_sources(source: str | None = None) -> dict:
    """Refresh one approved cantonal source, or all cantonal sources."""
    return await sources.crawl("cantonal", source)


@mcp.tool
async def crawl_municipal_sources(source: str | None = None) -> dict:
    """Refresh one approved municipal source, or all municipal sources."""
    return await sources.crawl("municipal", source)


@mcp.tool
async def search_knowledge(query: str, limit: int = 5) -> dict:
    """Find saved official-source passages with citations and crawl dates."""
    return await sources.search(query, limit)


@mcp.tool
def get_source(level: str, source: str) -> dict:
    """Read the complete saved page for an approved source."""
    return sources.get(level, source)


@mcp.tool
def source_status() -> dict:
    """Report when each data source was last refreshed, its age, and any failed refresh."""
    return sources.source_status()


@mcp.tool
def open_dashboard() -> dict:
    """Start the local data-source dashboard (status table and refresh buttons) and return its URL."""
    return sources.open_dashboard()
