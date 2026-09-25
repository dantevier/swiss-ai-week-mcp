"""
Acceptance tests for the `company_info` tool (docs/prd-zefix-company-info.md).

Written before the implementation exists (S0 of the plan in PRD §14): every
import below fails with ImportError until sources/lindas.py, sources/zefix.py,
sources/gazette.py, envelope.py, and tools/company_info.py (S1-S4) land. That
is expected. These tests are the acceptance criteria for those steps, not a
description of code that already runs.

Sources are never hit over the network: `CompanyLookup` is built by
tests.conftest.lookup over injected FakeLindas / FakeZefix / FakeGazette
clients (PRD refactor T1/T2). No module or settings attribute is patched.
"""

from __future__ import annotations

import json

import pytest
import respx

from mcp_swiss_info.config.settings import Settings
from mcp_swiss_info.zefix import envelope, gates
from mcp_swiss_info.zefix.sources import gazette
from mcp_swiss_info.zefix.sources.http import EgressDenied, SourceUnavailable, make_client
from mcp_swiss_info.zefix.sources.rest import format_uid

from .conftest import FakeGazette, FakeLindas, FakeZefix, lookup

FIVE_STATES = {"answered", "need_info", "no_match", "out_of_scope", "source_unavailable"}


def _refuses_lookup():
    """A CompanyLookup whose every source call fails the test if invoked.

    Used for gate tests (jurisdiction/analytics/topic) where §5.2 step 0 must
    short-circuit before any network call, and for the "no params" case.
    Unconfigured fakes (tests.conftest) fail the test on any call.
    """
    return lookup()


