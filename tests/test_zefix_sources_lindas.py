"""
HTTP-level tests for sources/lindas.py (PRD §6.2, interfaces.md).

Binding-shape note: interfaces.md gives graph-pattern predicate hints
(?idRes/?v for identifiers, a generic lang-tagged ?label for legal-form) but
not an exact SPARQL SELECT projection, and that projection is still moving
inside sources/lindas.py as it is being built (observed, while writing this
suite, cycling between a generic idType/idValue identifier row, named
?uid/?chid/?ehraid variables, and back). Rather than pin one internal wire
shape and re-chase every refactor, `_swisscom_detail_rows()` below emits a
row per fact under EVERY plausible variable name for that fact (e.g. both
`chid` and `idType`="CompanyCHID"/`idValue`; both `canton` and `region`).
`_binding_value` (sources/lindas.py) does a plain dict.get per key, so extra
unknown keys are inert -- whichever naming scheme find_by_uid/search_by_name
actually reads, the right value is present under that key. This keeps these
tests about the PUBLIC contract (Company fields, PRD §5.2 step 2 fallback
order) rather than about a specific query implementation, which is what S1
still owns.
"""

from __future__ import annotations

from urllib.parse import parse_qs

import httpx
import pytest
import respx

from mcp_boilerplate.config.settings import settings
from mcp_boilerplate.zefix.sources import lindas
from mcp_boilerplate.zefix.sources.http import SourceUnavailable

COMPANY_URI = "https://register.ld.admin.ch/zefix/company/415941"


def _binding(**kwargs):
    """Build one SPARQL-JSON result row. A dict value {"value":..., "lang":...}
    becomes a language-tagged literal; {"value":..., "type": "uri"} a URI."""
    row = {}
    for key, value in kwargs.items():
        if isinstance(value, dict):
            binding = {"type": value.get("type", "literal"), "value": value["value"]}
            if "lang" in value:
                binding["xml:lang"] = value["lang"]
            row[key] = binding
        else:
            row[key] = {"type": "literal", "value": str(value)}
    return row


def _company_uri_binding():
    return {"value": COMPANY_URI, "type": "uri"}


def _swisscom_detail_rows() -> list[dict]:
    """One row per fact, key(s) covering every plausible projection name for
    that fact (see module docstring)."""
    company = _company_uri_binding()
    lf_uri = {"value": "https://ld.admin.ch/ech/97/legalforms/0106", "type": "uri"}

    rows = [
        _binding(company=company, name={"value": "Swisscom (Schweiz) AG", "lang": "de"}),
        _binding(company=company, name={"value": "Swisscom (Suisse) SA", "lang": "fr"}),
        _binding(company=company, name={"value": "Swisscom (Svizzera) SA", "lang": "it"}),
        _binding(company=company, name={"value": "Swisscom (Switzerland) Ltd", "lang": "en"}),
        _binding(company=company, legalName="Swisscom (Schweiz) AG"),
        _binding(company=company, uid="CHE101654423", idType="CompanyUID", idValue="CHE101654423"),
        _binding(company=company, chid="CH-035.3.016.930-9", idType="CompanyCHID", idValue="CH-035.3.016.930-9"),
        _binding(company=company, ehraid="415941", idType="CompanyEHRAID", idValue="415941"),
        _binding(
            company=company,
            lf=lf_uri,
            lfCode="0106",
            lflabel={"value": "Aktiengesellschaft", "lang": "de"},
            lfLabel={"value": "Aktiengesellschaft", "lang": "de"},
        ),
        _binding(
            company=company,
            lf=lf_uri,
            lfCode="0106",
            lflabel={"value": "Société anonyme", "lang": "fr"},
            lfLabel={"value": "Société anonyme", "lang": "fr"},
        ),
        _binding(
            company=company,
            lf=lf_uri,
            lfCode="0106",
            lflabel={"value": "Società anonima", "lang": "it"},
            lfLabel={"value": "Società anonima", "lang": "it"},
        ),
        _binding(
            company=company,
            lf=lf_uri,
            lfCode="0106",
            lflabel={"value": "Company limited by shares", "lang": "en"},
            lfLabel={"value": "Company limited by shares", "lang": "en"},
        ),
        _binding(company=company, seat="Ittigen", bfs="362"),
        _binding(
            company=company,
            street="Alte Tiefenaustrasse 6",
            zip="3050",
            city="Bern",
            canton="BE",
            region="BE",
        ),
        _binding(company=company, purpose="Telekommunikations- und Informatikdienstleistungen."),
    ]
    return rows


