"""Response envelope for `company_info`: the five-state contract plus renderers.

Pure functions only: no I/O, no imports from `sources` or `tools`. Every
function here takes plain data in and returns a plain `dict` out, so the
tool layer (`tools/company_info.py`) and the tests can call it without any
network or process state. Field names follow PRD §5.3
(`docs/prd-zefix-company-info.md`) exactly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

# ---------------------------------------------------------------------------
# Language handling
# ---------------------------------------------------------------------------

LANGUAGES: frozenset[str] = frozenset({"de", "fr", "it", "en"})
DEFAULT_LANGUAGE = "de"


def normalize_language(language: str | None) -> str:
    """Accept de/fr/it/en; map "rm" and anything unknown to "de" (PRD G4/R9)."""
    if not language:
        return DEFAULT_LANGUAGE
    lang = language.strip().lower()
    return lang if lang in LANGUAGES else DEFAULT_LANGUAGE


# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------


def now_iso() -> str:
    """Current UTC time as ISO 8601 with a trailing Z, second precision."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Static translated content
# ---------------------------------------------------------------------------

NOTES: dict[str, str] = {
    "de": (
        "Zefix ist nicht rechtsverbindlich. Massgebend sind der beglaubigte "
        "Handelsregisterauszug des Kantons und die SHAB-Publikation."
    ),
    "fr": (
        "Zefix n'a pas de valeur juridique contraignante. Seuls l'extrait légalisé "
        "du registre du commerce cantonal et la publication FOSC font foi."
    ),
    "it": (
        "Zefix non ha valore legale vincolante. Fanno fede l'estratto autenticato "
        "del registro di commercio cantonale e la pubblicazione FUSC."
    ),
    "en": (
        "Zefix is not legally binding. The certified cantonal commercial register "
        "extract and the SHAB/FOSC/FUSC publication are authoritative."
    ),
}

# `need_info` question templates, by the single missing disambiguator.
NEED_INFO_QUESTIONS: dict[str, dict[str, str]] = {
    "uid": {
        "de": "Mehrere Firmen passen auf diesen Namen – welche UID (CHE-xxx.xxx.xxx) meinen Sie?",
        "fr": "Plusieurs entreprises correspondent à ce nom – quel est le numéro IDE (CHE-xxx.xxx.xxx) recherché ?",
        "it": "Più aziende corrispondono a questo nome: qual è l'IDI (CHE-xxx.xxx.xxx) desiderato?",
        "en": "Several companies match this name — which UID (CHE-xxx.xxx.xxx) do you mean?",
    },
    "canton": {
        "de": "Mehrere Firmen passen auf diesen Namen – in welchem Kanton hat die gesuchte Firma ihren Sitz?",
        "fr": "Plusieurs entreprises correspondent à ce nom – dans quel canton l'entreprise recherchée a-t-elle son siège ?",
        "it": "Più aziende corrispondono a questo nome: in quale cantone ha sede l'azienda cercata?",
        "en": "Several companies match this name — which canton is the company you mean seated in?",
    },
    "seat": {
        "de": "Mehrere Firmen passen auf diesen Namen – in welcher Gemeinde hat die gesuchte Firma ihren Sitz?",
        "fr": "Plusieurs entreprises correspondent à ce nom – dans quelle commune l'entreprise recherchée a-t-elle son siège ?",
        "it": "Più aziende corrispondono a questo nome: in quale comune ha sede l'azienda cercata?",
        "en": "Several companies match this name — which municipality is the company you mean seated in?",
    },
}

_ASK_NAME_QUESTION: dict[str, str] = {
    "de": "Wie lautet der Name der gesuchten Firma oder deren UID (CHE-xxx.xxx.xxx)?",
    "fr": "Quel est le nom de la société recherchée, ou son numéro IDE (CHE-xxx.xxx.xxx) ?",
    "it": "Qual è il nome dell'azienda cercata, oppure il suo numero IDI (CHE-xxx.xxx.xxx)?",
    "en": "What is the name of the company you're asking about, or its UID (CHE-xxx.xxx.xxx)?",
}

_ROMANSH_ASSUMPTION = "Romansh not available upstream; answered in German"

