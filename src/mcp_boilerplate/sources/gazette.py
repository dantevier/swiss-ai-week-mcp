"""Vendored and adapted from malkreide/register-mcp (MIT, Copyright (c) 2026 Hayal Oezkan).

Amtsblattportal (SHAB + cantonal gazettes) client (docs/prd-zefix-company-info.md
§6.4). UID-scoped publication lookups only — no free-text or person-name search
(PRD N3); `content` (the publication full text/XML) is never fetched or read.

Adapted from register-mcp `server.py`:
  - constants + retry policy                         L153-264
  - `_handle_http_error`                              L419-444 (folded into SourceUnavailable mapping)
  - gazette HTTP core / allow-list / plausibility guard / rubric cache  L1398-1600
  - `_gazette_meta_summary`                           L1607-1628
Stripped: the `mcp` SDK tool decorators, markdown rendering, module-level env
parsing (configuration comes from `settings`), and the `rubric`/`sub_rubric`
filter arguments on the public search entry point (`publications_for_uid` is
UID-scoped only, per the PRD).

Three upstream quirks, guarded here as in register-mcp:
  Quirk 1 (Silent Ignore)  An unknown query parameter is dropped silently and
                            the call returns the *whole* ~2.8M-publication
                            corpus with HTTP 200 instead of 400. Guarded by
                            `ALLOWED_GAZETTE_PARAMS` (params are only ever
                            built from this allow-list) and the plausibility
                            check in `_gazette_search` (raises
                            `GazetteFilterIgnored` if `total` implies the
                            filter was ignored).
  Quirk 2 (Silent Empty)   An invalid rubric/subRubric code returns HTTP 200
                            with an empty result, indistinguishable from a
                            real no-hit. Guarded by `_validate_rubric_code`,
                            which checks a code against the cached taxonomy
                            before it is ever sent upstream.
  Quirk 3 (Two-step fetch) The publications list endpoint returns metadata
                            only; the full text lives behind a separate XML
                            call. This module never makes that second call —
                            `content` is always None here.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from time import monotonic
from typing import Any

import httpx

from ..config.settings import settings
from .http import SourceUnavailable, classify_error, make_client

# ---------------------------------------------------------------------------
# Constants (register-mcp server.py L153-264)
# ---------------------------------------------------------------------------

# Known corpus size (register-mcp GAZETTE_CORPUS_SIZE, server.py L119) and the
# plausibility ratio/threshold used by the Quirk-1 guard.
GAZETTE_CORPUS_SIZE = 2_809_194
GAZETTE_IGNORED_FILTER_RATIO = 0.95
GAZETTE_IGNORED_FILTER_THRESHOLD = int(GAZETTE_CORPUS_SIZE * GAZETTE_IGNORED_FILTER_RATIO)

# Query parameters are built EXCLUSIVELY from this allow-list (Quirk 1 guard).
# Confirmed live 2026-09-24: the real query key for the UID filter is `uids`
# (plural) even for a single value — `uid` (singular) is silently dropped and
# returns the full corpus. `keyword` and `cantons` are deliberately NOT
# allow-listed: this client only performs UID-scoped lookups (PRD N3).
ALLOWED_GAZETTE_PARAMS: frozenset[str] = frozenset(
    {
        "publicationStates",
        "uids",
        "rubrics",
        "subRubrics",
        "publicationDate.start",
        "publicationDate.end",
        "pageRequest.size",
        "pageRequest.page",
    }
)

GAZETTE_MAX_LIMIT = 100

# Transient upstream errors that warrant a retry.
_TRANSIENT_STATUS = frozenset({502, 503, 504})
_RETRYABLE_STATUS = _TRANSIENT_STATUS | {429}

GAZETTE_MAX_RETRIES = 3
GAZETTE_RETRY_BACKOFF = 0.5

# Ceiling on a single wait.
GAZETTE_MAX_DELAY_S = 20.0

# Jitter on the linear backoff curve: lands in [0.5x, 1.5x] so clients hitting
# the same outage do not retry in lockstep.
GAZETTE_JITTER_SPREAD = 0.5

# One-sided jitter applied on top of a `Retry-After` hint: lands in
# [1.0x, 1.25x] — later is polite, earlier ignores what the gazette said.
GAZETTE_RETRY_AFTER_JITTER = 0.25

# Statuses carrying a meaningful `Retry-After` (RFC 9110 §10.2.3).
GAZETTE_RETRY_AFTER_STATUSES = frozenset({429, 503})


def parse_retry_after(resp: httpx.Response | None) -> float | None:
    """Seconds to wait per the response's `Retry-After`, or None.

    RFC 9110 §10.2.3 allows delta-seconds and an HTTP-date; both occur, both
    are read. Anything unparseable yields None so the caller falls back to
    its own backoff curve.
    """
    if resp is None or resp.status_code not in GAZETTE_RETRY_AFTER_STATUSES:
        return None
    raw = (resp.headers.get("Retry-After") or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return float(raw)
    try:
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    if when.tzinfo is None:  # RFC 9110 dates are GMT; a naive one means UTC
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - datetime.now(UTC)).total_seconds())


def gazette_retry_delay(attempt: int, resp: httpx.Response | None) -> float:
    """Seconds to wait after the failed `attempt` (1-based).

    A `Retry-After` from the gazette wins over the linear backoff guess.
    """
    hinted = parse_retry_after(resp)
    if hinted is not None:
        jittered = hinted * (1.0 + random.random() * GAZETTE_RETRY_AFTER_JITTER)
    else:
        jittered = (GAZETTE_RETRY_BACKOFF * attempt) * (
            1.0 - GAZETTE_JITTER_SPREAD + random.random() * 2 * GAZETTE_JITTER_SPREAD
        )
    return min(jittered, GAZETTE_MAX_DELAY_S)  # cap AFTER jitter


class GazetteFilterIgnored(Exception):
    """Raised when the upstream silently ignored a filter (Quirk 1)."""


class GazetteInvalidCode(ValueError):
    """Raised when a rubric/subRubric code is not in the taxonomy (Quirk 2)."""


# ---------------------------------------------------------------------------
# Deletion sub-rubrics (A6)
# ---------------------------------------------------------------------------

# Fetched live from https://amtsblattportal.ch/api/v1/rubrics on 2026-09-24.
# The "HR" rubric ("Handelsregistereintragungen") has exactly three
# sub-rubrics: HR01 "Neueintrag" (new entry), HR02 "Mutation" (change), and
# HR03 "Löschung" (deletion). Only HR03 means deletion.
DELETION_SUBRUBRICS: frozenset[str] = frozenset({"HR03"})


@dataclass
class Publication:
    id: str
    date: str  # YYYY-MM-DD, from meta.publicationDate
    registry_office: str | None  # meta.registrationOffice.displayName
    registry_canton: str | None  # meta.cantons[0] if present, else None
    rubric: str | None
    sub_rubric: str | None
    title: str | None  # meta.title[language], fallback de
    source_url: str  # public SPA route: https://amtsblattportal.ch/#!/search?publicationId={id}
    api_url: str  # fallback machine-readable route: {gazette_base_url}/publications/{id}/xml


def is_deletion(pub: Publication) -> bool:
    return pub.sub_rubric in DELETION_SUBRUBRICS


# ---------------------------------------------------------------------------
# HTTP core with retry (ARCH-014 in register-mcp; server.py L1398-1480)
# ---------------------------------------------------------------------------


async def _gazette_get_json(path: str, params: dict[str, Any] | None, *, budget_s: float) -> Any:
    """GET a gazette JSON endpoint, retrying what is worth retrying.

    Retried: transient 5xx (502/503/504), 429, and network errors/timeouts —
    the case an actual outage produces. Not retried: any other 4xx, which is
    a statement about the request and reads the same on a third try.
    `Retry-After` is honoured, attempts are capped at `GAZETTE_MAX_RETRIES`,
    and the whole call (every attempt, every wait) is bounded by `budget_s`.

    Raises `SourceUnavailable(source="gazette", ...)` if no attempt succeeds
    within the budget.
    """
    deadline = monotonic() + budget_s
    last_exc: Exception | None = None
    last_resp: httpx.Response | None = None

    async with make_client(budget_s) as client:
        for attempt in range(1, GAZETTE_MAX_RETRIES + 1):
            remaining = deadline - monotonic()
            if remaining <= 0:
                break
            try:
                async with asyncio.timeout(remaining):
                    resp = await client.get(
                        f"{settings.gazette_base_url}{path}", params=params, timeout=remaining
                    )
            except TimeoutError as exc:
                # The asyncio deadline fired, so the budget is spent by
                # definition — no point retrying into a budget of zero.
                raise SourceUnavailable("gazette", "timeout") from exc
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt >= GAZETTE_MAX_RETRIES:
                    break
                delay = gazette_retry_delay(attempt, None)
                if delay >= deadline - monotonic():
                    break
                await asyncio.sleep(delay)
                continue

            if resp.status_code in _RETRYABLE_STATUS and attempt < GAZETTE_MAX_RETRIES:
                last_resp = resp
                delay = gazette_retry_delay(attempt, resp)
                if delay < deadline - monotonic():
                    await asyncio.sleep(delay)
                    continue
                break
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                last_resp = resp
                break
            return resp.json()

    if last_exc is not None:
        error_class, retry_after_s = classify_error(last_exc)
        raise SourceUnavailable("gazette", error_class, retry_after_s=retry_after_s) from last_exc
    error_class, retry_after_s = (
        classify_error(httpx.HTTPStatusError("", request=None, response=last_resp))
        if last_resp is not None
        else ("timeout", None)
    )
    raise SourceUnavailable("gazette", error_class, retry_after_s=retry_after_s)


def _build_gazette_params(raw: dict[str, Any]) -> dict[str, Any]:
    """Build the query dict EXCLUSIVELY from `ALLOWED_GAZETTE_PARAMS` (Quirk 1)."""
    params: dict[str, Any] = {"publicationStates": "PUBLISHED"}
    for key, value in raw.items():
        if value in (None, "", []):
            continue
        if key not in ALLOWED_GAZETTE_PARAMS:
            continue  # defensive: drop anything not explicitly allowed
        params[key] = value
    return params


async def _gazette_search(raw_params: dict[str, Any], *, budget_s: float) -> dict:
    """Run a /publications search and enforce the Quirk-1 plausibility check."""
    params = _build_gazette_params(raw_params)
    data = await _gazette_get_json("/publications", params, budget_s=budget_s)
    if not isinstance(data, dict):
        return {"content": [], "total": 0}
    total = data.get("total")
    if isinstance(total, int) and total > GAZETTE_IGNORED_FILTER_THRESHOLD:
        raise GazetteFilterIgnored(
            f"Filter was silently ignored upstream — result not trustworthy "
            f"(total={total:,}, expected < {GAZETTE_IGNORED_FILTER_THRESHOLD:,}). "
            "Cause: Silent Ignore of an unrecognised parameter (Quirk 1)."
        )
    return data


# ---------------------------------------------------------------------------
# Rubric taxonomy — cached settings.reference_cache_ttl_s (Quirk 2 guard)
# ---------------------------------------------------------------------------

_rubrics_cache: tuple[float, list[dict]] | None = None


async def _fetch_rubrics(*, budget_s: float = 10.0) -> tuple[list[dict], bool]:
    """Fetch the rubric/subRubric taxonomy with a TTL cache.

    Returns (data, from_cache).
    """
    global _rubrics_cache
    now = monotonic()
    if _rubrics_cache and now - _rubrics_cache[0] < settings.reference_cache_ttl_s:
        return _rubrics_cache[1], True
    data = await _gazette_get_json("/rubrics", None, budget_s=budget_s)
    if not isinstance(data, list):
        data = []
    _rubrics_cache = (now, data)
    return data, False


def _extract_rubric_codes(rubrics_data: list[dict]) -> tuple[set[str], set[str]]:
    """Return (rubric_codes, subRubric_codes) from the taxonomy, defensively."""
    rubric_codes: set[str] = set()
    sub_codes: set[str] = set()
    for r in rubrics_data:
        if not isinstance(r, dict):
            continue
        code = r.get("code")
        if code:
            rubric_codes.add(code)
        for s in r.get("subRubrics", []) or []:
            if isinstance(s, dict) and s.get("code"):
                sub_codes.add(s["code"])
    return rubric_codes, sub_codes


async def _validate_rubric_code(code: str, kind: str, *, budget_s: float = 10.0) -> None:
    """Validate a rubric/subRubric code against the cached taxonomy (Quirk 2).

    An invalid code returns HTTP 200 with an empty result upstream, which is
    indistinguishable from a legitimate no-hit — so codes are validated
    before any `/publications` call that filters on them.
    """
    rubrics_data, _ = await _fetch_rubrics(budget_s=budget_s)
    rubric_codes, sub_codes = _extract_rubric_codes(rubrics_data)
    valid = rubric_codes if kind == "rubric" else sub_codes
    if code not in valid:
        raise GazetteInvalidCode(f"Invalid {kind} code {code!r}.")


async def rubrics() -> dict:
    """The gazette rubric/subRubric taxonomy, cached `settings.reference_cache_ttl_s`."""
    data, from_cache = await _fetch_rubrics()
    rubric_codes, sub_codes = _extract_rubric_codes(data)
    return {
        "rubrics": data,
        "rubric_codes": sorted(rubric_codes),
        "sub_rubric_codes": sorted(sub_codes),
        "from_cache": from_cache,
    }


# ---------------------------------------------------------------------------
# Publication parsing (register-mcp `_gazette_meta_summary`, L1607-1628)
# ---------------------------------------------------------------------------


def _publication_from_item(item: dict, *, language: str) -> Publication:
    meta = item.get("meta") if isinstance(item, dict) else None
    meta = meta if isinstance(meta, dict) else {}

    pub_id = meta.get("id") or ""

    date = meta.get("publicationDate")
    if isinstance(date, str) and "T" in date:
        date = date.split("T", 1)[0]

    ro = meta.get("registrationOffice")
    registry_office = ro.get("displayName") if isinstance(ro, dict) else None

    # Confirmed live 2026-09-24 (gazette /publications): `cantons` is a field
    # of `meta` directly, e.g. meta.cantons == ["NE"]. It is NOT nested under
    # `registrationOffice` — the recorded fixture (gazette_search.json) and a
    # live probe against amtsblattportal.ch both show `registrationOffice`
    # without a `cantons` key, and `cantons` as a sibling of it on `meta`.
    cantons = meta.get("cantons")
    registry_canton = cantons[0] if isinstance(cantons, list) and cantons else None

    title = meta.get("title")
    if isinstance(title, dict):
        title = title.get(language) or title.get("de") or next(iter(title.values()), None)

    return Publication(
        id=pub_id,
        date=date or "",
        registry_office=registry_office,
        registry_canton=registry_canton,
        rubric=meta.get("rubric"),
        sub_rubric=meta.get("subRubric"),
        title=title,
        source_url=f"https://amtsblattportal.ch/#!/search?publicationId={pub_id}",
        api_url=f"{settings.gazette_base_url}/publications/{pub_id}/xml",
    )


def _format_uid_for_query(uid: str) -> str:
    """"CHE101654423" -> "CHE-101.654.423".

    Confirmed live 2026-09-24: the gazette's `uids` filter only matches the
    dashed/dotted formatted UID; the unformatted 9-digit form returns zero
    results (not an error — a silent miss).
    """
    digits = uid[3:] if uid.startswith("CHE") else uid
    if len(digits) == 9 and digits.isdigit():
        return f"CHE-{digits[0:3]}.{digits[3:6]}.{digits[6:9]}"
    return uid


async def publications_for_uid(
    uid: str,
    *,
    limit: int,
    budget_s: float,
    language: str = "de",
    rubrics: list[str] | None = None,
) -> list[Publication]:
    """Gazette publications naming the given company UID, newest first.

    `uid` is the normalised, unformatted form ("CHE101654423"); it is
    reformatted internally for the upstream `uids` filter. `rubrics` restricts
    the result to gazette rubrics, e.g. ["HR"] for commercial-register
    entries only. Only `publicationStates=PUBLISHED`, `uids`, `rubrics`, and
    `pageRequest.size` are sent —
    built exclusively from `ALLOWED_GAZETTE_PARAMS` (Quirk 1 guard). Raises
    `GazetteFilterIgnored` if the plausibility guard trips, and
    `SourceUnavailable(source="gazette", ...)` on timeout/network/HTTP
    failure after retries.
    """
    data = await _gazette_search(
        {
            "uids": _format_uid_for_query(uid),
            "rubrics": ",".join(rubrics) if rubrics else None,
            "pageRequest.size": min(limit, GAZETTE_MAX_LIMIT),
        },
        budget_s=budget_s,
    )
    content = data.get("content", []) or []
    pubs = [_publication_from_item(item, language=language) for item in content]
    pubs.sort(key=lambda p: p.date, reverse=True)
    return pubs
