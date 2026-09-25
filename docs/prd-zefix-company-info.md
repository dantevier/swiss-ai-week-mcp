# PRD: `company_info` — Swiss commercial register grounding tool

Status: implemented on `victor-dev` (62 offline tests, 3 live tests). Owner: Victor Bonilla. Target: Swisscom "Swiss Grounding MCP" challenge submission, Fri 2026-09-25 12:00.

## 1. Summary

Add one MCP tool, `company_info`, that answers questions about a Swiss company (existence, legal form, seat, address, purpose, status, recent register publications) grounded in the federal Zefix index and the Swiss Official Gazette of Commerce (SHAB). It is a live proxy: every call hits upstream sources, nothing is persisted. The primary Zefix source is the Federal Office of Justice's linked-data publication on LINDAS (official, keyless, licence "open use, provide the source"). The keyless Zefix web endpoint enriches the record with status, SHAB date, and the cantonal-excerpt link when policy allows. The gazette client is vendored from `malkreide/register-mcp` (MIT) and re-exposed through this repo's FastMCP server behind the challenge's five-state response envelope.

Decisions:

| Code | Decision |
|---|---|
| D1 | Scope is company lookup plus the UID-joined gazette publications. No analytics over the register. |
| D2 | Zefix backend: LINDAS SPARQL is primary and always used. `ZefixREST/api/v1` is an optional enrichment, off by default, gated by the compliance switch, failure-tolerant. |
| D3 | When a primary source is unreachable the tool returns `source_unavailable`. No cache, no stale answers. |
| D4 | One tool, `company_info`. No separate search/detail/publications tools. |
| D5 | Reuse mode is vendoring the client layer of `register-mcp` (HTTP plumbing, gazette client, Zefix enrichment calls, fixtures, tests), not the server, not a sidecar, not a package dependency. |

## 2. Why this scope and this backend

- The challenge scores correctness and honesty first, breadth second, efficiency third. One well-grounded tool beats nine thin proxies. `BaseKnowledge/CHALLENGE.md` §5.1.
- Topic 14 "Companies, commercial register, VAT" is a listed federal topic with `zefix.ch` as the source. `BaseKnowledge/CHALLENGE.md` L236.
- Analytics ("how many AGs were founded in Zurich in 2025") needs the whole register locally and an ingest design. Out of scope for a submission due in under 24 hours.
- The UID join between Zefix and the gazette exists and works live in `register-mcp`, so joins cost nothing extra and need no store.
- LINDAS is primary because it is the only Zefix channel that is simultaneously official, documented, keyless, and licensed for machine use. The web endpoint is undocumented and the documented REST API needs credentials with unknown turnaround. Grounding the default answer in an official channel is worth ~1.5 h of extra build.

## 3. Goals and non-goals

Goals:

- G1 Answer "does company X exist / where is it / what legal form / is it active" with a citation, an authority, and an effective date.
- G2 Ask back for exactly one thing when the name is ambiguous and nothing in the question disambiguates.
- G3 Return the last N gazette publications for the resolved company, each with date, registry office, and mutation type.
- G4 Work in DE, FR, IT. Romansh questions are answered with German-labelled data and a note.
- G5 Zero credentials, zero persisted data, runs from the repo with `uv run`.
- G6 Configurable robots.txt/ToS compliance switch, honoured at request time, compliant by default as the challenge requires.

Non-goals:

- N1 Aggregations, statistics, lists of companies by criteria beyond disambiguation.
- N2 Natural-person data (board members, signatories, auditors). Neither LINDAS nor the Zefix record has structured person fields; names exist only inside free-text gazette messages, which the tool never returns. See §6.6.
- N3 Free-text gazette search (by keyword, person, or rubric across all companies). Data-protection risk; `register-mcp` deliberately excludes it and so do we.
- N4 VAT register status. Zefix does not carry it.
- N5 Cantonal register extracts (full text). We link to them, we do not fetch them.
- N6 Persistent cache, SQLite, pre-built index. D3.

## 4. Jury scenario

Unknown MCP client × unknown LLM, questions in four languages. Representative questions:

