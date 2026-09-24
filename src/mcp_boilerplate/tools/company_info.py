"""
`company_info`: the one MCP tool this server exposes (docs/prd-zefix-company-info.md).

Resolution algorithm implements PRD §5.2 (steps 0-6): step-0 gates (persons,
jurisdiction, analytics, topic) run on `question`/parameters alone, with no
network call, except the persons gate, which resolves the company first (so
the cantonal-excerpt link can still be returned) when `name`/`uid` is given.
The main path resolves the company on LINDAS (`sources/lindas.py`, primary,
always used), optionally enriches it via the Zefix web endpoint
(`sources/zefix.py`, policy-gated by `settings.respect_robots_txt` /
credentials), and attaches gazette publications (`sources/gazette.py`).

Every source call goes through `_call_source`, which never lets an exception
other than `SourceUnavailable` escape with a stack trace: it is caught,
logged, and turned into a `SourceUnavailable` carrying the original
exception's class name as `error_class` (PRD contract: no leaking internals).
"""

from __future__ import annotations

from time import monotonic
from typing import Any

from ..zefix import envelope, gates
from ..config.settings import settings
from ..server import mcp
from ..zefix.sources import gazette, lindas
from ..zefix.sources import rest as zefix
from ..zefix.sources.http import SourceUnavailable
from ..utils.logger import setup_logger

logger = setup_logger("mcp_boilerplate.tools.company_info")

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

# Gazette rubrics that are commercial-register publications (HR = Handelsregister).
# Other rubrics (building permits, debt enforcement, ...) also cite company UIDs
# but are not register entries and are out of scope for company_info.
REGISTER_RUBRICS: list[str] = ["HR"]

AUTHORITY = "Eidgenössisches Amt für das Handelsregister (EHRA), Bundesamt für Justiz"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _remaining(deadline: float) -> float:
    return max(0.0, deadline - monotonic())


async def _call_source(source_name: str, awaitable: Any) -> tuple[str, Any]:
    """Await a source call; never let a non-`SourceUnavailable` exception escape.

    Returns ("ok", value) or ("unavailable", SourceUnavailable instance).
    """
    try:
        return "ok", await awaitable
    except SourceUnavailable as exc:
        return "unavailable", exc
    except Exception as exc:  # noqa: BLE001 - contract: never leak a stack trace
        logger.exception("unexpected error calling %s", source_name)
        return "unavailable", SourceUnavailable(source_name, type(exc).__name__)


async def _safe_dataset_modified() -> str | None:
    outcome, value = await _call_source("lindas", lindas.dataset_modified())
    return value if outcome == "ok" else None


def _legal_form_label(company: lindas.Company, language: str) -> str | None:
    labels = company.legal_form_labels or {}
    return labels.get(language) or labels.get("de") or next(iter(labels.values()), None)


def _display_name(company: lindas.Company, language: str) -> str | None:
    return company.names.get(language) or company.legal_name or next(iter(company.names.values()), None)


def _candidate_dict(company: lindas.Company, language: str) -> dict[str, Any]:
    return _candidate_dict_for_group([company], language)


def _group_by_uid(companies: list[lindas.Company]) -> dict[str, list[lindas.Company]]:
    """Group Company rows by uid, preserving first-seen order of each uid.

    LINDAS can hold more than one row for the same legal entity: one per
    registered seat (F2 - e.g. UBS AG has rows for its Basel and Zürich
    seats, same CompanyUID, same legalName, different ehraid). Those are one
    company, not an ambiguity, so every disambiguation decision groups by
    uid first. A company with no uid (defensive; LINDAS always carries one)
    gets its own singleton group keyed by ehraid so it never merges with an
    unrelated company.
    """
    groups: dict[str, list[lindas.Company]] = {}
    for company in companies:
        key = company.uid or f"_no_uid_{company.ehraid}"
        groups.setdefault(key, []).append(company)
    return groups


def _seats_of(group: list[lindas.Company]) -> list[str]:
    seats: list[str] = []
    for company in sorted(group, key=lambda c: c.ehraid):
        if company.seat and company.seat not in seats:
            seats.append(company.seat)
    return seats