def _walk_keys(obj):
    """Yield every dict key found anywhere in a nested structure."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key
            yield from _walk_keys(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_keys(item)


def _assert_no_banned_keys(result: dict) -> None:
    # Round-trips through json.dumps/loads so this also proves the envelope is
    # actually JSON-serialisable, not just a dict of dataclasses.
    reloaded = json.loads(json.dumps(result))
    keys = set(_walk_keys(reloaded))
    assert "message" not in keys
    assert "content" not in keys


# ---------------------------------------------------------------------------
# Q1: exact name hit -> answered, full citation
# ---------------------------------------------------------------------------


async def test_q1_name_lookup_exact_hit_is_answered_with_citation(swisscom):
    """PRD §4 Q1, §5.2 step 2/3, §5.3: a single exact name hit resolves to `answered`
    with a fully populated citation and a deterministic passage."""
    company_lookup = lookup(
        lindas=FakeLindas(search_by_name=[swisscom], dataset_modified="2026-09-23"),
        gazette=FakeGazette(publications_for_uid=[]),
    )
    result = await company_lookup.lookup(name="Swisscom (Schweiz) AG", language="de")

    assert result["status"] == "answered"
    company = result["company"]
    assert company["name"] == "Swisscom (Schweiz) AG"
    assert company["names"]["fr"] == "Swisscom (Suisse) SA"
    assert company["uid"] == "CHE-101.654.423"
    assert company["ehraid"] == 415941
    assert company["seat"] == "Ittigen"
    assert company["canton"] == "BE"
    assert company["address"] == {"street": "Alte Tiefenaustrasse 6", "zip": "3050", "city": "Bern"}

    citation = result["citation"]
    assert "EHRA" in citation["authority"]
    assert citation["level"] == "federal"
    assert citation["source_url"] == "https://register.ld.admin.ch/zefix/company/415941"
    assert citation["zefix_url"] == "https://www.zefix.admin.ch/de/search/entity/list/firm/415941"
    assert citation["passage"] == (
        "Swisscom (Schweiz) AG, Aktiengesellschaft, Sitz: Ittigen (BE), "
        "Alte Tiefenaustrasse 6, 3050 Bern"
    )
    assert citation["source_status"] == "indicative"
    assert citation["dataset_modified"] == "2026-09-23"
    assert "source_validated_at" in citation

    assert result["notes"] == envelope.NOTES["de"]


async def test_q1_passage_is_deterministic_across_calls(swisscom):
    """PRD §5.3: `passage` is rendered from structured fields, never LLM-generated,
    so two calls against the same data produce byte-identical passages."""
    company_lookup = lookup(
        lindas=FakeLindas(search_by_name=[swisscom], dataset_modified="2026-09-23"),
        gazette=FakeGazette(publications_for_uid=[]),
    )
    first = await company_lookup.lookup(name="Swisscom (Schweiz) AG", language="de")
    second = await company_lookup.lookup(name="Swisscom (Schweiz) AG", language="de")
    assert first["citation"]["passage"] == second["citation"]["passage"]
    assert first["citation"]["passage"]


# ---------------------------------------------------------------------------
# Q2: ambiguous name -> need_info
# ---------------------------------------------------------------------------


async def test_q2_ambiguous_name_returns_need_info_with_candidates(nestle_candidates):
    """PRD §4 Q2, §5.2 step 3: several prefix hits with no exact legal_name match
    -> need_info with at most 5 candidates and exactly one question."""
    company_lookup = lookup(lindas=FakeLindas(search_by_name=nestle_candidates))
    result = await company_lookup.lookup(name="Nestlé", language="fr")

    assert result["status"] == "need_info"
    assert len(result["candidates"]) <= 5
    assert len(result["candidates"]) == 3
    for candidate in result["candidates"]:
        assert "uid" in candidate
    assert result["missing"] in {"uid", "canton", "seat"}
    assert isinstance(result["question"], str)
    assert result["question"].count("?") <= 1  # exactly one question, not several concatenated


# ---------------------------------------------------------------------------
# Q3 / Q3b: UID lookup, enrichment gated by the robots-txt switch
# ---------------------------------------------------------------------------


async def test_q3_uid_lookup_formats_uid_and_defaults_to_policy_robots(swisscom):
    """PRD §4 Q3, §6.5: default settings (respect_robots_txt=True, no credentials)
    never call the Zefix web endpoint; the answer is still returned, degraded."""

    def _must_not_be_called(*_args, **_kwargs):
        raise AssertionError("firm_detail must not run when respect_robots_txt=True and no credentials (§6.5)")

    zefix = FakeZefix(firm_detail=_must_not_be_called, respect_robots_txt=True, username=None, password=None)
    mocks = zefix.calls
    company_lookup = lookup(
        lindas=FakeLindas(find_by_uid=swisscom, dataset_modified="2026-09-23"),
        zefix=zefix,
        gazette=FakeGazette(publications_for_uid=[]),
    )

    result = await company_lookup.lookup(uid="CHE-101.654.423", language="de")

    assert result["status"] == "answered"
    assert result["company"]["uid"] == format_uid("CHE101654423")
    assert result["company"]["uid"] == "CHE-101.654.423"
    assert result["enrichment_status"] == "policy_robots"
    assert result["company"]["status"] == "ACTIVE"
    assert any("index membership" in a.lower() or "active-entity index" in a.lower() for a in result["assumptions"])
    assert result["citation"]["cantonal_excerpt_url"] is None
    mocks["firm_detail"].assert_not_awaited()


async def test_q3b_uid_lookup_with_enrichment_when_robots_disabled(swisscom, enrichment_active):
    """PRD §5.2 step 4, §6.5: RESPECT_ROBOTS_TXT=false runs the Zefix enrichment
    call and its fields (status, shab_date, cantonal excerpt) reach the envelope."""
    zefix = FakeZefix(firm_detail=enrichment_active, respect_robots_txt=False)
    mocks = zefix.calls
    company_lookup = lookup(
        lindas=FakeLindas(find_by_uid=swisscom, dataset_modified="2026-09-23"),
        zefix=zefix,
        gazette=FakeGazette(publications_for_uid=[]),
    )

    result = await company_lookup.lookup(uid="CHE101654423", language="de")

    assert result["status"] == "answered"
    assert result["enrichment_status"] == "answered"
    assert result["company"]["status"] == enrichment_active.status
    assert result["citation"]["effective_from"] == enrichment_active.shab_date
    assert result["citation"]["cantonal_excerpt_url"] == enrichment_active.cantonal_excerpt_url
    mocks["firm_detail"].assert_awaited_once()


# ---------------------------------------------------------------------------
# Q4: publications
# ---------------------------------------------------------------------------


async def test_q4_publications_attached_newest_first_capped(swisscom):
    """PRD §5.2 step 5, §4 Q4: gazette publications are attached newest first and
    capped at max_publications; publications_status is "answered" on success."""
    from mcp_swiss_info.zefix.sources.gazette import Publication

    six_newest_first = [
        Publication(
            id=f"pub-{i}",
            date=date,
            registry_office="Handelsregisteramt des Kantons Bern",
            registry_canton="BE",
            rubric="HR",
            sub_rubric="HR02",
            title="Mutation",
            source_url=f"https://amtsblattportal.ch/#!/search?publicationId=pub-{i}",
            api_url=f"https://amtsblattportal.ch/api/v1/publications/pub-{i}/xml",
        )
        for i, date in enumerate(
            ["2026-08-14", "2026-07-01", "2026-06-12", "2026-05-01", "2026-04-01", "2026-03-01"]
        )
    ]
    company_lookup = lookup(
        lindas=FakeLindas(find_by_uid=swisscom, dataset_modified="2026-09-23"),
        gazette=FakeGazette(publications_for_uid=six_newest_first),
    )

    result = await company_lookup.lookup(uid="CHE101654423", max_publications=3)

    assert result["status"] == "answered"
    assert result["publications_status"] == "answered"
    assert len(result["publications"]) == 3
    dates = [p["date"] for p in result["publications"]]
    assert dates == sorted(dates, reverse=True)
    assert dates == ["2026-08-14", "2026-07-01", "2026-06-12"]


async def test_q4_gazette_unavailable_still_answers_company(swisscom):
    """PRD §5.2 step 5: gazette failure degrades publications_status only; the
    company answer (resolved via LINDAS) is still returned."""
    company_lookup = lookup(
        lindas=FakeLindas(find_by_uid=swisscom, dataset_modified="2026-09-23"),
        gazette=FakeGazette(publications_for_uid=SourceUnavailable(source="gazette", error_class="timeout")),
    )

    result = await company_lookup.lookup(uid="CHE101654423")

    assert result["status"] == "answered"
    assert "company" in result
    assert result["publications_status"] == "source_unavailable"
    assert not result.get("publications")


# ---------------------------------------------------------------------------
# Q5: persons -> out_of_scope, no publications, no person data
# ---------------------------------------------------------------------------


async def test_q5_persons_question_is_out_of_scope_and_resolves_company_first(
    swisscom, enrichment_active
):
    """PRD §5.2 step 0 (persons), §6.6: a person-role question resolves the company
    (so the cantonal excerpt link can be returned) then declines with reason
    "persons", never attaching publications or any person data."""
    company_lookup = lookup(
        lindas=FakeLindas(search_by_name=[swisscom], dataset_modified="2026-09-23"),
        zefix=FakeZefix(firm_detail=enrichment_active, respect_robots_txt=False),
    )

    result = await company_lookup.lookup(
        question="Wer sitzt im Verwaltungsrat der Swisscom (Schweiz) AG?",
        name="Swisscom (Schweiz) AG",
        language="de",
    )

    assert result["status"] == "out_of_scope"
    assert result["reason"] == "persons"
    assert "publications" not in result
    assert result.get("cantonal_excerpt_url") == enrichment_active.cantonal_excerpt_url

    serialised = json.dumps(result)
    # Company/Enrichment/Publication carry no person fields at all (§6.6), so this
    # is a structural guarantee, not a heuristic: no field name suggesting person
    # data may appear in an out_of_scope(persons) envelope.
    for banned in ("board", "director", "signatory", "signatories", "auditor", "gerente", "amministratore"):
        assert banned not in serialised.lower()
    _assert_no_banned_keys(result)


# ---------------------------------------------------------------------------
# Q6: jurisdiction
# ---------------------------------------------------------------------------


async def test_q6_foreign_jurisdiction_question_is_out_of_scope():
    """PRD §5.2 step 0 (jurisdiction): a non-Swiss-country question with no Swiss
    anchor is declined before any network call."""
    result = await _refuses_lookup().lookup(question="Ist die Firma XY in Deutschland eingetragen?", language="de")
    assert result["status"] == "out_of_scope"
    assert result["reason"] == "jurisdiction"


async def test_q6_non_che_uid_is_out_of_scope_jurisdiction():
    """PRD §5.2 step 0 (jurisdiction): a uid not starting with CHE is a foreign
    identifier, declined before any network call."""
    result = await _refuses_lookup().lookup(uid="DE123456789")
    assert result["status"] == "out_of_scope"
    assert result["reason"] == "jurisdiction"


# ---------------------------------------------------------------------------
# Q7: LINDAS down -> source_unavailable
# ---------------------------------------------------------------------------


async def test_q7_lindas_unavailable():
    """PRD §4 Q7, §5.3: LINDAS failure always produces source_unavailable, with no
    cached/stale company record attached (D3)."""
    company_lookup = lookup(
        lindas=FakeLindas(
            search_by_name=SourceUnavailable(source="lindas", error_class="timeout"),
            dataset_modified="2026-09-23",
        )
    )
    result = await company_lookup.lookup(name="Swisscom (Schweiz) AG")
    assert result["status"] == "source_unavailable"
    assert result["source"] == "lindas"
    assert "error_class" in result
    assert "company" not in result


# ---------------------------------------------------------------------------
# Q8: analytics
# ---------------------------------------------------------------------------


async def test_q8_analytics_question_is_out_of_scope():
    """PRD §4 Q8, §5.2 step 0 (analytics), N1: counting/listing over a criterion is
    declined before any network call."""
    result = await _refuses_lookup().lookup(question="Wie viele AGs gibt es im Kanton Zug?", language="de")
    assert result["status"] == "out_of_scope"
    assert result["reason"] == "analytics"


# ---------------------------------------------------------------------------
# gates.classify() (S5: step-0 gates moved to zefix/gates.py): one case per
# `Reason` plus the None case, using the same inputs as the black-box
# out_of_scope tests above (Q5/Q6/Q8), now exercised directly and offline.
# ---------------------------------------------------------------------------


def test_classify_persons_reason():
    """Same input as test_q5_persons_question_is_out_of_scope_and_resolves_company_first."""
    reason = gates.classify(
        "Wer sitzt im Verwaltungsrat der Swisscom (Schweiz) AG?", None, None, True
    )
    assert reason == "persons"


def test_classify_jurisdiction_reason_from_foreign_country_question():
    """Same input as test_q6_foreign_jurisdiction_question_is_out_of_scope."""
    reason = gates.classify("Ist die Firma XY in Deutschland eingetragen?", None, None, False)
    assert reason == "jurisdiction"


def test_classify_jurisdiction_reason_from_non_che_uid():
    """Same input as test_q6_non_che_uid_is_out_of_scope_jurisdiction."""
    reason = gates.classify(None, "DE123456789", None, True)
    assert reason == "jurisdiction"


def test_classify_analytics_reason():
    """Same input as test_q8_analytics_question_is_out_of_scope."""
    reason = gates.classify("Wie viele AGs gibt es im Kanton Zug?", None, None, False)
    assert reason == "analytics"


def test_classify_topic_reason_when_no_identifier_and_not_company_like():
    """No name/uid and a question with no company-register hint -> "topic",
    the branch `_looks_company_like` gates and that only applies without an
    identifier (PRD §5.2 step 0)."""
    reason = gates.classify("Wie wird das Wetter morgen in Zürich?", None, None, False)
    assert reason == "topic"


def test_classify_returns_none_when_no_gate_fires():
    """Same input as test_no_params_and_no_question_asks_for_name (no gate fires;
    the tool, not classify(), turns this into need_info) and a resolvable case
    (name given, no gate-triggering question)."""
    assert gates.classify(None, None, None, False) is None
    assert gates.classify(None, None, None, True) is None


# ---------------------------------------------------------------------------
# No lookup parameter at all
# ---------------------------------------------------------------------------


async def test_no_params_and_no_question_asks_for_name():
    """PRD §5.1: name and uid both missing (and no question to self-detect from)
    -> need_info asking for the company name, never a schema-validation error."""
    result = await _refuses_lookup().lookup()
    assert result["status"] == "need_info"
    assert "name" in result["question"].lower() or "firma" in result["question"].lower() or "société" in result["question"].lower()


# ---------------------------------------------------------------------------
# Name search: zero hits
# ---------------------------------------------------------------------------


async def test_name_search_zero_hits_is_no_match():
    """PRD §5.2 step 2: prefix then CONTAINS both empty (internal to
    lindas.search_by_name) -> no_match, and the gazette is never consulted for a
    bare name search (only the uid branch 3b checks it)."""
    gazette_fake = FakeGazette()  # unconfigured: any call fails the test
    company_lookup = lookup(lindas=FakeLindas(search_by_name=[], dataset_modified="2026-09-23"), gazette=gazette_fake)
    result = await company_lookup.lookup(name="Ganz Unbekannte GmbH XYZ")

    assert result["status"] == "no_match"
    assert result["gazette_checked"] is False
    assert result["searched"]["name"] == "Ganz Unbekannte GmbH XYZ"
    assert result["searched"].get("uid") is None
    gazette_fake.calls["publications_for_uid"].assert_not_awaited()


# ---------------------------------------------------------------------------
# Branch 3b: uid given, zero LINDAS hits, gazette decides
# ---------------------------------------------------------------------------


async def test_uid_zero_hits_gazette_deletion_publication_is_answered_deleted(publications):
    """PRD §5.2 step 3b: uid resolves to nothing on LINDAS, but the gazette holds a
    deletion publication for that uid -> answered, status DELETED, derived."""
    deletion_pub = next(p for p in publications if p.sub_rubric in gazette.DELETION_SUBRUBRICS)
    company_lookup = lookup(
        lindas=FakeLindas(find_by_uid=None, dataset_modified="2026-09-23"),
        gazette=FakeGazette(publications_for_uid=[deletion_pub]),
    )

    result = await company_lookup.lookup(uid="CHE101654423")

    assert result["status"] == "answered"
    assert result["company"]["status"] == "DELETED"
    assert result["derived"] is True
    assert result.get("derived_rule")
    assert result["citation"]["effective_from"] == deletion_pub.date


async def test_uid_zero_hits_gazette_non_deletion_is_no_match_gazette_checked(publications):
    """PRD §5.2 step 3b: uid resolves to nothing on LINDAS and the gazette has no
    deletion publication -> no_match, but gazette_checked is True (it was consulted)."""
    non_deletion_pub = next(p for p in publications if p.sub_rubric not in gazette.DELETION_SUBRUBRICS)
    company_lookup = lookup(
        lindas=FakeLindas(find_by_uid=None, dataset_modified="2026-09-23"),
        gazette=FakeGazette(publications_for_uid=[non_deletion_pub]),
    )

    result = await company_lookup.lookup(uid="CHE101654423")

    assert result["status"] == "no_match"
    assert result["gazette_checked"] is True


async def test_uid_zero_hits_gazette_checked_even_with_include_publications_false(publications):
    """PRD §5.2 step 3b: "always query the gazette for that UID, regardless of
    include_publications (that flag only controls whether the list is attached)"."""
    deletion_pub = next(p for p in publications if p.sub_rubric in gazette.DELETION_SUBRUBRICS)
    gazette_fake = FakeGazette(publications_for_uid=[deletion_pub])
    mocks = gazette_fake.calls
    company_lookup = lookup(lindas=FakeLindas(find_by_uid=None, dataset_modified="2026-09-23"), gazette=gazette_fake)

    result = await company_lookup.lookup(uid="CHE101654423", include_publications=False)

    mocks["publications_for_uid"].assert_awaited_once()
    assert result["status"] == "answered"
    assert result["company"]["status"] == "DELETED"