| Q | Question | Expected state |
|---|---|---|
| Q1 | "Ist die Swisscom (Schweiz) AG im Handelsregister eingetragen und wo hat sie ihren Sitz?" | `answered` |
| Q2 | "Quelle est la forme juridique de Nestlé ?" | `need_info` (several "Nestlé" entities) |
| Q3 | "L'azienda con UID CHE-101.654.423 è ancora attiva?" | `answered` |
| Q4 | "Wann wurde die Firma Muster GmbH in Bern zuletzt im SHAB publiziert?" | `answered` with publications, or `no_match` |
| Q5 | "Wer sitzt im Verwaltungsrat der UBS AG?" | `out_of_scope(persons)` with the cantonal excerpt URL |
| Q6 | "Ist die Firma XY in Deutschland eingetragen?" | `out_of_scope(jurisdiction)` |
| Q7 | Any of the above while lindas.admin.ch is down | `source_unavailable` |
| Q8 | "Wie viele AGs gibt es im Kanton Zug?" | `out_of_scope(analytics)` |

## 5. Tool contract

### 5.1 Signature

```python
@mcp.tool
async def company_info(
    question: str | None = None,          # the user's question verbatim, lets the tool self-detect wrong-topic calls
    name: str | None = None,              # company name or prefix
    uid: str | None = None,               # CHE-xxx.xxx.xxx, dots/hyphen optional
    canton: str | None = None,            # two-letter code, narrows disambiguation
    language: str = "de",                 # de | fr | it | en; rm maps to de
    include_publications: bool = True,    # attach gazette publications for the resolved company
    max_publications: int = 5,            # 1..20
) -> dict
```

No lookup parameter is mandatory. If both `name` and `uid` are missing the tool returns `need_info` asking for the company name. A mandatory field would push the failure into the client's schema validation where the LLM cannot see it. `BaseKnowledge/CONTRACT.md` §4.4.

### 5.2 Resolution algorithm

0. Gates, evaluated on `question` plus parameters, before any network call:
   - persons: the question contains a person-role term (`Verwaltungsrat`, `Geschäftsführer`, `Zeichnungsberechtigt`, `Revisionsstelle`, `Inhaber`, `conseil d'administration`, `administrateur`, `gérant`, `signature`, `organe de révision`, `consiglio di amministrazione`, `amministratore`, `gerente`, `firma sociale`, `ufficio di revisione`, `board`, `director`, `signatory`, `auditor`) → resolve the company if `name`/`uid` is given (steps 1–4, so the excerpt link can be returned), then `out_of_scope(persons)`. Never attach publications.
   - jurisdiction: `uid` is present and does not start with `CHE`, or the question names a non-Swiss country or a foreign register identifier (`HRB`, `SIREN`, `SIRET`, `REA`, `Companies House`, `Handelsregister B`) without a Swiss anchor (canton, Swiss town, `CHE`) → `out_of_scope(jurisdiction)`. The country list is the ISO country names in de/fr/it/en minus Switzerland; a Swiss town anchor is checked against the cached municipality names.
   - analytics: the question asks for a count or a list over a criterion (`wie viele`, `combien`, `quante`, `how many`, `alle Firmen`, `toutes les sociétés`, `tutte le aziende`, `list all`) → `out_of_scope(analytics)`.
   - topic: §5.4.
1. Normalise `uid` to `CHE` + 9 digits.
2. Primary lookup on LINDAS:
   - `uid` given → exact triple-pattern query (80 ms measured). One hit → step 4. Zero → step 3b.
   - else `name`, staged, stopping at the first stage with hits, all stages sharing one 15 s LINDAS budget, optional canton filter on address region:
     - stage 0: exact literal match of the name as given (whitespace collapsed, case preserved) against `schema:legalName` and `schema:name` in de/fr/it/en via `VALUES`. Index lookup, 0.1–0.3 s measured, hit or miss. Catches full registered names such as "Swisscom (Schweiz) AG" or "UBS AG".
     - stage 1: `STRSTARTS(LCASE(schema:legalName), prefix)`, `LIMIT 10`. 1.2–2 s on a hit, about 6 s on a miss.
     - stage 2: same over `schema:name` (fr/it/en trade names), only if more than 3 s of budget remain. Up to 15 s on a miss.
     - stage 3: `CONTAINS` over `schema:legalName`, same gate.
     - all stages empty → `no_match`; a stage 1–3 timeout → `source_unavailable` with `error_class: "timeout_scan"`.
3. Disambiguate:
   - one hit → step 4
   - several hits, exactly one whose `legalName` equals the input case-insensitively → step 4 with `assumptions: ["selected the exact-name match among N prefix matches"]`
   - otherwise → `need_info` listing up to 5 candidates (name, legal form, seat, UID) and asking for one of: UID, canton, or seat. One question only.
   - (3b) UID given, zero LINDAS hits → always query the gazette for that UID, regardless of `include_publications` (that flag only controls whether the list is attached). Publications whose sub-rubric is a deletion code → `answered` with `status: "DELETED"`, `derived: true`, rule "absent from the active-entity index and a deletion publication exists", `effective_from` = that publication's date. Publications without a deletion code, or none → `no_match` with `gazette_checked: true`. Gazette unreachable → `source_unavailable(source: "gazette")`, because in this branch the gazette is the only source that can settle the question.
