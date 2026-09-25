"""
Tests for sources/zefix.py (PRD §6.3, interfaces.md).

sources/zefix.py does not exist yet (S2); every test here ImportErrors until
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

FIXTURE = Path(__file__).parent / "fixtures" / "zefix_firm_detail.json"


# ---------------------------------------------------------------------------
# UID normalisation / formatting (pure functions, no I/O)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    ["CHE-101.654.423", "che101654423", "CHE101654423", "101654423", " CHE-101.654.423 "],
)
def test_normalize_uid_accepts_all_documented_shapes(raw):
    """interfaces.md: "CHE-101.654.423" / "che101654423" / "101654423" -> "CHE101654423"."""
    from mcp_swiss_info.zefix.sources import rest as zefix

    assert zefix.normalize_uid(raw) == "CHE101654423"


@pytest.mark.parametrize("raw", [None, "", "not a uid", "DE123456789", "CHE12345678", "CHE1234567890"])
def test_normalize_uid_rejects_invalid_input(raw):
    """Anything that isn't a 9-digit Swiss UID (optionally CHE-prefixed) is None,
    including foreign identifiers (PRD §5.2 jurisdiction gate relies on this)."""
    from mcp_swiss_info.zefix.sources import rest as zefix

    assert zefix.normalize_uid(raw) is None


def test_format_uid_renders_dot_and_dash_grouping():
    """interfaces.md: "CHE101654423" -> "CHE-101.654.423"."""
    from mcp_swiss_info.zefix.sources import rest as zefix

    assert zefix.format_uid("CHE101654423") == "CHE-101.654.423"


def test_canton_codes_has_26_entries():
    """interfaces.md: CANTON_CODES: frozenset[str], 26 codes."""
    from mcp_swiss_info.zefix.sources import rest as zefix

    assert len(zefix.CANTON_CODES) == 26
    assert "BE" in zefix.CANTON_CODES
    assert "ZG" in zefix.CANTON_CODES
    assert "DE" not in zefix.CANTON_CODES


def test_zefix_detail_url_pattern():
    """PRD §5.3 citation.zefix_url, verified live per action A3."""
    from mcp_swiss_info.zefix.sources import rest as zefix

    assert (
        zefix.zefix_detail_url(415941, language="de")
        == "https://www.zefix.admin.ch/de/search/entity/list/firm/415941"
    )
    assert zefix.zefix_detail_url(415941) == zefix.zefix_detail_url(415941, language="de")


# ---------------------------------------------------------------------------
# firm_detail: HTTP parsing against the vendored fixture
# ---------------------------------------------------------------------------


async def test_firm_detail_parses_the_fixture():
    """PRD §6.3: fields read are status, shabDate, deleteDate, cantonalExcerptWeb,
    oldNames, shabPub[].{shabDate, shabId, registryOfficeCanton, mutationTypes[].key}.
    Fixture: tests/fixtures/zefix_firm_detail.json (ehraid 1287765), copied
    verbatim from register-mcp; see tests/fixtures/PROVENANCE.md."""
    from mcp_swiss_info.zefix.sources import rest as zefix

    payload = json.loads(FIXTURE.read_text())
    with respx.mock(assert_all_called=True) as mocked:
        mocked.get(f"{settings.zefix_base_url}/firm/1287765.json").respond(200, json=payload)
        enrichment = await zefix.ZefixClient().firm_detail(1287765, budget_s=5.0)

    assert enrichment.status == "EXISTIEREND"
    assert enrichment.shab_date == "2025-03-14"
    assert enrichment.delete_date is None
    assert enrichment.cantonal_excerpt_url == (
        "https://zh.chregister.ch/cr-portal/auszug/auszug.xhtml?uid=CHE-238.945.329"
    )
    assert enrichment.old_names == ["Anlagestiftung der Migros-Pensionskasse Immobilien"]
    # newest first, de-duplicated: fixture's shabPub[0] is "aenderungorgane" (newest,
    # 2025-03-14) and it repeats many times through the list.
    assert enrichment.mutation_types[0] == "aenderungorgane"
    assert len(enrichment.mutation_types) == len(set(enrichment.mutation_types))


async def test_firm_detail_never_exposes_shab_message():
    """PRD §6.3: "shabPub[].message is never read." The fixture's message fields
    hold redacted personal-data placeholders; Enrichment must not carry them
    under any attribute name."""
    from mcp_swiss_info.zefix.sources import rest as zefix

    payload = json.loads(FIXTURE.read_text())
    assert "message" in payload["shabPub"][0]  # sanity: the fixture does have it

    with respx.mock(assert_all_called=True) as mocked:
        mocked.get(f"{settings.zefix_base_url}/firm/1287765.json").respond(200, json=payload)
        enrichment = await zefix.ZefixClient().firm_detail(1287765, budget_s=5.0)

    field_names = " ".join(vars(enrichment).keys()).lower()
    assert "message" not in field_names
    for value in vars(enrichment).values():
        serialised = json.dumps(value, default=str)
        assert "redigiert" not in serialised.lower()


async def test_firm_detail_basic_auth_when_credentials_set():
    """PRD §6.3: "Basic auth if settings.zefix_username and zefix_password set."."""
    from mcp_swiss_info.zefix.sources import rest as zefix

    client = zefix.ZefixClient(username="tester", password="secret")
    payload = json.loads(FIXTURE.read_text())

    with respx.mock(assert_all_called=True) as mocked:
        route = mocked.get(f"{settings.zefix_base_url}/firm/1287765.json").respond(200, json=payload)
        await client.firm_detail(1287765, budget_s=5.0)

    request = route.calls.last.request
    assert "authorization" in {k.lower() for k in request.headers.keys()}


async def test_firm_detail_timeout_raises_source_unavailable_zefix():
    """PRD §6.3, §5.3: enrichment failures raise SourceUnavailable(source="zefix");
    tools/company_info.py is responsible for downgrading this to a degraded field,
    not a hard failure of the whole call."""
    from mcp_swiss_info.zefix.sources import rest as zefix

    with respx.mock(assert_all_called=True) as mocked:
        mocked.get(f"{settings.zefix_base_url}/firm/415941.json").mock(
            side_effect=httpx.TimeoutException("timed out")
        )
        with pytest.raises(SourceUnavailable) as excinfo:
            await zefix.ZefixClient().firm_detail(415941, budget_s=5.0)

    assert excinfo.value.source == "zefix"


# ---------------------------------------------------------------------------
# enrichment_allowed()
# ---------------------------------------------------------------------------


def test_enrichment_allowed_false_by_default():
    """PRD §6.5: respect_robots_txt=True and no credentials -> enrichment not allowed."""
    from mcp_swiss_info.zefix.sources import rest as zefix

    client = zefix.ZefixClient(respect_robots_txt=True, username=None, password=None)
    assert client.enrichment_allowed() is False


def test_enrichment_allowed_true_when_robots_disabled():
    """PRD §6.5: respect_robots_txt=False -> allowed even without credentials."""
    from mcp_swiss_info.zefix.sources import rest as zefix

    client = zefix.ZefixClient(respect_robots_txt=False, username=None, password=None)
    assert client.enrichment_allowed() is True


def test_enrichment_allowed_true_with_credentials_even_when_robots_respected():
    """PRD §6.5: "the credential grant is the ToS acceptance" -- credentials allow
    enrichment under either value of respect_robots_txt."""
    from mcp_swiss_info.zefix.sources import rest as zefix

    client = zefix.ZefixClient(respect_robots_txt=True, username="tester", password="secret")
    assert client.enrichment_allowed() is True
