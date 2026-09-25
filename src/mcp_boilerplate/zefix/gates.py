"""Step-0 gates for `company_info` (PRD §5.2, §5.4): persons, jurisdiction,
analytics, topic. These run on `question`/parameters alone, before any
network call, and decide whether the tool answers "out_of_scope" instead of
resolving a company.

Pure functions and data only: no I/O, no `settings`. The only import outside
the standard library is `zefix.sources.rest.{normalize_uid,CANTON_CODES}`,
two I/O-free helpers (UID string normalisation and the static 26-canton-code
set) that `_is_jurisdiction_gate`, `_has_swiss_anchor`, and
`_looks_company_like` need to tell a Swiss UID/canton from a foreign one;
nothing here constructs a client or touches the network.
"""

from __future__ import annotations

import re
from typing import Literal

from .sources import rest as zefix

# ---------------------------------------------------------------------------
# Module constants: word lists for the step-0 gates (PRD §5.2, §5.4)
# ---------------------------------------------------------------------------

_PERSON_TERMS: tuple[str, ...] = (
    "verwaltungsrat",
    "geschäftsführer",
    "geschaeftsfuehrer",
    "zeichnungsberechtigt",
    "revisionsstelle",
    "inhaber",
    "conseil d'administration",
    "conseil d’administration",
    "administrateur",
    "gérant",
    "gerant",
    "signature",
    "organe de révision",
    "organe de revision",
    "consiglio di amministrazione",
    "amministratore",
    "gerente",
    "firma sociale",
    "ufficio di revisione",
    "board",
    "director",
    "signatory",
    "auditor",
)

_ANALYTICS_TERMS: tuple[str, ...] = (
    "wie viele",
    "combien",
    "quante",
    "how many",
    "alle firmen",
    "toutes les sociétés",
    "toutes les societes",
    "tutte le aziende",
    "list all",
)

_TOPIC_HINTS: tuple[str, ...] = (
    "firma",
    "société",
    "societe",
    "azienda",
    "handelsregister",
    "registre du commerce",
    "registro di commercio",
    "shab",
    "fosc",
    "fusc",
)

_LEGAL_FORM_SUFFIXES: tuple[str, ...] = (
    "ag",
    "gmbh",
    "sa",
    "sagl",
    "sàrl",
    "sarl",
    "snc",
    "scs",
    "genossenschaft",
)

_FOREIGN_REGISTER_IDS: tuple[str, ...] = (
    "hrb",
    "siren",
    "siret",
    "rea",
    "companies house",
    "handelsregister b",
)

# Hand-written, ~40 common country names (minus Switzerland) in de/fr/it/en.
# Compact by design (interfaces.md deltas): a hint list, not an ISO table.
_COUNTRY_NAMES: frozenset[str] = frozenset(
    {
        "deutschland", "allemagne", "germania", "germany",
        "österreich", "oesterreich", "autriche", "austria",
        "frankreich", "france", "francia",
        "italien", "italie", "italy",
        "liechtenstein",
        "spanien", "espagne", "spagna", "spain",
        "portugal",
        "grossbritannien", "royaume-uni", "regno unito", "united kingdom",
        "england", "angleterre", "inghilterra",
        "vereinigte staaten", "états-unis", "etats-unis", "stati uniti", "united states", "usa",
        "niederlande", "pays-bas", "paesi bassi", "netherlands",
        "belgien", "belgique", "belgio", "belgium",
        "luxemburg", "luxembourg", "lussemburgo",
        "polen", "pologne", "polonia", "poland",
        "schweden", "suède", "suede", "svezia", "sweden",
        "norwegen", "norvège", "norvegia", "norway",
        "dänemark", "danemark", "danimarca", "denmark",
        "finnland", "finlande", "finlandia", "finland",
        "irland", "irlande", "irlanda", "ireland",
        "griechenland", "grèce", "grecia", "greece",
        "türkei", "turquie", "turchia", "turkey",
        "russland", "russie", "russia",
        "china", "chine", "cina",
        "japan", "japon", "giappone",
        "indien", "inde", "india",
        "brasilien", "brésil", "brasile", "brazil",
        "kanada", "canada",
        "mexiko", "mexique", "messico", "mexico",
        "tschechien", "république tchèque", "repubblica ceca", "czech republic",
        "ungarn", "hongrie", "ungheria", "hungary",
        "kroatien", "croatie", "croazia", "croatia",
        "ukraine",
        "rumänien", "roumanie", "romania",
    }
)