4. Enrichment, run when `RESPECT_ROBOTS_TXT=false`, or when `ZEFIX_USERNAME`/`ZEFIX_PASSWORD` are set (the documented API is credentialed and not a crawl target, so it runs under either setting): `GET {ZEFIX_BASE_URL}/firm/{ehraid}.json`. Adds `status`, `shabDate`, `deleteDate`, `cantonalExcerptWeb`, `oldNames`. Any failure or a 5 s timeout leaves the fields null and sets `enrichment_status: "skipped" | "source_unavailable" | "policy_robots"`. Enrichment never changes the state.
5. Gazette: `GET publications?uids=CHE-xxx.xxx.xxx&rubrics=HR`, `PUBLISHED`, newest first, cap `max_publications`. Only the commercial-register rubric `HR` is requested; other rubrics (building permits, debt enforcement) also cite company UIDs but are not register entries. Failure sets `publications_status: "source_unavailable"`, answer still returned.
6. Build the envelope.

Total budget per call: 25 s wall clock. LINDAS phase 15 s across all stages, enrichment 5 s, gazette the remainder (minimum 5 s). Each phase's deadline is the minimum of its own cap and the remaining call budget. A query with few matches cannot stop at `LIMIT`, so LINDAS scans every name literal, measured 15–21 s for the multilingual `schema:name` set; that is why stage 0 exists and why a true miss ends as `timeout_scan` with the sentence "provide the UID or the exact registered name and canton".

### 5.3 Envelope

Fields follow `BaseKnowledge/CONTRACT.md` §5. Example `answered`, with enrichment on (`RESPECT_ROBOTS_TXT=false`):

```json
{
  "status": "answered",
  "answer": "Swisscom (Schweiz) AG ist eine aktive Aktiengesellschaft mit Sitz in Ittigen (BE).",
  "company": {
    "name": "Swisscom (Schweiz) AG",
    "names": {"de": "Swisscom (Schweiz) AG", "fr": "Swisscom (Suisse) SA", "it": "Swisscom (Svizzera) SA", "en": "Swisscom (Switzerland) Ltd"},
    "uid": "CHE-101.654.423",
    "chid": "CH-035.3.016.930-9",
    "ehraid": 415941,
    "legal_form": "Aktiengesellschaft",
    "legal_form_code": "0106",
    "seat": "Ittigen",
    "seat_bfs_id": 362,
    "canton": "BE",
    "address": {"street": "Alte Tiefenaustrasse 6", "zip": "3050", "city": "Bern"},
    "purpose": "...",
    "status": "ACTIVE",
    "deleted_on": null,
    "old_names": []
  },
  "publications": [
    {"date": "2026-06-12", "id": "...", "registry_office": "Handelsregisteramt des Kantons Bern", "registry_canton": "BE", "rubric": "HR", "mutation_types": ["HR02"], "title": "...", "source_url": "https://amtsblattportal.ch/..."}
  ],
  "publications_status": "answered",
  "enrichment_status": "answered",
  "citation": {
    "authority": "Eidgenössisches Amt für das Handelsregister (EHRA), Bundesamt für Justiz",
    "level": "federal",
    "source_url": "https://register.ld.admin.ch/zefix/company/415941",
    "zefix_url": "https://www.zefix.admin.ch/de/search/entity/list/firm/415941",
    "cantonal_excerpt_url": "https://be.chregister.ch/cr-portal/auszug/...",
    "passage": "Swisscom (Schweiz) AG, Aktiengesellschaft, Sitz: Ittigen (BE), Alte Tiefenaustrasse 6, 3050 Bern",
    "effective_from": "2026-06-12",
    "published_at": "2026-06-12",
    "dataset_modified": "2026-09-23",
    "source_status": "indicative",
    "source_validated_at": "2026-09-24T14:03:11Z"
  },
  "assumptions": [],
  "derived": false,
  "notes": "Zefix ist nicht rechtsverbindlich. Massgebend sind der beglaubigte Handelsregisterauszug des Kantons und die SHAB-Publikation."
}
```

Field semantics:

| Field | Source | Rule |
|---|---|---|
| `passage` | rendered from structured fields | Sources return records, not prose. The passage is a deterministic one-line rendering of the fields the answer relies on, in the requested language. Never LLM-generated. |
| `effective_from` | enrichment `shabDate`, else newest gazette `publicationDate`, else `dataset_modified` | Best available "state as of" date, in that priority. The chosen origin is stated in `assumptions`. |
| `published_at` | same as `effective_from` | Register entries take effect on publication. |
| `dataset_modified` | LINDAS `schema:dateModified` | Freshness of the primary source; updated daily. |
| `reference_year` | omitted | The contract's `reference_year` exists for datasets with yearly editions (premiums, rates). A register record has no edition; `effective_from` carries the temporal anchor. |
| `status` | enrichment `status`; else `ACTIVE` because LINDAS holds active entities only; `DELETED` only via 3b | Origin stated in `assumptions` when not from enrichment. |
| `source_status` | constant `indicative` | Zefix has no legal effect; the cantonal extract is binding. `notes` says so in the answer language. |
| `source_url` | LINDAS resource URI | Dereferenceable, official, stable. |
| `zefix_url` | built from `ehraid` | Human-facing Zefix detail page. Verified by opening one such URL before submission (A3). |
| `cantonal_excerpt_url` | enrichment `cantonalExcerptWeb` | Binding source, linked, not fetched. Null without enrichment. |
| publication `source_url` | built from publication id | Public amtsblattportal.ch URL, pattern confirmed by A4; fallback is the API XML path. |

Other states:

- `need_info`: `{status, question, candidates[], missing: "uid | canton | seat"}`. One question. Candidates carry `uid` so the follow-up call is exact.
- `no_match`: `{status, searched: {name, uid, canton}, gazette_checked: bool, source_url: <LINDAS query URL>, dataset_modified, source_validated_at}`. Sentence states the active-entity index was reached as of `dataset_modified` and holds no such entry.
- `out_of_scope`: `{status, reason: "topic | jurisdiction | persons | analytics", covered: "..."}`. For `persons`, includes `cantonal_excerpt_url` when the company was resolved first and enrichment ran.
- `source_unavailable`: `{status, source: "lindas | gazette", error_class, retry_after_s?, source_validated_at}`. LINDAS failure always produces this state; gazette failure produces it only in branch 3b, where the gazette is the deciding source; otherwise enrichment and gazette failures degrade fields. Never carries a cached record (D3).

### 5.4 Wrong-topic self-detection

If `question` is present and neither it nor the parameters contain anything company-like (UID, legal-form suffix, "Firma", "société", "azienda", "Handelsregister", "registre du commerce", "registro di commercio", "SHAB", "FOSC", "FUSC") and `name`/`uid` are empty, return `out_of_scope(topic)`. If `name` or `uid` is given, always run the lookup. The word list is a hint, not a gate.

## 6. Data sources and collection architecture

### 6.1 Topology

```
MCP client ──stdio/SSE──▶ FastMCP server (this repo)
                              └─ tools/company_info.py  (MCP surface, delegates to CompanyLookup)
                                   └─ zefix/lookup.py    CompanyLookup orchestrator
                                        ├─ zefix/sources/lindas.py   LindasClient  ──httpx POST──▶ lindas.admin.ch/query          (primary)
                                        ├─ zefix/sources/rest.py     ZefixClient   ──httpx GET───▶ www.zefix.admin.ch/ZefixREST/api/v1  (enrichment, policy-gated)
                                        └─ zefix/sources/gazette.py  GazetteClient ──httpx GET───▶ amtsblattportal.ch/api/v1      (publications)
```

Live proxy. Request-scoped `httpx.AsyncClient`, egress allow-list hook, no queue, no worker, no scheduler.

### 6.2 LINDAS backend (primary)

| Item | Value |
|---|---|
| Endpoint | `https://lindas.admin.ch/query` (setting `LINDAS_ENDPOINT`). `lindas.admin.ch/sparql` is the HTML UI and always returns HTML; do not use it. Mirror: `https://register.ld.admin.ch/query`. |
| Auth | none |
| Protocol | SPARQL 1.1, `POST`, form-encoded `query`, `Accept: application/sparql-results+json` |
| Graph | `<https://lindas.admin.ch/foj/zefix>`, 27.3 M triples, ~794 k organisations |
| Subject URI | `https://register.ld.admin.ch/zefix/company/{ehraid}` |
| Fields | `schema:name` (de/fr/it/en), `schema:legalName`, `schema:identifier` → `{CompanyUID, CHID, EHRAID}` via `schema:name`/`schema:value`, `schema:additionalType` → legal form `ld.admin.ch/ech/97/legalforms/{code}` with labels, `schema.ld.admin.ch/municipality` → BFS municipality with `schema:name`, `schema:address` → street, postcode, locality, region, `schema:description` = purpose |
| Absent | status, SHAB date, capital, links to zefix.ch or cantonal excerpt. Dissolved companies are removed from the graph. |
| Freshness | `schema:dateModified` on the dataset node, `accrualPeriodicity` DAILY. Read once per process and refreshed with the 24 h reference cache. |
| Licence | `dcterms:rights` → `ld.admin.ch/vocabulary/TermsOfUse/Provide-the-Source`: "Open use. Must provide the source." |
| Latency | Measured 2026-09-24: UID lookup 0.2 s; exact-name lookup 0.1–0.3 s; `legalName` prefix 1.2–2 s on a hit, 6 s on a miss; `schema:name` prefix or contains 15–21 s on a miss. No full-text index (`bif:contains` returns zero rows silently). A `LIMIT` only helps when matches are plentiful. |
| Timeout | 15 s for the whole staged search |

