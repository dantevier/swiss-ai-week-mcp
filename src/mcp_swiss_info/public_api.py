"""Small read-only requests to official Swiss public-data APIs."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MAX_RESPONSE_BYTES = 4 * 1024 * 1024


def request_json(url: str, payload: dict | None = None, timeout: int = 35) -> dict | list:
    headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (SwissAIWeekMCP/1.0)"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers=headers,
    )
    with urlopen(request, timeout=timeout) as response:
        content = response.read(MAX_RESPONSE_BYTES + 1)
    if len(content) > MAX_RESPONSE_BYTES:
        raise ValueError("Official API response exceeds 4 MB")
    return json.loads(content)


def unavailable(exc: Exception) -> dict:
    if isinstance(exc, HTTPError) and exc.code == 404:
        return {"status": "not_found", "message": "The official source did not find this item."}
    if isinstance(exc, (HTTPError, URLError, TimeoutError, OSError)):
        return {
            "status": "source_unavailable",
            "message": "The official data service is unavailable.",
        }
    return {
        "status": "source_unavailable",
        "message": "The official data response could not be read.",
    }