def _resolve_seat_group(group: list[lindas.Company], canton: str | None) -> tuple[lindas.Company, list[str]]:
    """Pick one row to represent a uid's group of registered seats.

    Prefers the seat whose canton matches the `canton` parameter, else the
    lowest ehraid (deterministic). Returns (chosen, assumptions) - assumptions
    is empty for a singleton group (nothing to explain).
    """
    ordered = sorted(group, key=lambda c: c.ehraid)
    chosen = ordered[0]
    if canton:
        canton_norm = canton.strip().upper()
        for company in ordered:
            if (company.canton or "").upper() == canton_norm:
                chosen = company
                break

    assumptions: list[str] = []
    if len(ordered) > 1:
        seats = _seats_of(ordered)
        assumptions.append(
            f"UID has {len(seats)} registered seats: {', '.join(seats)}; showing {chosen.seat}"
        )
    return chosen, assumptions


def _candidate_dict_for_group(group: list[lindas.Company], language: str) -> dict[str, Any]:
    ordered = sorted(group, key=lambda c: c.ehraid)
    representative = ordered[0]
    seats = _seats_of(ordered)
    return {
        "name": _display_name(representative, language),
        "legal_form": _legal_form_label(representative, language),
        "seat": ", ".join(seats) if seats else None,
        "uid": zefix.format_uid(representative.uid) if representative.uid else None,
    }


def _publication_dict(pub: gazette.Publication) -> dict[str, Any]:
    return {
        "id": pub.id,
        "date": pub.date,
        "registry_office": pub.registry_office,
        "registry_canton": pub.registry_canton,
        "rubric": pub.rubric,
        "sub_rubric": pub.sub_rubric,
        "mutation_types": [pub.sub_rubric] if pub.sub_rubric else [],
        "title": pub.title,
        "source_url": pub.source_url,
        "api_url": pub.api_url,
    }


def _map_status(enrichment: zefix.Enrichment) -> str:
    raw = (enrichment.status or "").strip()
    if enrichment.delete_date:
        return "DELETED"
    if raw == "EXISTIEREND":
        return "ACTIVE"
    if raw == "GELOESCHT":
        return "DELETED"
    if raw:
        return raw.upper()
    return "ACTIVE"


def _build_company_dict(
    company: lindas.Company,
    language: str,
    *,
    status: str,
    deleted_on: str | None,
    old_names: list[str],
) -> dict[str, Any]:
    address = dict(company.address) if company.address else {"street": None, "zip": None, "city": None}
    return {
        "name": _display_name(company, language),
        "names": dict(company.names),
        "uid": zefix.format_uid(company.uid) if company.uid else None,
        "chid": company.chid,
        "ehraid": company.ehraid,
        "legal_form": _legal_form_label(company, language),
        "legal_form_code": company.legal_form_code or None,
        "seat": company.seat or None,
        "seat_bfs_id": company.seat_bfs_id,
        "canton": company.canton,
        "address": address,
        "purpose": company.purpose,
        "status": status,
        "deleted_on": deleted_on,
        "old_names": old_names,
    }


def _build_derived_company_dict(
    normalized_uid: str, canton: str | None, deletion_pub: gazette.Publication
) -> dict[str, Any]:
    return {
        "name": None,
        "names": {},
        "uid": zefix.format_uid(normalized_uid),
        "chid": None,
        "ehraid": None,
        "legal_form": None,
        "legal_form_code": None,
        "seat": None,
        "seat_bfs_id": None,
        "canton": canton,
        "address": {"street": None, "zip": None, "city": None},
        "purpose": None,
        "status": "DELETED",
        "deleted_on": deletion_pub.date,
        "old_names": [],
    }


# ---------------------------------------------------------------------------
# Resolution: LINDAS lookup, disambiguation, branch 3b, enrichment (§5.2 1-4)
# ---------------------------------------------------------------------------


async def _run_enrichment(ehraid: int, deadline: float) -> tuple[zefix.Enrichment | None, str]:
    if not zefix.enrichment_allowed():
        return None, "policy_robots"
    remaining = _remaining(deadline)
    if remaining <= 0:
        return None, "skipped"
    budget = min(settings.zefix_timeout_s, remaining)
    outcome, value = await _call_source("zefix", zefix.firm_detail(ehraid, budget_s=budget))
    if outcome == "unavailable":
        return None, "source_unavailable"
    return value, "answered"


