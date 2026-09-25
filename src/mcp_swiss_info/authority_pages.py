"""Fetch short, source-backed excerpts from explicitly selected authority pages."""

import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class MainParagraphs(HTMLParser):
    """Collect page headings and paragraphs after the first H1, excluding navigation."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.started = False
        self.hidden = 0
        self.current: str | None = None
        self.parts: list[str] = []
        self.blocks: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "nav", "footer", "noscript"}:
            self.hidden += 1
        if not self.hidden and tag in {"h1", "h2", "h3", "p"} and (self.started or tag == "h1"):
            self.current = tag
            self.parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == self.current:
            text = " ".join(" ".join(self.parts).split())
            if text:
                self.blocks.append((tag, text))
            if tag == "h1":
                self.started = True
            self.current = None
        if tag in {"script", "style", "nav", "footer", "noscript"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden and self.current is not None:
            self.parts.append(data)


def fetch_page(url: str, expected_title: str) -> dict:
    """Only callers with fixed official URLs use this; never accept pasted user URLs."""
    host = urlparse(url).hostname
    if host not in {"www.bazg.admin.ch", "www.bk.admin.ch", "www.sem.admin.ch"}:
        raise ValueError("Unapproved authority URL")
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (SwissAIWeekMCP/1.0)"})
    with urlopen(request, timeout=30) as response:
        if (
            urlparse(response.url).hostname != host
            or response.headers.get_content_type() != "text/html"
        ):
            raise ValueError("Authority page redirected or changed format")
        data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError("Authority page exceeds 2 MB")
        content = data.decode(response.headers.get_content_charset() or "utf-8", errors="replace")
    parser = MainParagraphs()
    parser.feed(content)
    blocks = parser.blocks
    if not blocks or blocks[0] != ("h1", expected_title):
        raise ValueError("Authority page title changed")
    return {
        "blocks": blocks,
        "source_url": response.url,
        "fetched_at_utc": datetime.now(UTC).isoformat(),
    }


def paragraph(page: dict, *phrases: str) -> str:
    """Return a verbatim paragraph matching all required phrases, or fail closed."""
    for tag, text in page["blocks"]:
        normalized = re.sub(r"\s+", " ", text).casefold()
        if tag == "p" and all(phrase.casefold() in normalized for phrase in phrases):
            return text
    raise ValueError("Expected rule missing from the authority page")
