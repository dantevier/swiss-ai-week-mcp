"""SEM residence and employment guidance with citations to selected official pages."""

import asyncio
from urllib.error import HTTPError, URLError

from ..server import mcp
from ._authority_pages import fetch_page
from ._public_api import unavailable

BASE = "https://www.sem.admin.ch/sem/en/home/themen/"
EU = BASE + "aufenthalt/eu_efta/"
THIRD = BASE + "aufenthalt/nicht_eu_efta/"
PAGES = {
    "eu_efta": {
        "residence": (
            BASE + "fza_schweiz-eu-efta/eu-efta_buerger_schweiz.html",
            "EU/EFTA Citizens: Living and Working in Switzerland",
        ),
        "L": (EU + "ausweis_l_eu_efta.html", "L EU/EFTA permit (Short-term residents)"),
        "B": (EU + "ausweis_b_eu_efta.html", "B EU/EFTA permit (Resident foreign nationals)"),
        "C": (EU + "ausweis_c_eu_efta.html", "C EU/EFTA permit (Settled foreign nationals)"),
        "G": (EU + "ausweis_g_eu_efta.html", "G EU/EFTA permit (Cross-border commuters)"),
    },
    "third_country": {
        "residence": (
            BASE + "aufenthalt.html",
            "Residence",
        ),
        "work": (BASE + "arbeit/nicht-eu_efta-angehoerige.html", "Non-EU/EFTA nationals"),
        "L_B_C": (
            BASE + "aufenthalt/biometr_auslaenderausweis.html",
            "Biometric residence permits for foreign nationals",
        ),
        "F": (THIRD + "ausweis_f__vorlaeufig.html", "Permit F (provisionally admitted foreigners)"),
        "N": (THIRD + "ausweis_n__asylsuchende.html", "Permit N (permit for asylum-seekers)"),
        "S": (
            THIRD + "ausweis_s__schutzbeduerftige.html",
            "Permit S (people in need of protection)",
        ),
    },
    "uk": {
        "residence": (BASE + "arbeit/uk.html", "United Kingdom"),
    },
}


def _guidance(group: str, topic: str) -> dict:
    if group not in PAGES or topic not in PAGES[group]:
        return {
            "status": "invalid_input",
            "message": "Use eu_efta (residence/L/B/C/G), third_country (residence/work/L_B_C/F/N/S), or uk (residence). L_B_C describes the biometric card, not eligibility.",
        }
    url, title = PAGES[group][topic]
    try:
        page = fetch_page(url, title)
        # Only the opening source paragraphs describe the selected subject;
        # later paragraphs often contain document lists or unrelated news.
        paragraphs = []
        for tag, text in page["blocks"]:
            if tag != "p":
                continue
            if text.startswith("Last modification"):
                break
            if len(text) >= 40:
                paragraphs.append(text)
            if len(paragraphs) == 4:
                break
        if not paragraphs or sum(len(p) for p in paragraphs) < 40:
            raise ValueError("SEM page contains no useful guidance")
        return {
            "status": "answered",
            "group": group,
            "topic": topic,
            "source_excerpts": paragraphs,
            "source_url": page["source_url"],
            "fetched_at_utc": page["fetched_at_utc"],
            "note": "This describes an official SEM page, not a personal eligibility decision. Cantonal migration authorities issue residence permits. For UK nationals, pre-2021 acquired rights can differ from new arrivals.",
        }
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as exc:
        return unavailable(exc)


@mcp.tool
async def swiss_residence_permit_guidance(group: str, topic: str = "residence") -> dict:
    """Retrieve relevant SEM residence/work guidance for EU/EFTA, third-country or UK nationals.

    group: eu_efta, third_country, uk. topic: residence; eu_efta L/B/C/G;
    third_country work, L_B_C (card format only), F/N/S. UK: residence.
    Returns sourced paragraphs, not a permit approval or nationality inference.
    Source: https://www.sem.admin.ch/sem/en/home/themen/aufenthalt.html
    """
    return await asyncio.to_thread(_guidance, group, topic)