# `out_of_scope` sentences, by reason. Each states what this tool covers (or,
# for `persons`, points at the cantonal excerpt as the authoritative source).
OUT_OF_SCOPE_SENTENCES: dict[str, dict[str, str]] = {
    "topic": {
        "de": (
            "Diese Anfrage betrifft nicht das Handelsregister. Dieses Werkzeug "
            "beantwortet nur Fragen zu Existenz, Rechtsform, Sitz, Adresse, Status "
            "und SHAB-Publikationen von Schweizer Firmen (Zefix)."
        ),
        "fr": (
            "Cette demande ne concerne pas le registre du commerce. Cet outil "
            "répond uniquement aux questions sur l'existence, la forme juridique, "
            "le siège, l'adresse, le statut et les publications FOSC des "
            "entreprises suisses (Zefix)."
        ),
        "it": (
            "Questa richiesta non riguarda il registro di commercio. Questo "
            "strumento risponde solo a domande su esistenza, forma giuridica, "
            "sede, indirizzo, stato e pubblicazioni FUSC delle aziende svizzere "
            "(Zefix)."
        ),
        "en": (
            "This request is not about the commercial register. This tool only "
            "answers questions about the existence, legal form, seat, address, "
            "status, and SHAB publications of Swiss companies (Zefix)."
        ),
    },
    "jurisdiction": {
        "de": (
            "Dieses Werkzeug deckt nur im Schweizer Handelsregister (Zefix) "
            "eingetragene Firmen ab, nicht ausländische Register."
        ),
        "fr": (
            "Cet outil couvre uniquement les entreprises inscrites au registre du "
            "commerce suisse (Zefix), pas les registres étrangers."
        ),
        "it": (
            "Questo strumento copre solo le aziende iscritte nel registro di "
            "commercio svizzero (Zefix), non i registri esteri."
        ),
        "en": (
            "This tool only covers companies registered in the Swiss commercial "
            "register (Zefix), not foreign registers."
        ),
    },
    "persons": {
        "de": (
            "Zefix und das LINDAS-Register enthalten keine Personendaten (z. B. "
            "Verwaltungsrat, Geschäftsführer, Zeichnungsberechtigte). Massgebend "
            "dafür ist der beglaubigte Handelsregisterauszug des Kantons."
        ),
        "fr": (
            "Zefix et le registre LINDAS ne contiennent pas de données "
            "personnelles (p. ex. conseil d'administration, gérants, personnes "
            "autorisées à signer). L'extrait légalisé du registre du commerce "
            "cantonal fait foi pour ces informations."
        ),
        "it": (
            "Zefix e il registro LINDAS non contengono dati personali (ad es. "
            "consiglio di amministrazione, gerenti, persone autorizzate a "
            "firmare). Per queste informazioni fa fede l'estratto autenticato "
            "del registro di commercio cantonale."
        ),
        "en": (
            "Zefix and the LINDAS register hold no person data (e.g. board "
            "members, managing officers, authorised signatories). The certified "
            "cantonal commercial register extract is authoritative for that "
            "information."
        ),
    },
    "analytics": {
        "de": (
            "Dieses Werkzeug beantwortet Einzelfirmen-Anfragen, keine Zählungen "
            "oder Listen über das gesamte Register."
        ),
        "fr": (
            "Cet outil répond à des demandes sur une entreprise précise, pas à "
            "des comptages ou des listes portant sur l'ensemble du registre."
        ),
        "it": (
            "Questo strumento risponde a richieste su una singola azienda, non a "
            "conteggi o elenchi sull'intero registro."
        ),
        "en": (
            "This tool answers single-company questions, not counts or lists "
            "across the whole register."
        ),
    },
}

