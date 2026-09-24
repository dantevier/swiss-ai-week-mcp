"""`company_info` MCP tool registration (docs/prd-zefix-company-info.md).

The MCP surface only: signature, docstring, one delegate call. Resolution and
envelope assembly live in `zefix.lookup.CompanyLookup`.
"""

from __future__ import annotations

from typing import Any

from ..server import mcp
from ..zefix import CompanyLookup


@mcp.tool
async def company_info(
    question: str | None = None,
    name: str | None = None,
    uid: str | None = None,
    canton: str | None = None,
    language: str = "de",
    include_publications: bool = True,
    max_publications: int = 5,
) -> dict[str, Any]:
    """Look up a Swiss company in the federal commercial register index (Zefix)
    and its SHAB/FOSC/FUSC register publications.

    Scope: existence, legal form, seat/address, register status (active or
    deleted), and recent commercial-register gazette publications of a single
    Swiss company. Grounded in the Federal Office of Justice's official Zefix
    linked-data publication (LINDAS) plus, when policy allows, the Zefix web
    endpoint and the amtsblattportal.ch gazette. Not covered, ever: natural
    persons (board members, managing officers, signatories, auditors — this
    tool never reads or returns person data, PRD §6.6), VAT status, foreign
    registers, cantonal-extract full text, or aggregate/analytics queries
    ("how many...", "list all...") over the whole register.

    No parameter is mandatory. Pass whatever you have: `question` (the user's
    question verbatim — used to self-detect wrong-topic, jurisdiction,
    person, and analytics questions before any lookup), `name` (company name
    or a prefix of it), `uid` (CHE-xxx.xxx.xxx, dashes/dots optional), and/or
    `canton` (a 2-letter code) to narrow an ambiguous name. If both `name`
    and `uid` are missing, the tool asks back for the company name instead of
    failing; it never requires a parameter the caller may not have.
    `language` is "de" | "fr" | "it" | "en" (default "de"); "rm" (Romansh) is
    answered in German with a note, since none of the upstream sources
    publish Romansh data. `include_publications` attaches the last
    `max_publications` (1-20, default 5) gazette entries for the resolved
    company; set it False to skip that call.

    Always returns one of exactly five states in the `status` field:
    - "answered": the company was found; `company`, `citation`, and
      (optionally) `publications` are populated. `company.status` is
      "ACTIVE" or "DELETED"; when no live-status enrichment ran, "ACTIVE"
      means "present in the active-entity index", not a freshly confirmed
      status, and `assumptions` says so explicitly.
    - "need_info": the name is ambiguous (or missing) and the tool asks back
      for exactly one more thing (a UID, canton, or seat) with up to 5
      candidates.
    - "no_match": the index holds no such company (and, when a UID was given
      and a matching gazette deletion notice exists instead, "answered" with
      a derived DELETED status is returned rather than "no_match").
    - "out_of_scope": the question is about persons, a foreign
      jurisdiction, register-wide analytics, or an unrelated topic.
    - "source_unavailable": an upstream source could not be reached. This is
      never accompanied by a cached or stale company record.

    This is a live proxy: every call hits upstream sources fresh, nothing is
    persisted or cached across calls except tiny reference data (legal-form
    labels, the LINDAS freshness date, the gazette rubric taxonomy).
    """
    return await CompanyLookup().lookup(
        question=question,
        name=name,
        uid=uid,
        canton=canton,
        language=language,
        include_publications=include_publications,
        max_publications=max_publications,
    )
