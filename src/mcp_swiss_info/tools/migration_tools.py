"""SEM residence and employment MCP tool registration."""

import asyncio

from ..authority_pages import fetch_page
from ..migration import Migration
from ..server import mcp

migration = Migration(fetcher=fetch_page)


@mcp.tool
async def swiss_residence_permit_guidance(group: str, topic: str = "residence") -> dict:
    """Retrieve relevant SEM residence/work guidance for EU/EFTA, third-country or UK nationals.

    group: eu_efta, third_country, uk. topic: residence; eu_efta L/B/C/G;
    third_country work, L_B_C (card format only), F/N/S. UK: residence.
    Returns sourced paragraphs, not a permit approval or nationality inference.
    Source: https://www.sem.admin.ch/sem/en/home/themen/aufenthalt.html
    """
    return await asyncio.to_thread(migration.guidance, group, topic)
