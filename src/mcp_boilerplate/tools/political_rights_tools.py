"""Federal Chancellery political-rights MCP tool registration."""

import asyncio

from ..authority_pages import fetch_page
from ..political_rights import PoliticalRights
from ..server import mcp

political_rights = PoliticalRights(fetcher=fetch_page)


@mcp.tool
async def swiss_federal_political_rights(topic: str) -> dict:
    """Look up BK/FCh rules for initiative, referendum, national_council, petition, federal_vote.

    Returns the relevant federal threshold or eligibility rule and a verbatim
    German paragraph from bk.admin.ch. No unconfirmed vote dates or ballots.
    Source: https://www.bk.admin.ch/de/politische-rechte
    """
    return await asyncio.to_thread(political_rights.rules, topic)
