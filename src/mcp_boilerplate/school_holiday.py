"""Live Swiss school holidays from OpenHolidays (CC BY 4.0).

Adapted from the school-holiday client/tool in swiss-holidays-mcp, MIT,
Copyright (c) 2026 Hayal Oezkan. See THIRD_PARTY_NOTICES.md.
"""

import asyncio
import json
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BASE = "https://openholidaysapi.org"
CANTONS = set(
    "AG AI AR BE BL BS FR GE GL GR JU LU NE NW OW SG SH SO SZ TG TI UR VD VS ZG ZH".split()
)
SOURCE = {"name": "OpenHolidays API", "url": BASE, "license": "CC BY 4.0"}


def _fetch_json(url: str) -> list[dict]:
    request = Request(
        url, headers={"Accept": "application/json", "User-Agent": "swiss-ai-week-mcp/0.1"}
    )
    with urlopen(request, timeout=15) as response:
        data = json.load(response)
    if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
        raise ValueError("Unexpected OpenHolidays response")
    return data


def _municipality(tree: list[dict], canton: str, query: str) -> tuple[str, str] | None:
    root = next((entry for entry in tree if entry.get("code") == canton), None)
    if root is None:
        return None

    matches = []
    stack = [root]
    query = query.casefold()
    while stack:
        node = stack.pop()
        stack.extend(node.get("children") or [])
        code = node.get("code", "")
        if code.count("-") < 3:
            continue
        names = [name.get("text", "") for name in node.get("name", [])]
        if query == code.casefold() or any(query == name.casefold() for name in names):
            matches.append((code, names[0] if names else code))
    return matches[0] if len(matches) == 1 else None


async def get_school_holidays(
    canton: str,
    school_year: int | None = None,
    holiday_type: str | None = None,
    municipality: str | None = None,
) -> dict:
    """Fetch Swiss school holidays from OpenHolidays (CC BY 4.0; network required).

    canton: two-letter Swiss canton code (ZH) or ISO code (CH-ZH).
    school_year: starting year, e.g. 2026 means 2026/27; defaults to the
    current school year in Europe/Zurich (August 1 through July 31).
    holiday_type: optional case-insensitive name filter, e.g. summer or Sommerferien.
    municipality: optional exact municipality name or OpenHolidays subdivision code.
    Local variation requires a municipality; school types remain separate records.
    """
    code = canton.strip().upper() if isinstance(canton, str) else ""
    if code.startswith("CH-"):
        code = code[3:]
    if code not in CANTONS:
        return {
            "status": "invalid_input",
            "message": "canton must be a Swiss two-letter code or CH-XX code.",
        }
    if school_year is None:
        today = datetime.now(ZoneInfo("Europe/Zurich")).date()
        school_year = today.year if today.month >= 8 else today.year - 1
    if (
        isinstance(school_year, bool)
        or not isinstance(school_year, int)
        or not 2020 <= school_year <= 9998
    ):
        return {
            "status": "invalid_input",
            "message": "school_year must be a starting year from 2020 to 9998.",
        }
    if holiday_type is not None and (
        not isinstance(holiday_type, str) or not 0 < len(holiday_type.strip()) <= 80
    ):
        return {
            "status": "invalid_input",
            "message": "holiday_type must be a nonempty name of at most 80 characters.",
        }
    if municipality is not None and (
        not isinstance(municipality, str) or not 0 < len(municipality.strip()) <= 100
    ):
        return {
            "status": "invalid_input",
            "message": "municipality must be an exact name or subdivision code.",
        }

    canton_code = f"CH-{code}"
    area_code, area_name = canton_code, code
    try:
        if municipality:
            tree_url = f"{BASE}/Subdivisions?{urlencode({'countryIsoCode': 'CH'})}"
            area = _municipality(
                await asyncio.to_thread(_fetch_json, tree_url), canton_code, municipality.strip()
            )
            if area is None:
                return {
                    "status": "invalid_input",
                    "message": "Unknown or ambiguous municipality in this canton; use its OpenHolidays subdivision code.",
                }
            area_code, area_name = area
        params = {
            "countryIsoCode": "CH",
            "subdivisionCode": area_code,
            "validFrom": f"{school_year}-08-01",
            "validTo": f"{school_year + 1}-07-31",
        }
        source_url = f"{BASE}/SchoolHolidays?{urlencode(params)}"
        rows = await asyncio.to_thread(_fetch_json, source_url)
    except (OSError, ValueError):
        return {
            "status": "source_unavailable",
            "source": SOURCE,
            "message": "OpenHolidays could not be reached or returned invalid data.",
        }

    scope = {
        "level": "municipality" if municipality else "canton",
        "code": area_code,
        "name": area_name,
    }
    result = {
        "canton": canton_code,
        "school_year": f"{school_year}/{str(school_year + 1)[-2:]}",
        "valid_from": params["validFrom"],
        "valid_to": params["validTo"],
        "scope": scope,
        "source": {**SOURCE, "query_url": source_url},
    }
    if not municipality and (
        code == "ZH"
        or any(
            any(s.get("code") != canton_code for s in row.get("subdivisions") or []) for row in rows
        )
    ):
        return {
            **result,
            "status": "municipality_required",
            "holidays": [],
            "message": "School holiday dates vary locally; provide a municipality for a scoped result.",
        }

    holidays = []
    holiday_type = holiday_type.strip() if holiday_type else None
    try:
        for row in rows:
            names = row.get("name") or []
            if holiday_type and not any(
                holiday_type.casefold() in name.get("text", "").casefold() for name in names
            ):
                continue
            areas = [s.get("code", "") for s in row.get("subdivisions") or []]
            depth = max((s.count("-") for s in areas), default=0)
            holidays.append(
                {
                    "start_date": row["startDate"],
                    "end_date": row["endDate"],
                    "name": next(
                        (n["text"] for n in names if n.get("language") == "EN"),
                        names[0]["text"] if names else "",
                    ),
                    "school_types": [g["code"] for g in row.get("groups", [])],
                    "scope": "municipality"
                    if depth >= 3
                    else "district"
                    if depth == 2
                    else "canton"
                    if depth == 1
                    else "national"
                    if row.get("nationwide")
                    else "unspecified",
                    "area_codes": areas,
                }
            )
    except (KeyError, TypeError, AttributeError):
        return {
            "status": "source_unavailable",
            "source": SOURCE,
            "message": "OpenHolidays returned invalid holiday data.",
        }
    holidays.sort(key=lambda h: (h["start_date"], h["end_date"]))
    result.update(status="answered" if holidays else "no_data", holidays=holidays)
    if code == "ZH":
        result["coverage_note"] = (
            "Zurich schools set some dates locally; OpenHolidays may omit local sport holidays and school-free days. Confirm with the school."
        )
    return result