def _sparql_json(bindings: list[dict]) -> dict:
    return {"head": {"vars": sorted({k for row in bindings for k in row})}, "results": {"bindings": bindings}}


def _assert_is_swisscom(company) -> None:
    assert company is not None
    assert company.ehraid == 415941
    assert company.uid == "CHE101654423"
    assert company.chid == "CH-035.3.016.930-9"
    assert company.names["de"] == "Swisscom (Schweiz) AG"
    assert company.names["fr"] == "Swisscom (Suisse) SA"
    assert company.legal_name == "Swisscom (Schweiz) AG"
    assert company.legal_form_code == "0106"
    assert company.legal_form_labels["de"] == "Aktiengesellschaft"
    assert company.legal_form_labels["fr"] == "Société anonyme"
    assert company.seat == "Ittigen"
    assert company.seat_bfs_id == 362
    assert company.canton == "BE"
    assert company.address == {"street": "Alte Tiefenaustrasse 6", "zip": "3050", "city": "Bern"}
    assert company.purpose
    assert company.source_url == COMPANY_URI


async def test_find_by_uid_parses_a_full_company():
    """PRD §6.2: a single-hit SPARQL response is parsed into a Company with names,
    identifiers, legal form, municipality, address and purpose populated."""
    body = _sparql_json(_swisscom_detail_rows())
    with respx.mock(assert_all_called=True) as mocked:
        mocked.post(settings.lindas_endpoint).respond(200, json=body)
        company = await lindas.LindasClient().find_by_uid("CHE101654423", budget_s=10.0)

    _assert_is_swisscom(company)


async def test_find_by_uid_zero_hits_returns_none():
    """PRD §5.2 step 3b relies on find_by_uid returning None, not raising, on a miss."""
    body = _sparql_json([])
    with respx.mock(assert_all_called=True) as mocked:
        mocked.post(settings.lindas_endpoint).respond(200, json=body)
        company = await lindas.LindasClient().find_by_uid("CHE999999999", budget_s=10.0)

    assert company is None


def _query_text(request: httpx.Request) -> str:
    """The `query` form field, form-decoded (the wire body is urlencoded, so
    raw `.decode()` would leave e.g. `?n` as `%3Fn`) and upper-cased."""
    form = parse_qs(request.content.decode())
    return form["query"][0].upper()


# Follow-up 2026-09-24 (F1): search_by_name is staged, cheapest/most-selective
# first, stopping at the first stage with hits (sources/lindas.py
# `search_by_name` docstring):
#   stage 0: exact literal match via VALUES (indexed, no LCASE/FILTER)
#   stage 1: schema:legalName STRSTARTS(LCASE)
#   stage 2: schema:name STRSTARTS(LCASE)
#   stage 3: schema:legalName CONTAINS(LCASE)
# These helpers identify which stage a captured request's query body belongs
# to, matching the exact candidate-clause text `_search_exact_query` /
# `_search_prefix_query` emit (sources/lindas.py) - distinct from the shared
# detail OPTIONAL block's `?company schema:name ?name` / `?company
# schema:legalName ?legalName`, which every stage's query also contains.
def _is_exact_query(query: str) -> bool:
    return "VALUES" in query


def _is_stage1_query(query: str) -> bool:
    return "SCHEMA:LEGALNAME ?N . FILTER(STRSTARTS" in query