async def _resolve_company(
    *, name: str | None, uid: str | None, canton: str | None, deadline: float, language: str
) -> dict[str, Any]:
    """Steps 1-4 of PRD §5.2: normalise uid, LINDAS lookup, disambiguate, enrich.

    Returns a dict tagged by "kind": "resolved" | "ambiguous" | "no_match" |
    "derived_deleted" (branch 3b) | "source_unavailable".
    """
    normalized_uid = zefix.normalize_uid(uid) if uid else None
    lindas_budget = min(settings.lindas_timeout_s, _remaining(deadline))

    if normalized_uid:
        outcome, value = await _call_source("lindas", lindas.find_by_uid(normalized_uid, budget_s=lindas_budget))
        if outcome == "unavailable":
            exc: SourceUnavailable = value
            return {
                "kind": "source_unavailable",
                "source": exc.source,
                "error_class": exc.error_class,
                "retry_after_s": exc.retry_after_s,
            }
        company = value
        if company is not None:
            enrichment, enrichment_status = await _run_enrichment(company.ehraid, deadline)
            return {
                "kind": "resolved",
                "company": company,
                "assumptions": [],
                "enrichment": enrichment,
                "enrichment_status": enrichment_status,
            }

        # Branch 3b: uid given, zero LINDAS hits -> the gazette decides.
        gazette_budget = max(_remaining(deadline), 5.0)
        outcome, value = await _call_source(
            "gazette",
            gazette.publications_for_uid(normalized_uid, limit=20, budget_s=gazette_budget, language=language, rubrics=REGISTER_RUBRICS),
        )
        if outcome == "unavailable":
            exc = value
            return {
                "kind": "source_unavailable",
                "source": exc.source,
                "error_class": exc.error_class,
                "retry_after_s": exc.retry_after_s,
            }
        pubs = value
        deletion_pub = next((p for p in pubs if gazette.is_deletion(p)), None)
        if deletion_pub is not None:
            return {"kind": "derived_deleted", "publications": pubs, "deletion_pub": deletion_pub}
        return {
            "kind": "no_match",
            "searched": {"name": None, "uid": zefix.format_uid(normalized_uid), "canton": canton},
            "gazette_checked": True,
        }

    if name:
        outcome, value = await _call_source(
            "lindas", lindas.search_by_name(name, canton=canton, limit=10, budget_s=lindas_budget)
        )
        if outcome == "unavailable":
            exc = value
            return {
                "kind": "source_unavailable",
                "source": exc.source,
                "error_class": exc.error_class,
                "retry_after_s": exc.retry_after_s,
            }
        candidates: list[lindas.Company] = value
        if not candidates:
            return {"kind": "no_match", "searched": {"name": name, "uid": None, "canton": canton}, "gazette_checked": False}

        # F2: group by uid before applying any disambiguation rule. Several
        # rows sharing one uid are one legal entity with several registered
        # seats, not an ambiguity - resolve straight through regardless of
        # the exact-legal-name rule below.
        groups = _group_by_uid(candidates)
        if len(groups) == 1:
            group = next(iter(groups.values()))
            company, seat_assumptions = _resolve_seat_group(group, canton)
            enrichment, enrichment_status = await _run_enrichment(company.ehraid, deadline)
            return {
                "kind": "resolved",
                "company": company,
                "assumptions": seat_assumptions,
                "enrichment": enrichment,
                "enrichment_status": enrichment_status,
            }

        exact = [c for c in candidates if (c.legal_name or "").strip().casefold() == name.strip().casefold()]
        exact_groups = _group_by_uid(exact)
        if len(exact_groups) == 1:
            group = next(iter(exact_groups.values()))
            company, seat_assumptions = _resolve_seat_group(group, canton)
            enrichment, enrichment_status = await _run_enrichment(company.ehraid, deadline)
            assumptions = [f"selected the exact-name match among {len(candidates)} prefix matches", *seat_assumptions]
            return {
                "kind": "resolved",
                "company": company,
                "assumptions": assumptions,
                "enrichment": enrichment,
                "enrichment_status": enrichment_status,
            }

        missing = "seat" if canton else "uid"
        cand_dicts = [_candidate_dict_for_group(g, language) for g in list(groups.values())[:5]]
        return {"kind": "ambiguous", "candidates": cand_dicts, "missing": missing}

    # uid was given but malformed and not jurisdiction-gated (e.g. wrong digit count).
    return {"kind": "no_match", "searched": {"name": None, "uid": uid, "canton": canton}, "gazette_checked": False}


# ---------------------------------------------------------------------------
# Envelope assembly for the two "answered" shapes
# ---------------------------------------------------------------------------