# `source_unavailable` sentences, by source. Each says explicitly that the
# source could not be reached and that this is not evidence of non-existence.
SOURCE_UNAVAILABLE_SENTENCES: dict[str, dict[str, str]] = {
    "lindas": {
        "de": (
            "Das LINDAS-Register (Zefix-Daten) konnte nicht erreicht werden. "
            "Das bedeutet nicht, dass die Firma nicht existiert."
        ),
        "fr": (
            "Le registre LINDAS (données Zefix) n'a pas pu être atteint. Cela ne "
            "signifie pas que l'entreprise n'existe pas."
        ),
        "it": (
            "Il registro LINDAS (dati Zefix) non è raggiungibile. Questo non "
            "significa che l'azienda non esista."
        ),
        "en": (
            "The LINDAS register (Zefix data) could not be reached. This does "
            "not mean the company does not exist."
        ),
    },
    "zefix": {
        "de": (
            "Der Zefix-Webdienst (Statusanreicherung) konnte nicht erreicht "
            "werden. Das bedeutet nicht, dass die Firma nicht existiert."
        ),
        "fr": (
            "Le service web Zefix (enrichissement du statut) n'a pas pu être "
            "atteint. Cela ne signifie pas que l'entreprise n'existe pas."
        ),
        "it": (
            "Il servizio web Zefix (arricchimento dello stato) non è "
            "raggiungibile. Questo non significa che l'azienda non esista."
        ),
        "en": (
            "The Zefix web service (status enrichment) could not be reached. "
            "This does not mean the company does not exist."
        ),
    },
    "gazette": {
        "de": (
            "Das Amtsblattportal (SHAB) konnte nicht erreicht werden. Das "
            "bedeutet nicht, dass die Firma nicht existiert."
        ),
        "fr": (
            "Le portail des publications officielles (FOSC) n'a pas pu être "
            "atteint. Cela ne signifie pas que l'entreprise n'existe pas."
        ),
        "it": (
            "Il portale dei fogli ufficiali (FUSC) non è raggiungibile. Questo "
            "non significa che l'azienda non esista."
        ),
        "en": (
            "The official gazette portal (SHAB/FOSC/FUSC) could not be reached. "
            "This does not mean the company does not exist."
        ),
    },
}

# Addendum (coordinator, mid-S4): lindas.search_by_name raises
# SourceUnavailable(error_class="timeout_scan") when a name scan (STRSTARTS/
# CONTAINS full-table scan) blows its budget. That failure mode is
# actionable by the caller (unlike a generic network outage): give a UID or
# an exact name+canton instead of a fuzzy prefix, so the answer sentence for
# it is a distinct, more specific override of the generic lindas sentence.
_TIMEOUT_SCAN_SENTENCES: dict[str, str] = {
    "de": (
        "Der Firmenindex konnte die Namenssuche nicht rechtzeitig abschliessen. "
        "Bitte UID (CHE-xxx.xxx.xxx) oder exakten Firmennamen und Kanton angeben."
    ),
    "fr": (
        "L'index des entreprises n'a pas pu terminer la recherche par nom à temps. "
        "Veuillez indiquer le numéro IDE (CHE-xxx.xxx.xxx) ou le nom exact de "
        "l'entreprise et le canton."
    ),
    "it": (
        "L'indice delle aziende non è riuscito a completare la ricerca per nome in "
        "tempo. Indicare l'IDI (CHE-xxx.xxx.xxx) oppure il nome esatto dell'azienda "
        "e il cantone."
    ),
    "en": (
        "The company index could not complete the name search in time. Provide the "
        "UID (CHE-xxx.xxx.xxx) or the exact registered name and canton."
    ),
}

# `no_match` sentence: "the active-entity index as of {date} holds no entry for …".
_NO_MATCH_DATE_CLAUSE: dict[str, str] = {
    "de": "(Stand {date})",
    "fr": "(état au {date})",
    "it": "(aggiornato al {date})",
    "en": "(as of {date})",
}
_NO_MATCH_TEMPLATE: dict[str, str] = {
    "de": "Der Index der aktiven Rechtseinheiten {date_clause} enthält keinen Eintrag für {query}.",
    "fr": "L'index des entités actives {date_clause} ne contient aucune entrée pour {query}.",
    "it": "L'indice delle entità attive {date_clause} non contiene alcuna voce per {query}.",
    "en": "The active-entity index {date_clause} holds no entry for {query}.",
}

_SEARCH_CANTON_TEMPLATE: dict[str, str] = {
    "de": "{name} (Kanton {canton})",
    "fr": "{name} (canton {canton})",
    "it": "{name} (Cantone {canton})",
    "en": "{name} (canton {canton})",
}

_VALID_OUT_OF_SCOPE_REASONS: frozenset[str] = frozenset({"topic", "jurisdiction", "persons", "analytics"})
_VALID_SOURCES: frozenset[str] = frozenset({"lindas", "zefix", "gazette"})


def _describe_search(searched: dict[str, Any], language: str) -> str:
    uid = searched.get("uid")
    if uid:
        return str(uid)
    name = searched.get("name") or "?"
    canton = searched.get("canton")
    if canton:
        return _SEARCH_CANTON_TEMPLATE[language].format(name=name, canton=canton)
    return str(name)


