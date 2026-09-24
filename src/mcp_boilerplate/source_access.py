"""Services for approved sources and the local data-source dashboard."""

from collections.abc import Callable

from .crawler import Crawler
from .knowledge import KnowledgeBase


class SourceAccess:
    """Delegate source operations to injected crawl, storage and dashboard clients."""

    def __init__(
        self,
        crawler_factory: Callable[[], Crawler],
        knowledge_factory: Callable[[], KnowledgeBase],
        status: Callable[[], dict],
        dashboard: Callable[[], str],
    ):
        self.crawler_factory = crawler_factory
        self.knowledge_factory = knowledge_factory
        self.status = status
        self.dashboard = dashboard

    async def crawl(self, level: str, source: str | None = None) -> dict:
        return await self.crawler_factory().crawl(level, source)

    async def search(self, query: str, limit: int = 5) -> dict:
        return await self.knowledge_factory().search(query, limit)

    def get(self, level: str, source: str) -> dict:
        return self.knowledge_factory().get(level, source)

    def source_status(self) -> dict:
        return self.status()

    def open_dashboard(self) -> dict:
        return {"url": self.dashboard()}