async def test_uid_zero_hits_gazette_unavailable_is_source_unavailable_gazette():
    """PRD §5.2 step 3b, §5.3: in this branch the gazette is the only source that
    can settle the question, so its failure is a hard source_unavailable(gazette)."""
    company_lookup = lookup(
        lindas=FakeLindas(find_by_uid=None, dataset_modified="2026-09-23"),
        gazette=FakeGazette(publications_for_uid=SourceUnavailable(source="gazette", error_class="timeout")),
    )

    result = await company_lookup.lookup(uid="CHE101654423")

    assert result["status"] == "source_unavailable"
    assert result["source"] == "gazette"


# ---------------------------------------------------------------------------
# Addendum: name-scan timeout is a distinct, actionable source_unavailable
# ---------------------------------------------------------------------------


async def test_name_search_timeout_scan_gives_actionable_source_unavailable():
    """Addendum (mid-S4): lindas.search_by_name raises
    SourceUnavailable(error_class="timeout_scan") when the name scan (STRSTARTS/
    CONTAINS full-table scan) exceeds its budget. company_info surfaces
    error_class "timeout_scan" unchanged, but overrides the answer sentence with
    one telling the caller to provide the UID or the exact name + canton instead."""
    company_lookup = lookup(
        lindas=FakeLindas(
            search_by_name=SourceUnavailable(source="lindas", error_class="timeout_scan"),
            dataset_modified="2026-09-23",
        )
    )
    result = await company_lookup.lookup(name="Ganz Unbekannte GmbH XYZ", language="de")

    assert result["status"] == "source_unavailable"
    assert result["source"] == "lindas"
    assert result["error_class"] == "timeout_scan"
    assert "UID" in result["answer"]
    assert "CHE-xxx.xxx.xxx" in result["answer"]