Queries live in `zefix/sources/lindas.py` as string templates with parameter escaping. Input never reaches the query unescaped: UID is validated by regex, name is lower-cased and escaped for SPARQL string literals, canton is validated against the canton allow-list.

Verified live 2026-09-24 with UID `CHE101654423` → Swisscom (Schweiz) AG, EHRAID 415941, Ittigen (BFS 362).

### 6.3 Zefix web endpoint (enrichment)

| Item | Value |
|---|---|
| Base URL | `https://www.zefix.admin.ch/ZefixREST/api/v1` (setting `ZEFIX_BASE_URL`) |
| Auth | none |
| Call | `GET firm/{ehraid}.json` only. Search is not used; LINDAS resolves the entity. |
| Fields read | `status, shabDate, deleteDate, cantonalExcerptWeb, oldNames, shabPub[].{shabDate, shabId, registryOfficeCanton, mutationTypes[].key}`. `shabPub[].message` is never read. |
| Timeout | 5 s |
| Headers | `Accept: application/json`, `User-Agent: mcp-swiss-info/<version> (+repo URL)` |
| Gate | `RESPECT_ROBOTS_TXT=false`, or credentials set (documented API) |

Verified live 2026-09-24: detail HTTP 200 without auth. The API root answers 403; concrete resource paths answer 200. The endpoint is the zefix.ch web app's internal API; it has no published documentation or terms. The documented alternative `ZefixPublicREST/api/v1` (Basic Auth, OpenAPI at `/ZefixPublicREST/v3/api-docs`, registration by email to zefix@bj.admin.ch) has the same `firm/{ehraid}` shape; `ZEFIX_BASE_URL` plus `ZEFIX_USERNAME`/`ZEFIX_PASSWORD` switch to it without code change.

### 6.4 Gazette backend

| Item | Value |
|---|---|
| Base URL | `https://amtsblattportal.ch/api/v1` (setting `GAZETTE_BASE_URL`) |
| Auth | none |
| List | `GET publications?publicationStates=PUBLISHED&uids={CHE-xxx.xxx.xxx}&rubrics=HR&pageRequest.size={n}`; the UID must be the formatted form and the key is `uids` (the unformatted form silently returns nothing). Optional `subRubrics`, `publicationDate.start/end`. Query built only from an allow-list of parameter names; unknown parameters are silently ignored upstream and would return the whole corpus. |
| Detail | `GET publications/{id}/xml`, not called by `company_info` (N3, N5) |
| Rubrics | `GET rubrics`, TTL cache 24 h, used to validate any rubric filter before calling upstream because an invalid code returns an empty 200 |
| Retry | on 429, 502, 503, 504 and network errors; honours `Retry-After`; max 3 attempts; total budget bounded by the remaining call budget |
| Plausibility | if `total` exceeds 95 % of the known corpus size the filter was ignored; raise, do not return |

Fields read: `meta.id, meta.publicationDate, meta.registrationOffice.displayName, meta.cantons[], meta.rubric, meta.subRubric, meta.title.{de,fr,it}`. `content` is never read. `publications[].registry_canton` is `meta.cantons[0]` when present, else null; `publications[].mutation_types` is the `subRubric` code of that publication (`HR01` new entry, `HR02` mutation, `HR03` deletion). Deletion detection uses `HR03`. Deletion detection for step 3b uses `subRubric` codes for "Löschung"; the exact codes are taken from the cached rubric taxonomy at build time (A6).

### 6.5 Compliance switch

The challenge requires robots.txt/ToS compliance to be a configuration setting. `BaseKnowledge/CHALLENGE.md` L112.

Facts (fetched 2026-09-24):

