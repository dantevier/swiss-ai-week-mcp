"""Federal political-rights rules sourced directly from the Federal Chancellery."""

import asyncio
import re
from urllib.error import HTTPError, URLError

from ..server import mcp
from ._authority_pages import fetch_page, paragraph
from ._public_api import unavailable

PAGES = {
    "initiative": ("https://www.bk.admin.ch/de/volksinitiativen", "Volksinitiativen"),
    "referendum": ("https://www.bk.admin.ch/de/referenden", "Referenden"),
    "national_council": ("https://www.bk.admin.ch/de/nationalratswahlen", "Nationalratswahlen"),
    "petition": ("https://www.bk.admin.ch/de/petitionen", "Petitionen"),
    "federal_vote": ("https://www.bk.admin.ch/de/volksabstimmungen", "Volksabstimmungen"),
}


def _rules(topic: str) -> dict:
    if topic not in PAGES:
        return {"status": "invalid_input", "message": f"topic must be one of: {', '.join(PAGES)}."}
    url, title = PAGES[topic]
    try:
        page = fetch_page(url, title)
        if topic == "initiative":
            evidence = paragraph(page, "18 Monaten", "Unterschriften")
            if not re.search(r"100\s*000 gültige Unterschriften", evidence):
                raise ValueError("Initiative threshold changed")
            details = {"signatures_required": 100000, "collection_period_months": 18}
        elif topic == "referendum":
            evidence = paragraph(page, "100 Tagen", "Unterschriften")
            if not re.search(r"50\s*000 gültige Unterschriften", evidence):
                raise ValueError("Referendum threshold changed")
            details = {"signatures_required": 50000, "collection_period_days": 100}
        elif topic == "national_council":
            evidence = paragraph(page, "18. Altersjahr", "Ständeratswahlen")
            details = {"federal_voting_age": 18, "council_of_states_rules": "cantonal"}
        elif topic == "petition":
            evidence = paragraph(page, "Jede Person", "Nationalität")
            details = {"open_to_all_ages_and_nationalities": True}
        else:
            evidence = paragraph(page, "mindestens vier Monate", "Abstimmungstermin")
            details = {
                "note": "Federal Council sets ballot questions at least four months before a federal vote; this page does not list confirmed vote dates or ballots."
            }
        return {
            "status": "answered",
            "topic": topic,
            **details,
            "source_excerpt_de": evidence,
            "source_language": "de",
            "source_url": page["source_url"],
            "fetched_at_utc": page["fetched_at_utc"],
            "scope": "Federal level only; Council of States and cantonal/municipal elections follow cantonal rules.",
        }
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as exc:
        return unavailable(exc)


@mcp.tool
async def swiss_federal_political_rights(topic: str) -> dict:
    """Look up BK/FCh rules for initiative, referendum, national_council, petition, federal_vote.

    Returns the relevant federal threshold or eligibility rule and a verbatim
    German paragraph from bk.admin.ch. No unconfirmed vote dates or ballots.
    Source: https://www.bk.admin.ch/de/politische-rechte
    """
    return await asyncio.to_thread(_rules, topic)
