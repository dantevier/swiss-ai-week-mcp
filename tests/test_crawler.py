"""Small contract check for source selection and fetcher routing."""

import pytest

from src.mcp_boilerplate.crawler import Crawler
from src.mcp_boilerplate.server import mcp


class FakeFetcher:
    def __init__(self):
        self.calls = []

    async def fetch(self, url, level):
        self.calls.append((url, level))
        return {"markdown": "official source text", "metadata": {"status_code": 200}}


@pytest.mark.asyncio
async def test_crawl_tools_and_authority_boundary():
    assert {tool.name for tool in await mcp.list_tools()} == {
        "crawl_federal_sources",
        "crawl_cantonal_sources",
        "crawl_municipal_sources",
    }
    web, pdf = FakeFetcher(), FakeFetcher()
    crawler = Crawler(web_fetcher=web, pdf_fetcher=pdf)
    with pytest.raises(ValueError, match="not a reviewed"):
        await crawler.crawl("municipal", url="https://example.com/page")
    assert not web.calls and not pdf.calls

    result = await crawler.crawl(
        "cantonal",
        url="https://www.gr.ch/DE/institutionen/verwaltung/ekud/avs/Volksschule/"
        "SB_Ferienplaene_2026_2027_de.pdf",
    )
    assert result["source"] == "pasted_url"
    assert result["markdown"] == "official source text"
    assert len(pdf.calls) == 1 and not web.calls
