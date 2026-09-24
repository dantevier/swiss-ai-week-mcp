"""Refresh all federal-source snapshots through Crawlora MCP."""

import asyncio

from mcp_boilerplate.crawler import Crawler


async def main() -> None:
    for result in (await Crawler().crawl("federal"))["sources"]:
        print(f"{result['source']}: {result.get('snapshot', result.get('error'))}")


if __name__ == "__main__":
    asyncio.run(main())