# ---------------------------------------------------------------------------
# Disambiguation: exactly one exact legal_name match
# ---------------------------------------------------------------------------


async def test_ambiguous_prefix_with_one_exact_legal_name_match_is_answered(nestle_candidates):
    """PRD §5.2 step 3: "several hits, exactly one whose legalName equals the input
    case-insensitively -> step 4 with assumptions: [selected the exact-name match...]"."""
    company_lookup = lookup(
        lindas=FakeLindas(search_by_name=nestle_candidates, dataset_modified="2026-09-23"),
        gazette=FakeGazette(publications_for_uid=[]),
    )

    result = await company_lookup.lookup(name="nestlé s.a.")  # case-insensitive match to candidate[0].legal_name

    assert result["status"] == "answered"
    assert result["company"]["uid"] == format_uid(nestle_candidates[0].uid)
    assert any("exact" in a.lower() for a in result["assumptions"])


# ---------------------------------------------------------------------------
# F2: LINDAS rows for the same uid (multiple registered seats) are one
# company, not an ambiguity -- disambiguation groups by uid first.
# ---------------------------------------------------------------------------


def _ubs_seats():
    """Two LINDAS rows for UBS AG: same uid/legal_name, different ehraid/seat.

    Mirrors the live shape reported by the verifier: ehraid 415520 (Basel)
    and 421132 (Zürich), both CHE101329561, both legalName "UBS AG".
    """
    from mcp_swiss_info.zefix.sources.lindas import Company

    common = {
        "uid": "CHE101329561",
        "chid": "CH-030.3.929.999-1",
        "names": {"de": "UBS AG", "fr": "UBS SA", "it": "UBS SA", "en": "UBS AG"},
        "legal_name": "UBS AG",
        "legal_form_code": "0106",
        "legal_form_labels": {
            "de": "Aktiengesellschaft",
            "fr": "Société anonyme",
            "it": "Società anonima",
            "en": "Company limited by shares",
        },
        "purpose": "Banking.",
    }
    basel = Company(
        ehraid=415520,
        seat="Basel",
        seat_bfs_id=2701,
        canton="BS",
        address={"street": "Bahnhofstrasse 45", "zip": "4051", "city": "Basel"},
        source_url="https://register.ld.admin.ch/zefix/company/415520",
        **common,
    )
    zurich = Company(
        ehraid=421132,
        seat="Zürich",
        seat_bfs_id=261,
        canton="ZH",
        address={"street": "Bahnhofstrasse 45", "zip": "8001", "city": "Zürich"},
        source_url="https://register.ld.admin.ch/zefix/company/421132",
        **common,
    )
    return basel, zurich


