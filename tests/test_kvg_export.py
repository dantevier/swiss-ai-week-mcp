"""Check the generated KVG26 data exports for missing or mismatched scenarios."""

import csv
from collections import Counter
from io import BytesIO
from pathlib import Path

import pytest

from scripts import build_kvg_premiums as exporter

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_all_premium_scenarios_and_empty_areas() -> None:
    with (DATA_DIR / "kvg_minimum_premiums_2026.csv").open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 52_200
    scenarios = Counter(
        (row["age_group"], row["accident_cover"], row["deductible_chf"]) for row in rows
    )
    assert set(scenarios) == {
        (age, accident, str(deductible))
        for age in ("adult_26_plus", "young_19_25")
        for accident in ("included", "excluded")
        for deductible in (300, 500, 1000, 1500, 2000, 2500)
    }
    assert set(scenarios.values()) == {2175}
    assert all(row["year"] == "2026" for row in rows)
    assert len({row["source_url"] for row in rows}) == 24
    assert len({(row["source_url"], row["bfs_number"]) for row in rows}) == len(rows)

    missing = [row for row in rows if not row["minimum_premium"]]
    assert len(missing) == 3 * 24
    assert {row["municipality"] for row in missing} == {
        "Staatswald Galm",
        "Comunanza Cadenazzo/Monteceneri",
        "Comunanza Capriasca/Lugano",
    }
    assert all(
        row["best_insurer"] and row["best_model"]
        for row in rows if row["minimum_premium"]
    )

    sample = next(
        row for row in rows
        if row["bfs_number"] == "1" and row["age_group"] == "adult_26_plus"
        and row["accident_cover"] == "excluded" and row["deductible_chf"] == "2500"
    )
    assert (sample["minimum_premium"], sample["best_insurer"], sample["best_model"]) == (
        "300.9", "Sanitas", "TelMed (Compact One)"
    )


def test_markdown_has_one_data_row_per_csv_record() -> None:
    markdown = (DATA_DIR / "kvg_minimum_premiums_2026.md").read_text(encoding="utf-8")
    assert markdown.count("\n## ") == 24
    assert sum(line.startswith("| ") for line in markdown.splitlines()) == 52_200 + 24 * 2
    assert "| Aeugst am Albis | 1 | 1.0 | ZH3 | 300.9 | Sanitas | TelMed (Compact One) |" in markdown
    assert "valid only for the 2026 premium year. They are invalid for 2027" in markdown
    assert "https://www.priminfo.admin.ch/de/praemien" in markdown


def test_new_year_produces_separate_files_and_correct_year_labels(tmp_path, monkeypatch) -> None:
    properties = dict.fromkeys(exporter.PROPERTY_COLUMNS)
    properties.update({
        "gemeinde.NAME": "Example",
        "BFS_NUMMER": 1,
        "BFS": 1.0,
        "Prämie": 100.0,
        "Versicherer": "Example insurer",
        "Tarifbezeichnung": "Example model",
    })
    urls = []

    def fake_fetch(url: str, year: int) -> list[dict]:
        assert year == 2027
        urls.append(url)
        return [{"properties": properties}]

    monkeypatch.setattr(exporter, "fetch_features", fake_fetch)
    exporter.build_exports(2027, "https://kvgmapper27.github.io", tmp_path)

    with (tmp_path / "kvg_minimum_premiums_2027.csv").open(encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    markdown = (tmp_path / "kvg_minimum_premiums_2027.md").read_text(encoding="utf-8")
    assert len(rows) == 24
    assert all(row["year"] == "2027" and row["minimum_premium"] == "100.0" for row in rows)
    assert {row["source_url"] for row in rows} == set(urls)
    assert "https://kvgmapper27.github.io/maps/map-AKL-JUG-MIT-UNF-FRA-2500.html" in urls
    assert "valid only for the 2027 premium year. They are invalid for 2028" in markdown
    assert "https://www.priminfo.admin.ch/de/praemien" in markdown


def test_export_rejects_a_map_for_the_wrong_year(monkeypatch) -> None:
    monkeypatch.setattr(
        exporter, "urlopen", lambda request, timeout: BytesIO(b"<title>KVG26 mapper</title>")
    )
    with pytest.raises(ValueError, match="Map title does not confirm 2027"):
        exporter.fetch_features("https://kvgmapper27.github.io/maps/example.html", 2027)
