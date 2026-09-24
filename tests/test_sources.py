"""Registry checks for SOURCES and its API_SOURCES view (docs/prd-company-info-refactor.md S3, T5)."""

import pytest

from mcp_boilerplate.config.settings import settings
from mcp_boilerplate.crawler import Crawler, check_url
from mcp_boilerplate.knowledge import KnowledgeBase
from mcp_boilerplate.server import mcp
from mcp_boilerplate.sources import API_SOURCES, SOURCES, ApiSource, Source, pages
from mcp_boilerplate.tools import source_tools  # noqa: F401  registers the crawl tools
from mcp_boilerplate.zefix.sources import http
from tests.test_crawler import FakeEmbedder, FakeFetcher

API_NAMES = ("zefix_lindas", "zefix_web", "gazette")


@pytest.mark.parametrize("name", API_NAMES)
def test_api_source_is_a_federal_row(name):
    assert isinstance(SOURCES["federal"][name], ApiSource)
    assert SOURCES["federal"][name] is API_SOURCES[name]


def test_api_sources_is_the_api_view_of_sources():
    assert API_SOURCES == {
        name: entry
        for entries in SOURCES.values()
        for name, entry in entries.items()
        if isinstance(entry, ApiSource)
    }
    for level in SOURCES:
        assert all(isinstance(entry, Source) for entry in pages(level).values())
        assert not set(pages(level)) & set(API_SOURCES)


def test_every_api_source_host_is_allowed():
    allowed = http.allowed_hosts()
    for name, source in API_SOURCES.items():
        for host in source.hosts:
            assert host in allowed, f"{name} host {host!r} missing from allowed_hosts()"


def test_zefix_lindas_base_url_is_not_a_crawlable_source():
    with pytest.raises(ValueError):
        check_url("federal", API_SOURCES["zefix_lindas"].base_url)


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
async def test_crawl_tool_rejects_api_source_as_unknown():
    with pytest.raises(Exception, match="Unknown federal source: zefix_lindas"):
        await mcp.call_tool("crawl_federal_sources", {"source": "zefix_lindas"})


@pytest.mark.asyncio
@pytest.mark.parametrize("name", API_NAMES)
async def test_crawler_rejects_api_source_like_unknown_source(tmp_path, name):
    fetcher = FakeFetcher()
    crawler = Crawler(fetcher, fetcher, KnowledgeBase(tmp_path / "kb.sqlite3"), FakeEmbedder())
    with pytest.raises(ValueError, match=f"Unknown federal source: {name}"):
        await crawler.crawl("federal", name)
    assert not fetcher.calls


@pytest.mark.asyncio
async def test_crawl_all_never_touches_an_api_source(tmp_path):
    fetcher = FakeFetcher()
    crawler = Crawler(fetcher, fetcher, KnowledgeBase(tmp_path / "kb.sqlite3"), FakeEmbedder())
    await crawler.crawl("federal", "all")
    fetched = {url for url, _ in fetcher.calls}
    assert fetched == {entry.url for entry in pages("federal").values()}
    assert not fetched & {source.base_url for source in API_SOURCES.values()}


@pytest.mark.parametrize("name", API_NAMES)
def test_get_source_treats_api_source_as_unknown(tmp_path, name):
    kb = KnowledgeBase(tmp_path / "kb.sqlite3")
    with pytest.raises(ValueError) as unknown:
        kb.get("federal", "nope")
    with pytest.raises(ValueError) as api:
        kb.get("federal", name)
    assert str(api.value) == str(unknown.value) == "Unknown approved source"