async def test_uid_with_multiple_registered_seats_exact_match_is_answered():
    """F2: two Company rows sharing one uid (two registered seats of UBS AG) with
    an exact legal_name match resolve to `answered`, not `need_info` -- they are
    one legal entity, not an ambiguity. The lower ehraid (Basel) is shown by
    default, and the assumption names both seats."""
    basel, zurich = _ubs_seats()
    company_lookup = lookup(
        lindas=FakeLindas(search_by_name=[basel, zurich], dataset_modified="2026-09-23"),
        gazette=FakeGazette(publications_for_uid=[]),
    )

    result = await company_lookup.lookup(name="UBS AG", language="de")

    assert result["status"] == "answered"
    assert result["company"]["uid"] == format_uid("CHE101329561")
    assert result["company"]["seat"] == "Basel"
    assert any(
        "registered seats" in a.lower() and "basel" in a.lower() and "zürich" in a.lower()
        for a in result["assumptions"]
    )


async def test_uid_with_multiple_registered_seats_prefers_canton_match():
    """F2: when `canton` narrows to one of the uid's registered seats, that seat
    is shown instead of the lowest-ehraid default."""
    basel, zurich = _ubs_seats()
    company_lookup = lookup(
        lindas=FakeLindas(search_by_name=[basel, zurich], dataset_modified="2026-09-23"),
        gazette=FakeGazette(publications_for_uid=[]),
    )

    result = await company_lookup.lookup(name="UBS AG", canton="ZH", language="de")

    assert result["status"] == "answered"
    assert result["company"]["seat"] == "Zürich"