def _is_stage2_query(query: str) -> bool:
    return "SCHEMA:NAME ?N . FILTER(STRSTARTS" in query


def _is_stage3_query(query: str) -> bool:
    return "SCHEMA:LEGALNAME ?N . FILTER(CONTAINS" in query


def _route_search_by_name(*, exact_hits=False, stage1_hits=False, stage2_hits=False, stage3_hits=False):
    """A respx side_effect answering each search stage independently."""

    def _side_effect(request: httpx.Request) -> httpx.Response:
        query = _query_text(request)
        if _is_exact_query(query):
            hit = exact_hits
        elif _is_stage1_query(query):
            hit = stage1_hits
        elif _is_stage2_query(query):
            hit = stage2_hits
        elif _is_stage3_query(query):
            hit = stage3_hits
        else:
            raise AssertionError(f"query matched no known search stage: {query}")
        body = _sparql_json(_swisscom_detail_rows()) if hit else _sparql_json([])
        return httpx.Response(200, json=body)

    return _side_effect


async def test_search_by_name_exact_hit_stops_at_stage0():
    """Stage 0 (exact literal match) is tried first; a hit there must not
    trigger any of the STRSTARTS/CONTAINS scan stages."""
    with respx.mock(assert_all_called=True) as mocked:
        route = mocked.post(settings.lindas_endpoint).mock(
            side_effect=_route_search_by_name(exact_hits=True, stage1_hits=True, stage2_hits=True, stage3_hits=True)
        )
        results = await lindas.LindasClient().search_by_name("Swisscom (Schweiz) AG", budget_s=10.0)
        queries = [_query_text(call.request) for call in route.calls]

    assert len(results) == 1
    _assert_is_swisscom(results[0])
    assert len(queries) == 1
    assert _is_exact_query(queries[0])


async def test_search_by_name_falls_back_through_stages_in_order():
    """A miss at stage 0 falls through legalName STRSTARTS, then schema:name
    STRSTARTS, to legalName CONTAINS, trying each at most once and in order."""
    with respx.mock(assert_all_called=True) as mocked:
        route = mocked.post(settings.lindas_endpoint).mock(
            side_effect=_route_search_by_name(stage3_hits=True)
        )
        results = await lindas.LindasClient().search_by_name("swisscom", budget_s=10.0)
        queries = [_query_text(call.request) for call in route.calls]

    assert len(results) == 1
    _assert_is_swisscom(results[0])
    assert len(queries) == 4, "expected all 4 stages to be tried in order before the stage-3 hit"
    assert _is_exact_query(queries[0])
    assert _is_stage1_query(queries[1])
    assert _is_stage2_query(queries[2])
    assert _is_stage3_query(queries[3])


async def test_search_by_name_stops_at_first_hitting_stage():
    """A hit at stage 1 (legalName STRSTARTS) must not trigger stages 2 or 3."""
    with respx.mock(assert_all_called=True) as mocked:
        route = mocked.post(settings.lindas_endpoint).mock(
            side_effect=_route_search_by_name(stage1_hits=True, stage2_hits=True, stage3_hits=True)
        )
        results = await lindas.LindasClient().search_by_name("swisscom", budget_s=10.0)
        queries = [_query_text(call.request) for call in route.calls]

    assert len(results) == 1
    assert len(queries) == 2  # stage 0 (miss), stage 1 (hit)
    assert not any(_is_stage2_query(q) or _is_stage3_query(q) for q in queries)


async def test_search_by_name_zero_hits_all_stages_returns_empty():
    """A miss at every stage returns an empty list, not raising, and tries
    at most 4 upstream queries total."""
    with respx.mock(assert_all_called=True) as mocked:
        route = mocked.post(settings.lindas_endpoint).mock(side_effect=_route_search_by_name())
        results = await lindas.LindasClient().search_by_name("ganz unbekannte gmbh xyz", budget_s=10.0)
        queries = [_query_text(call.request) for call in route.calls]

    assert results == []
    assert len(queries) <= 4
    assert _is_exact_query(queries[0])
    assert any(_is_stage1_query(q) for q in queries)
    assert any(_is_stage2_query(q) for q in queries)
    assert any(_is_stage3_query(q) for q in queries)


