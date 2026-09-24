"""Offline lookup of BWO/UFAB housing and renting knowledge from SQLite."""

import json
import math
import re
import sqlite3
import unicodedata
from collections import Counter
from contextlib import closing
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from ..config.settings import settings
from ..server import mcp

DEFAULT_DATABASE = Path(__file__).resolve().parents[3] / "var" / "swissproject.sqlite3"
Language = Literal["it", "de", "fr", "rm"]
LANGUAGES = {"it", "de", "fr", "rm"}
CANONICAL_LANGUAGE = "it"
# Search keywords per topic in IT, DE, FR, RM and EN: passages are in the four national
# languages, so a question in another language (often English, when the calling model
# translates it) can only match through these keywords.
TOPIC_ALIASES = {
    "reference_rate": "tasso riferimento ipotecario guida referenzzinssatz hypothekarisch leitzins taux reference hypothecaire directeur mortgage interest",
    "rent_adjustment": "affitto pigione canone aumento riduzione contestare mietzins erhohung senkung anfechten loyer hausse baisse contester tschains augment increase decrease reduction reduce contest challenge adjustment",
    "jurisdiction": "cantone cantonale federale competenza kanton kantonal bund kompetenz canton cantonal federal competence jurisdiction",
    "deposit": "cauzione deposito garanzia kaution depot mietkaution caution garantie cauziun deposit security guarantee",
    "handover": "consegna riconsegna verbale trasloco ubergabe protokoll einzug auszug etat lieux remise surdada protocol handover move moving inspection report",
    "utilities": "spese accessorie acconto conteggio nebenkosten akonto abrechnung charges acompte decompte custs accessorics aconto utilities ancillary heating statement",
    "defects": "difetti danni riparazione guasto schaden reparatur kaputt degats reparation dommages donns reparatura defect damage damaged repair broken break breaks",
    "alterations": "modifiche cambiare dipingere lavatrice verandern veranderung streichen waschmaschine changements repeindre midadas alteration paint painting renovate renovation modify",
    "termination": "disdetta disdire kundigung kundigen resiliation resilier disditga disdir terminate termination cancel notice",
}
CONCILIATION_TERMS = ("concilia", "schlichtung", "mediaziun")
# Address/location questions; whole words so "dov'è" matches and "ou" (or) does not.
ADDRESS_TERMS = ("indirizz", "adress", "address", "elenco")
ADDRESS_WORDS = {"dove", "dov", "wo", "où", "liste", "list", "lista", "nua"}
ALIAS_BONUS = 2.0
INITIAL_RENT_TERMS = ("pigione iniziale", "affitto iniziale", "anfangsmietzins", "loyer initial", "tschains da locaziun inizial")
ROW_COLUMNS = """item_key, record_kind, topic, language, title, summary, source_passage, data_json,
    conditions_json, publisher, publisher_level, jurisdiction_level, jurisdiction_code,
    source_kind, source_url, source_locator, source_version_date, published_on,
    effective_from, applicability_verified, scraped_at, last_verified_at, next_check_at"""


def _database_path() -> Path:
    if settings.housing_db_path:
        return Path(settings.housing_db_path).expanduser()
    return DEFAULT_DATABASE


def _unavailable(detail: str) -> dict:
    return {
        "status": "source_unavailable",
        "message": f"Housing SQLite data is {detail}. Run 'python scripts/import_housing.py' on this server and configure HOUSING_DB_PATH if needed.",
    }


def _current_rows(where: str = "1 = 1", parameters: tuple = ()) -> list[sqlite3.Row] | dict:
    """Current rows of every language, or a source_unavailable response."""
    path = _database_path()
    if not path.is_file():
        return _unavailable("missing")
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            return db.execute(
                f"SELECT {ROW_COLUMNS} FROM housing_knowledge WHERE is_current = 1 AND {where}",
                parameters,
            ).fetchall()
    except sqlite3.Error:
        return _unavailable("unreadable or not imported")


def _pick_language(rows: list[sqlite3.Row], language: str) -> sqlite3.Row:
    """Row in the requested language, else the canonical Italian row."""
    by_language = {row["language"]: row for row in rows}
    return by_language.get(language) or by_language[CANONICAL_LANGUAGE]


def _freshness(row: sqlite3.Row, today: date) -> str:
    stale = datetime.now(UTC) > datetime.fromisoformat(row["next_check_at"])
    if row["record_kind"] == "rate_publication":
        # A newer quarterly publication may exist from the announced date on.
        stale = stale or today >= date.fromisoformat(json.loads(row["data_json"])["next_publication_on"])
    return "stale" if stale else "fresh"