- `www.zefix.admin.ch/robots.txt` is `Disallow: /` for all agents, with a short allow-list of landing pages for Googlebot and Bingbot. It does not mention the API paths.
- `amtsblattportal.ch/robots.txt` and `www.shab.ch/robots.txt` are `Disallow: /`.
- `lindas.admin.ch/query` is a SPARQL endpoint published by the federal administration for machine access, with explicit terms of use in the dataset metadata.
- Legal basis for free public access to identification data of active entities: Art. 14 para. 2 HRegV.

Setting `RESPECT_ROBOTS_TXT` (bool, default `true`; the challenge requires compliance by default and a switch, `BaseKnowledge/CHALLENGE.md` L112):

| Setting | LINDAS | Zefix web endpoint | Zefix documented API (credentials set) | Gazette API |
|---|---|---|---|---|
| `false` | used | used | used | used |
| `true` | used; a published SPARQL endpoint with its own terms is not a crawl target | not used; `enrichment_status: "policy_robots"` | used; the credential grant is the ToS acceptance | used; the API has its own GTC and is not a crawl target |

Under the default `true` without credentials, the answer loses `status` from the source (it becomes "active by index membership", flagged), `shabDate`, and the cantonal excerpt link. The state machine is unchanged. This is the whole cost of R1.

### 6.6 Person data

Neither LINDAS nor the Zefix record has structured person fields (verified against the LINDAS predicate inventory, the live web-endpoint response, and the PublicREST OpenAPI `CompanyFull` schema). Person names appear only in `shabPub[].message` and gazette `content`, neither of which the tool reads. Questions about persons return `out_of_scope(persons)` with the cantonal excerpt URL when available. This keeps the tool safe under the revised Federal Act on Data Protection without a review step.

### 6.7 Egress

Outbound hosts are limited to `lindas.admin.ch`, `register.ld.admin.ch`, `www.zefix.admin.ch`, and `amtsblattportal.ch` by an httpx event hook that also inspects redirects. The allow-list is derived from `API_SOURCES` in `src/mcp_swiss_info/sources.py`.

## 7. Storage

There is no persistent storage.

| What | Where | Lifetime | Why |
|---|---|---|---|
| Legal-form labels (de/fr/it/en) | process memory | 24 h TTL | tiny, static; one LINDAS query per process |
| LINDAS `dateModified` | process memory | 24 h TTL | freshness stamp for every answer |
| Gazette rubric taxonomy | process memory | 24 h TTL | validation before calling upstream; deletion sub-rubric codes |
| Company records | nowhere | request | D3: no stale answers, no retention question, nothing to declare as a pre-built index |
| Test fixtures | `tests/fixtures/*.json` | repo | recorded upstream responses with personal data redacted, provenance file with SHA-256 |

Rejected: cache-on-read (SQLite). It would let the tool answer during an upstream outage, but every such answer would be a stale record presented next to a "not legally binding" note, on a source whose whole value is being current. The challenge scores an honest `source_unavailable` as correct. A cache also creates a retention obligation for gazette metadata that we otherwise do not hold.

## 8. Code architecture in this repo

