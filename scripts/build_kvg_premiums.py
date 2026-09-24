"""Export all KVG mapper premium scenarios to year-specific CSV and Markdown.

Run from the repository root: python3 scripts/build_kvg_premiums.py --year 2027
"""

import argparse
import csv
import json
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
AGES = {"AKL-ERW": "adult_26_plus", "AKL-JUG": "young_19_25"}
ACCIDENT_COVER = {"OHN-UNF": "excluded", "MIT-UNF": "included"}
DEDUCTIBLES = (300, 500, 1000, 1500, 2000, 2500)

# Every GeoJSON feature property is represented once, with a more useful column name.
PROPERTY_COLUMNS = {
    "gemeinde.NAME": "municipality",
    "BFS_NUMMER": "bfs_number",
    "BFS": "bfs",
    "Region": "region",
    "Prämie": "minimum_premium",
    "Versicherer": "best_insurer",
    "Tarifbezeichnung": "best_model",
    "Tarif": "tariff",
    "Tariftyp": "tariff_type",
    "Prämie_old": "previous_minimum_premium",
    "Versicherer_old": "previous_insurer",
    "Tarifbezeichnung_old": "previous_model",
    "Tarif_old": "previous_tariff",
    "Tariftyp_old": "previous_tariff_type",
    "%_increase": "percent_increase",
    "Rec": "recommendation",
    "Action": "action",
    "Savincr": "premium_change",
}
SCENARIO_COLUMNS = ("year", "age_group", "accident_cover", "deductible_chf")
COLUMNS = (*SCENARIO_COLUMNS, *PROPERTY_COLUMNS.values(), "source_url")


def fetch_features(url: str, year: int) -> list[dict]:
    request = Request(url, headers={"User-Agent": "swiss-ai-week-mcp-kvg-export/1.0"})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=60) as response:
                html = response.read().decode("utf-8")
            break
        except (HTTPError, URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2**attempt)

    if not re.search(rf"<title>\s*KVG{year % 100:02d} mapper\s*</title>", html):
        raise ValueError(f"Map title does not confirm {year}: {url}")
    match = re.search(r"\bvar mygeojs = (\{[^\r\n]*\});", html)
    if not match:
        raise ValueError(f"No embedded GeoJSON found in {url}")
    features = json.loads(match.group(1))["features"]
    if not features:
        raise ValueError(f"No features found in {url}")
    return features


