"""Registry checks for SOURCES and API_SOURCES (docs/prd-company-info-refactor.md S3, T5)."""

import pytest

from mcp_boilerplate.config.settings import settings
from mcp_boilerplate.crawler import Crawler, check_url
from mcp_boilerplate.knowledge import KnowledgeBase
from mcp_boilerplate.sources import API_SOURCES, NOT_A_PAGE, SOURCES, Source
from mcp_boilerplate.zefix.sources import http
from tests.test_crawler import FakeEmbedder, FakeFetcher

API_NAMES = ("zefix_lindas", "zefix_web", "gazette")


@pytest.mark.parametrize("name", API_NAMES)
def test_api_source_is_listed_as_a_federal_row(name):
    row = SOURCES["federal"][name]
    assert isinstance(row, Source)
    assert row.url == API_SOURCES[name].base_url
    assert row.authority == API_SOURCES[name].authority
    assert row.expected == NOT_A_PAGE


def test_every_api_source_host_is_allowed():
    allowed = http.allowed_hosts()
    for name, source in API_SOURCES.items():
        for host in source.hosts:
            assert host in allowed, f"{name} host {host!r} missing from allowed_hosts()"


def test_check_url_accepts_listed_api_url_only():
    check_url("federal", API_SOURCES["zefix_lindas"].base_url)
    with pytest.raises(ValueError):
        check_url("federal", "https://lindas.admin.ch/other")


@pytest.mark.parametrize(
    ("settings_field", "registry_key"),
    [
        ("lindas_endpoint", "zefix_lindas"),
        ("zefix_base_url", "zefix_web"),
        ("gazette_base_url", "gazette"),
    ],
)
def test_settings_defaults_match_registry_base_urls(settings_field, registry_key):
    assert getattr(settings, settings_field) == API_SOURCES[registry_key].base_url


@pytest.mark.asyncio
async def test_crawling_an_api_row_fails_validation_and_saves_nothing(tmp_path):
    db = KnowledgeBase(tmp_path / "kb.sqlite3")
    row = SOURCES["federal"]["zefix_lindas"]
    db.save(
        {
            "authority_level": "federal", "source": "zefix_lindas",
            "authority": row.authority, "url": row.url,
            "crawled_at": "2026-09-24T00:00:00+00:00",
            "markdown": "previous", "metadata": {},
        },
        ["previous"],
        [[1.0, 0.0]],
    )
    fetcher = FakeFetcher()
    fetcher.text = "any API response text"
    crawler = Crawler(fetcher, fetcher, db, FakeEmbedder())

    with pytest.raises(ValueError, match="Expected source content missing: zefix_lindas"):
        await crawler.crawl("federal", "zefix_lindas")

    saved = db.get("federal", "zefix_lindas")
    assert saved["markdown"] == "previous"
    assert saved["crawled_at"] == "2026-09-24T00:00:00+00:00"
    assert saved["refresh_error"] == "Expected source content missing: zefix_lindas"
    assert saved["refresh_failed_at"]


@pytest.mark.asyncio
async def test_full_federal_refresh_reports_api_rows_as_failed(tmp_path):
    db = KnowledgeBase(tmp_path / "kb.sqlite3")
    fetcher = FakeFetcher()
    crawler = Crawler(fetcher, fetcher, db, FakeEmbedder())

    result = await crawler.crawl("federal", "all")

    by_name = {entry["source"]: entry for entry in result["sources"]}
    for name in API_NAMES:
        assert by_name[name]["error"] == f"Expected source content missing: {name}"
        with pytest.raises(ValueError, match="Source has not been crawled"):
            db.get("federal", name)