def _evidence(row: sqlite3.Row, language: str, today: date) -> dict:
    item = {
        "item_key": row["item_key"],
        "title": row["title"],
        "summary": row["summary"],
        "data": json.loads(row["data_json"]),
        "conditions": json.loads(row["conditions_json"]),
        "publisher": row["publisher"],
        "publisher_level": row["publisher_level"],
        "jurisdiction_level": row["jurisdiction_level"],
        "jurisdiction_code": row["jurisdiction_code"],
        "effective_from": row["effective_from"],
        "applicability_verified": bool(row["applicability_verified"]),
        "source": {
            "url": row["source_url"],
            "locator": row["source_locator"],
            "passage": row["source_passage"],
            "language": row["language"],
            "kind": row["source_kind"],
            "version_date": row["source_version_date"],
            "published_on": row["published_on"],
        },
        "scraped_at": row["scraped_at"],
        "last_verified_at": row["last_verified_at"],
        "freshness": _freshness(row, today),
    }
    if row["language"] != language:
        item["language_fallback"] = f"No verified {language} source for this item; returning the {row['language']} source."
    return item


def _stems(text: str) -> list[str]:
    folded = unicodedata.normalize("NFKD", text.casefold())
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    return [token[:6] for token in re.findall(r"\w+", folded) if len(token) >= 4 or token.isdigit()]


def _rank(question: str, items: dict[str, list[sqlite3.Row]]) -> list[tuple[float, str]]:
    """BM25-like score per item: rare words weigh more, repeats saturate, topic keywords add a bonus.

    ponytail: 6-char prefix stems over ~70 rows; switch to FTS5 or embeddings if the corpus grows.
    """
    query = set(_stems(question))
    if not query:
        return sorted((0.0, item_key) for item_key in items)
    documents = {
        item_key: [(Counter(_stems(f"{row['title']} {row['summary']} {row['source_passage']}")), set(_stems(row["title"]))) for row in variants]
        for item_key, variants in items.items()
    }
    frequency = Counter(stem for variants in documents.values() for stem in set().union(*(terms for terms, _ in variants)))
    idf = {stem: math.log(1 + len(items) / frequency[stem]) for stem in query if frequency[stem]}
    ranked = []
    for item_key, variants in documents.items():
        aliases = set(_stems(TOPIC_ALIASES[items[item_key][0]["topic"]]))
        best = max(
            sum(weight * terms[stem] * 2.2 / (terms[stem] + 1.2) for stem, weight in idf.items())
            + sum(idf.get(stem, 0.0) for stem in query & title)
            for terms, title in variants
        )
        score = best + ALIAS_BONUS * len(query & aliases)
        if score > 0:
            ranked.append((score, item_key))
    return sorted(ranked, key=lambda pair: (-pair[0], pair[1]))


def _bp_percent(value: int) -> str:
    return f"{value / 100:.2f}"


@mcp.tool
def swiss_reference_interest_rate(as_of: str | None = None, language: Language = "it") -> dict:
    """Return the Swiss mortgage reference interest rate for rents (BWO/UFAB).

    Call this tool first, before search_knowledge, for the reference rate
    (Referenzzinssatz, taux de référence, tasso di riferimento).
    National value, valid in all cantons: never ask for a canton. as_of is an
    ISO date (YYYY-MM-DD, default today); the publication in force on that
    date is chosen by its effective date. Dates before the imported coverage,
    or after the announced next publication, are not answered: the history is
    not imported and future values are not forecast. language (it, de, fr, rm)
    selects the source passage; without a verified source in that language
    the Italian publication is returned and labelled. Rates are also given in
    basis points (125 = 1.25%). Rent changes are not calculated here.
    """
    today = date.today()
    if language not in LANGUAGES:
        return {"status": "invalid_input", "message": "language must be it, de, fr or rm."}
    try:
        target = date.fromisoformat(as_of) if as_of else today
    except ValueError:
        return {"status": "invalid_input", "message": "as_of must be an ISO date (YYYY-MM-DD)."}

    rows = _current_rows("record_kind = 'rate_publication'")
    if isinstance(rows, dict):
        return rows
    publications: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        publications.setdefault(row["item_key"], []).append(row)
    ordered = sorted(
        (_pick_language(variants, language) for variants in publications.values()),
        key=lambda row: row["effective_from"],
    )
    if not ordered:
        return _unavailable("empty")
    coverage = {"from": ordered[0]["effective_from"], "publications": len(ordered)}
    in_force = [row for row in ordered if date.fromisoformat(row["effective_from"]) <= target]
    if not in_force:
        return {
            "status": "no_match",
            "as_of": target.isoformat(),
            "coverage": coverage,
            "message": f"No verified publication in force on {target}; coverage starts {coverage['from']}. Earlier history is not imported.",
        }

    row = in_force[-1]
    evidence = _evidence(row, language, today)
    data = evidence["data"]
    next_publication = date.fromisoformat(data["next_publication_on"])
    if target >= next_publication:
        if target > today:
            return {
                "status": "no_match",
                "as_of": target.isoformat(),
                "coverage": coverage,
                "message": f"{target} is on or after the announced next publication ({next_publication}); future rates are not forecast.",
            }
        return {
            "status": "source_unavailable",
            "as_of": target.isoformat(),
            "coverage": coverage,
            "message": f"A publication was announced for {next_publication} but has not been imported; the last observation below may be outdated.",
            "last_observation": evidence,
        }

    return {
        "status": "answered",
        "as_of": target.isoformat(),
        "reference_rate_percent": _bp_percent(data["reference_rate_bp"]),
        "reference_rate_bp": data["reference_rate_bp"],
        "average_rate_percent": _bp_percent(data["average_rate_bp"]),
        "average_rate_bp": data["average_rate_bp"],
        "average_rate_as_of": data["average_rate_as_of"],
        "effective_from": row["effective_from"],
        "published_on": row["published_on"],
        "value_unchanged_since": data["value_unchanged_since"],
        "next_publication_on": data["next_publication_on"],
        "coverage": coverage,
        "evidence": evidence,
        "message": "National rate for rent adjustments; applies in all cantons. Individual rent changes depend on the contract.",
    }


