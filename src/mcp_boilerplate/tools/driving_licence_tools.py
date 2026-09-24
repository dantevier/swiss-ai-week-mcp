"""Read documented foreign driving licence exchange facts from SQLite."""

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Literal

from ..config.settings import settings
from ..server import mcp


DEFAULT_DATABASE = Path(__file__).resolve().parents[3] / "var" / "swissproject.sqlite3"
FactType = Literal["all", "fee", "deadline", "requirement"]


def _database_path() -> Path:
    return Path(settings.driving_licence_db_path).expanduser() if settings.driving_licence_db_path else DEFAULT_DATABASE


def _chf(rappen: int) -> str:
    return f"{rappen // 100}.{rappen % 100:02d}"


@mcp.tool
def get_driving_licence_exchange_info(canton: str = "CH", fact_type: FactType = "all") -> dict:
    """Look up official-source facts about exchanging a foreign driving licence in Switzerland.

    Call this tool first, before search_knowledge, for any foreign driving
    licence exchange question: control drive (Kontrollfahrt, course de
    contrôle, corsa di controllo), country exemptions (ASTRA country lists,
    e.g. Taiwan only for categories A1 and B), fees, deadlines, documents.
    Use canton "CH" when no canton is given.
    Call this tool for Swiss driving licence exchange questions about fees,
    deadlines, required documents, exams or eligibility. Use a two-letter
    canton code (for example GR, ZH or VD); CH returns federal rules only.
    fact_type can narrow the result to fee, deadline or requirement.

    Every result includes its authority, source URL, validation date and
    applicability conditions. Conditions are supplied as documented: the
    caller must check them against the person's circumstances before treating
    a conditional fact as applicable. A missing fact does not mean that a fee
    is zero or that a requirement is waived.
    """
    jurisdiction = (canton or "CH").strip().upper()
    if len(jurisdiction) != 2 or not jurisdiction.isalpha():
        return {"status": "invalid_input", "message": "Use CH or a two-letter Swiss canton code."}
    if fact_type not in {"all", "fee", "deadline", "requirement"}:
        return {"status": "invalid_input", "message": "fact_type must be all, fee, deadline or requirement."}

    path = _database_path()
    if not path.is_file():
        return {
            "status": "source_unavailable",
            "message": "Driving licence SQLite data is unavailable. Import it on this server and configure DRIVING_LICENCE_DB_PATH if needed.",
        }

    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            if not db.execute(
                "SELECT 1 FROM driving_licence_sources WHERE jurisdiction = ?",
                (jurisdiction,),
            ).fetchone():
                return {"status": "invalid_input", "message": f"No driving licence source for jurisdiction {jurisdiction}."}

            query = """
                SELECT f.id, f.rule_jurisdiction, f.fact_key, f.fact_type,
                       f.description_en, f.source_url, f.validated_at,
                       f.amount_min_rappen, f.amount_max_rappen, f.fee_code,
                       f.fee_model, f.period_value, f.period_unit, f.period_anchor,
                       f.deadline_code, f.requirement_code, f.requirement_kind,
                       f.requirement_effect, s.authority, s.authority_level,
                       s.source_status, c.field, c.operator, c.value
                FROM driving_licence_applicable_facts AS f
                JOIN driving_licence_sources AS s ON s.id = f.source_id
                LEFT JOIN driving_licence_fact_conditions AS c ON c.fact_id = f.id
                WHERE f.jurisdiction = ?
            """
            parameters: list[str] = [jurisdiction]
            if fact_type != "all":
                query += " AND f.fact_type = ?"
                parameters.append(fact_type)
            query += """
                ORDER BY CASE f.fact_type
                             WHEN 'deadline' THEN 0
                             WHEN 'fee' THEN 1
                             ELSE 2 END,
                         CASE WHEN f.rule_jurisdiction = 'CH' THEN 0 ELSE 1 END,
                         f.fact_key, c.field, c.value
            """

            facts_by_id: dict[int, dict] = {}
            for row in db.execute(query, parameters):
                fact = facts_by_id.get(row["id"])
                if fact is None:
                    fact = {
                        "rule_jurisdiction": row["rule_jurisdiction"],
                        "fact_key": row["fact_key"],
                        "fact_type": row["fact_type"],
                        "description_en": row["description_en"],
                        "authority": row["authority"],
                        "authority_level": row["authority_level"],
                        "source_status": row["source_status"],
                        "source_url": row["source_url"],
                        "validated_at": row["validated_at"],
                        "conditions": [],
                    }
                    if row["fact_type"] == "fee":
                        fact.update({
                            "fee_code": row["fee_code"],
                            "fee_model": row["fee_model"],
                            "amount_min_chf": _chf(row["amount_min_rappen"]),
                            "amount_max_chf": _chf(row["amount_max_rappen"]),
                        })
                    elif row["fact_type"] == "deadline":
                        fact.update({
                            "deadline_code": row["deadline_code"],
                            "period_value": row["period_value"],
                            "period_unit": row["period_unit"],
                            "period_anchor": row["period_anchor"],
                        })
                    else:
                        fact.update({
                            "requirement_code": row["requirement_code"],
                            "requirement_kind": row["requirement_kind"],
                            "requirement_effect": row["requirement_effect"],
                        })
                    facts_by_id[row["id"]] = fact
                if row["field"] is not None:
                    fact["conditions"].append({
                        "field": row["field"],
                        "operator": row["operator"],
                        "value": row["value"],
                    })

            groups: dict[str, list[str]] = {}
            if any(
                condition["field"] == "country_group"
                for fact in facts_by_id.values()
                for condition in fact["conditions"]
            ):
                for row in db.execute(
                    "SELECT group_code, country_code FROM driving_licence_country_groups "
                    "ORDER BY group_code, country_code"
                ):
                    groups.setdefault(row["group_code"], []).append(row["country_code"])
    except sqlite3.Error:
        return {
            "status": "source_unavailable",
            "message": "Driving licence SQLite data is unreadable or its schema has not been imported.",
        }

    facts = list(facts_by_id.values())
    return {
        "status": "answered" if facts else "no_data",
        "jurisdiction": jurisdiction,
        "fact_type": fact_type,
        "facts": facts,
        "country_groups": groups,
        "interpretation": (
            "Conditions on different fields mean AND; multiple values for one field mean OR. "
            "Apply specific waivers over general requirements. Amounts are documented line "
            "items or ranges; do not sum components unless the source explicitly makes them "
            "additive. Missing facts mean unknown, not free or waived."
        ),
    }
