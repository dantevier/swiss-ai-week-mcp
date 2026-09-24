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
    """Get one Swiss company's register facts from Zefix (official, via LINDAS).

    Answers existence, legal form, seat/address, ACTIVE/DELETED status and
    recent SHAB gazette publications (amtsblattportal.ch). Never answers:
    natural persons, VAT, foreign registers, register-wide analytics.
    No parameter is mandatory: pass question verbatim plus any of name,
    uid (CHE-xxx.xxx.xxx), canton (2-letter). language: de|fr|it|en (rm is
    answered in de). include_publications; max_publications 1-20.
    status: answered | need_info | no_match | out_of_scope | source_unavailable.
    Live proxy; company records are never cached. Contract: docs/prd-zefix-company-info.md
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