@mcp.tool
def swiss_housing_info(
    question: str | None = None,
    language: Language = "it",
    topic: str | None = None,
    limit: int = 5,
) -> dict:
    """Find official BWO/UFAB guidance on Swiss residential renting.

    Call this tool first for any Swiss residential renting question (Mietrecht,
    bail à loyer, locazione, locaziun), before search_knowledge: rent deposit
    (Kaution, caution, cauzione), termination, rent increase or reduction,
    ancillary costs, defects, move-in/move-out reports. Answer from the
    returned passages; do not add articles or amounts they do not contain.
    Covers: reference-rate method and rent adjustment FAQ (increase, reduction,
    contesting, exceptions), federal vs cantonal competence, and the "Abitare
    in Svizzera" guide on deposit, move-in/move-out reports, ancillary costs,
    defects, alterations and termination. Topics: reference_rate,
    rent_adjustment, jurisdiction, deposit, handover, utilities, defects,
    alterations, termination. Use swiss_reference_interest_rate for the
    current rate value. Rules are national: do not ask for a canton.
    Not covered: cantonal initial-rent forms, conciliation authority
    addresses, individual rent calculations, commercial leases, purchases.
    Each result carries the verbatim source passage, URL, locator, source
    language and conditions; check the conditions before applying a result.
    limit: 1-10.
    """
    today = date.today()
    if language not in LANGUAGES:
        return {"status": "invalid_input", "message": "language must be it, de, fr or rm."}
    if not 1 <= limit <= 10:
        return {"status": "invalid_input", "message": "limit must be between 1 and 10."}
    if topic is not None and topic not in TOPIC_ALIASES:
        return {"status": "invalid_input", "message": f"topic must be one of: {', '.join(TOPIC_ALIASES)}."}
    if not (question and question.strip()) and topic is None:
        return {"status": "need_info", "message": "Provide a question or a topic."}

    lowered = f" {(question or '').casefold()} "
    words = set(re.findall(r"\w+", lowered))
    if any(term in lowered for term in INITIAL_RENT_TERMS):
        return {
            "status": "out_of_scope",
            "message": "The initial-rent form obligation depends on canton and date; the cantonal list is not imported.",
            "orientation_source": "https://www.bwo.admin.ch/it/modulo-ufficiale-pigione-iniziale",
        }
    if any(term in lowered for term in CONCILIATION_TERMS) and (
        words & ADDRESS_WORDS or any(term in lowered for term in ADDRESS_TERMS)
    ):
        return {
            "status": "out_of_scope",
            "message": "Conciliation authorities are local; their directory is not imported.",
            "orientation_source": "https://www.bwo.admin.ch/it/procedura-di-conciliazione",
        }

    where, parameters = "record_kind != 'rate_publication'", ()
    if topic:
        where, parameters = where + " AND topic = ?", (topic,)
    rows = _current_rows(where, parameters)
    if isinstance(rows, dict):
        return rows
    items: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        items.setdefault(row["item_key"], []).append(row)

    ranked = _rank(question or "", items)
    if not ranked:
        return {"status": "no_match", "message": "No imported BWO/UFAB housing guidance matches this question."}

    results = [_evidence(_pick_language(items[item_key], language), language, today) for _, item_key in ranked[:limit]]
    return {
        "status": "answered",
        "language": language,
        "results": results,
        "message": "Official explanations and guides, not legal text. General information: apply the listed conditions; no individual contract advice.",
    }
