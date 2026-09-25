"""
Tests for sources/gazette.py (PRD §6.4, interfaces.md).

sources/gazette.py does not exist yet (S2); every test here ImportErrors until
it lands. Expected -- see tests/conftest.py's module docstring.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from mcp_swiss_info.config.settings import settings
from mcp_swiss_info.zefix.sources.http import SourceUnavailable

FIXTURES = Path(__file__).parent / "fixtures"
SEARCH_FIXTURE = json.loads((FIXTURES / "gazette_search.json").read_text())
CORPUS_TOTAL = json.loads((FIXTURES / "gazette_corpus_total.json").read_text())["total"]

ALLOWED_PARAMS = {
    "publicationStates",
    "uids",
    "pageRequest.size",
    "pageRequest.page",
    "rubrics",
    "subRubrics",
    "publicationDate.start",
    "publicationDate.end",
}


async def test_publications_for_uid_parses_the_fixture():
    """PRD §6.4 field list, A4 URL pattern. Fixture: tests/fixtures/gazette_search.json
    (2 entries, HR/HR03), copied verbatim from register-mcp; meta.title/content are
    redacted placeholders per tests/fixtures/PROVENANCE.md, structure is real."""
    from mcp_swiss_info.zefix.sources import gazette

    with respx.mock(assert_all_called=True) as mocked:
        mocked.get(f"{settings.gazette_base_url}/publications").respond(200, json=SEARCH_FIXTURE)
        pubs = await gazette.GazetteClient().publications_for_uid("CHE101654423", limit=5, budget_s=10.0, language="de")

    assert len(pubs) == 2
    ids = {p.id for p in pubs}
    assert ids == {"f814f790-f0d9-441f-8ebe-8850f8ab8040", "566da172-2075-4f84-b436-d5da63cb897c"}
    by_id = {p.id: p for p in pubs}
    fr_row = by_id["f814f790-f0d9-441f-8ebe-8850f8ab8040"]
    assert fr_row.date == "2026-08-14"
    assert fr_row.registry_office == "Bundesamt für Justiz (BJ), Eidgenössisches Amt für das Handelsregister"
    assert fr_row.registry_canton == "NE"
    assert fr_row.rubric == "HR"
    assert fr_row.sub_rubric == "HR03"
    assert fr_row.title == "[redigiert — siehe PROVENANCE.md]"
    assert fr_row.source_url == (
        "https://amtsblattportal.ch/#!/search?publicationId=f814f790-f0d9-441f-8ebe-8850f8ab8040"
    )


async def test_publications_for_uid_retries_on_503_then_succeeds():
    """PRD §6.4: "Retry on 429, 502, 503, 504 and network errors ... max 3 attempts."."""
    from mcp_swiss_info.zefix.sources import gazette

    responses = [httpx.Response(503), httpx.Response(200, json=SEARCH_FIXTURE)]

    def _side_effect(request: httpx.Request) -> httpx.Response:
        return responses.pop(0)

    with respx.mock(assert_all_called=True) as mocked:
        route = mocked.get(f"{settings.gazette_base_url}/publications").mock(side_effect=_side_effect)
        pubs = await gazette.GazetteClient().publications_for_uid("CHE101654423", limit=5, budget_s=10.0)

    assert len(pubs) == 2
    assert route.calls.call_count == 2


async def test_publications_for_uid_gives_up_after_max_three_attempts():
    """PRD §6.4: "max 3 attempts" then the failure surfaces as source_unavailable."""
    from mcp_swiss_info.zefix.sources import gazette

    with respx.mock(assert_all_called=True) as mocked:
        mocked.get(f"{settings.gazette_base_url}/publications").respond(503)
        with pytest.raises(SourceUnavailable) as excinfo:
            await gazette.GazetteClient().publications_for_uid("CHE101654423", limit=5, budget_s=10.0)

    assert excinfo.value.source == "gazette"
    assert mocked.calls.call_count <= 3


async def test_publications_for_uid_raises_gazette_filter_ignored_when_total_implausible():
    """PRD §6.4 quirk 1: "if total exceeds 95% of the known corpus size the filter
    was ignored; raise, do not return." Corpus size from tests/fixtures/gazette_corpus_total.json."""
    from mcp_swiss_info.zefix.sources import gazette

    implausible_total = int(CORPUS_TOTAL * 0.99)
    payload = {**SEARCH_FIXTURE, "total": implausible_total}

    with respx.mock(assert_all_called=True) as mocked:
        mocked.get(f"{settings.gazette_base_url}/publications").respond(200, json=payload)
        with pytest.raises(gazette.GazetteFilterIgnored):
            await gazette.GazetteClient().publications_for_uid("CHE101654423", limit=5, budget_s=10.0)


async def test_publications_for_uid_never_sends_a_non_allow_listed_param():
    """PRD §6.4: "Query built only from an allow-list of parameter names; unknown
    parameters are silently ignored upstream and would return the whole corpus."."""
    from mcp_swiss_info.zefix.sources import gazette

    with respx.mock(assert_all_called=True) as mocked:
        route = mocked.get(f"{settings.gazette_base_url}/publications").respond(200, json=SEARCH_FIXTURE)
        await gazette.GazetteClient().publications_for_uid("CHE101654423", limit=5, budget_s=10.0)

    request = route.calls.last.request
    sent_params = set(httpx.QueryParams(request.url.query).keys())
    assert sent_params <= ALLOWED_PARAMS
    assert "uids" in sent_params


def test_is_deletion_matches_deletion_subrubrics_only():
    """PRD §5.2 step 3b, §6.4: "Deletion detection ... uses subRubric codes for
    Löschung; the exact codes are taken from the cached rubric taxonomy" (A6)."""
    from mcp_swiss_info.zefix.sources import gazette

    deletion_code = next(iter(gazette.DELETION_SUBRUBRICS))
    deletion_pub = gazette.Publication(
        id="x",
        date="2026-06-12",
        registry_office=None,
        registry_canton=None,
        rubric="HR",
        sub_rubric=deletion_code,
        title=None,
        source_url="https://amtsblattportal.ch/#!/search?publicationId=x",
        api_url="https://amtsblattportal.ch/api/v1/publications/x/xml",
    )
    non_deletion_pub = gazette.Publication(
        id="y",
        date="2026-06-12",
        registry_office=None,
        registry_canton=None,
        rubric="HR",
        sub_rubric="HR02",
        title=None,
        source_url="https://amtsblattportal.ch/#!/search?publicationId=y",
        api_url="https://amtsblattportal.ch/api/v1/publications/y/xml",
    )
    assert "HR02" not in gazette.DELETION_SUBRUBRICS
    assert gazette.is_deletion(deletion_pub) is True
    assert gazette.is_deletion(non_deletion_pub) is False


async def test_rubrics_parses_hr_deletion_code_from_the_taxonomy_fixture():
    """PRD action A6: the deletion sub-rubric code(s) come from the live taxonomy.
    tests/fixtures/gazette_rubrics.json's HR rubric lists HR03 with
    name.de == "Löschung", which is where DELETION_SUBRUBRICS must originate."""
    from mcp_swiss_info.zefix.sources import gazette

    rubrics_payload = json.loads((FIXTURES / "gazette_rubrics.json").read_text())
    hr = next(r for r in rubrics_payload if r["code"] == "HR")
    loeschung = next(sr for sr in hr["subRubrics"] if sr["name"]["de"] == "Löschung")
    assert loeschung["code"] == "HR03"
    assert loeschung["code"] in gazette.DELETION_SUBRUBRICS
