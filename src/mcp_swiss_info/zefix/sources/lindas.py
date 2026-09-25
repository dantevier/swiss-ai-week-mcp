"""LINDAS backend (primary source) for the Zefix commercial-register graph.

Class wrapper: `LindasClient` holds endpoint/timeout/cache TTL; its methods
keep the original module-function names, bodies and signatures.

docs/prd-zefix-company-info.md §6.2. SPARQL 1.1 over HTTP: POST form-encoded
`query` to `LindasClient.endpoint` (default `https://lindas.admin.ch/query`),
`Accept: application/sparql-results+json`. Graph
`<https://lindas.admin.ch/foj/zefix>` (27.3M triples, ~794k organisations).

Predicates verified live 2026-09-24 against
`https://register.ld.admin.ch/zefix/company/415941` (Swisscom (Schweiz) AG,
UID CHE101654423), every shape below timed with `curl` against the
production endpoint before being used here:

- Identifiers: ``?company schema:identifier ?idRes`` where ``?idRes`` carries
  ``schema:name``/``schema:value``. The `schema:name` values actually used by
  the dataset are **"CompanyUID"**, **"CompanyCHID"**, **"CompanyEHRAID"**
  (not the bare "CHID"/"EHRAID" sketched in the module interface doc -
  confirmed by dumping every `schema:identifier` triple for EHRAID 415941:
  the three identifier resource IRIs end in `/UID/CHE101654423`,
  `/CHID/CH03530169309`, `/EHRAID`, with `schema:name` literals exactly
  `CompanyUID`, `CompanyCHID`, `CompanyEHRAID`). This module queries the
  identifier predicate generically (`?idRes schema:name ?idType ;
  schema:value ?idValue`) and classifies rows client-side by substring match
  ("EHRAID"/"CHID"/"UID"), so it is agnostic to which of the two naming
  conventions a given deployment/fixture uses.
- Names: `schema:name` is lang-tagged (observed: fr/it/en for this company,
  no `de` tag - the German display name is only `schema:legalName`, so
  `Company.names` may legitimately omit "de"). `schema:legalName` is a plain
  (untagged) literal.
- Legal form: `?company schema:additionalType ?lf` where `?lf` is an IRI
  under `https://ld.admin.ch/ech/97/legalforms/{code}`; the code is derived
  in-query with `BIND(REPLACE(STR(?lf), "^.*/", "") AS ?lfCode)` (verified
  live: yields "0106"). The label resource lives OUTSIDE the zefix graph
  (default graph): `?lf schema:name ?label` there returns lang-tagged labels
  (observed de/fr for code 0106, "Aktiengesellschaft" / "Société anonyme").
  Querying `?lf schema:name ?label` *inside* `GRAPH <...zefix>` returns zero
  rows.
- Municipality: `?company <https://schema.ld.admin.ch/municipality> ?m`
  inside the graph; `?m` (e.g. `https://ld.admin.ch/municipality/362`) is
  also OUTSIDE the graph, where `?m schema:name ?seat` (plain literal,
  "Ittigen") and `?m schema:identifier ?bfs` (typed xsd:integer literal,
  "362") resolve.
- Address: `?company schema:address ?a` inside the graph; `?a` carries
  `schema:streetAddress`, `schema:postalCode`, `schema:addressLocality`,
  `schema:addressRegion` (2-letter canton code, e.g. "BE") as plain literals
  on the SAME node, all inside the graph (unlike municipality/legal form).
- Purpose: `schema:description`, plain literal, inside the graph.
- Dataset freshness: the dataset node
  `https://register.ld.admin.ch/.well-known/dataset/foj-zefix` carries
  `schema:dateModified` (xsd:date) INSIDE the graph. Live value on
  2026-09-24 was "2026-09-23", matching the PRD.

Query-shape gotcha found while probing (load-bearing for correctness, not
just style): binding two OUT-OF-GRAPH lookups (legal-form label, municipality
name/bfs) as two independent *sibling* top-level `OPTIONAL` blocks makes this
endpoint's query planner blow up - a query that returns in <0.2s with either
lookup alone took >15s and produced hundreds of MB before being cut off with
both siblings present. Nesting them inside one outer `OPTIONAL` block
(`OPTIONAL { OPTIONAL {...lf...} OPTIONAL {...m...} }`) is semantically
equivalent (each independently optional) and measured at ~0.1-0.2s. Every
detail query in this module uses that nested shape.

`STRSTARTS`/`CONTAINS` name search has no supporting index: a query that
matches nothing must scan every `schema:name`/`schema:legalName` triple
before returning zero rows. Measured live: prefix search for "swisscom"
(positive, LIMIT cuts the scan short) 2.2-2.7s; prefix search for
"zzzzqqqq" (true negative, full scan) 17.7-21s - past `lindas_timeout_s`
(10s) on its own.

Follow-up investigation (2026-09-24) into whether that negative-scan cost is
an artefact of this module's query shape, isolating each factor with `curl`,
2 runs each, "zzzzqqqq" (negative) / "swisscom" (positive):

| Query (GRAPH-scoped, no detail projection, no out-of-graph joins) | negative | positive |
|---|---|---|
| `schema:name` UNION `schema:legalName`, STRSTARTS | 18.5s, 17.7s | 2.25s, 2.22s |
| `schema:name` only, STRSTARTS | 15.5s, 15.6s | - |
| `schema:legalName` only, STRSTARTS | 5.5s, 6.4s | 1.28s, 1.21s |
| `schema:legalName` only, CONTAINS | 6.3s, 6.3s | 1.23s, 1.21s |
| `schema:name` only, CONTAINS | 15.2s, 12.7s | - |

The cost is entirely the `schema:name` scan (lang-tagged, ~4 literals/company
vs. 1 untagged `schema:legalName` literal/company) - not this module's
detail projection, its nested-OPTIONAL joins, or STRSTARTS vs. CONTAINS.
Dropping `schema:name` from the match set would get the negative case under
~8s, but `schema:name` carries trade names in fr/it/en that never appear in
`schema:legalName` (e.g. "Swisscom (Suisse) SA" only exists as a `schema:name`
literal); removing it would silently drop real matches for non-German
queries, so it stays. No restructuring of `search_by_name` (candidate query
shape, projection, join order) gets a correctness-preserving negative search
under ~8s - the endpoint's `schema:name` literal scan is the floor.

Given that, a negative `search_by_name` call is expected to consume most or
all of its `lindas_timeout_s` budget and often gets cut off by the httpx
timeout before the CONTAINS retry can even start. That timeout is reported
distinctly from other LINDAS failures: `SourceUnavailable("lindas",
"timeout_scan", ...)` rather than the generic `"timeout"` `find_by_uid` and
`dataset_modified` use, so the tool layer can phrase it as "the index could
not complete a name scan in time; provide the UID" instead of a bare
`source_unavailable`.

`search_by_name` embeds the full detail projection directly in the
STRSTARTS/CONTAINS query (candidate selection as an inner `SELECT DISTINCT
?company ... LIMIT n` subquery, joined back to the same detail OPTIONAL
block used by `find_by_uid`), so one upstream call is enough for a
successful prefix search - no separate per-candidate detail round trip.
Verified live: 10-candidate "swisscom" prefix search, 2.3-2.45s.

Licence: `dcterms:rights` -> Provide-the-Source ("open use, must provide the
source").
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

import httpx

from ...config.settings import settings
from .http import SourceUnavailable, classify_error, make_client

GRAPH = "https://lindas.admin.ch/foj/zefix"
_UID_RE = re.compile(r"^CHE\d{9}$")

_SELECT_CLAUSE = (
    "?company ?name ?legalName ?idType ?idValue ?lfCode ?lfLabel "
    "?seat ?bfs ?street ?zip ?city ?canton ?purpose"
)

# Shared OPTIONAL blocks used by every detail-bearing query (find_by_uid and
# search_by_name). Multiple lang-tagged names/legal-form-labels and multiple
# identifiers each produce one row per value; callers aggregate client-side.
_DETAIL_PATTERN = (
    "    OPTIONAL { ?company schema:name ?name }\n"
    "    OPTIONAL { ?company schema:legalName ?legalName }\n"
    "    OPTIONAL { ?company schema:identifier ?idRes . ?idRes schema:name ?idType ; schema:value ?idValue }\n"
    '    OPTIONAL { ?company schema:additionalType ?lf . BIND(REPLACE(STR(?lf), "^.*/", "") AS ?lfCode) }\n'
    "    OPTIONAL { ?company schema:address ?a . ?a schema:streetAddress ?street ; schema:postalCode ?zip ; "
    "schema:addressLocality ?city ; schema:addressRegion ?canton }\n"
    "    OPTIONAL { ?company schema:description ?purpose }\n"
    "    OPTIONAL { ?company <https://schema.ld.admin.ch/municipality> ?m }\n"
)

# ?lf and ?m are bound inside the GRAPH block above (or left unbound); this
# nested-OPTIONAL join to the out-of-graph label/municipality resources is
# the shape that avoids the query-planner blowup described above.
_OUTSIDE_OPTIONAL = (
    "  OPTIONAL {\n"
    "    OPTIONAL { ?lf schema:name ?lfLabel }\n"
    "    OPTIONAL { ?m schema:name ?seat ; schema:identifier ?bfs }\n"
    "  }\n"
)


def escape_literal(s: str) -> str:
    """Escape a string for safe interpolation into a SPARQL string literal.

    Escapes backslash, double quote, newline, carriage return, tab. Callers
    must always pass caller-controlled text through this before it is placed
    inside a `"..."` literal in a query template.
    """
    return (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _find_by_uid_query(uid: str) -> str:
    return (
        "PREFIX schema: <http://schema.org/>\n"
        f"SELECT {_SELECT_CLAUSE} WHERE {{\n"
        f"  GRAPH <{GRAPH}> {{\n"
        "    ?company schema:identifier ?uidRes .\n"
        f'    ?uidRes schema:name "CompanyUID" ; schema:value "{uid}" .\n'
        f"{_DETAIL_PATTERN}"
        "  }\n"
        f"{_OUTSIDE_OPTIONAL}"
        "}\n"
    )


def _canton_clause(canton: str | None) -> str:
    if not canton:
        return ""
    return f'        ?company schema:address ?ca . ?ca schema:addressRegion "{canton}" .\n'


def _wrap_candidate_subquery(candidate_where: str, canton: str | None, limit: int) -> str:
    """Wrap a candidate WHERE-clause body (already GRAPH-scoped) as the inner
    `SELECT DISTINCT ?company ... LIMIT n` subquery, joined to the shared
    detail OPTIONAL block - the shape used by every search stage below.
    """
    return (
        "PREFIX schema: <http://schema.org/>\n"
        f"SELECT {_SELECT_CLAUSE} WHERE {{\n"
        "  {\n"
        "    SELECT DISTINCT ?company WHERE {\n"
        f"      GRAPH <{GRAPH}> {{\n"
        f"{candidate_where}"
        f"{_canton_clause(canton)}"
        "      }\n"
        f"    }} LIMIT {int(limit)}\n"
        "  }\n"
        f"  GRAPH <{GRAPH}> {{\n"
        f"{_DETAIL_PATTERN}"
        "  }\n"
        f"{_OUTSIDE_OPTIONAL}"
        "}\n"
    )


def _search_exact_query(literal_name: str, canton: str | None, limit: int) -> str:
    """Stage 0: exact literal match via VALUES - an indexed lookup, not a
    scan, so it stays fast even on a miss (see module docstring, "Stage 0").
    `literal_name` is the trimmed/whitespace-collapsed name as given (case
    preserved), already escaped with escape_literal().
    """
    lang_values = " ".join(f'"{literal_name}"@{lang}' for lang in ("de", "fr", "it", "en"))
    candidate_where = (
        f'        {{ ?company schema:legalName ?n . VALUES ?n {{ "{literal_name}" }} }}\n'
        "        UNION\n"
        f'        {{ ?company schema:name ?n . VALUES ?n {{ {lang_values} "{literal_name}" }} }}\n'
    )
    return _wrap_candidate_subquery(candidate_where, canton, limit)


def _search_prefix_query(needle: str, match_fn: str, predicate: str, canton: str | None, limit: int) -> str:
    """Stages 1-3: single-predicate STRSTARTS/CONTAINS(LCASE) scan.

    `predicate` is "schema:legalName" or "schema:name"; `needle` is already
    lower-cased and escaped. One predicate per query (not a UNION of both) -
    see module docstring, "Stage 1-3": splitting them out lets a cheap
    legalName scan resolve most lookups before ever touching the far more
    expensive lang-tagged schema:name literal set.
    """
    candidate_where = f'        ?company {predicate} ?n . FILTER({match_fn}(LCASE(STR(?n)), "{needle}"))\n'
    return _wrap_candidate_subquery(candidate_where, canton, limit)


def _dataset_modified_query() -> str:
    return (
        "PREFIX schema: <http://schema.org/>\n"
        "SELECT ?d WHERE {\n"
        f"  GRAPH <{GRAPH}> {{\n"
        "    ?ds schema:dateModified ?d .\n"
        "  }\n"
        "} LIMIT 1\n"
    )


@dataclass
class Company:
    ehraid: int
    uid: str  # 9 digits with prefix, unformatted: "CHE101654423"
    chid: str | None
    names: dict[str, str] = field(default_factory=dict)  # lang -> name, keys among de/fr/it/en
    legal_name: str = ""
    legal_form_code: str = ""  # e.g. "0106"
    legal_form_labels: dict[str, str] = field(default_factory=dict)  # lang -> label
    seat: str = ""  # municipality name
    seat_bfs_id: int | None = None
    canton: str | None = None  # 2-letter code from address region, may be None
    address: dict[str, str | None] = field(default_factory=lambda: {"street": None, "zip": None, "city": None})
    purpose: str | None = None
    source_url: str = ""  # https://register.ld.admin.ch/zefix/company/{ehraid}


# --- result aggregation ---------------------------------------------------


def _binding_value(binding: dict, key: str) -> str | None:
    cell = binding.get(key)
    return cell["value"] if cell else None


def _binding_lang(binding: dict, key: str) -> str | None:
    cell = binding.get(key)
    return cell.get("xml:lang") if cell else None


def _ehraid_from_uri(company_uri: str) -> int:
    return int(company_uri.rstrip("/").rsplit("/", 1)[-1])


def _aggregate_company(company_uri: str, rows: list[dict], known_uid: str | None = None) -> Company:
    """Fold multiple result rows (one per lang-tagged name/legal-form-label/
    identifier combination) for a single company into one Company.

    `known_uid` short-circuits UID extraction when the caller already knows
    it (find_by_uid); search_by_name leaves it None and it is recovered from
    the generic identifier rows instead.
    """
    names: dict[str, str] = {}
    legal_name = ""
    chid: str | None = None
    ehraid_str: str | None = None
    uid = known_uid
    legal_form_code = ""
    legal_form_labels: dict[str, str] = {}
    seat = ""
    seat_bfs_id: int | None = None
    canton: str | None = None
    street: str | None = None
    zip_: str | None = None
    city: str | None = None
    purpose: str | None = None

    for row in rows:
        name_val = _binding_value(row, "name")
        name_lang = _binding_lang(row, "name")
        if name_val and name_lang:
            names[name_lang] = name_val
        legal_name = legal_name or _binding_value(row, "legalName") or ""

        id_type = _binding_value(row, "idType")
        id_value = _binding_value(row, "idValue")
        if id_type and id_value:
            if "EHRAID" in id_type:
                ehraid_str = ehraid_str or id_value
            elif "CHID" in id_type:
                chid = chid or id_value
            elif "UID" in id_type:
                uid = uid or id_value

        legal_form_code = legal_form_code or _binding_value(row, "lfCode") or ""
        lf_label = _binding_value(row, "lfLabel")
        lf_lang = _binding_lang(row, "lfLabel")
        if lf_label and lf_lang:
            legal_form_labels[lf_lang] = lf_label

        seat = seat or _binding_value(row, "seat") or ""
        bfs = _binding_value(row, "bfs")
        if bfs and seat_bfs_id is None:
            try:
                seat_bfs_id = int(float(bfs))
            except ValueError:
                seat_bfs_id = None

        street = street or _binding_value(row, "street")
        zip_ = zip_ or _binding_value(row, "zip")
        city = city or _binding_value(row, "city")
        canton = canton or _binding_value(row, "canton")
        purpose = purpose or _binding_value(row, "purpose")

    ehraid = int(ehraid_str) if ehraid_str else _ehraid_from_uri(company_uri)

    return Company(
        ehraid=ehraid,
        uid=uid or "",
        chid=chid,
        names=names,
        legal_name=legal_name,
        legal_form_code=legal_form_code,
        legal_form_labels=legal_form_labels,
        seat=seat,
        seat_bfs_id=seat_bfs_id,
        canton=canton,
        address={"street": street, "zip": zip_, "city": city},
        purpose=purpose,
        source_url=f"https://register.ld.admin.ch/zefix/company/{ehraid}",
    )


def _companies_from_bindings(bindings: list[dict]) -> list[Company]:
    """Group flat result rows by company (preserving first-seen order) and
    fold each group into a Company via `_aggregate_company`."""
    order: list[str] = []
    grouped: dict[str, list[dict]] = {}
    for row in bindings:
        uri = row["company"]["value"]
        if uri not in grouped:
            grouped[uri] = []
            order.append(uri)
        grouped[uri].append(row)
    return [_aggregate_company(uri, grouped[uri]) for uri in order]


# Stages 2 and 3 scan the far more expensive schema:name / CONTAINS surface
# (module docstring, "Follow-up investigation": 12.7-18.5s for a true
# negative); only attempt them when there is plausibly enough budget left
# for one such scan to complete rather than burn the remainder on a doomed
# call.
_MIN_STAGE_BUDGET_S = 3.0


# Keyed by endpoint so two clients with different endpoints never share an entry.
_dataset_modified_cache: dict[str, tuple[str, float]] = {}


# --- client ----------------------------------------------------------------


class LindasClient:
    """LINDAS SPARQL client. Config is fixed at construction; each argument
    defaults to the matching `settings` field read when the client is built."""

    def __init__(
        self,
        endpoint: str | None = None,
        timeout_s: float | None = None,
        cache_ttl_s: float | None = None,
    ) -> None:
        self.endpoint = settings.lindas_endpoint if endpoint is None else endpoint
        self.timeout_s = settings.lindas_timeout_s if timeout_s is None else timeout_s
        self.cache_ttl_s = settings.reference_cache_ttl_s if cache_ttl_s is None else cache_ttl_s

    async def _run_query(self, query: str, timeout: float) -> dict:
        """POST a SPARQL query to the LINDAS endpoint and return the parsed JSON.

        Any httpx failure (timeout, network, non-2xx, egress denial) is mapped to
        SourceUnavailable("lindas", ...). `timeout` must be > 0; callers clamp the
        remaining call/query budget before calling this.
        """
        timeout = max(timeout, 0.1)
        try:
            async with make_client(timeout, accept="application/sparql-results+json") as client:
                resp = await client.post(self.endpoint, data={"query": query})
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as exc:
            error_class, retry_after_s = classify_error(exc)
            raise SourceUnavailable("lindas", error_class, retry_after_s=retry_after_s) from exc
        except SourceUnavailable:
            raise
        except Exception as exc:  # pragma: no cover - defensive (e.g. bad JSON body)
            error_class, retry_after_s = classify_error(exc)
            raise SourceUnavailable("lindas", error_class, retry_after_s=retry_after_s) from exc


    async def _run_search_query(self, query: str, timeout: float) -> dict:
        """Like `_run_query`, but for the name-search path specifically.

        A plain "timeout" here almost always means the endpoint's unindexed
        `schema:name` literal scan (see module docstring - measured 12.7-18.5s
        for a true negative) didn't finish in the budget, not a generic upstream
        hiccup. Re-raised as `error_class="timeout_scan"` so callers/the tool
        layer can tell "the name index scan ran out of time" apart from other
        `source_unavailable` causes and suggest the UID path instead of just
        retrying.
        """
        try:
            return await self._run_query(query, timeout)
        except SourceUnavailable as exc:
            if exc.error_class == "timeout":
                raise SourceUnavailable("lindas", "timeout_scan", retry_after_s=exc.retry_after_s) from exc
            raise


    async def find_by_uid(self, uid: str, *, budget_s: float) -> Company | None:
        """Look up one company by unformatted UID ("CHE123456789").

        One SPARQL query (exact triple pattern on CompanyUID plus OPTIONAL blocks
        for everything else, per the module interface); result rows are
        aggregated into a single Company. Returns None on zero hits or on a
        malformed uid (defensive - callers are expected to normalise first).
        Raises SourceUnavailable("lindas", ...) on any transport/HTTP failure.
        """
        if not _UID_RE.match(uid):
            return None

        query = _find_by_uid_query(escape_literal(uid))
        timeout = min(budget_s, self.timeout_s)
        data = await self._run_query(query, timeout)
        bindings = data.get("results", {}).get("bindings", [])
        if not bindings:
            return None
        company_uri = bindings[0]["company"]["value"]
        return _aggregate_company(company_uri, bindings, known_uid=uid)

    async def search_by_name(
        self, name: str, *, canton: str | None = None, limit: int = 10, budget_s: float
    ) -> list[Company]:
        """Search companies by name, staged from cheapest/most-selective to most
        expensive, stopping at the first stage with hits, sharing `budget_s`
        (computed with time.monotonic(), each stage bounded by what remains):

        - Stage 0: exact literal match via `VALUES` on `schema:legalName` and
          lang-tagged/plain `schema:name` (name trimmed, internal whitespace
          collapsed, case preserved - no LCASE, no FILTER). This is an indexed
          lookup on this endpoint, not a scan: fast even on a miss (measured
          live 0.1-0.25s for "Swisscom (Schweiz) AG", "UBS AG", "Nestlé S.A."
          and a miss - see module docstring, "Stage 0"). Added because a
          STRSTARTS/CONTAINS scan for a name with very few matches (e.g. a full
          legal name, exactly one hit) cannot stop early at LIMIT and ends up
          scanning as much of the corpus as a true miss (measured 10s+, vs.
          "swisscom"'s 2.5s where 10 matches are found quickly).
        - Stage 1: `schema:legalName` STRSTARTS(LCASE) LIMIT `limit` (measured
          ~1.2s on a hit, ~6s on a miss - legalName is untagged, one
          literal/company, cheap to scan).
        - Stage 2: `schema:name` STRSTARTS(LCASE) LIMIT `limit`, only attempted
          if the remaining budget exceeds `_MIN_STAGE_BUDGET_S` (this predicate
          is lang-tagged, ~4 literals/company, and its scan is the expensive one
          - 12.7-18.5s for a true miss).
        - Stage 3: `schema:legalName` CONTAINS(LCASE), only attempted if the
          remaining budget exceeds `_MIN_STAGE_BUDGET_S`.

        At most 4 upstream SPARQL queries total (one per stage, stopping at the
        first hit). Each is a single query: candidate selection as an inner
        `SELECT DISTINCT ?company ... LIMIT n` subquery joined to the shared
        detail OPTIONAL block, so a hit at any stage resolves to full Company
        rows without a separate detail round trip. Results are DISTINCT by
        company, in the order the candidate subquery returned them.

        A timeout at stage 1, 2 or 3 (the unindexed literal scans) is raised as
        `SourceUnavailable("lindas", "timeout_scan", ...)`, not the generic
        `"timeout"` `find_by_uid` uses, so callers can distinguish "the name
        index scan ran out of time" from other source failures. Stage 0's exact
        `VALUES` lookup is indexed, not a scan, so a timeout there keeps the
        plain `"timeout"` class - it would mean a generic LINDAS problem, not an
        exhausted scan.
        """
        original = " ".join(name.split())  # trim + collapse internal whitespace, case preserved
        if not original:
            return []
        exact_literal = escape_literal(original)
        needle = escape_literal(original.lower())
        canton_norm = escape_literal(canton.strip().upper()) if canton else None

        start = time.monotonic()
        budget = min(budget_s, self.timeout_s)

        def remaining() -> float:
            return budget - (time.monotonic() - start)

        async def _attempt(query: str, timeout: float, *, reclassify_timeout: bool) -> list[Company]:
            runner = self._run_search_query if reclassify_timeout else self._run_query
            data = await runner(query, timeout)
            return _companies_from_bindings(data.get("results", {}).get("bindings", []))

        # Stage 0: exact literal match - an indexed lookup, not a scan (module
        # docstring, "Stage 0"), so a timeout here is a generic LINDAS problem,
        # not "the scan ran out of time": keep the plain "timeout" error_class.
        r = remaining()
        if r <= 0:
            return []
        hits = await _attempt(_search_exact_query(exact_literal, canton_norm, limit), r, reclassify_timeout=False)
        if hits:
            return hits

        # Stages 1-3 are unindexed literal scans; their timeouts are reclassified
        # as "timeout_scan" (see _run_search_query).

        # Stage 1: legalName STRSTARTS.
        r = remaining()
        if r <= 0:
            return []
        hits = await _attempt(
            _search_prefix_query(needle, "STRSTARTS", "schema:legalName", canton_norm, limit), r, reclassify_timeout=True
        )
        if hits:
            return hits

        # Stage 2: schema:name STRSTARTS - only if there's plausibly enough budget.
        r = remaining()
        if r > _MIN_STAGE_BUDGET_S:
            hits = await _attempt(
                _search_prefix_query(needle, "STRSTARTS", "schema:name", canton_norm, limit), r, reclassify_timeout=True
            )
            if hits:
                return hits

        # Stage 3: legalName CONTAINS - only if there's plausibly enough budget.
        r = remaining()
        if r > _MIN_STAGE_BUDGET_S:
            hits = await _attempt(
                _search_prefix_query(needle, "CONTAINS", "schema:legalName", canton_norm, limit), r, reclassify_timeout=True
            )
            if hits:
                return hits

        return []

    async def dataset_modified(self) -> str | None:
        """Return the LINDAS zefix graph's `schema:dateModified` as "YYYY-MM-DD".

        Cached in-process for `self.cache_ttl_s`. On any failure
        (network, HTTP, missing binding) returns None rather than raising -
        freshness metadata is never worth failing a call over.
        """
        now = time.monotonic()
        cached = _dataset_modified_cache.get(self.endpoint)
        if cached is not None and (now - cached[1]) < self.cache_ttl_s:
            return cached[0]

        try:
            data = await self._run_query(_dataset_modified_query(), self.timeout_s)
            bindings = data.get("results", {}).get("bindings", [])
            if not bindings:
                return None
            value = bindings[0]["d"]["value"]
        except Exception:
            return None

        _dataset_modified_cache[self.endpoint] = (value, now)
        return value
