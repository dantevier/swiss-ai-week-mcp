"""Build the shipped SQLite seed from fresh approved-source crawls."""

import asyncio
import os
import tempfile
from pathlib import Path

from mcp_boilerplate.crawler import Crawler
from mcp_boilerplate.knowledge import SEED, KnowledgeBase
from mcp_boilerplate.sources import SOURCES


async def main() -> None:
    with tempfile.NamedTemporaryFile(dir=SEED.parent, suffix=".sqlite3", delete=False) as file:
        temporary = Path(file.name)
    try:
        crawler = Crawler(database=KnowledgeBase(temporary))
        for level, entries in SOURCES.items():
            for source in entries:
                result = await crawler.crawl(level, source)
                print(f"{level}/{source}: {result['passages']} passages", flush=True)
        os.replace(temporary, SEED)
        print(f"Built {SEED} from {sum(map(len, SOURCES.values()))} fresh sources")
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(main())