async def test_mixed_ambiguous_candidates_are_deduplicated_by_uid():
    """F2: a genuinely ambiguous prefix search (two distinct legal entities) still
    de-duplicates need_info candidates by uid, joining the seats of a
    multi-seat uid into one candidate row rather than listing it twice."""
    from mcp_swiss_info.zefix.sources.lindas import Company

    basel, zurich = _ubs_seats()
    fund_mgmt = Company(
        ehraid=430500,
        uid="CHE999999999",
        chid=None,
        names={"de": "UBS Fund Management (Switzerland) AG"},
        legal_name="UBS Fund Management (Switzerland) AG",
        legal_form_code="0106",
        legal_form_labels={"de": "Aktiengesellschaft"},
        seat="Basel",
        canton="BS",
        source_url="https://register.ld.admin.ch/zefix/company/430500",
    )
    company_lookup = lookup(lindas=FakeLindas(search_by_name=[basel, zurich, fund_mgmt]))

    result = await company_lookup.lookup(name="UBS")  # prefix match, no exact legal_name hit

    assert result["status"] == "need_info"
    assert len(result["candidates"]) == 2
    ubs_ag = next(c for c in result["candidates"] if c["uid"] == format_uid("CHE101329561"))
    assert "Basel" in ubs_ag["seat"]
    assert "Zürich" in ubs_ag["seat"]


