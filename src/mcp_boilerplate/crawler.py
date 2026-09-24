"""Crawl reviewed Swiss authority pages through Crawlora, with a PDF fallback."""

import asyncio
import io
import os
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client
from pypdf import PdfReader

from .knowledge import KnowledgeBase, OpenAIEmbedder, split_passages
from .sources import SOURCES

ROOT = Path(__file__).resolve().parents[2]


def check_url(level: str, url: str) -> None:
    """Reject any URL outside the exact reviewed list."""
    if level not in SOURCES or url not in {entry.url for entry in SOURCES[level].values()}:
        raise ValueError("URL is not in the approved source list")


class CrawloraFetcher:
    """Fetch HTML and JSON pages with Crawlora's web_scrape MCP tool."""

    def __init__(self, key: str | None = None):
        self.key = key or os.environ.get("CRAWLORA_API_KEY") or dotenv_values(
            ROOT / ".env"
        ).get("CRAWLORA_API_KEY")

    async def fetch(self, url: str, level: str) -> dict:
        if not self.key:
            raise RuntimeError("Set CRAWLORA_API_KEY or add it to .env")
        client = create_mcp_http_client(headers={"Authorization": f"Bearer {self.key}"})
        async with client, streamable_http_client(
            "https://mcp.crawlora.net/mcp", http_client=client
        ) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "web_scrape",
                {
                    "url": url,
                    "formats": ["markdown", "metadata"],
                    "only_main_content": "/filestore/" not in url,
                    "render": "auto",
                    "max_age": 0,
                },
            )
        data = (result.structured_content or {}).get("data", {})
        if result.is_error or not data.get("markdown"):
            raise RuntimeError("Crawlora returned no page text")
        check_url(level, data.get("metadata", {}).get("source_url", url))
        return data


class PdfFetcher:
    """Extract searchable text from official PDFs when Crawlora cannot."""

    async def fetch(self, url: str, level: str) -> dict:
        return await asyncio.to_thread(self._fetch, url, level)

    @staticmethod
    def _fetch(url: str, level: str) -> dict:
        class CheckedRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, request, fp, code, msg, headers, newurl):
                check_url(level, newurl)
                return super().redirect_request(request, fp, code, msg, headers, newurl)

        opener = urllib.request.build_opener(CheckedRedirect)
        request = urllib.request.Request(url, headers={"User-Agent": "swiss-ai-week-mcp/0.1"})
        with opener.open(request, timeout=30) as response:
            if response.headers.get_content_type() != "application/pdf":
                raise ValueError("Expected a PDF response")
            raw = response.read(20_000_001)
            if len(raw) > 20_000_000:
                raise ValueError("PDF exceeds 20 MB limit")
            content = "\n\n".join(
                page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages
            ).strip()
            if not content:
                raise ValueError("PDF contains no extractable text")
            return {
                "markdown": content,
                "metadata": {
                    "source_url": response.url,
                    "status_code": response.status,
                    "content_type": "application/pdf",
                },
            }


class Crawler:
    """Refresh approved sources and atomically replace their saved passages."""

    def __init__(self, web_fetcher=None, pdf_fetcher=None, database=None, embedder=None):
        self.web_fetcher = web_fetcher or CrawloraFetcher()
        self.pdf_fetcher = pdf_fetcher or PdfFetcher()
        self.database = database or KnowledgeBase()
        self.embedder = embedder or OpenAIEmbedder()

    async def crawl(self, level: str, source: str | None = None) -> dict:
        if level not in SOURCES:
            raise ValueError("Unknown authority level")
        if source and source != "all" and source not in SOURCES[level]:
            raise ValueError(f"Unknown {level} source: {source}")

        selected = (
            [(source, SOURCES[level][source])]
            if source and source != "all"
            else list(SOURCES[level].items())
        )
        results = []
        for source_id, entry in selected:
            try:
                check_url(level, entry.url)
                fetcher = (
                    self.pdf_fetcher
                    if urlparse(entry.url).path.lower().endswith(".pdf")
                    else self.web_fetcher
                )
                data = await fetcher.fetch(entry.url, level)
                markdown = data.get("markdown", "")
                metadata = data.get("metadata", {})
                if not markdown or entry.expected.casefold() not in " ".join(markdown.split()).casefold():
                    raise ValueError(f"Expected source content missing: {source_id}")
                if metadata.get("source_url", entry.url) != entry.url:
                    raise ValueError(f"Source URL changed: {source_id}")
                if not 200 <= int(metadata.get("status_code", 0)) < 300:
                    raise ValueError(f"Source returned non-success status: {source_id}")
                record = {
                    "source": source_id,
                    "authority_level": level,
                    "authority": entry.authority,
                    "url": entry.url,
                    "crawled_at": datetime.now(UTC).isoformat(),
                    "markdown": markdown,
                    "metadata": metadata,
                }
                chunks = split_passages(markdown)
                vectors = await self.embedder.embed(chunks)
                self.database.save(record, chunks, vectors)
                results.append({
                    "source": source_id, "authority": entry.authority, "url": entry.url,
                    "crawled_at": record["crawled_at"], "passages": len(chunks),
                })
            except Exception as exc:
                self.database.failed(level, source_id, str(exc))
                if len(selected) == 1:
                    raise
                results.append({"source": source_id, "url": entry.url, "error": str(exc)})
        return results[0] if len(selected) == 1 else {"sources": results}