async def _build_answered_envelope(
    resolution: dict[str, Any],
    *,
    include_publications: bool,
    max_publications: int,
    deadline: float,
    lang: str,
    is_romansh: bool,
) -> dict[str, Any]:
    company: lindas.Company = resolution["company"]
    enrichment: zefix.Enrichment | None = resolution.get("enrichment")
    enrichment_status: str = resolution.get("enrichment_status", "skipped")
    assumptions: list[str] = list(resolution.get("assumptions", []))

    max_pub = max(1, min(int(max_publications), 20))

    pubs: list[gazette.Publication] = []
    if include_publications:
        gazette_budget = max(_remaining(deadline), 5.0)
        outcome, value = await _call_source(
            "gazette",
            gazette.publications_for_uid(company.uid, limit=max_pub, budget_s=gazette_budget, language=lang, rubrics=REGISTER_RUBRICS),
        )
        if outcome == "ok":
            pubs = value
            publications_status = "answered"
        else:
            publications_status = "source_unavailable"
    else:
        publications_status = "skipped"

    pubs_sorted = sorted(pubs, key=lambda p: p.date, reverse=True)[:max_pub]

    enrichment_answered = enrichment is not None and enrichment_status == "answered"
    if enrichment_answered:
        status = _map_status(enrichment)
        status_source = "zefix"
        deleted_on = enrichment.delete_date
        old_names = list(enrichment.old_names)
        cantonal_excerpt_url = enrichment.cantonal_excerpt_url
    else:
        status = "ACTIVE"
        status_source = "index"
        deleted_on = None
        old_names = []
        cantonal_excerpt_url = None

    dataset_modified_value = await _safe_dataset_modified()

    if status_source == "index":
        assumptions.append(
            "status inferred from membership in the active-entity index as of "
            f"{dataset_modified_value or 'unknown date'}"
        )

    if enrichment_answered and enrichment.shab_date:
        effective_from = enrichment.shab_date
        assumptions.append("effective_from from the Zefix enrichment shabDate")
    elif pubs_sorted:
        effective_from = pubs_sorted[0].date
        assumptions.append("effective_from from the newest gazette publication")
    else:
        effective_from = dataset_modified_value
        assumptions.append("effective_from from the LINDAS dataset_modified date")

    if is_romansh:
        assumptions.append(envelope._ROMANSH_ASSUMPTION)

    company_dict = _build_company_dict(company, lang, status=status, deleted_on=deleted_on, old_names=old_names)

    citation = {
        "authority": AUTHORITY,
        "level": "federal",
        "source_url": company.source_url,
        "zefix_url": zefix.zefix_detail_url(company.ehraid, lang),
        "cantonal_excerpt_url": cantonal_excerpt_url,
        "passage": envelope.render_passage(company_dict, lang),
        "effective_from": effective_from,
        "published_at": effective_from,
        "dataset_modified": dataset_modified_value,
        "source_status": "indicative",
        "source_validated_at": envelope.now_iso(),
    }

    answer = envelope.render_answer(company_dict, lang, status_source=status_source)
    publications_payload = [_publication_dict(p) for p in pubs_sorted] if include_publications else None

    return envelope.answered(
        answer=answer,
        company=company_dict,
        citation=citation,
        publications=publications_payload,
        publications_status=publications_status,
        enrichment_status=enrichment_status,
        assumptions=assumptions,
        derived=False,
        derived_rule=None,
        language=lang,
    )


async def _build_derived_deleted_envelope(
    resolution: dict[str, Any],
    *,
    uid: str,
    canton: str | None,
    include_publications: bool,
    max_publications: int,
    lang: str,
    is_romansh: bool,
) -> dict[str, Any]:
    pubs: list[gazette.Publication] = resolution["publications"]
    deletion_pub: gazette.Publication = resolution["deletion_pub"]
    max_pub = max(1, min(int(max_publications), 20))
    pubs_sorted = sorted(pubs, key=lambda p: p.date, reverse=True)[:max_pub]

    normalized_uid = zefix.normalize_uid(uid)
    company_dict = _build_derived_company_dict(normalized_uid, canton, deletion_pub)

    dataset_modified_value = await _safe_dataset_modified()

    assumptions = ["effective_from from the gazette deletion publication (no LINDAS record for this UID)"]
    if is_romansh:
        assumptions.append(envelope._ROMANSH_ASSUMPTION)

    citation = {
        "authority": AUTHORITY,
        "level": "federal",
        "source_url": deletion_pub.source_url,
        "zefix_url": None,
        "cantonal_excerpt_url": None,
        "passage": envelope.render_passage(company_dict, lang),
        "effective_from": deletion_pub.date,
        "published_at": deletion_pub.date,
        "dataset_modified": dataset_modified_value,
        "source_status": "indicative",
        "source_validated_at": envelope.now_iso(),
    }

    answer = envelope.render_answer(company_dict, lang, status_source="gazette")

    if include_publications:
        publications_payload = [_publication_dict(p) for p in pubs_sorted]
        publications_status = "answered"
    else:
        publications_payload = None
        publications_status = "skipped"

    return envelope.answered(
        answer=answer,
        company=company_dict,
        citation=citation,
        publications=publications_payload,
        publications_status=publications_status,
        enrichment_status="skipped",
        assumptions=assumptions,
        derived=True,
        derived_rule="absent from the active-entity index and a deletion publication exists",
        language=lang,
    )