def display(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def markdown_cell(value: object) -> str:
    return display(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def build_exports(year: int, site_url: str, data_dir: Path) -> None:
    rows = []
    scenarios = []
    reference_places = None
    missing = set()

    for age_code, age_group in AGES.items():
        for accident_code, accident_cover in ACCIDENT_COVER.items():
            for deductible in DEDUCTIBLES:
                url = f"{site_url}/maps/map-{age_code}-{accident_code}-FRA-{deductible}.html"
                features = fetch_features(url, year)
                places = {}
                scenario_rows = []
                for feature in features:
                    props = feature["properties"]
                    if set(props) != set(PROPERTY_COLUMNS):
                        raise ValueError(f"Unexpected property fields in {url}: {set(props) ^ set(PROPERTY_COLUMNS)}")
                    bfs_number = props["BFS_NUMMER"]
                    if not isinstance(bfs_number, int) or bfs_number in places:
                        raise ValueError(f"Missing or duplicate BFS number in {url}: {bfs_number}")
                    places[bfs_number] = props["gemeinde.NAME"]
                    if props["Prämie"] is None:
                        missing.add((bfs_number, props["gemeinde.NAME"]))
                    elif not all(props[key] is not None for key in ("Versicherer", "Tarifbezeichnung")):
                        raise ValueError(f"Premium without insurer/model for BFS {bfs_number} in {url}")

                    row = dict(zip(
                        SCENARIO_COLUMNS, (year, age_group, accident_cover, deductible), strict=True
                    ))
                    row.update({column: props[key] for key, column in PROPERTY_COLUMNS.items()})
                    row["source_url"] = url
                    scenario_rows.append(row)

                if reference_places is None:
                    reference_places = places
                elif places != reference_places:
                    raise ValueError(f"Jurisdictions differ from first scenario: {url}")

                scenario_rows.sort(key=lambda row: row["bfs_number"])
                rows.extend(scenario_rows)
                scenarios.append((age_group, accident_cover, deductible, url, scenario_rows))
                print(f"{age_group}, {accident_cover}, CHF {deductible}: {len(scenario_rows)} rows")

    data_dir.mkdir(exist_ok=True)
    csv_path = data_dir / f"kvg_minimum_premiums_{year}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    md_path = data_dir / f"kvg_minimum_premiums_{year}.md"
    table_columns = tuple(PROPERTY_COLUMNS.values())
    with md_path.open("w", encoding="utf-8") as output:
        output.write(f"# {year} minimum basic health insurance premiums by Swiss jurisdiction\n\n")
        output.write(
            f"Source: [KVG{year % 100:02d} mapper]({site_url}/). "
            "Extracted directly from the embedded GeoJSON of each linked map scenario. "
            f"The year {year} follows the map's KVG{year % 100:02d} title; "
            "the maps do not explicitly state the monetary unit or billing period. "
            "Amounts are preserved as shown; no currency or billing-period conversion was applied.\n\n"
        )
        output.write(
            f"**Validity:** These premiums are valid only for the {year} premium year. "
            f"They are invalid for {year + 1}; obtain a new {year + 1} dataset instead. "
            "Official premium reference: [Priminfo (Federal Office of Public Health)]"
            "(https://www.priminfo.admin.ch/de/praemien). "
            "The jurisdiction-level values below were extracted from the linked KVG mapper "
            "pages, not downloaded directly from Priminfo.\n\n"
        )
        output.write(
            f"**Coverage:** {len(reference_places)} jurisdictions × {len(scenarios)} scenarios "
            f"= {len(rows)} records. Adult = age 26+; young = age 19–25. "
            "Accident cover is included or excluded; deductible is in CHF. "
            "One row is kept for each jurisdiction in every scenario, including areas with "
            "no published premium (blank fields). Geometry is omitted.\n\n"
        )
        output.write("**Source field mapping:** " + "; ".join(
            f"`{key}` → `{column}`" for key, column in PROPERTY_COLUMNS.items()
        ) + ". Each source property appears once in both exports. "
            "`previous_*`, `recommendation`, `action`, `percent_increase`, and "
            "`premium_change` reproduce the map's comparison/recommendation fields; "
            f"they are not additional {year} offers.\n\n")
        output.write(
            "The CSV contains the same records and properties, plus explicit `year`, "
            "`age_group`, `accident_cover`, `deductible_chf`, and `source_url` columns. "
            "For each table below, these scenario values and the source URL are specified in the heading.\n\n"
        )
        if missing:
            output.write("**Jurisdictions with missing premiums:** " + "; ".join(
                f"{name} (BFS {bfs})" for bfs, name in sorted(missing)
            ) + ".\n\n")
        for age_group, accident_cover, deductible, url, scenario_rows in scenarios:
            output.write(
                f"## {age_group} · accident {accident_cover} · deductible CHF {deductible}\n\n"
                f"Year: {year} · Source: [{url}]({url})\n\n"
            )
            output.write("| " + " | ".join(table_columns) + " |\n")
            output.write("| " + " | ".join("---" for _ in table_columns) + " |\n")
            for row in scenario_rows:
                output.write("| " + " | ".join(markdown_cell(row[key]) for key in table_columns) + " |\n")
            output.write("\n")

    print(f"Wrote {len(rows)} records to {csv_path} and {md_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2026, help="Premium year (default: 2026)")
    parser.add_argument(
        "--site-url", help="Map website origin (default: https://kvgmapperYY.github.io)"
    )
    args = parser.parse_args()
    if not 2000 <= args.year <= 2099:
        parser.error("--year must be between 2000 and 2099")
    site_url = (args.site_url or f"https://kvgmapper{args.year % 100:02d}.github.io").rstrip("/")
    parsed = urlsplit(site_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.query or parsed.fragment:
        parser.error("--site-url must be an HTTPS URL without query or fragment")
    build_exports(args.year, site_url, DATA_DIR)


if __name__ == "__main__":
    main()
