"""
Shared fixtures for the company_info test suite.

docs/prd-zefix-company-info.md is authoritative for behaviour; the module
interfaces this file imports against are the binding contract for S1-S4
(config/settings.py and sources/http.py already exist; sources/lindas.py,
sources/zefix.py, sources/gazette.py, envelope.py, tools/company_info.py do
not yet exist -- every import below fails with ImportError until they land.
That failure is expected and is the point of S0: these are acceptance tests
written before the implementation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from mcp_boilerplate.config import settings as settings_module
from mcp_boilerplate.zefix_sources import gazette
from mcp_boilerplate.zefix_sources.gazette import Publication
from mcp_boilerplate.zefix_sources.lindas import Company
from mcp_boilerplate.zefix_sources.zefix import Enrichment

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@pytest.fixture
def settings_override(monkeypatch):
    """Return a setter that monkeypatches attributes on the live settings singleton.

    Usage: settings_override(respect_robots_txt=False, zefix_username="u").
    monkeypatch restores the original values automatically at teardown.
    """

    def _override(**kwargs):
        for key, value in kwargs.items():
            monkeypatch.setattr(settings_module.settings, key, value)
        return settings_module.settings

    return _override


# ---------------------------------------------------------------------------
# Company / Enrichment / Publication fixtures (PRD §5.3)
# ---------------------------------------------------------------------------


@pytest.fixture
def swisscom() -> Company:
    """The Swisscom (Schweiz) AG record exactly as recorded in PRD §5.3 / §6.2."""
    return Company(
        ehraid=415941,
        uid="CHE101654423",
        chid="CH-035.3.016.930-9",
        names={
            "de": "Swisscom (Schweiz) AG",
            "fr": "Swisscom (Suisse) SA",
            "it": "Swisscom (Svizzera) SA",
            "en": "Swisscom (Switzerland) Ltd",
        },
        legal_name="Swisscom (Schweiz) AG",
        legal_form_code="0106",
        legal_form_labels={
            "de": "Aktiengesellschaft",
            "fr": "Société anonyme",
            "it": "Società anonima",
            "en": "Company limited by shares",
        },
        seat="Ittigen",
        seat_bfs_id=362,
        canton="BE",
        address={"street": "Alte Tiefenaustrasse 6", "zip": "3050", "city": "Bern"},
        purpose=(
            "Erbringung von Dienstleistungen und Vertrieb von Produkten in den "
            "Bereichen Telekommunikation und Informationstechnologie in der Schweiz."
        ),
        source_url="https://register.ld.admin.ch/zefix/company/415941",
    )


@pytest.fixture
def nestle_candidates() -> list[Company]:
    """Three companies sharing the prefix "nestl", none an exact legal-name match for "Nestlé"."""
    return [
        Company(
            ehraid=100001,
            uid="CHE106893085",
            chid="CH-021.3.906.075-4",
            names={"de": "Nestlé S.A.", "fr": "Nestlé S.A.", "it": "Nestlé S.A.", "en": "Nestlé S.A."},
            legal_name="Nestlé S.A.",
            legal_form_code="0106",
            legal_form_labels={
                "de": "Aktiengesellschaft",
                "fr": "Société anonyme",
                "it": "Società anonima",
                "en": "Company limited by shares",
            },
            seat="Vevey",
            seat_bfs_id=5890,
            canton="VD",
            address={"street": "Avenue Nestlé 55", "zip": "1800", "city": "Vevey"},
            purpose="Holding.",
            source_url="https://register.ld.admin.ch/zefix/company/100001",
        ),
        Company(
            ehraid=100002,
            uid="CHE114328765",
            chid="CH-021.3.914.876-1",
            names={
                "de": "Nestlé Health Science SA",
                "fr": "Nestlé Health Science SA",
                "it": "Nestlé Health Science SA",
                "en": "Nestlé Health Science SA",
            },
            legal_name="Nestlé Health Science SA",
            legal_form_code="0106",
            legal_form_labels={
                "de": "Aktiengesellschaft",
                "fr": "Société anonyme",
                "it": "Società anonima",
                "en": "Company limited by shares",
            },
            seat="Épalinges",
            seat_bfs_id=5591,
            canton="VD",
            address={"street": "Route de Sévaz 6", "zip": "1070", "city": "Puidoux"},
            purpose="Recherche et commercialisation de nutrition médicale.",
            source_url="https://register.ld.admin.ch/zefix/company/100002",
        ),
        Company(
            ehraid=100003,
            uid="CHE108795640",
            chid="CH-021.3.908.796-8",
            names={
                "de": "Nestlé Waters (Switzerland) SA",
                "fr": "Nestlé Waters (Switzerland) SA",
                "it": "Nestlé Waters (Switzerland) SA",
                "en": "Nestlé Waters (Switzerland) SA",
            },
            legal_name="Nestlé Waters (Switzerland) SA",
            legal_form_code="0106",
            legal_form_labels={
                "de": "Aktiengesellschaft",
                "fr": "Société anonyme",
                "it": "Società anonima",
                "en": "Company limited by shares",
            },
            seat="Vevey",
            seat_bfs_id=5890,
            canton="VD",
            address={"street": "Avenue Nestlé 55", "zip": "1800", "city": "Vevey"},
            purpose="Production et distribution d'eaux minérales.",
            source_url="https://register.ld.admin.ch/zefix/company/100003",
        ),
    ]


@pytest.fixture
def enrichment_active() -> Enrichment:
    """A Zefix enrichment payload for an active company (PRD §5.3 example)."""
    return Enrichment(
        status="ACTIVE",
        shab_date="2026-06-12",
        delete_date=None,
        cantonal_excerpt_url="https://be.chregister.ch/cr-portal/auszug/x",
        old_names=[],
        mutation_types=[],
    )


@pytest.fixture
def publications() -> list[Publication]:
    """Two gazette publications for the same company: one a deletion, one not.

    The deletion sub-rubric code is read from gazette.DELETION_SUBRUBRICS
    rather than hardcoded, per the module contract in interfaces.md.
    """
    deletion_code = next(iter(gazette.DELETION_SUBRUBRICS))
    return [
        Publication(
            id="1006731743",
            date="2026-06-01",
            registry_office="Handelsregisteramt des Kantons Bern",
            registry_canton="BE",
            rubric="HR",
            sub_rubric="HR02",
            title="Mutation",
            source_url="https://amtsblattportal.ch/#!/search?publicationId=1006731743",
            api_url="https://amtsblattportal.ch/api/v1/publications/1006731743/xml",
        ),
        Publication(
            id="1006731894",
            date="2026-06-12",
            registry_office="Handelsregisteramt des Kantons Bern",
            registry_canton="BE",
            rubric="HR",
            sub_rubric=deletion_code,
            title="Löschung",
            source_url="https://amtsblattportal.ch/#!/search?publicationId=1006731894",
            api_url="https://amtsblattportal.ch/api/v1/publications/1006731894/xml",
        ),
    ]


# ---------------------------------------------------------------------------
# Source-layer monkeypatch helper
# ---------------------------------------------------------------------------


def _as_async_mock(value):
    """Wrap a fixed value, an exception, or a callable into an AsyncMock.

    - Exception instance or exception class -> AsyncMock(side_effect=...) that raises.
    - Any other callable (a plain function, sync or async) -> used as side_effect,
      so its return value becomes the coroutine's result (AsyncMock supports this).
    - Anything else (a dataclass instance, list, dict, None, str, ...) -> AsyncMock(return_value=...).
    """
    if isinstance(value, BaseException):
        return AsyncMock(side_effect=value)
    if isinstance(value, type) and issubclass(value, BaseException):
        return AsyncMock(side_effect=value)
    if callable(value):
        return AsyncMock(side_effect=value)
    return AsyncMock(return_value=value)


_UNSET = object()  # distinguishes "don't patch this" from "patch it to return None"
                    # (find_by_uid=None is a legitimate mocked return value: a LINDAS miss)


def patch_sources(
    monkeypatch,
    *,
    find_by_uid=_UNSET,
    search_by_name=_UNSET,
    firm_detail=_UNSET,
    publications_for_uid=_UNSET,
    dataset_modified=_UNSET,
):
    """Monkeypatch the source-module functions as seen from tools.company_info.

    tools/company_info.py does `from ..zefix_sources import lindas, zefix, gazette` and
    calls them as `lindas.find_by_uid(...)` etc. (interfaces.md), so patching the
    attribute on the module object patches every caller, including company_info.

    Pass a Company/list[Company]/Enrichment/list[Publication]/str/None for a
    fixed return value (find_by_uid=None mocks a LINDAS miss -- it is NOT the
    same as omitting the argument), an Exception instance/class to make the
    call raise, or a callable for per-call behaviour. Returns a dict of the
    AsyncMocks that were installed (keyed by parameter name) so tests can
    assert on call_count/args.

    Also relevant: enrichment_allowed() is gated purely by settings
    (respect_robots_txt, zefix_username, zefix_password) per interfaces.md, so
    tests control it via settings_override rather than patching a function.
    """
    from mcp_boilerplate.tools import company_info as company_info_module

    installed: dict[str, AsyncMock] = {}
    if find_by_uid is not _UNSET:
        mock = _as_async_mock(find_by_uid)
        monkeypatch.setattr(company_info_module.lindas, "find_by_uid", mock)
        installed["find_by_uid"] = mock
    if search_by_name is not _UNSET:
        mock = _as_async_mock(search_by_name)
        monkeypatch.setattr(company_info_module.lindas, "search_by_name", mock)
        installed["search_by_name"] = mock
    if firm_detail is not _UNSET:
        mock = _as_async_mock(firm_detail)
        monkeypatch.setattr(company_info_module.zefix, "firm_detail", mock)
        installed["firm_detail"] = mock
    if publications_for_uid is not _UNSET:
        mock = _as_async_mock(publications_for_uid)
        monkeypatch.setattr(company_info_module.gazette, "publications_for_uid", mock)
        installed["publications_for_uid"] = mock
    if dataset_modified is not _UNSET:
        mock = _as_async_mock(dataset_modified)
        monkeypatch.setattr(company_info_module.lindas, "dataset_modified", mock)
        installed["dataset_modified"] = mock
    return installed
