#!/usr/bin/env python3
"""Generate benchmark questions whose answers are computed from official Swiss open data.

    python benchmark/build/generate.py            # downloads into .cache/bench, writes data/generated.jsonl

Sources (all public, no credentials):
- BAG health insurance premiums 2026 (archive behind opendata.bagnet.ch)
- SR 832.106 Annex 1, premium region per municipality, version in force on 1 Jan 2026 (Fedlex filestore)
- BFS official register of municipalities: snapshot, levels, mutations since 2015

Every answer is looked up in these files, never typed by hand, and each item quotes the rows it came from.
Standard library only. Same seed, same data -> same output.
"""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import random
import re
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".cache" / "bench"
OUT = ROOT / "benchmark" / "data" / "generated.jsonl"
UA = "swiss-grounding-benchmark/0.1 (Swiss AI Weeks hackathon)"
TODAY = "2026-09-24"
REGISTER_DATE = "24-09-2026"

URLS = {
    "premiums.zip": "https://opendata.bagnet.ch/?r=/download&path=L1ByYWVtaWVuL0FyY2hpdl9QcmFlbWllbl8yMDI2LnppcA%3D%3D",
    "regions.html": "https://www.fedlex.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/2022/184/20260101/de/html/"
                    "fedlex-data-admin-ch-eli-cc-2022-184-20260101-de-html.html",
    "communes.csv": f"https://www.agvchapp.bfs.admin.ch/api/communes/snapshot?date={REGISTER_DATE}",
    "levels.csv": f"https://www.agvchapp.bfs.admin.ch/api/communes/levels?date={REGISTER_DATE}",
    "mutations.csv": "https://www.agvchapp.bfs.admin.ch/api/communes/mutations?startPeriod=01-01-2015"
                     f"&endPeriod={REGISTER_DATE}&includeTerritoryExchange=false",
}
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
LANG_OF_REGION = {"1": "de", "2": "fr", "3": "it", "4": "de"}


def fetch(name: str) -> Path:
    path = CACHE / name
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(URLS[name], headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=300) as r:
            path.write_bytes(r.read())
    return path


def read_csv(name: str, delimiter: str = ",") -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(fetch(name).read_text(encoding="utf-8-sig")), delimiter=delimiter))


def zip_csv(member: str, delimiter: str) -> list[dict[str, str]]:
    with zipfile.ZipFile(fetch("premiums.zip")) as z:
        name = next(n for n in z.namelist() if n.endswith(member))
        text = z.read(name).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text), delimiter=delimiter))


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


class Data:
    def __init__(self) -> None:
        self.cantons = {c["BfsCode"]: c["ShortName"] for c in read_csv("communes.csv") if c["Level"] == "1"}
        self.communes = {}
        for c in read_csv("levels.csv"):
            self.communes[c["BfsCode"]] = {
                "bfs": c["BfsCode"], "name": c["Name"], "canton": self.cantons[c["CantonId"]],
                "lang": LANG_OF_REGION.get(c["SPRGEB2020"], "de"),
            }
        self.mutations = read_csv("mutations.csv")
        self.regions = self._regions()
        self.premiums = self._premiums()

    def _regions(self) -> dict[str, str]:
        doc = fetch("regions.html").read_text(encoding="utf-8")
        if "no-script-warning" in doc:
            raise SystemExit("Fedlex returned the SPA shell instead of the consolidated text")
        table = {}
        for tr in re.findall(r"<tr>(.*?)</tr>", doc, re.S):
            cells = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", td))).strip()
                     for td in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if len(cells) == 3 and cells[0].isdigit() and cells[2].isdigit():
                table[cells[0]] = cells[2]
        return table

    def _premiums(self) -> dict[tuple, list[dict]]:
        catchment = {(int(x["Versicherer"]), x["Kanton"], x["Region"], x["Tarif"])
                     for x in zip_csv("Einzugsgebiete.csv", ";")}
        by_key = defaultdict(list)
        for r in zip_csv("Prämien_CH.csv", ","):
            if r["Altersklasse"] not in ("AKL-ERW", "AKL-JUG"):
                continue
            offered = r["Tariftyp"] == "TAR-BASE" or (int(r["Versicherer"]), r["Kanton"], r["Region"], r["Tarif"]) in catchment
            if offered:
                by_key[(r["Kanton"], r["Region"], r["Altersklasse"], r["Franchise"], r["Unfalleinschluss"])].append(r)
        return by_key

    def region_of(self, commune: dict) -> str | None:
        multi = {k[1] for k in self.premiums if k[0] == commune["canton"]}
        if multi == {"PR-REG CH0"}:
            return "0"
        return self.regions.get(commune["bfs"])

    def cheapest(self, commune: dict, age: str, franchise: int, accident: bool, standard: bool) -> dict | None:
        region = self.region_of(commune)
        if region is None:
            return None
        rows = self.premiums.get((commune["canton"], f"PR-REG CH{region}", age, f"FRA-{franchise}",
                                  "MIT-UNF" if accident else "OHN-UNF"), [])
        if standard:
            rows = [r for r in rows if r["Tariftyp"] == "TAR-BASE"]
        return min(rows, key=lambda r: float(r["Prämie"])) if rows else None


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
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    data = Data()
    lugano = next(c for c in data.communes.values() if c["name"] == "Lugano")
    check = data.cheapest(lugano, "AKL-ERW", 2500, False, False)
    if not check or check["Prämie"] != "449.9":
        raise SystemExit(f"self-check failed: Lugano adult 2500 no accident should be 449.9, got {check and check['Prämie']}")

    rng = random.Random(args.seed)
    items = (gen_premiums(data, rng, args.premiums_per_canton) + gen_regions(data, rng, args.regions)
             + gen_cantons(data, rng, args.cantons) + gen_mergers(data, rng, args.mergers)
             + gen_same_name(data) + gen_foreign(data) + gen_askback(data))
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
    counts = defaultdict(int)
    for it in items:
        counts[it["id"].split("-")[1]] += 1
    print(f"wrote {len(items)} items to {args.out}: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