_SWISS_WORDS: frozenset[str] = frozenset({"schweiz", "suisse", "svizzera", "switzerland", "che"})

_CANTON_NAMES: frozenset[str] = frozenset(
    {
        "zürich", "zuerich", "zurich", "bern", "berne", "luzern", "lucerne", "uri",
        "schwyz", "obwalden", "nidwalden", "glarus", "zug", "freiburg", "fribourg",
        "solothurn", "basel", "bâle", "basilea", "schaffhausen", "appenzell",
        "st. gallen", "st gallen", "san gallo", "graubünden", "grigioni", "grisons",
        "aargau", "argovie", "argovia", "thurgau", "thurgovie", "turgovia",
        "ticino", "tessin", "vaud", "waadt", "wallis", "valais", "vallese",
        "neuchâtel", "neuenburg", "neuchatel", "genf", "genève", "geneve", "ginevra", "jura",
    }
)

_FOREIGN_UID_PREFIX_RE = re.compile(r"^[A-Z]{2,}")


def _uid_is_foreign(raw: str) -> bool:
    """True if `raw` carries a non-CHE alphabetic UID prefix (e.g. "DE...")."""
    s = raw.strip().upper()
    if s.startswith("CHE"):
        return False
    return bool(_FOREIGN_UID_PREFIX_RE.match(s))


def _has_swiss_anchor(question: str, canton: str | None) -> bool:
    if canton:
        return True
    q_lower = question.lower()
    if any(word in q_lower for word in _SWISS_WORDS):
        return True
    if any(name in q_lower for name in _CANTON_NAMES):
        return True
    q_upper = question.upper()
    for code in zefix.CANTON_CODES:
        if re.search(rf"\b{code}\b", q_upper):
            return True
    return False


def _has_persons_terms(question: str | None) -> bool:
    if not question:
        return False
    q = question.lower()
    return any(term in q for term in _PERSON_TERMS)


def _is_jurisdiction_gate(uid: str | None, question: str | None, canton: str | None) -> bool:
    if uid and zefix.normalize_uid(uid) is None and _uid_is_foreign(uid):
        return True
    if not question:
        return False
    q_lower = question.lower()
    has_country = any(country in q_lower for country in _COUNTRY_NAMES)
    has_foreign_id = any(fid in q_lower for fid in _FOREIGN_REGISTER_IDS)
    if not (has_country or has_foreign_id):
        return False
    return not _has_swiss_anchor(question, canton)


def _has_analytics_terms(question: str | None) -> bool:
    if not question:
        return False
    q = question.lower()
    return any(term in q for term in _ANALYTICS_TERMS)


def _looks_company_like(question: str) -> bool:
    q = question.lower()
    if any(hint in q for hint in _TOPIC_HINTS):
        return True
    if zefix.normalize_uid(question) is not None:
        return True
    if re.search(r"\bche[-\s]?\d{3}[.\s]?\d{3}[.\s]?\d{3}\b", q):
        return True
    for suffix in _LEGAL_FORM_SUFFIXES:
        if re.search(rf"\b{re.escape(suffix)}\b", q):
            return True
    return False


# ---------------------------------------------------------------------------
# classify(): the single entry point, reproducing the step-0 gate order
# ---------------------------------------------------------------------------

Reason = Literal["persons", "jurisdiction", "analytics", "topic"]


def classify(
    question: str | None, uid: str | None, canton: str | None, has_identifier: bool
) -> Reason | None:
    """Run the step-0 gates in order and return the first reason that fires.

    Order and conditions match the former inline block in
    `company_info()` exactly (D6, zero behaviour change):

    1. persons - `_has_persons_terms(question)`, checked unconditionally.
    2. jurisdiction - `_is_jurisdiction_gate(uid, question, canton)`, checked
       unconditionally.
    3. analytics - `_has_analytics_terms(question)`, checked unconditionally.
    4. topic - only when `has_identifier` is False (no `name`/`uid` given)
       and `question` is truthy and not `_looks_company_like(question)`.

    Returns None when no gate fires. The caller still must handle the
    `not has_identifier` case with no gate firing (missing name/uid but a
    question that either is absent or looks company-like): the former inline
    block returns "need_info" there, which is not an out-of-scope reason and
    stays the caller's responsibility.
    """
    if _has_persons_terms(question):
        return "persons"
    if _is_jurisdiction_gate(uid, question, canton):
        return "jurisdiction"
    if _has_analytics_terms(question):
        return "analytics"
    if not has_identifier and question and not _looks_company_like(question):
        return "topic"
    return None
