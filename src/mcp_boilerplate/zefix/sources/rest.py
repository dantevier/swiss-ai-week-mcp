"""Vendored and adapted from malkreide/register-mcp (MIT, Copyright (c) 2026 Hayal Oezkan).

Zefix web-endpoint enrichment client (docs/prd-zefix-company-info.md §6.3).

LINDAS (sources/lindas.py) is the primary, always-used Zefix source. This
module adds a single optional enrichment call, `firm_detail`, gated by
`enrichment_allowed()`: `GET {zefix_base_url}/firm/{ehraid}.json`. It never
performs a search (LINDAS resolves the entity) and it never reads or returns
`shabPub[].message`, which carries free-text SHAB wording that can include
person names (PRD §6.6, N2).

Adapted from register-mcp `server.py`: UID formatting (`_uid_format`,
L488-493), the canton code list (`CANTON_CODES`, L275-302), and the inline
firm-detail GET used by `zefix_get_company` (~L908). Stripped: the `mcp` SDK
tool decorators, markdown rendering, the Zefix search endpoint (not used
here), and module-level env parsing — configuration comes from `settings`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import httpx

from ...config.settings import settings
from .http import SourceUnavailable, classify_error, make_client

# Same 26 cantons as register-mcp's CANTON_CODES (server.py L275-302).
CANTON_CODES: frozenset[str] = frozenset(
    {
        "AG", "AI", "AR", "BE", "BL", "BS", "FR", "GE", "GL", "GR", "JU", "LU",
        "NE", "NW", "OW", "SG", "SH", "SO", "SZ", "TG", "TI", "UR", "VD", "VS",
        "ZG", "ZH",
    }
)

# Matches a normalised UID: "CHE" + 9 digits, no separators. This is the shape
# `normalize_uid` returns and the shape carried on `Company.uid` (lindas.py) /
# `Enrichment` lookups. register-mcp's own `UID_RE` (server.py L170) matches
# the *formatted* string instead; that check is folded into `normalize_uid`
# here via digit counting rather than a second regex.
UID_RE = re.compile(r"^CHE\d{9}$")

_UID_PREFIX_RE = re.compile(r"^[A-Z]{2,}")


def normalize_uid(raw: str | None) -> str | None:
    """Normalise a Swiss company UID to "CHE" + 9 digits, or None if invalid.

    Accepts "CHE-101.654.423", "CHE101654423", "che 101 654 423", and the bare
    "101.654.423" (assumed Swiss when no other country prefix is present).
    Rejects anything with a non-CHE alphabetic prefix (e.g. "DE...") or that
    does not resolve to exactly 9 digits.
    """
    if not raw:
        return None
    s = raw.strip().upper()
    if not s:
        return None
    if s.startswith("CHE"):
        digits = re.sub(r"[^0-9]", "", s[3:])
    else:
        if _UID_PREFIX_RE.match(s):
            return None  # some other alphabetic prefix, e.g. "DE123456789"
        digits = re.sub(r"[^0-9]", "", s)
    if len(digits) != 9:
        return None
    return f"CHE{digits}"


def format_uid(uid: str) -> str:
    """Inverse of `normalize_uid`: "CHE101654423" -> "CHE-101.654.423"."""
    digits = uid[3:]
    return f"CHE-{digits[0:3]}.{digits[3:6]}.{digits[6:9]}"


def zefix_detail_url(ehraid: int, language: str = "de") -> str:
    """Human-facing Zefix detail page for a company (verified A3 in the PRD)."""
    return f"https://www.zefix.admin.ch/{language}/search/entity/list/firm/{ehraid}"


def enrichment_allowed() -> bool:
    """Whether the Zefix web-endpoint enrichment call may run (PRD §6.5).

    Runs when robots/ToS compliance is turned off, or when credentials for the
    documented ZefixPublicREST API are configured (the credential grant is
    itself the ToS acceptance for that API).
    """
    return (not settings.respect_robots_txt) or bool(
        settings.zefix_username and settings.zefix_password
    )


@dataclass
class Enrichment:
    status: str | None = None
    shab_date: str | None = None
    delete_date: str | None = None
    cantonal_excerpt_url: str | None = None
    old_names: list[str] = field(default_factory=list)
    mutation_types: list[str] = field(default_factory=list)


def _mutation_types_newest_first(shab_pub: list) -> list[str]:
    """Flatten `shabPub[].mutationTypes[].key`, newest first, de-duplicated.

    Never reads `shabPub[].message` (may contain person names, PRD §6.6).
    Sorted explicitly by `shabDate` descending rather than trusting upstream
    order, then de-duplicated keeping the first (newest) occurrence of a key.
    """
    entries = [p for p in shab_pub if isinstance(p, dict)]
    entries.sort(key=lambda p: p.get("shabDate") or "", reverse=True)
    seen: set[str] = set()
    out: list[str] = []
    for pub in entries:
        for m in pub.get("mutationTypes", []) or []:
            if not isinstance(m, dict):
                continue
            key = m.get("key")
            if key and key not in seen:
                seen.add(key)
                out.append(key)
    return out


async def firm_detail(ehraid: int, *, budget_s: float) -> Enrichment:
    """GET {settings.zefix_base_url}/firm/{ehraid}.json.

    Basic auth is used when both `settings.zefix_username` and
    `settings.zefix_password` are set (documented ZefixPublicREST API);
    otherwise the call is anonymous (undocumented zefix.ch web endpoint).
    Raises `SourceUnavailable(source="zefix", ...)` on any HTTP error,
    timeout, or network failure. A 404 maps to error_class "http_404".
    """
    auth = None
    if settings.zefix_username and settings.zefix_password:
        auth = httpx.BasicAuth(settings.zefix_username, settings.zefix_password)

    url = f"{settings.zefix_base_url}/firm/{ehraid}.json"
    try:
        async with make_client(budget_s, auth=auth) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        error_class, retry_after_s = classify_error(exc)
        raise SourceUnavailable("zefix", error_class, retry_after_s=retry_after_s) from exc
    except httpx.TimeoutException as exc:
        error_class, retry_after_s = classify_error(exc)
        raise SourceUnavailable("zefix", error_class, retry_after_s=retry_after_s) from exc
    except httpx.RequestError as exc:
        error_class, retry_after_s = classify_error(exc)
        raise SourceUnavailable("zefix", error_class, retry_after_s=retry_after_s) from exc

    if not isinstance(data, dict):
        raise SourceUnavailable("zefix", "bad_response")

    old_names = [
        n.get("name")
        for n in (data.get("oldNames") or [])
        if isinstance(n, dict) and n.get("name")
    ]

    return Enrichment(
        status=data.get("status"),
        shab_date=data.get("shabDate"),
        delete_date=data.get("deleteDate"),
        cantonal_excerpt_url=data.get("cantonalExcerptWeb"),
        old_names=old_names,
        mutation_types=_mutation_types_newest_first(data.get("shabPub") or []),
    )