def test_escape_literal_escapes_backslash_quote_and_newline():
    """PRD §6.2: "Input never reaches the query unescaped ... name is ... escaped
    for SPARQL string literals." Standard SPARQL string-literal escaping."""
    raw = 'a "quote", a \\ backslash, and a\nnewline'
    escaped = lindas.escape_literal(raw)

    assert escaped.count('\\"') >= 1
    assert "\\\\" in escaped
    assert "\n" not in escaped
    assert "\\n" in escaped


async def test_find_by_uid_timeout_raises_source_unavailable_lindas():
    """PRD §5.3: "LINDAS failure always produces source_unavailable"."""
    with respx.mock(assert_all_called=True) as mocked:
        mocked.post(settings.lindas_endpoint).mock(side_effect=httpx.TimeoutException("timed out"))
        with pytest.raises(SourceUnavailable) as excinfo:
            await lindas.LindasClient().find_by_uid("CHE101654423", budget_s=1.0)

    assert excinfo.value.source == "lindas"
    assert excinfo.value.error_class


async def test_search_by_name_timeout_raises_timeout_scan():
    """Follow-up 2026-09-24: a negative name search's STRSTARTS/CONTAINS
    scan stages (1-3) have no supporting index on this endpoint and can take
    15-20s regardless of query shape (see sources/lindas.py docstring,
    "Follow-up investigation"), easily exceeding budget_s. That must surface
    distinctly from a generic LINDAS timeout so the tool layer can suggest
    the UID path instead of just retrying. Stage 0 (exact match) misses
    here so the scan stage is actually reached."""

    def _side_effect(request: httpx.Request) -> httpx.Response:
        if _is_exact_query(_query_text(request)):
            return httpx.Response(200, json=_sparql_json([]))
        raise httpx.TimeoutException("timed out")

    with respx.mock(assert_all_called=True) as mocked:
        mocked.post(settings.lindas_endpoint).mock(side_effect=_side_effect)
        with pytest.raises(SourceUnavailable) as excinfo:
            await lindas.LindasClient().search_by_name("ganz unbekannte gmbh xyz", budget_s=1.0)

    assert excinfo.value.source == "lindas"
    assert excinfo.value.error_class == "timeout_scan"


async def test_search_by_name_exact_stage_timeout_is_not_reclassified():
    """Stage 0 is an indexed VALUES lookup, not a scan (module docstring,
    "Stage 0"): a timeout there is a generic LINDAS problem and must keep
    the plain "timeout" error_class, not "timeout_scan"."""
    with respx.mock(assert_all_called=True) as mocked:
        mocked.post(settings.lindas_endpoint).mock(side_effect=httpx.TimeoutException("timed out"))
        with pytest.raises(SourceUnavailable) as excinfo:
            await lindas.LindasClient().search_by_name("Swisscom (Schweiz) AG", budget_s=1.0)

    assert excinfo.value.source == "lindas"
    assert excinfo.value.error_class != "timeout_scan"


async def test_find_by_uid_timeout_is_not_reclassified_as_timeout_scan():
    """The timeout_scan reclassification is specific to search_by_name; a
    find_by_uid timeout (exact UID lookup, not a name scan) must keep the
    generic "timeout" error_class."""
    with respx.mock(assert_all_called=True) as mocked:
        mocked.post(settings.lindas_endpoint).mock(side_effect=httpx.TimeoutException("timed out"))
        with pytest.raises(SourceUnavailable) as excinfo:
            await lindas.LindasClient().find_by_uid("CHE101654423", budget_s=1.0)

    assert excinfo.value.error_class != "timeout_scan"
