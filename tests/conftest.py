"""
Shared fixtures for the company_info test suite.

docs/prd-zefix-company-info.md is authoritative for behaviour. Tests drive
`zefix.lookup.CompanyLookup` with injected fakes (FakeLindas, FakeZefix,
FakeGazette) built by `lookup(...)`, the same constructor-injection style as
`Crawler(fetcher, fetcher, db, FakeEmbedder())` in tests/test_crawler.py. No
module attribute or settings field is monkeypatched.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from mcp_swiss_info.config.settings import Settings
from mcp_swiss_info.zefix import CompanyLookup
from mcp_swiss_info.zefix.sources import gazette
from mcp_swiss_info.zefix.sources.gazette import Publication
from mcp_swiss_info.zefix.sources.lindas import Company
from mcp_swiss_info.zefix.sources.rest import Enrichment, ZefixClient

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
# Fake source clients (T1)
# ---------------------------------------------------------------------------


_UNSET = object()  # distinguishes "not configured" from "configured to return None"
                    # (find_by_uid=None is a legitimate canned return value: a LINDAS miss)


def _as_async_mock(owner: str, method: str, value) -> AsyncMock:
    """Wrap one canned behaviour into an AsyncMock that records its awaits.

    - _UNSET -> fails the test if awaited (pytest.fail raises a BaseException,
      so CompanyLookup._call_source cannot swallow it).
    - Exception instance or exception class -> raised when awaited.
    - Any other callable (a plain function, sync or async) -> used as side_effect,
      so its return value becomes the coroutine's result.
    - Anything else (a dataclass instance, list, dict, None, str, ...) -> returned.
    """
    if value is _UNSET:

        def _unconfigured(*_args, **_kwargs):
            pytest.fail(f"{owner}.{method} was called but not configured")

        return AsyncMock(side_effect=_unconfigured)
    if isinstance(value, BaseException):
        return AsyncMock(side_effect=value)
    if isinstance(value, type) and issubclass(value, BaseException):
        return AsyncMock(side_effect=value)
    if callable(value):
        return AsyncMock(side_effect=value)
    return AsyncMock(return_value=value)


class FakeLindas:
    """Stands in for `LindasClient`. `calls[method]` is the AsyncMock behind
    each method, for call-count/argument assertions."""

    def __init__(self, *, find_by_uid=_UNSET, search_by_name=_UNSET, dataset_modified=_UNSET):
        self.calls = {
            "find_by_uid": _as_async_mock("FakeLindas", "find_by_uid", find_by_uid),
            "search_by_name": _as_async_mock("FakeLindas", "search_by_name", search_by_name),
            "dataset_modified": _as_async_mock("FakeLindas", "dataset_modified", dataset_modified),
        }

    async def find_by_uid(self, uid: str, *, budget_s: float) -> Company | None:
        return await self.calls["find_by_uid"](uid, budget_s=budget_s)

    async def search_by_name(
        self, name: str, *, canton: str | None = None, limit: int = 10, budget_s: float
    ) -> list[Company]:
        return await self.calls["search_by_name"](name, canton=canton, limit=limit, budget_s=budget_s)

    async def dataset_modified(self) -> str | None:
        return await self.calls["dataset_modified"]()


class FakeZefix(ZefixClient):
    """Stands in for `ZefixClient`. Inherits the real `enrichment_allowed()`
    policy (PRD §6.5), driven by the constructor's respect_robots_txt /
    username / password; `firm_detail` is canned."""

    def __init__(
        self,
        *,
        firm_detail=_UNSET,
        respect_robots_txt: bool = True,
        username: str | None = None,
        password: str | None = None,
    ):
        super().__init__(
            base_url="https://fake.invalid",
            username=username,
            password=password,
            respect_robots_txt=respect_robots_txt,
        )
        self.calls = {"firm_detail": _as_async_mock("FakeZefix", "firm_detail", firm_detail)}

    async def firm_detail(self, ehraid: int, *, budget_s: float) -> Enrichment:
        return await self.calls["firm_detail"](ehraid, budget_s=budget_s)


class FakeGazette:
    """Stands in for `GazetteClient`."""

    def __init__(self, *, publications_for_uid=_UNSET, rubrics=_UNSET):
        self.calls = {
            "publications_for_uid": _as_async_mock("FakeGazette", "publications_for_uid", publications_for_uid),
            "rubrics": _as_async_mock("FakeGazette", "rubrics", rubrics),
        }

    async def publications_for_uid(
        self,
        uid: str,
        *,
        limit: int,
        budget_s: float,
        language: str = "de",
        rubrics: list[str] | None = None,
    ) -> list[Publication]:
        return await self.calls["publications_for_uid"](
            uid, limit=limit, budget_s=budget_s, language=language, rubrics=rubrics
        )

    async def rubrics(self) -> dict:
        return await self.calls["rubrics"]()


def lookup(
    *,
    lindas: FakeLindas | None = None,
    zefix: FakeZefix | None = None,
    gazette: FakeGazette | None = None,
    config: Settings | None = None,
) -> CompanyLookup:
    """Build a `CompanyLookup` over fakes. A fake not passed in is an
    unconfigured one (any call fails the test); `config` defaults to
    `Settings` built without reading a .env file."""
    return CompanyLookup(
        lindas=lindas if lindas is not None else FakeLindas(),
        zefix=zefix if zefix is not None else FakeZefix(),
        gazette=gazette if gazette is not None else FakeGazette(),
        config=config if config is not None else Settings(_env_file=None),
    )