# ---------------------------------------------------------------------------
# Language handling
# ---------------------------------------------------------------------------


async def test_romansh_falls_back_to_german_with_a_note(swisscom):
    """PRD G4, R9: a Romansh (rm) request is answered with German-labelled data and
    an explicit note about the fallback."""
    company_lookup = lookup(
        lindas=FakeLindas(find_by_uid=swisscom, dataset_modified="2026-09-23"),
        gazette=FakeGazette(publications_for_uid=[]),
    )
    result = await company_lookup.lookup(uid="CHE101654423", language="rm")

    assert result["status"] == "answered"
    assert result["notes"] == envelope.NOTES["de"]
    assert result["company"]["name"] == swisscom.names["de"]
    assumptions_and_notes = " ".join(result["assumptions"]) + " " + result["notes"]
    assert "rm" in assumptions_and_notes.lower() or "romansh" in assumptions_and_notes.lower() or "rätoromanisch" in assumptions_and_notes.lower() or "romanche" in assumptions_and_notes.lower()


async def test_french_language_notes_is_the_french_sentence(swisscom):
    """PRD G4: language="fr" renders notes (and by extension the answer) in French."""
    company_lookup = lookup(
        lindas=FakeLindas(find_by_uid=swisscom, dataset_modified="2026-09-23"),
        gazette=FakeGazette(publications_for_uid=[]),
    )
    result = await company_lookup.lookup(uid="CHE101654423", language="fr")

    assert result["status"] == "answered"
    assert result["notes"] == envelope.NOTES["fr"]


