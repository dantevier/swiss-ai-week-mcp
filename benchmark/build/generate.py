#!/usr/bin/env python3
"""Generate a balanced sector suite and the full offline-data benchmark corpus.

    python scripts/build_knowledge_db.py
    python benchmark/build/generate.py

The database was built from BAG, Fedlex and BFS official data. This generator does not
access the network. Lower-data sectors use question framings grounded in verified QA
items; these variants retain their source fact cluster. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sqlite3
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "swiss_places_premiums_2026.sqlite"
OUT = ROOT / "benchmark" / "data" / "generated.jsonl"
FULL_OUT = ROOT / "benchmark" / "data" / "generated_full.jsonl"
FULL_SECTOR_OUT = ROOT / "benchmark" / "data" / "generated_full_by_sector"
QA_SEEDS = ROOT / "benchmark" / "data" / "qa.jsonl"
SECTOR_OUT = ROOT / "benchmark" / "data" / "generated_by_sector"
TODAY = "2026-09-24"
REGISTER_DATE = "24-09-2026"
PREMIUM_PAGE = "https://opendata.swiss/de/dataset/health-insurance-premiums"
REGION_PAGE = "https://www.fedlex.admin.ch/eli/cc/2022/184/de"
REGISTER_PAGE = "https://www.agvchapp.bfs.admin.ch/de/communes/query"

CANTON_NAMES = {
    "ZH": ["Zürich", "Zurich", "Zurigo"], "BE": ["Bern", "Berne", "Berna"], "LU": ["Luzern", "Lucerne", "Lucerna"],
    "UR": ["Uri"], "SZ": ["Schwyz", "Schwytz", "Svitto"], "OW": ["Obwalden", "Obwald", "Obvaldo"],
    "NW": ["Nidwalden", "Nidwald", "Nidvaldo"], "GL": ["Glarus", "Glaris", "Glarona"], "ZG": ["Zug", "Zoug", "Zugo"],
    "FR": ["Freiburg", "Fribourg", "Friburgo"], "SO": ["Solothurn", "Soleure", "Soletta"],
    "BS": ["Basel-Stadt", "Bâle-Ville", "Basilea Città", "Basel-City"],
    "BL": ["Basel-Landschaft", "Basel-Land", "Bâle-Campagne", "Basilea Campagna"],
    "SH": ["Schaffhausen", "Schaffhouse", "Sciaffusa"],
    "AR": ["Appenzell Ausserrhoden", "Rhodes-Extérieures", "Appenzello Esterno", "Appenzell Outer Rhodes"],
    "AI": ["Appenzell Innerrhoden", "Rhodes-Intérieures", "Appenzello Interno", "Appenzell Inner Rhodes"],
    "SG": ["St. Gallen", "Sankt Gallen", "Saint-Gall", "San Gallo", "St Gallen"],
    "GR": ["Graubünden", "Grisons", "Grigioni", "Grischun"], "AG": ["Aargau", "Argovie", "Argovia"],
    "TG": ["Thurgau", "Thurgovie", "Turgovia"], "TI": ["Tessin", "Ticino"], "VD": ["Waadt", "Vaud"],
    "VS": ["Wallis", "Valais", "Vallese"], "NE": ["Neuenburg", "Neuchâtel"], "GE": ["Genf", "Genève", "Ginevra", "Geneva"],
    "JU": ["Jura", "Giura"],
}
LANG_OF_REGION = {1: "de", 2: "fr", 3: "it", 4: "de"}
AREA_SLUGS = {
    1: "health-insurance-premiums", 2: "taxes-and-duties", 3: "law-and-regulations",
    4: "waste-and-recycling", 5: "residence-and-civil-status", 6: "migration",
    7: "social-insurance-and-pensions", 8: "work-and-unemployment", 9: "schools-and-education",
    10: "public-transport", 11: "road-traffic-and-licences", 12: "housing-and-rental",
    13: "voting-and-political-rights", 14: "companies-and-vat", 15: "customs",
    16: "statistics-and-open-data",
}
CONTEXT_PREFIX = {
    "de": "Kannst du mir bitte helfen? ",
    "fr": "Pouvez-vous m'aider ? ",
    "it": "Può aiutarmi? ",
    # Keep Romansh prompts intact until a Romansh reviewer can verify variants.
    "rm": "",
}
QUESTION_FRAMINGS = {
    "de": ["Bitte beantworte kurz: ", "Ich brauche dazu eine verlässliche Auskunft: ",
           "Ich möchte gern wissen: ", "Kannst du mir bitte sagen: ",
           "Bitte erkläre mir Folgendes: ", "Ich habe eine Frage: ",
           "Bitte prüfe folgende Frage: ", "Wie lautet die Auskunft dazu? ",
           "Kannst du mir weiterhelfen? ", "Ich suche die offizielle Information: "],
    "fr": ["Veuillez répondre brièvement : ", "J'aimerais obtenir un renseignement fiable : ",
           "Je voudrais savoir : ", "Pouvez-vous me préciser : ",
           "Veuillez m'expliquer ceci : ", "J'ai une question : ",
           "Veuillez vérifier la question suivante : ", "Quelle est l'information officielle ? ",
           "Pouvez-vous m'aider ? ", "Je cherche une information fiable : "],
    "it": ["Risponda brevemente, per favore: ", "Vorrei un'informazione affidabile: ",
           "Vorrei sapere: ", "Può precisarmi: ",
           "Mi spieghi per favore quanto segue: ", "Ho una domanda: ",
           "Verifichi per favore questa domanda: ", "Qual è l'informazione ufficiale? ",
           "Può aiutarmi? ", "Cerco un'informazione affidabile: "],
}


def base_name(name: str) -> str:
    return re.sub(r"\s*\([A-Z]{2}\)$", "", name).strip()


def name_pattern(name: str) -> str:
    return r"(?i)(?<![\w-])" + re.escape(base_name(name)).replace(r"\ ", r"[\s-]") + r"(?![\w-])"


def same_spelling(a: str, b: str) -> bool:
    def norm(s: str) -> str:
        return re.sub(r"[\s-]+", " ", base_name(s)).lower()
    return norm(a) == norm(b)


def canton_pattern(ct: str) -> str:
    names = "|".join(re.escape(n).replace(r"\ ", r"\s") for n in CANTON_NAMES[ct])
    return rf"(?i:{names})|\b{ct}\b"


def chf_pattern(value: float) -> str:
    whole, cents = f"{value:.2f}".split(".")
    if cents == "00":
        return rf"\b{whole}(?:[.,]0{{1,2}}|\.[-–])?(?![.,]?\d)"
    if cents.endswith("0"):
        return rf"\b{whole}[.,]{cents[0]}0?\b"
    return rf"\b{whole}[.,]{cents}\b"


def item(**kw) -> dict:
    base = {
        "sample": False, "must_not_include": [], "ask_for": [], "common_errors": [],
        "verified_at": TODAY, "verified_by": "generated from official data by benchmark/build/generate.py",
        "valid_until": "",
    }
    base.update(kw)
    return base


def read_verified_seeds() -> list[dict]:
    if not QA_SEEDS.exists():
        raise SystemExit(f"verified benchmark seeds not found: {QA_SEEDS}")
    with QA_SEEDS.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def gen_context_variants(seeds: list[dict]) -> list[dict]:
    """Add a light prompt-context case for each non-Romansh verified seed."""
    out = []
    for seed in seeds:
        prefix = CONTEXT_PREFIX.get(seed["lang"])
        if not prefix:
            continue
        row = dict(seed)
        row["id"] = f"gen-context-{seed['id']}"
        row["question"] = prefix + seed["question"]
        row["sample"] = seed.get("sample", False)
        row["generated_variant"] = "context_prefix"
        row["source_item_id"] = seed["id"]
        row["fact_cluster_id"] = seed["id"]
        row["verified_by"] = "generated prompt variant from verified benchmark item; answer and evidence retained"
        out.append(row)
    return out


def make_balanced_sector_suite(items: list[dict], seeds: list[dict], per_area: int) -> list[dict]:
    """Build an equal-sized sector suite from official rows and verified seed variants."""
    by_area: dict[int, list[dict]] = defaultdict(list)
    for row in items:
        by_area[int(row["topic_area"])].append(row)
    seed_by_area: dict[int, list[dict]] = defaultdict(list)
    for row in seeds:
        seed_by_area[int(row["topic_area"])].append(row)

    suite = []
    for area, slug in AREA_SLUGS.items():
        pool = sorted(by_area.get(area, []), key=lambda row: row["id"])
        chosen: list[dict] = []
        chosen_clusters: set[str] = set()
        # Give each available verified fact one seat before drawing more data rows.
        for row in pool:
            if row.get("generated_variant") != "context_prefix":
                continue
            cluster = row.get("fact_cluster_id", row["id"])
            if cluster not in chosen_clusters:
                chosen.append(row)
                chosen_clusters.add(cluster)
        direct = [row for row in pool if row.get("generated_variant") != "context_prefix"]
        direct = [row for row in direct if row["id"] not in {item["id"] for item in chosen}]
        needed = max(0, per_area - len(chosen))
        if len(direct) > needed:
            direct = random.Random(2026 + area).sample(direct, needed)
        chosen.extend(direct[:needed])

        variants = []
        for seed in seed_by_area.get(area, []):
            for variant_no, prefix in enumerate(QUESTION_FRAMINGS.get(seed["lang"], []), 1):
                row = dict(seed)
                row["id"] = f"gen-balanced-{area:02d}-{seed['id']}-{variant_no:02d}"
                row["question"] = prefix + seed["question"]
                row["sample"] = seed.get("sample", False)
                row["generated_variant"] = "question_framing"
                row["source_item_id"] = seed["id"]
                row["fact_cluster_id"] = seed["id"]
                row["verified_by"] = "generated question framing from verified benchmark item; answer and evidence retained"
                variants.append(row)
        seen_questions = {row["question"] for row in chosen}
        for row in variants:
            if len(chosen) >= per_area:
                break
            if row["question"] not in seen_questions:
                chosen.append(row)
                seen_questions.add(row["question"])
        if len(chosen) != per_area:
            raise SystemExit(
                f"topic area {area} ({slug}) has {len(chosen)} distinct grounded questions; "
                f"cannot meet target {per_area}. Add verified seeds or reduce --questions-per-area."
            )
        for row in chosen:
            row = dict(row)
            row.setdefault("fact_cluster_id", row.get("source_item_id", row["id"]))
            row["sector_suite"] = "balanced_sector"
            suite.append(row)
    return suite


def write_sector_files(items: list[dict], directory: Path) -> dict[int, int]:
    directory.mkdir(parents=True, exist_ok=True)
    counts = {}
    for area, slug in AREA_SLUGS.items():
        rows = [it for it in items if int(it["topic_area"]) == area]
        path = directory / f"area-{area:02d}-{slug}.jsonl"
        with path.open("w", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        counts[area] = len(rows)
    return counts


class Data:
    def __init__(self, db_path: Path) -> None:
        if not db_path.exists():
            raise SystemExit(
                f"knowledge database not found: {db_path}\n"
                "Run: python scripts/build_knowledge_db.py"
            )
        self.connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        self.connection.row_factory = sqlite3.Row
        self.communes = {
            str(row["bfs_code"]): {
                "bfs": str(row["bfs_code"]),
                "name": row["name"],
                "canton": row["canton"],
                "lang": LANG_OF_REGION.get(row["language_region"], "de"),
                "region": str(row["premium_region"]),
            }
            for row in self.connection.execute(
                "SELECT * FROM communes ORDER BY source_order"
            )
        }
        self.mutations = [
            {
                "MutationNumber": str(row["mutation_number"]),
                "MutationDate": ".".join(reversed(row["mutation_date"].split("-"))),
                "InitialHistoricalCode": str(row["initial_historical_code"]),
                "InitialCode": str(row["initial_bfs_code"]),
                "InitialName": row["initial_name"],
                "TerminalHistoricalCode": str(row["terminal_historical_code"]),
                "TerminalCode": str(row["terminal_bfs_code"]),
                "TerminalName": row["terminal_name"],
            }
            for row in self.connection.execute(
                "SELECT * FROM municipality_mutations"
            )
        ]

    def region_of(self, commune: dict) -> str:
        return commune["region"]

    def cheapest(
        self,
        commune: dict,
        age: str,
        franchise: int,
        accident: bool,
        standard: bool,
    ) -> dict | None:
        standard_filter = "AND tariff_type = 'TAR-BASE'" if standard else ""
        row = self.connection.execute(
            f"""
            SELECT * FROM premium_offers
            WHERE canton = ?
              AND premium_region = ?
              AND business_year = 2026
              AND age_class = ?
              AND deductible_chf = ?
              AND accident_included = ?
              AND is_offered_in_region = 1
              {standard_filter}
            ORDER BY monthly_premium_rappen, insurer_id, tariff_code
            LIMIT 1
            """,
            (
                commune["canton"],
                int(commune["region"]),
                age,
                franchise,
                int(accident),
            ),
        ).fetchone()
        if row is None:
            return None
        return {
            "Versicherer": str(row["insurer_id"]),
            "Kanton": row["canton"],
            "Region": f"PR-REG CH{row['premium_region']}",
            "Altersklasse": row["age_class"],
            "Unfalleinschluss": (
                "MIT-UNF" if row["accident_included"] else "OHN-UNF"
            ),
            "Tarif": row["tariff_code"],
            "Tariftyp": row["tariff_type"],
            "Franchise": f"FRA-{row['deductible_chf']}",
            "Prämie": str(Decimal(row["monthly_premium_rappen"]) / 100),
            "Tarifbezeichnung": row["tariff_name"],
        }


def premium_row_evidence(row: dict) -> str:
    keys = ["Versicherer", "Kanton", "Region", "Altersklasse", "Unfalleinschluss", "Tariftyp", "Franchise", "Prämie",
            "Tarifbezeichnung"]
    return "Prämien_CH.csv (BAG, Geschäftsjahr 2026), cheapest matching row: " + ", ".join(f"{k}={row[k]}" for k in keys)


def region_evidence(data: Data, commune: dict) -> str:
    region = data.region_of(commune)
    if region == "0":
        return f"Canton {commune['canton']} has a single premium region (PR-REG CH0 in Prämien_CH.csv)."
    return f"SR 832.106 Anhang 1 (in force 1.1.2026): {commune['bfs']} {commune['name']} {region}"


WHO = {
    "AKL-ERW": {"de": "eine erwachsene Person (ab 26 Jahren)", "fr": "un adulte (dès 26 ans)",
                "it": "un adulto (dai 26 anni)", "en": "an adult (26 or older)"},
    "AKL-JUG": {"de": "eine junge erwachsene Person (19 bis 25 Jahre)", "fr": "un jeune adulte (19 à 25 ans)",
                "it": "un giovane adulto (da 19 a 25 anni)", "en": "a young adult (19 to 25)"},
}
ACC = {True: {"de": "mit Unfalldeckung", "fr": "avec couverture accidents", "it": "con copertura infortuni"},
       False: {"de": "ohne Unfalldeckung", "fr": "sans couverture accidents", "it": "senza copertura infortuni"}}
MODEL = {True: {"de": "im Standardmodell (ohne Hausarzt-, HMO- oder Telmed-Modell)",
                "fr": "dans le modèle standard (sans modèle médecin de famille, HMO ou telmed)",
                "it": "nel modello standard (senza medico di famiglia, HMO o telmed)"},
         False: {"de": "wobei alle Versicherungsmodelle zählen", "fr": "tous modèles d'assurance confondus",
                 "it": "considerando tutti i modelli assicurativi"}}
PREMIUM_Q = {
    "de": "Wie hoch ist 2026 die günstigste monatliche Prämie der obligatorischen Grundversicherung für {who} mit "
          "Wohnsitz in {place} ({ct}), Franchise {fr} Franken, {acc}, {model}?",
    "fr": "Quelle est en 2026 la prime mensuelle la plus basse de l'assurance obligatoire des soins pour {who} "
          "domicilié à {place} ({ct}), avec une franchise de {fr} francs, {acc}, {model} ?",
    "it": "Qual è nel 2026 il premio mensile più basso dell'assicurazione obbligatoria delle cure per {who} "
          "domiciliato a {place} ({ct}), con franchigia di {fr} franchi, {acc}, {model}?",
}


def gen_premiums(data: Data, rng: random.Random, per_canton: int) -> list[dict]:
    out = []
    by_canton = defaultdict(list)
    for c in data.communes.values():
        if data.region_of(c) is not None:
            by_canton[c["canton"]].append(c)
    for ct in sorted(by_canton):
        communes = sorted(by_canton[ct], key=lambda c: c["bfs"])
        by_region = defaultdict(list)
        for c in communes:
            by_region[data.region_of(c)].append(c)
        picks = [rng.choice(v) for _, v in sorted(by_region.items())]
        rest = [c for c in communes if c not in picks]
        picks += rng.sample(rest, min(len(rest), max(0, per_canton - len(picks))))
        for c in picks:
            age = rng.choice(["AKL-ERW", "AKL-ERW", "AKL-JUG"])
            fr = rng.choice([300, 500, 1000, 1500, 2000, 2500])
            acc = rng.random() < 0.4
            std = rng.random() < 0.35
            row = data.cheapest(c, age, fr, acc, std)
            other = data.cheapest(c, age, fr, not acc, std)
            alt = data.cheapest(c, age, fr, acc, not std)
            if not row:
                continue
            lang = c["lang"]
            value = float(row["Prämie"])
            q = PREMIUM_Q[lang].format(who=WHO[age][lang], place=base_name(c["name"]), ct=ct, fr=f"{fr:,}".replace(",", "'"),
                                       acc=ACC[acc][lang], model=MODEL[std][lang])
            errors = []
            if other:
                errors.append(f"Gives the figure {'without' if acc else 'with'} accident cover (CHF {float(other['Prämie']):.2f})")
            if alt:
                errors.append(f"Gives the {'cheapest-of-all-models' if std else 'standard-model'} figure (CHF {float(alt['Prämie']):.2f})")
            errors.append("Gives a cantonal average or a premium from another region")
            out.append(item(
                id=f"gen-premium-{c['bfs']}-{age[-3:].lower()}-{fr}-{'acc' if acc else 'noacc'}-{'std' if std else 'any'}",
                lang=lang, topic_area=1, topic="health_insurance_premiums", level="federal",
                failure_mode="invisible_data", question=q, expected_behavior="answer",
                reference_answer=(f"CHF {value:.2f} per month in 2026 ({row['Tarifbezeichnung']}, insurer no. "
                                  f"{row['Versicherer']}). " + (
                                      f"Canton {ct} has a single premium region." if data.region_of(c) == "0" else
                                      f"{base_name(c['name'])} is in premium region {data.region_of(c)} of canton {ct}.")),
                must_include=[{"fact": f"CHF {value:.2f}", "pattern": chf_pattern(value)}],
                common_errors=errors,
                authority="Federal Office of Public Health (BAG)", source_url=PREMIUM_PAGE,
                source_domains=["priminfo.admin.ch", "bag.admin.ch", "opendata.swiss"],
                evidence=premium_row_evidence(row) + ". " + region_evidence(data, c),
                valid_until="2026-12-31",
            ))
    return out


REGION_Q = {
    "de": "In welcher Prämienregion der Krankenversicherung liegt die Gemeinde {place} ({ct})?",
    "fr": "Dans quelle région de primes de l'assurance-maladie se trouve la commune de {place} ({ct}) ?",
    "it": "In quale regione di premio dell'assicurazione malattie si trova il comune di {place} ({ct})?",
}


def gen_regions(data: Data, rng: random.Random, n: int) -> list[dict]:
    candidates = [c for c in data.communes.values() if data.region_of(c) not in (None, "0")]
    out = []
    for c in sorted(rng.sample(candidates, min(n, len(candidates))), key=lambda c: c["bfs"]):
        region = data.region_of(c)
        out.append(item(
            id=f"gen-region-{c['bfs']}", lang=c["lang"], topic_area=1, topic="health_insurance_premiums",
            level="federal", failure_mode="invisible_data",
            question=REGION_Q[c["lang"]].format(place=base_name(c["name"]), ct=c["canton"]),
            expected_behavior="answer",
            reference_answer=f"Premium region {region} of canton {c['canton']} (SR 832.106, Annex 1, in force 2026).",
            must_include=[{"fact": f"region {region}", "pattern": rf"(?i)regi\w*\D{{0,25}}\b{region}\b|\b{c['canton']}\s?{region}\b"}],
            common_errors=["Says the canton has one premium level", "Gives the region of a neighbouring municipality"],
            authority="Federal Department of Home Affairs (SR 832.106)", source_url=REGION_PAGE,
            source_domains=["fedlex.admin.ch", "bag.admin.ch"], evidence=region_evidence(data, c),
            valid_until="2026-12-31",
        ))
    return out


CANTON_Q = {
    "de": "In welchem Kanton liegt die Gemeinde {place}?",
    "fr": "Dans quel canton se trouve la commune de {place} ?",
    "it": "In quale cantone si trova il comune di {place}?",
}


def gen_cantons(data: Data, rng: random.Random, n: int) -> list[dict]:
    counts = defaultdict(int)
    for c in data.communes.values():
        counts[base_name(c["name"]).lower()] += 1
    old_names = {base_name(m["InitialName"]).lower() for m in data.mutations}
    candidates = [c for c in data.communes.values()
                  if counts[base_name(c["name"]).lower()] == 1 and "(" not in c["name"]
                  and base_name(c["name"]).lower() not in old_names - {base_name(c["name"]).lower()}
                  and c["name"].lower() not in {n.lower() for v in CANTON_NAMES.values() for n in v}]
    out = []
    for c in sorted(rng.sample(candidates, min(n, len(candidates))), key=lambda c: c["bfs"]):
        ct = c["canton"]
        out.append(item(
            id=f"gen-canton-{c['bfs']}", lang=c["lang"], topic_area=16, topic="statistics", level="federal",
            failure_mode="invisible_data", question=CANTON_Q[c["lang"]].format(place=c["name"]),
            expected_behavior="answer",
            reference_answer=f"In the canton of {' / '.join(CANTON_NAMES[ct][:3])} ({ct}).",
            must_include=[{"fact": f"canton {ct}", "pattern": canton_pattern(ct)}],
            common_errors=["Names a neighbouring canton", "Confuses it with a similarly named place"],
            authority="Federal Statistical Office (BFS)", source_url=REGISTER_PAGE, source_domains=["bfs.admin.ch"],
            evidence=f"Official register of Swiss municipalities, state {REGISTER_DATE}: BFS no. {c['bfs']} {c['name']}, canton {ct}.",
        ))
    return out


MERGED_Q = {
    "de": "Ich ziehe nach {old}. Bei welcher Gemeinde muss ich mich anmelden?",
    "fr": "Je déménage à {old}. Auprès de quelle commune dois-je m'annoncer ?",
    "it": "Mi trasferisco a {old}. Presso quale comune devo annunciarmi?",
}


def gen_mergers(data: Data, rng: random.Random, n: int) -> list[dict]:
    successor = {}
    for m in data.mutations:
        if m["InitialCode"] != m["TerminalCode"] or m["InitialName"] != m["TerminalName"]:
            successor[m["InitialHistoricalCode"]] = m
    current = {c["name"].lower() for c in data.communes.values()} | {base_name(c["name"]).lower() for c in data.communes.values()}
    old_count = defaultdict(set)
    for m in data.mutations:
        old_count[base_name(m["InitialName"]).lower()].add(m["InitialCode"])
    found = {}
    for m in data.mutations:
        old = m["InitialName"]
        if base_name(old).lower() in current or len(old_count[base_name(old).lower()]) > 1 or old == m["TerminalName"]:
            continue
        step, seen = m, set()
        while step["TerminalHistoricalCode"] in successor and step["TerminalHistoricalCode"] not in seen:
            seen.add(step["TerminalHistoricalCode"])
            step = successor[step["TerminalHistoricalCode"]]
        new = data.communes.get(step["TerminalCode"])
        if (new and new["name"] == step["TerminalName"] and not same_spelling(old, new["name"])
                and not re.search(name_pattern(new["name"]), old)):
            found[m["InitialCode"]] = (m, step, new)
    out = []
    keys = sorted(found)
    for code in sorted(rng.sample(keys, min(n, len(keys)))):
        m, last, new = found[code]
        lang = new["lang"]
        date = m["MutationDate"]
        out.append(item(
            id=f"gen-merger-{code}", lang=lang, topic_area=5, topic="residence_registration", level="municipal",
            failure_mode="outdated", question=MERGED_Q[lang].format(old=m["InitialName"]),
            expected_behavior="answer",
            reference_answer=(f"{m['InitialName']} is no longer a separate municipality: since {date} it is part of "
                              f"{m['TerminalName']}" + (f", today {new['name']}" if last is not m else "")
                              + f" ({new['canton']}). You register with the municipality of {new['name']}."),
            must_include=[{"fact": new["name"], "pattern": name_pattern(new["name"])}],
            common_errors=[f"Tells the user to register with the former municipality of {m['InitialName']}",
                           "Gives a municipality from before the merger"],
            authority="Federal Statistical Office (BFS)", source_url=REGISTER_PAGE, source_domains=["bfs.admin.ch"],
            evidence=(f"BFS register, mutation no. {m['MutationNumber']} of {date}: {m['InitialName']} (BFS {m['InitialCode']}) "
                      f"-> {m['TerminalName']} (BFS {m['TerminalCode']})"
                      + (f"; later mutation no. {last['MutationNumber']} of {last['MutationDate']}: -> {last['TerminalName']}"
                         if last is not m else "") + "."),
        ))
    return out


SAME_NAME_Q = {
    "de": "Wie hoch ist 2026 die günstigste monatliche Grundversicherungsprämie für eine erwachsene Person in {place}, "
          "Franchise 2500 Franken, ohne Unfalldeckung?",
    "fr": "Quelle est en 2026 la prime mensuelle la plus basse de l'assurance de base pour un adulte à {place}, "
          "franchise de 2500 francs, sans couverture accidents ?",
    "it": "Qual è nel 2026 il premio mensile più basso dell'assicurazione di base per un adulto a {place}, "
          "franchigia di 2500 franchi, senza copertura infortuni?",
}


def gen_same_name(data: Data) -> list[dict]:
    groups = defaultdict(list)
    for c in data.communes.values():
        if re.search(r"\([A-Z]{2}\)$", c["name"]):
            groups[base_name(c["name"])].append(c)
    out = []
    for name, communes in sorted(groups.items()):
        if len({c["canton"] for c in communes}) < 2:
            continue
        prices = {}
        for c in communes:
            row = data.cheapest(c, "AKL-ERW", 2500, False, False)
            if row:
                prices[c["bfs"]] = (c, float(row["Prämie"]), row)
        if len(prices) < 2 or len({p for _, p, _ in prices.values()}) < 2:
            continue
        lang = max(communes, key=lambda c: c["lang"] == "de")["lang"]
        listing = "; ".join(f"{c['name']}: CHF {p:.2f}" for c, p, _ in prices.values())
        cts = "|".join(canton_pattern(c["canton"]) for c, _, _ in prices.values())
        out.append(item(
            id=f"gen-samename-{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')}", lang=lang, topic_area=1,
            topic="health_insurance_premiums", level="municipal", failure_mode="wrong_jurisdiction",
            question=SAME_NAME_Q[lang].format(place=name), expected_behavior="ask_back",
            reference_answer=f"There are several municipalities called {name}, with different premiums ({listing}). "
                             "Ask which one is meant.",
            must_include=[],
            ask_for=[{"info": "which municipality / canton", "pattern": rf"(?i)kanton|canton|cantone|which|welche[snm]?\b|quel(le)?\b|quale\b|{cts}"}],
            must_not_include=[],
            common_errors=["Picks one of the municipalities without saying so", "Gives a single premium"],
            authority="Federal Office of Public Health (BAG), Federal Statistical Office (BFS)",
            source_url=PREMIUM_PAGE, source_domains=["priminfo.admin.ch", "bag.admin.ch", "bfs.admin.ch"],
            evidence=" | ".join(f"{c['name']} (BFS {c['bfs']}): {premium_row_evidence(r)}" for c, _, r in prices.values()),
            valid_until="2026-12-31",
        ))
    return out


FOREIGN_TOWNS = [
    ("Konstanz", "DE"), ("Lörrach", "DE"), ("Weil am Rhein", "DE"), ("Waldshut-Tiengen", "DE"), ("Singen", "DE"),
    ("Friedrichshafen", "DE"), ("Freiburg im Breisgau", "DE"), ("Bad Säckingen", "DE"), ("Jestetten", "DE"),
    ("Como", "IT"), ("Varese", "IT"), ("Domodossola", "IT"), ("Chiavenna", "IT"), ("Luino", "IT"), ("Aosta", "IT"),
    ("Annecy", "FR"), ("Annemasse", "FR"), ("Évian-les-Bains", "FR"), ("Thonon-les-Bains", "FR"),
    ("Pontarlier", "FR"), ("Saint-Louis", "FR"), ("Mulhouse", "FR"), ("Ferney-Voltaire", "FR"), ("Chamonix", "FR"),
    ("Bregenz", "AT"), ("Feldkirch", "AT"), ("Dornbirn", "AT"), ("Vaduz", "LI"), ("Schaan", "LI"),
]
COUNTRY = {
    "DE": ("Germany", "de", "deutschland|germany|allemagne|germania"),
    "IT": ("Italy", "it", "italien|italy|italie|italia"),
    "FR": ("France", "fr", "frankreich|france|francia"),
    "AT": ("Austria", "de", "österreich|oesterreich|austria|autriche"),
    "LI": ("Liechtenstein", "de", "liechtenstein"),
}
NOT_CH = (r"not (located )?in switzerland|not swiss|outside switzerland|nicht in der schweiz|ausserhalb der schweiz|"
          r"keine schweizer|pas en suisse|hors de suisse|n'est pas suisse|non (è |si trova )?in svizzera|fuori dalla svizzera")
FOREIGN_Q = {
    "premium": {"de": "Wie hoch ist die günstigste Krankenkassenprämie in {town}?",
                "fr": "Quelle est la prime d'assurance-maladie la moins chère à {town} ?",
                "it": "Qual è il premio di cassa malati più basso a {town}?"},
    "moving": {"de": "Innert wie vielen Tagen muss ich mich nach dem Umzug nach {town} bei der Gemeinde anmelden?",
               "fr": "Dans quel délai dois-je m'annoncer à la commune après mon déménagement à {town} ?",
               "it": "Entro quanti giorni devo annunciarmi al comune dopo il trasloco a {town}?"},
    "school": {"de": "Wann sind in {town} die Herbstferien 2026?",
               "fr": "Quand sont les vacances d'automne 2026 à {town} ?",
               "it": "Quando sono le vacanze autunnali 2026 a {town}?"},
}
FOREIGN_TOPIC = {"premium": (1, "health_insurance_premiums"), "moving": (5, "residence_registration"),
                 "school": (9, "school_holidays")}


def gen_foreign(data: Data) -> list[dict]:
    swiss = {base_name(c["name"]).lower() for c in data.communes.values()}
    swiss |= {base_name(m["InitialName"]).lower() for m in data.mutations}
    out = []
    for town, cc in FOREIGN_TOWNS:
        if town.lower() in swiss:
            continue
        country, lang, pat = COUNTRY[cc]
        for kind, templates in FOREIGN_Q.items():
            area, topic = FOREIGN_TOPIC[kind]
            must_not = []
            if kind == "premium" and cc != "LI":
                must_not = [{"reason": "quotes a Swiss premium for a foreign town", "pattern": r"CHF\s?\d{2,3}[.,]\d{2}"}]
            out.append(item(
                id=f"gen-foreign-{re.sub(r'[^a-z0-9]+', '-', town.lower())}-{kind}", lang=lang, topic_area=area,
                topic=topic, level="foreign", failure_mode="foreign_confusion",
                question=templates[lang].format(town=town), expected_behavior="not_switzerland",
                reference_answer=f"{town} is in {country}, not in Switzerland. Swiss authorities and rules do not apply; "
                                 f"the user should consult the authorities of {country}.",
                must_include=[{"fact": f"says {town} is not in Switzerland / is in {country}", "pattern": f"(?i){pat}|{NOT_CH}"}],
                must_not_include=must_not,
                common_errors=["Answers with Swiss rules or figures", "Maps the town to a similarly named Swiss municipality"],
                authority="n/a (outside Switzerland)", source_url=REGISTER_PAGE, source_domains=[],
                evidence=f"'{town}' does not appear as a municipality, current or merged since 2015, in the official BFS register ({REGISTER_DATE}).",
            ))
    return out


ASKBACK = [
    ("premium", "fr", "Quelle est la prime d'assurance-maladie la moins chère pour un adulte avec une franchise de 2500 francs ?"),
    ("premium", "it", "Qual è il premio di cassa malati più basso per un adulto con franchigia di 2500 franchi?"),
    ("premium", "de", "Welche Krankenkasse ist 2026 für mich am günstigsten? Ich bin 40 und nehme die höchste Franchise."),
    ("premium", "fr", "Combien coûte au minimum l'assurance de base pour un jeune de 22 ans en 2026 ?"),
    ("premium", "it", "Quanto pago al minimo di cassa malati nel 2026 se ho 35 anni e franchigia 300?"),
    ("region", "de", "In welcher Prämienregion wohne ich?"),
    ("region", "fr", "Dans quelle région de primes est-ce que j'habite ?"),
    ("region", "it", "In quale regione di premio abito?"),
]


def gen_askback(data: Data) -> list[dict]:
    lugano = next(c for c in data.communes.values() if c["name"] == "Lugano")
    geneve = next(c for c in data.communes.values() if c["name"] == "Genève")
    zurich = next(c for c in data.communes.values() if c["name"] == "Zürich")
    ex = []
    for c in (lugano, geneve, zurich):
        row = data.cheapest(c, "AKL-ERW", 2500, False, False)
        ex.append(f"{c['name']}: CHF {float(row['Prämie']):.2f}")
    muni = (r"(?i)gemeinde|wohnort|wohnsitz|wo wohn|municipal|which (town|city|place)|where (do )?you live|commune|"
            r"quelle ville|où (habitez|vivez)|comune|quale citt|dove (abit|viv)|kanton|canton|cantone")
    out = []
    for i, (kind, lang, q) in enumerate(ASKBACK, 1):
        out.append(item(
            id=f"gen-askback-{kind}-{lang}-{i}", lang=lang, topic_area=1, topic="health_insurance_premiums",
            level="municipal", failure_mode="wrong_jurisdiction", question=q, expected_behavior="ask_back",
            reference_answer=("Ask for the municipality of residence. Premiums depend on canton and premium region "
                              f"(2026, adult, CHF 2,500 deductible, no accident cover: {'; '.join(ex)})."),
            must_include=[],
            ask_for=[{"info": "municipality", "pattern": muni}],
            common_errors=["Gives a single premium without asking where the user lives", "Gives a national average",
                           "Names an insurer without knowing the place"],
            authority="Federal Office of Public Health (BAG)", source_url=PREMIUM_PAGE,
            source_domains=["priminfo.admin.ch", "bag.admin.ch"],
            evidence="Prämien_CH.csv 2026 is keyed by Kanton and Region; " + "; ".join(ex) + ".",
            valid_until="2026-12-31",
        ))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--premiums-per-canton", type=int, default=16)
    parser.add_argument("--regions", type=int, default=80)
    parser.add_argument("--cantons", type=int, default=150)
    parser.add_argument("--mergers", type=int, default=150)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=OUT,
                        help="balanced generated set (default: 10 cases per area)")
    parser.add_argument("--full-out", type=Path, default=FULL_OUT,
                        help="preserve the full data-derived corpus as a separate file")
    parser.add_argument("--sector-dir", type=Path, default=SECTOR_OUT,
                        help="balanced per-area test files")
    parser.add_argument("--full-sector-dir", type=Path, default=FULL_SECTOR_OUT,
                        help="per-area partitions of the full, unbalanced corpus")
    parser.add_argument("--questions-per-area", type=int, default=10,
                        help="target generated cases in each balanced sector file")
    args = parser.parse_args()

    data = Data(args.db)
    lugano = next(c for c in data.communes.values() if c["name"] == "Lugano")
    check = data.cheapest(lugano, "AKL-ERW", 2500, False, False)
    if not check or check["Prämie"] != "449.9":
        raise SystemExit(f"self-check failed: Lugano adult 2500 no accident should be 449.9, got {check and check['Prämie']}")

    rng = random.Random(args.seed)
    seeds = read_verified_seeds()
    full_items = (gen_premiums(data, rng, args.premiums_per_canton) + gen_regions(data, rng, args.regions)
                  + gen_cantons(data, rng, args.cantons) + gen_mergers(data, rng, args.mergers)
                  + gen_same_name(data) + gen_foreign(data) + gen_askback(data) + gen_context_variants(seeds))
    items = make_balanced_sector_suite(full_items, seeds, args.questions_per_area)
    ids = [i["id"] for i in items]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise SystemExit(f"duplicate ids: {sorted(dupes)[:5]}")
    for it in items:
        for group in ("must_include", "must_not_include", "ask_for"):
            for p in it[group]:
                re.compile(p["pattern"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    with args.full_out.open("w", encoding="utf-8") as f:
        for it in full_items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    sector_counts = write_sector_files(items, args.sector_dir)
    full_sector_counts = write_sector_files(full_items, args.full_sector_dir)
    if any(count != args.questions_per_area for count in sector_counts.values()):
        raise SystemExit(f"balanced sector counts do not match target: {sector_counts}")
    ids = [row["id"] for row in items]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate ids in balanced sector suite")
    print(f"wrote balanced {len(items)} items to {args.out}: "
          + ", ".join(f"area {area}={count}" for area, count in sorted(sector_counts.items())))
    print(f"preserved full {len(full_items)}-item corpus at {args.full_out}; full per-area counts: "
          + ", ".join(f"{area}={count}" for area, count in sorted(full_sector_counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