# ---------------------------------------------------------------------------
# The tool
# ---------------------------------------------------------------------------


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
    lang = envelope.normalize_language(language)
    is_romansh = (language or "").strip().lower() == "rm"
    deadline = monotonic() + settings.call_budget_s

    # --- Step 0: gates, evaluated on question + parameters, no network call
    # except the persons gate's own (optional) company resolution. ----------

    has_identifier = bool(name or uid)
    reason = gates.classify(question, uid, canton, has_identifier)

    if reason == "persons":
        # classify() cannot express this in a single reason: the persons gate
        # is the one gate that does its own (optional) I/O before answering,
        # so it can still return the cantonal-excerpt link when a company was
        # given. That resolution stays here, not in gates.py (pure).
        cantonal_excerpt_url: str | None = None
        if name or uid:
            resolution = await _resolve_company(name=name, uid=uid, canton=canton, deadline=deadline, language=lang)
            if resolution["kind"] == "resolved":
                enrichment = resolution.get("enrichment")
                if enrichment is not None:
                    cantonal_excerpt_url = enrichment.cantonal_excerpt_url
        return envelope.out_of_scope(
            reason="persons",
            covered=envelope.OUT_OF_SCOPE_SENTENCES["persons"][lang],
            cantonal_excerpt_url=cantonal_excerpt_url,
            language=lang,
        )

    if reason == "jurisdiction":
        return envelope.out_of_scope(
            reason="jurisdiction",
            covered=envelope.OUT_OF_SCOPE_SENTENCES["jurisdiction"][lang],
            language=lang,
        )

    if reason == "analytics":
        return envelope.out_of_scope(
            reason="analytics",
            covered=envelope.OUT_OF_SCOPE_SENTENCES["analytics"][lang],
            language=lang,
        )

    if reason == "topic":
        return envelope.out_of_scope(
            reason="topic",
            covered=envelope.OUT_OF_SCOPE_SENTENCES["topic"][lang],
            language=lang,
        )

    if not has_identifier:
        return envelope.need_info(
            question=envelope._ASK_NAME_QUESTION[lang], candidates=[], missing="name", language=lang
        )

    # --- Steps 1-6: resolve, enrich, attach publications, build envelope. --

    resolution = await _resolve_company(name=name, uid=uid, canton=canton, deadline=deadline, language=lang)
    kind = resolution["kind"]

    if kind == "source_unavailable":
        result = envelope.source_unavailable(
            source=resolution["source"],
            error_class=resolution["error_class"],
            retry_after_s=resolution.get("retry_after_s"),
            language=lang,
        )
        if resolution["error_class"] == "timeout_scan":
            result["answer"] = envelope._TIMEOUT_SCAN_SENTENCES[lang]
        return result

    if kind == "ambiguous":
        missing = resolution["missing"]
        return envelope.need_info(
            question=envelope.NEED_INFO_QUESTIONS[missing][lang],
            candidates=resolution["candidates"],
            missing=missing,
            language=lang,
        )

    if kind == "no_match":
        dataset_modified_value = await _safe_dataset_modified()
        return envelope.no_match(
            searched=resolution["searched"],
            gazette_checked=resolution["gazette_checked"],
            source_url=settings.lindas_endpoint,
            dataset_modified=dataset_modified_value,
            language=lang,
        )

    if kind == "derived_deleted":
        return await _build_derived_deleted_envelope(
            resolution,
            uid=uid,  # type: ignore[arg-type]  # normalized_uid was truthy to reach this branch
            canton=canton,
            include_publications=include_publications,
            max_publications=max_publications,
            lang=lang,
            is_romansh=is_romansh,
        )

    return await _build_answered_envelope(
        resolution,
        include_publications=include_publications,
        max_publications=max_publications,
        deadline=deadline,
        lang=lang,
        is_romansh=is_romansh,
    )


company_info_tool = mcp.tool(company_info, name="company_info")