# ---------------------------------------------------------------------------
# Negative / cross-cutting checks
# ---------------------------------------------------------------------------


async def test_no_envelope_ever_serialises_message_or_content_keys(
    swisscom, nestle_candidates, enrichment_active
):
    """PRD §6.3, §6.4: `shabPub[].message` and gazette `content` are never read, so
    they can never leak into any envelope, in any of the five states."""

    def _lookup_with(search_by_name):
        # Every step shares the same enrichment/gazette/freshness fakes; only
        # the LINDAS name search result changes.
        return lookup(
            lindas=FakeLindas(search_by_name=search_by_name, dataset_modified="2026-09-23"),
            zefix=FakeZefix(firm_detail=enrichment_active, respect_robots_txt=False),
            gazette=FakeGazette(publications_for_uid=[]),
        )

    answered = await _lookup_with([swisscom]).lookup(name="Swisscom (Schweiz) AG")
    _assert_no_banned_keys(answered)

    need_info = await _lookup_with(nestle_candidates).lookup(name="Nestlé")
    _assert_no_banned_keys(need_info)

    no_match = await _lookup_with([]).lookup(name="Ganz Unbekannte GmbH XYZ")
    _assert_no_banned_keys(no_match)

    out_of_scope = await _lookup_with([]).lookup(question="Wie viele AGs gibt es im Kanton Zug?")
    _assert_no_banned_keys(out_of_scope)

    unavailable = await _lookup_with(SourceUnavailable(source="lindas", error_class="timeout")).lookup(
        name="Swisscom (Schweiz) AG"
    )
    _assert_no_banned_keys(unavailable)

    for result in (answered, need_info, no_match, out_of_scope, unavailable):
        assert result["status"] in FIVE_STATES
        assert "source_validated_at" in result


def test_respect_robots_txt_defaults_to_true():
    """PRD §6.5, `BaseKnowledge/CHALLENGE.md` L112: compliant by default."""
    assert Settings().respect_robots_txt is True


async def test_egress_denied_for_unknown_host():
    """PRD §6.7: outbound requests are limited to the egress allow-list; a host
    outside it is rejected before any real network I/O. respx guards against an
    actual network call ever being attempted regardless."""
    with respx.mock(assert_all_called=False) as mocked:
        mocked.get("https://example.com").respond(200)
        async with make_client(5.0) as client:
            with pytest.raises(EgressDenied):
                await client.get("https://example.com")
