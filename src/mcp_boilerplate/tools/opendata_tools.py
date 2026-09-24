"""Search the official Swiss Open Government Data metadata catalogue."""

import asyncio
import html
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

from ..server import mcp
from ._public_api import request_json, unavailable

API = "https://ckan.opendata.swiss/api/3/action/"


def _label(value: object, language: str) -> str:
    if isinstance(value, dict):
        value = next(
            (value.get(lang) for lang in (language, "en", "de", "fr", "it") if value.get(lang)), ""
        )
    return html.unescape(re.sub(r"<[^>]+>", " ", str(value or ""))).strip()


def _summary(
    package: dict, language: str, include_resources: bool = False, resource_start: int = 0
) -> dict:
    name = package["name"]
    result = {
        "id": name,
        "title": _label(package.get("display_name") or package.get("title"), language),
        "description": _label(package.get("description"), language)[:500],
        "publisher": _label((package.get("publisher") or {}).get("name"), language),
        "modified": package.get("metadata_modified"),
        "dataset_url": f"https://opendata.swiss/{language}/dataset/{name}",
        "resource_count": len(package.get("resources") or []),
    }
    if include_resources:
        result["resource_start"] = resource_start
        result["has_more_resources"] = resource_start + 20 < result["resource_count"]
        result["resources"] = [
            {
                "title": _label(
                    resource.get("title") or resource.get("display_name") or resource.get("name"),
                    language,
                ),
                "format": resource.get("format"),
                "url": resource.get("download_url") or resource.get("url"),
                "rights": resource.get("rights"),
            }
            for resource in package.get("resources", [])[resource_start : resource_start + 20]
        ]
    return result


def _search(query: str, limit: int, language: str) -> dict:
    if (
        not query.strip()
        or len(query) > 120
        or not 1 <= limit <= 10
        or language not in ("en", "de", "fr", "it")
    ):
        return {
            "status": "invalid_input",
            "message": "Provide a search phrase (1–120 characters), limit 1–10 and language en/de/fr/it.",
        }
    # Escape Lucene syntax, so the query is treated as text and not a Solr expression.
    clean_query = re.sub(r"([+\-&|!(){}\[\]^\"~*?:\\/])", r"\\\1", query.strip())
    url = API + "package_search?" + urlencode({"q": clean_query, "rows": limit})
    try:
        response = request_json(url)
        if not response["success"]:
            return {"status": "source_unavailable", "message": "The catalogue rejected the search."}
        result = response["result"]
        return {
            "status": "answered" if result["results"] else "no_data",
            "total_matches": result["count"],
            "datasets": [_summary(package, language) for package in result["results"]],
            "source_url": url,
            "source": "opendata.swiss dataset catalogue",
            "note": "Catalogue metadata only; dataset resources are hosted by their respective publishers. Use opendata_dataset for download links and rights.",
        }
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as exc:
        return unavailable(exc)


def _dataset(dataset_id: str, language: str, resource_start: int) -> dict:
    if (
        not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,149}", dataset_id)
        or language not in ("en", "de", "fr", "it")
        or not 0 <= resource_start <= 1000
    ):
        return {
            "status": "invalid_input",
            "message": "Use a dataset ID from opendata_search_datasets, language en/de/fr/it and resource_start 0–1000.",
        }
    url = API + "package_show?" + urlencode({"id": dataset_id})
    try:
        response = request_json(url)
        if not response["success"]:
            return {"status": "not_found", "message": "Dataset not found in opendata.swiss."}
        return {
            "status": "answered",
            "dataset": _summary(response["result"], language, True, resource_start),
            "source_url": url,
            "source": "opendata.swiss dataset catalogue",
        }
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as exc:
        return unavailable(exc)


@mcp.tool
async def opendata_search_datasets(query: str, limit: int = 5, language: str = "en") -> dict:
    """Find Swiss federal, cantonal and municipal open datasets by topic.

    Returns dataset IDs, descriptions and publisher metadata, not data values.
    Search: https://ckan.opendata.swiss/api/3/action/package_search
    """
    return await asyncio.to_thread(_search, query, limit, language)


@mcp.tool
async def opendata_dataset(dataset_id: str, language: str = "en", resource_start: int = 0) -> dict:
    """Get one opendata.swiss dataset's metadata and up to 20 resource links.

    Use resource_start=20, 40, etc. to page through the resource links.
    Resource rights and formats vary; this catalogue does not host the files.
    Lookup: https://ckan.opendata.swiss/api/3/action/package_show
    """
    return await asyncio.to_thread(_dataset, dataset_id, language, resource_start)