def _no_match_message(searched: dict[str, Any], dataset_modified: str | None, language: str) -> str:
    query = _describe_search(searched, language)
    date_clause = _NO_MATCH_DATE_CLAUSE[language].format(date=dataset_modified) if dataset_modified else ""
    text = _NO_MATCH_TEMPLATE[language].format(date_clause=date_clause, query=query)
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# Passage / answer rendering
# ---------------------------------------------------------------------------

_SEAT_WORD: dict[str, str] = {
    "de": "Sitz",
    "fr": "siège",
    "it": "sede",
    "en": "registered office",
}

_LOCATION_PREPOSITION: dict[str, str] = {
    "de": "mit Sitz in",
    "fr": "avec siège à",
    "it": "con sede a",
    "en": "with its registered office in",
}

_GENERIC_ENTITY: dict[str, str] = {
    "de": "Unternehmen",
    "fr": "entreprise",
    "it": "impresa",
    "en": "company",
}

# Gender/article simplification: most Swiss legal forms in German are
# feminine ("die Aktiengesellschaft", "die GmbH", "die Genossenschaft"), so a
# fixed feminine/generic article per language covers the common cases without
# a full grammatical-gender table. Rare masculine forms (e.g. "Verein") would
# read slightly off in German/French/Italian; documented, not fixed here.
_ARTICLE: dict[str, str] = {"de": "eine", "fr": "une", "it": "una", "en": "a"}


def render_passage(company: dict[str, Any], language: str) -> str:
    """Deterministic one-liner: "Name, LegalForm, Sitz: Seat (CT), Street, Zip City".

    Never LLM-generated (PRD §5.3). None parts are skipped.
    """
    lang = normalize_language(language)
    seat_word = _SEAT_WORD[lang]

    name = company.get("name")
    legal_form = company.get("legal_form")
    seat = company.get("seat")
    canton = company.get("canton")
    address = company.get("address") or {}
    street = address.get("street")
    zip_code = address.get("zip")
    city = address.get("city")

    parts: list[str] = []
    if name:
        parts.append(str(name))
    if legal_form:
        parts.append(str(legal_form))

    if seat:
        seat_bit = f"{seat} ({canton})" if canton else str(seat)
        parts.append(f"{seat_word}: {seat_bit}")

    if street:
        parts.append(str(street))

    city_bits = [str(bit) for bit in (zip_code, city) if bit]
    if city_bits:
        parts.append(" ".join(city_bits))

    return ", ".join(parts)


def _location_phrase(company: dict[str, Any], language: str) -> str | None:
    seat = company.get("seat")
    if not seat:
        return None
    canton = company.get("canton")
    location = f"{seat} ({canton})" if canton else str(seat)
    return f"{_LOCATION_PREPOSITION[language]} {location}"


def render_answer(company: dict[str, Any], language: str, *, status_source: str = "zefix") -> str:
    """One-sentence answer, e.g. "Swisscom (Schweiz) AG ist eine aktive
    Aktiengesellschaft mit Sitz in Ittigen (BE)."

    `status_source` tells the sentence how the status was determined:
    - "zefix": enrichment confirmed the live status (ACTIVE/DELETED spoken plainly).
    - "index": no enrichment ran; the company is present in the LINDAS
      active-entity index only, so activity is index membership, not a
      confirmed live status ("... im Index der aktiven Rechtseinheiten geführt").
    - "gazette": DELETED was derived from a gazette deletion publication (§5.2 3b).
    """
    lang = normalize_language(language)
    name = str(company.get("name") or "")
    legal_form = company.get("legal_form")
    form = str(legal_form) if legal_form else _GENERIC_ENTITY[lang]
    status = str(company.get("status") or "").upper()
    location = _location_phrase(company, lang) or ""
    article = _ARTICLE[lang]

    if status == "DELETED":
        return _sentence_deleted(name, form, location, lang)
    if status == "ACTIVE" and status_source == "index":
        return _sentence_index_active(name, form, location, lang)
    if status == "ACTIVE":
        return _sentence_active(name, form, location, lang, article)
    return _sentence_plain(name, form, location, lang, article)


def _join(*parts: str) -> str:
    return " ".join(p for p in parts if p)


def _sentence_active(name: str, form: str, location: str, language: str, article: str) -> str:
    if language == "de":
        return _join(f"{name} ist eine aktive {form}", location) + "."
    if language == "fr":
        return _join(f"{name} est {article} {form} active", location) + "."
    if language == "it":
        return _join(f"{name} è {article} {form} attiva", location) + "."
    return _join(f"{name} is an active {form}", location) + "."