```
src/mcp_swiss_info/
  config/settings.py            + LINDAS_ENDPOINT, ZEFIX_BASE_URL, ZEFIX_USERNAME, ZEFIX_PASSWORD, GAZETTE_BASE_URL,
                                  RESPECT_ROBOTS_TXT, USER_AGENT, LINDAS_TIMEOUT_S, ZEFIX_TIMEOUT_S,
                                  CALL_BUDGET_S, REFERENCE_CACHE_TTL_S
  sources.py                     `ApiSource`/`API_SOURCES` registry (zefix_lindas, zefix_web, gazette) plus `api_hosts()`;
                                 also the crawler's unrelated `SOURCES` page registry
  zefix/
    __init__.py                 exports `CompanyLookup`
    lookup.py                   `CompanyLookup` orchestrator: resolution algorithm §5.2, constructor-injected
                                 `LindasClient`/`ZefixClient`/`GazetteClient`/`Settings`
    gates.py                    step-0 gates (persons, jurisdiction, analytics, topic) behind `classify()`
    envelope.py                 response models: answered, need_info, no_match, out_of_scope, source_unavailable;
                                 passage renderer per language
    sources/
      __init__.py
      http.py                   make_client(), allowed_hosts() (reads sources.api_hosts()), egress allow-list hook,
                                 EgressDenied                                                  (vendored, register-mcp server.py L378-444)
      lindas.py                 `LindasClient`: find_by_uid(), search_by_name(), legal_form_labels(),
                                 dataset_modified(), SPARQL templates + escaping                (new)
      rest.py                   `ZefixClient`: firm_detail(), uid normalisation, canton codes, error mapping
                                                                (vendored L419-537 + inlined GET at L908 extracted)
      gazette.py                `GazetteClient`: get_json(), search_publications(), rubrics(), retry policy,
                                 param allow-list, quirk guards                                (vendored L153-264, L1398-1600)
      LICENSE-register-mcp      MIT notice, Copyright 2026 Hayal Oezkan
  tools/company_info.py         the MCP surface only: `@mcp.tool` signature and docstring, delegates to
                                 `zefix.CompanyLookup`; registered via tools/__init__.py
tests/
  fixtures/                     zefix_firm_detail, gazette_* copied verbatim from register-mcp incl. PROVENANCE.md;
                                lindas_* recorded fresh with a provenance entry
  conftest.py                   `FakeLindas`/`FakeZefix`/`FakeGazette` and a `lookup(**fakes)` helper
  test_zefix_sources_lindas.py  respx; UID hit, prefix search, zero hits, escaping, timeout
  test_zefix_sources_zefix.py   respx; detail parse, 404, timeout → enrichment degraded (covers zefix/sources/rest.py)
  test_zefix_sources_gazette.py respx; quirks 1-3, retry, budget, deletion detection
  test_sources.py               every `API_SOURCES` host is in `http.allowed_hosts()`; the three endpoints are rows of `SOURCES["federal"]` with `expected = NOT_A_PAGE`; `API_SOURCES` holds base URL, hosts, authority and terms
  test_company_info.py          state machine: each of the 5 states from injected fakes; ambiguity; rm→de; persons; robots switch
  test_company_info_registration.py  the tool is registered on the MCP server with the documented signature
  test_live.py                  @pytest.mark.live, excluded by default
```

Dependencies added: `httpx>=0.27`, dev `respx`, `pytest-asyncio`. Vendored code is roughly 500 lines after dropping Zefix search and everything tied to the `mcp` SDK (`MCPServer`, cache hints, `logged_tool`, SSE middleware); FastMCP provides transport and this repo has its own logger.

Vendoring rules: keep function names and the three upstream-quirk guards intact so future diffs against `register-mcp` stay readable; keep the MIT notice in `zefix/sources/LICENSE-register-mcp` and a one-line attribution at the top of each vendored module; do not re-add free-text gazette search.

## 9. Tests

- Unit, offline, run by `make test`: all five states reachable from fixtures; UID normalisation; ambiguity rules; language fallback; SPARQL escaping; egress denial; gazette quirks; retry budget; robots switch degrading enrichment only.
- Live, `pytest -m live`: one LINDAS UID query, one prefix search, one Zefix detail, one gazette list. Run manually before submission, not in CI.
- Contract check: a script that starts the server over stdio, calls `tools/list`, calls `company_info` against fixture-backed mocks, and asserts the envelope keys. This is the "one runnable MCP check per implemented behaviour" that `BaseKnowledge/STATUS.md` asks for.
- The existing broken `tests/conftest.py` is replaced; obsolete boilerplate tests are deleted.

## 10. README and operability obligations

- Scope declaration: "Swiss companies in the federal commercial register index (Zefix) and their SHAB publications. Federal level, all cantons. Not covered: persons, VAT status, cantonal extracts, statistics."
- Credentials: none required. Optional `ZEFIX_USERNAME`/`ZEFIX_PASSWORD` for the documented Zefix API, with the registration email address.
- `RESPECT_ROBOTS_TXT`: default `true`, meaning, which fields the Zefix web endpoint adds when set to `false`, and that setting credentials enables the documented API under either value, in one paragraph.
- Attribution: "Company data: Zefix, Federal Office of Justice / EHRA, via LINDAS (lindas.admin.ch, terms: open use, provide the source). Not legally binding; the cantonal commercial register extract is authoritative. Official notices: SHAB via amtsblattportal.ch; the signed PDF is the binding version." Plus MIT attribution for `register-mcp`.
- Prompt-injection stance: every upstream string is data. The tool forwards only company names, purpose, and address as free text, and the README says so.
- Local run: `uv sync && uv run python -m mcp_swiss_info.main`. No build step, no index download. `uv.lock` is tracked because every client config runs `uv run --frozen`.

## 11. Risks

