"""Small, unambiguous queries of official FSO (BFS) PxWeb statistics."""

from collections.abc import Callable
from urllib.error import HTTPError, URLError

from .public_api import request_json, unavailable

TABLE = "px-x-0103010000_101"
TABLE_URL = f"https://www.pxweb.bfs.admin.ch/api/v1/en/{TABLE}/{TABLE}.px"
POPULATION_TYPE = {"permanent": "1", "non_permanent": "2"}
SEX = {"total": "-99999", "male": "1", "female": "2"}
OTHER_TOTALS = {
    "Anwesenheitsbewilligung": "-99999",
    "Altersklasse": "-99999",
    "Staatsangehörigkeit": "-99999",
}


def _population(
    canton: str,
    start_year: int | None,
    end_year: int | None,
    population_type: str,
    sex: str,
    requester: Callable[..., dict | list] | None = None,
) -> dict:
    canton = canton.upper()
    if population_type not in POPULATION_TYPE or sex not in SEX:
        return {
            "status": "invalid_input",
            "message": "population_type: permanent or non_permanent; sex: total, male or female.",
        }
    if start_year is not None and (not 1900 <= start_year <= 2100):
        return {"status": "invalid_input", "message": "start_year must be a four-digit year."}
    if end_year is not None and (not 1900 <= end_year <= 2100):
        return {"status": "invalid_input", "message": "end_year must be a four-digit year."}
    if (
        start_year is not None
        and end_year is not None
        and (end_year < start_year or end_year - start_year >= 10)
    ):
        return {"status": "invalid_input", "message": "Select no more than ten consecutive years."}
    try:
        request = requester or request_json
        metadata = request(TABLE_URL)
        variables = {variable["code"]: variable for variable in metadata["variables"]}
        cantons = dict(
            zip(variables["Kanton"]["values"], variables["Kanton"]["valueTexts"], strict=True)
        )
        canton_code = "8100" if canton in ("CH", "SWITZERLAND") else canton
        if canton_code not in cantons or canton_code == "-9":
            return {
                "status": "invalid_input",
                "message": "Use CH or an official two-letter Swiss canton code.",
            }
        available_years = [int(year) for year in variables["Jahr"]["values"]]
        first = (
            start_year
            if start_year is not None
            else (end_year if end_year is not None else max(available_years))
        )
        last = end_year if end_year is not None else first
        years = [str(year) for year in range(first, last + 1)]
        if len(years) > 10 or not years or any(int(year) not in available_years for year in years):
            return {
                "status": "invalid_input",
                "message": f"Select 1–10 years available in this table ({min(available_years)}–{max(available_years)}).",
            }
        choices = {
            "Jahr": years,
            "Kanton": [canton_code],
            "Bevölkerungstyp": [POPULATION_TYPE[population_type]],
            "Geschlecht": [SEX[sex]],
            **{dimension: [value] for dimension, value in OTHER_TOTALS.items()},
        }
        query = {
            "query": [
                {
                    "code": variable["code"],
                    "selection": {"filter": "item", "values": choices[variable["code"]]},
                }
                for variable in metadata["variables"]
            ],
            "response": {"format": "json"},
        }
        data = request(TABLE_URL, query, timeout=75)
        values = [
            {
                "year": int(row["key"][0]),
                "population": int(row["values"][0]) if row["values"][0].isdigit() else None,
            }
            for row in data["data"]
        ]
        return {
            "status": "answered" if values else "no_data",
            "canton": canton_code,
            "canton_name": cantons[canton_code],
            "population_type": population_type,
            "sex": sex,
            "unit": "persons",
            "values": values,
            "source": "Federal Statistical Office (FSO/BFS)",
            "source_url": TABLE_URL,
            "table_title": metadata["title"],
            "note": "Annual population count; all residence permits, ages and citizenships combined. Not a current/live population estimate.",
        }
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as exc:
        return unavailable(exc)


class BFSStatistics:
    """Query the Federal Statistical Office's selected PxWeb table."""

    def __init__(self, requester: Callable[..., dict | list] = request_json) -> None:
        self.requester = requester

    def population(
        self,
        canton: str,
        start_year: int | None,
        end_year: int | None,
        population_type: str,
        sex: str,
    ) -> dict:
        return _population(canton, start_year, end_year, population_type, sex, self.requester)
