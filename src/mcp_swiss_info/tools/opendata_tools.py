"""opendata.swiss catalogue MCP tool registration."""

import asyncio

from ..opendata_catalog import OpenDataCatalog
from ..public_api import request_json
from ..server import mcp

catalog = OpenDataCatalog(requester=request_json)


@mcp.tool
async def opendata_search_datasets(query: str, limit: int = 5, language: str = "en") -> dict:
    """Find Swiss federal, cantonal and municipal open datasets by topic.

    Returns dataset IDs, descriptions and publisher metadata, not data values.
    Search: https://ckan.opendata.swiss/api/3/action/package_search
    """
    return await asyncio.to_thread(catalog.search, query, limit, language)


@mcp.tool
async def opendata_dataset(dataset_id: str, language: str = "en", resource_start: int = 0) -> dict:
    """Get one opendata.swiss dataset's metadata and up to 20 resource links.

    Use resource_start=20, 40, etc. to page through the resource links.
    Resource rights and formats vary; this catalogue does not host the files.
    Lookup: https://ckan.opendata.swiss/api/3/action/package_show
    """
    return await asyncio.to_thread(catalog.dataset, dataset_id, language, resource_start)
