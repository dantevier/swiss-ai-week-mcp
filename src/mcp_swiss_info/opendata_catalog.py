"""Search the official Swiss Open Government Data metadata catalogue."""

import html
import re
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

from .public_api import request_json, unavailable

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


def _search(
    query: str, limit: int, language: str, requester: Callable[..., dict | list] | None = None
) -> dict:
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
        response = (requester or request_json)(url)
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


def _dataset(
    dataset_id: str,
    language: str,
    resource_start: int,
    requester: Callable[..., dict | list] | None = None,
) -> dict:
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
        response = (requester or request_json)(url)
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


class OpenDataCatalog:
    """Search metadata and resources in the opendata.swiss catalogue."""

    def __init__(self, requester: Callable[..., dict | list] = request_json) -> None:
        self.requester = requester

    def search(self, query: str, limit: int, language: str) -> dict:
        return _search(query, limit, language, self.requester)

    def dataset(self, dataset_id: str, language: str, resource_start: int) -> dict:
        return _dataset(dataset_id, language, resource_start, self.requester)
