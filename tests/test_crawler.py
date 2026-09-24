"""Knowledge-base contract checks without network calls."""

import pytest

from mcp_boilerplate import knowledge
from mcp_boilerplate.crawler import Crawler, check_url
from mcp_boilerplate.knowledge import KnowledgeBase
from mcp_boilerplate.server import mcp
from mcp_boilerplate.source_access import SourceAccess
from mcp_boilerplate.sources import SOURCES
from mcp_boilerplate.tools import source_tools


class FakeFetcher:
    def __init__(self):
        self.text = "Hypothekarischer Referenzzinssatz: 1,25 Prozent."
        self.error = None
        self.calls = []

    async def fetch(self, url, level):
        self.calls.append((url, level))
        if self.error:
            raise RuntimeError(self.error)
        return {
            "markdown": self.text,
            "metadata": {"source_url": url, "status_code": 200, "language": "de"},
        }


class FakeEmbedder:
    async def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


class OfflineEmbedder:
    async def embed(self, texts):
        raise RuntimeError("offline")


@pytest.mark.asyncio
async def test_crawl_search_refresh_and_failure(tmp_path, monkeypatch):
    db = KnowledgeBase(tmp_path / "knowledge.sqlite3")
    fetcher = FakeFetcher()
    crawler = Crawler(fetcher, fetcher, db, FakeEmbedder())
    source = "reference_interest_rate"
    url = SOURCES["federal"][source].url

    assert {
        "crawl_federal_sources",
        "crawl_cantonal_sources",
        "crawl_municipal_sources",
        "search_knowledge",
        "get_source",
    } <= {tool.name for tool in await mcp.list_tools()}
    with pytest.raises(ValueError, match="approved"):
        check_url("federal", "https://www.bwo.admin.ch/unlisted")
    with pytest.raises(ValueError, match="Unknown federal source"):
        await crawler.crawl("federal", "unlisted")
    with pytest.raises(TypeError):
        await crawler.crawl("federal", url=url)
    assert not fetcher.calls

    await crawler.crawl("federal", source)
    first = db.get("federal", source)
    assert first["url"] == url
    assert first["authority"] == SOURCES["federal"][source].authority
    assert first["metadata"]["language"] == "de"
    assert first["crawled_at"]
    semantic = await db.search("mortgage rate", embedder=FakeEmbedder())
    assert semantic["method"] == "semantic"
    assert semantic["results"][0]["passage"] == fetcher.text
    assert semantic["results"][0]["url"] == url
    assert semantic["results"][0]["authority"] == first["authority"]
    assert semantic["results"][0]["crawled_at"] == first["crawled_at"]

    fetcher.text = "Hypothekarischer Referenzzinssatz: neuer Wert."
    await crawler.crawl("federal", source)
    assert db.get("federal", source)["markdown"] == fetcher.text
    assert len((await db.search("rate", embedder=FakeEmbedder()))["results"]) == 1

    fallback = await db.search("Referenzzinssatz", embedder=OfflineEmbedder())
    assert fallback["method"] == "keyword_fallback"
    assert fallback["results"][0]["source"] == source

    fetcher.text = "Wrong page"
    with pytest.raises(ValueError, match="Expected source content"):
        await crawler.crawl("federal", source)
    assert db.get("federal", source)["markdown"] == "Hypothekarischer Referenzzinssatz: neuer Wert."
    assert db.get("federal", source)["refresh_failed_at"]

    fetcher.error = "network down"
    with pytest.raises(RuntimeError, match="network down"):
        await crawler.crawl("federal", source)
    assert db.get("federal", source)["markdown"] == "Hypothekarischer Referenzzinssatz: neuer Wert."

    fetcher.error = None
    fetcher.text = "Hypothekarischer Referenzzinssatz: weiterer Wert."
    crawler.embedder = OfflineEmbedder()
    with pytest.raises(RuntimeError, match="offline"):
        await crawler.crawl("federal", source)
    assert db.get("federal", source)["markdown"] == "Hypothekarischer Referenzzinssatz: neuer Wert."

    monkeypatch.setattr(
        source_tools,
        "sources",
        SourceAccess(Crawler, lambda: db, source_tools.get_status, source_tools.ensure_running),
    )
    monkeypatch.setattr(knowledge, "OpenAIEmbedder", OfflineEmbedder)
    got = await mcp.call_tool("get_source", {"level": "federal", "source": source})
    found = await mcp.call_tool("search_knowledge", {"query": "Referenzzinssatz"})
    assert not got.is_error and not found.is_error
    assert got.structured_content["url"] == url
    assert got.structured_content["refresh_failed_at"]
    assert found.structured_content["method"] == "keyword_fallback"
    assert found.structured_content["results"][0]["url"] == url


def test_seed_copied_once(tmp_path, monkeypatch):
    seed = tmp_path / "seed.sqlite3"
    original = KnowledgeBase(seed)
    original.save(
        {
            "authority_level": "federal",
            "source": "reference_interest_rate",
            "authority": "Federal Office for Housing (BWO)",
            "url": SOURCES["federal"]["reference_interest_rate"].url,
            "crawled_at": "2026-09-24T00:00:00+00:00",
            "markdown": "Hypothekarischer Referenzzinssatz",
            "metadata": {},
        },
        ["Hypothekarischer Referenzzinssatz"],
        [[1.0, 0.0]],
    )
    target = tmp_path / "runtime" / "knowledge.sqlite3"
    monkeypatch.setattr(knowledge, "SEED", seed)
    monkeypatch.setattr(knowledge.settings, "knowledge_db_path", str(target))
    db = KnowledgeBase()
    assert (
        db.get("federal", "reference_interest_rate")["markdown"]
        == "Hypothekarischer Referenzzinssatz"
    )
    original.save(
        {
            "authority_level": "federal",
            "source": "reference_interest_rate",
            "authority": "Federal Office for Housing (BWO)",
            "url": SOURCES["federal"]["reference_interest_rate"].url,
            "crawled_at": "2026-09-25T00:00:00+00:00",
            "markdown": "Changed seed",
            "metadata": {},
        },
        ["Changed seed"],
        [[1.0, 0.0]],
    )
    assert (
        KnowledgeBase().get("federal", "reference_interest_rate")["markdown"]
        == "Hypothekarischer Referenzzinssatz"
    )