| Code | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Jury keeps the default `RESPECT_ROBOTS_TXT=true` without credentials; enrichment fields are absent | high | low | LINDAS still answers; degradation is explicit in `enrichment_status` and `assumptions` |
| R2 | LINDAS lags one day; a company deleted yesterday still shows as active | certain | low | `dataset_modified` in every citation; enrichment supplies live `status` when allowed |
| R3 | Ambiguity rule picks the wrong entity | medium | high | prefer `need_info` whenever more than one prefix match exists and no exact `legalName` match; log candidates |
| R4 | Name search misses because LINDAS has no fuzzy or full-text search; a name matching nothing times out at the phase budget | medium | medium | exact-literal stage first, then prefix and `CONTAINS`; `timeout_scan` answer asks for the UID; README states "exact or prefix name" and the timeout |
| R11 | One UID with several registered seats (UBS AG: Basel and Zürich) appears as two LINDAS entities | certain for a few large companies | low | hits are grouped by UID before disambiguation; the answer states the seats and which one is shown |
| R5 | LINDAS endpoint slow or down during the jury run | low | high | 10 s timeout; `source_unavailable` is a correct answer; `LINDAS_ENDPOINT` can point at the `register.ld.admin.ch` mirror |
| R6 | Zefix web endpoint changes or blocks non-browser clients | low | low | enrichment degrades; `ZEFIX_BASE_URL` switch to the documented API |
| R7 | Gazette total > cap because a parameter was silently ignored | low | medium | allow-list plus plausibility guard, vendored |
| R8 | `zefix_url` or gazette publication URL pattern is wrong | medium | medium | A3, A4 verify by opening one URL each |
| R9 | Romansh question, no `rm` upstream | certain | low | map to `de`, note in the answer |
| R10 | Wrong-topic calls waste a tool call | medium | low | §5.4 hint; `question` parameter |

## 12. Open questions

| Code | Question | Owner | Needed by |
|---|---|---|---|
| O2 | Does the FOJ answer the PublicREST registration before Friday 12:00? Only affects the documented-API switch, not the submission. | Victor | Fri morning |

## 13. Actions

| Code | Action | Owner | When |
|---|---|---|---|
| A1 | Email zefix@bj.admin.ch for PublicREST credentials (username = team email) | Victor | now |
| A3 | Open `https://www.zefix.admin.ch/de/search/entity/list/firm/415941` in a browser and confirm it renders Swisscom (Schweiz) AG; adjust the `zefix_url` pattern if not | any | Thu |
| A4 | Confirm the public amtsblattportal.ch URL pattern for a single publication id | any | Thu |
| A5 | Read Zefix "Rechtliches" and Amtsblattportal GTC in a real browser; paste the binding-source sentence verbatim into README | any | Thu |

## 14. Implementation plan

| Step | Work | Est. |
|---|---|---|
| S0 | Tests first, by an agent other than the implementer, from this PRD alone: `tests/test_company_info.py` with the five states from fixtures, the eight jury questions of §4, and the negative checks (`message`/`content` never serialised, `RESPECT_ROBOTS_TXT` defaults to `true`, egress denied for unknown hosts). Red until S4 lands. | 1 h |
| S1 | Settings, deps (`httpx`, `respx`), `zefix/sources/http.py`, `zefix/sources/lindas.py` with the two queries from §6.2, legal-form labels, `dateModified`; record LINDAS fixtures (A7) | 2.5 h |
| S2 | `zefix/sources/gazette.py` vendored; rubric cache; retry policy; deletion codes (A6). `zefix/sources/rest.py` enrichment call | 1.5 h |
| S3 | `envelope.py` with the five states and the passage renderer (de/fr/it/en) | 1 h |
| S4 | `tools/company_info.py`: resolution algorithm, ambiguity rules, robots gate, person guard, budgets | 2 h |
| S5 | Source-level tests (LINDAS, Zefix, gazette, egress) and the stdio contract check; make S0 green | 1.5 h |
| S6 | README: scope, credentials, robots setting (default `true`), attribution, prompt-injection stance; remove boilerplate tools (`math`, `text`, `utility`, `tax`) from `tools/__init__.py` | 1 h |
| S7 | Smoke run by a fresh agent: start the server, ask Q1, Q3, Q5, Q7 through a real MCP client, compare the CHE-101.654.423 answer field by field against its own curl to LINDAS. Fix wording of `answer` per language. | 1 h |

Total ≈ 12 h. Sequencing: S0 first; S1, S2, S3 are independent; S4 depends on all three; S6 runs in parallel with S5.

Verification rule: the implementer's report is a claim, `uv run pytest` and the S7 smoke run are the evidence. The agent that writes S0 and the agent that runs S7 are never the implementer. Two fix rounds max, then the owner decides.