def _sentence_index_active(name: str, form: str, location: str, language: str) -> str:
    if language == "de":
        return _join(f"{name} wird als {form} im Index der aktiven Rechtseinheiten geführt", location) + "."
    if language == "fr":
        return _join(f"{name} est enregistrée comme {form} dans l'index des entités actives", location) + "."
    if language == "it":
        return _join(f"{name} è registrata come {form} nell'indice delle entità attive", location) + "."
    return _join(f"{name} is listed as a {form} in the active-entity index", location) + "."


def _sentence_deleted(name: str, form: str, location: str, language: str) -> str:
    if language == "de":
        return _join(f"{name} war eine {form}", location) + " und ist im Handelsregister gelöscht."
    if language == "fr":
        return _join(f"{name} était une {form}", location) + " et a été radiée du registre du commerce."
    if language == "it":
        return _join(f"{name} era una {form}", location) + " ed è stata cancellata dal registro di commercio."
    return _join(f"{name} was a {form}", location) + " and has been deleted from the commercial register."


def _sentence_plain(name: str, form: str, location: str, language: str, article: str) -> str:
    if language == "de":
        return _join(f"{name} ist eine {form}", location) + "."
    if language == "fr":
        return _join(f"{name} est {article} {form}", location) + "."
    if language == "it":
        return _join(f"{name} è {article} {form}", location) + "."
    return _join(f"{name} is {article} {form}", location) + "."


# ---------------------------------------------------------------------------
# Envelope builders — one per state (PRD §5.3)
# ---------------------------------------------------------------------------


def answered(
    *,
    answer: str,
    company: dict[str, Any],
    citation: dict[str, Any],
    publications: list[dict[str, Any]] | None,
    publications_status: str,
    enrichment_status: str,
    assumptions: list[str],
    derived: bool,
    derived_rule: str | None,
    language: str,
) -> dict[str, Any]:
    lang = normalize_language(language)
    return {
        "status": "answered",
        "answer": answer,
        "company": company,
        "publications": publications,
        "publications_status": publications_status,
        "enrichment_status": enrichment_status,
        "citation": citation,
        "assumptions": assumptions,
        "derived": derived,
        "derived_rule": derived_rule,
        "notes": NOTES[lang],
        "source_validated_at": now_iso(),
    }


def need_info(
    *,
    question: str,
    candidates: list[dict[str, Any]],
    missing: str,
    language: str,
) -> dict[str, Any]:
    normalize_language(language)  # accepted for interface symmetry; `question` is already localised
    return {
        "status": "need_info",
        "question": question,
        "candidates": candidates,
        "missing": missing,
        "source_validated_at": now_iso(),
    }


def no_match(
    *,
    searched: dict[str, Any],
    gazette_checked: bool,
    source_url: str,
    dataset_modified: str | None,
    language: str,
) -> dict[str, Any]:
    lang = normalize_language(language)
    return {
        "status": "no_match",
        "searched": searched,
        "gazette_checked": gazette_checked,
        "source_url": source_url,
        "dataset_modified": dataset_modified,
        "answer": _no_match_message(searched, dataset_modified, lang),
        "source_validated_at": now_iso(),
    }


def out_of_scope(
    *,
    reason: str,
    covered: str,
    cantonal_excerpt_url: str | None = None,
    language: str,
) -> dict[str, Any]:
    if reason not in _VALID_OUT_OF_SCOPE_REASONS:
        raise ValueError(f"unknown out_of_scope reason: {reason!r}")
    normalize_language(language)  # accepted for interface symmetry; `covered` is already localised
    envelope: dict[str, Any] = {
        "status": "out_of_scope",
        "reason": reason,
        "covered": covered,
        "source_validated_at": now_iso(),
    }
    if cantonal_excerpt_url is not None:
        envelope["cantonal_excerpt_url"] = cantonal_excerpt_url
    return envelope


def source_unavailable(
    *,
    source: str,
    error_class: str,
    retry_after_s: float | None,
    language: str,
) -> dict[str, Any]:
    if source not in _VALID_SOURCES:
        raise ValueError(f"unknown source: {source!r}")
    lang = normalize_language(language)
    return {
        "status": "source_unavailable",
        "source": source,
        "error_class": error_class,
        "retry_after_s": retry_after_s,
        "answer": SOURCE_UNAVAILABLE_SENTENCES[source][lang],
        "source_validated_at": now_iso(),
    }
