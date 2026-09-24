# mcp-swiss-info

An MCP server that answers questions about Swiss companies, grounded in official
federal sources: the Zefix commercial register index and the Swiss Official
Gazette of Commerce (SHAB). It is a live proxy — every call hits the upstream
sources directly, nothing is cached or persisted.

Team: Roberto Cerrone, Edoardo Diana, Alberto Minetti, Vincent Van Loo, Victor
Bonilla, Jesus Sebastian, Jiaqi Yu.

## Scope

Swiss companies in the federal commercial register index (Zefix) and their
SHAB/cantonal gazette publications. Federal level, all 26 cantons. Languages:
German, French, Italian, English; Romansh questions are answered in German
with a note.

Not covered: natural persons (board members, signatories), VAT status,
cantonal register extracts, statistics or lists over the register.

## Tool: `company_info`

One tool, no mandatory parameters. Omitting both `name` and `uid` returns
`need_info` asking for a company name — a mandatory field would push that
failure into client-side schema validation, where the calling LLM cannot see
it.

| Parameter | Type | Default | Purpose |
|---|---|---|---|
| `question` | `str \| None` | `None` | The user's question verbatim; used to self-detect wrong-topic, person, jurisdiction, and analytics questions |
| `name` | `str \| None` | `None` | Company name or name prefix |
| `uid` | `str \| None` | `None` | `CHE-xxx.xxx.xxx`; dots and hyphens optional |
| `canton` | `str \| None` | `None` | Two-letter canton code, narrows disambiguation |
| `language` | `str` | `"de"` | `de \| fr \| it \| en`; `rm` maps to `de` |
| `include_publications` | `bool` | `True` | Attach recent gazette publications for the resolved company |
| `max_publications` | `int` | `5` | 1–20 |

### Response states

- `answered` — company resolved, with citation, authority, and effective date.
- `need_info` — the name was ambiguous or missing; the tool asks for exactly one of UID, canton, or seat, with up to 5 candidates.
- `no_match` — no company found at the primary source (and, when a UID was given, no deletion publication either).
- `out_of_scope` — the question is about persons, a non-Swiss jurisdiction, register-wide analytics, or an unrelated topic.
- `source_unavailable` — a source the answer depends on could not be reached; the tool never falls back to a cached or stale record.

### Example (`answered`, abbreviated)

```json
{
  "status": "answered",
  "answer": "Swisscom (Schweiz) AG ist eine aktive Aktiengesellschaft mit Sitz in Ittigen (BE).",
  "company": {
    "name": "Swisscom (Schweiz) AG",
    "uid": "CHE-101.654.423",
    "legal_form": "Aktiengesellschaft",
    "seat": "Ittigen",
    "canton": "BE",
    "address": {"street": "Alte Tiefenaustrasse 6", "zip": "3050", "city": "Bern"},
    "status": "ACTIVE"
  },
  "publications": [
    {"date": "2026-06-12", "registry_office": "Handelsregisteramt des Kantons Bern", "rubric": "HR", "source_url": "https://amtsblattportal.ch/..."}
  ],
  "citation": {
    "authority": "Eidgenössisches Amt für das Handelsregister (EHRA), Bundesamt für Justiz",
    "source_url": "https://register.ld.admin.ch/zefix/company/415941",
    "cantonal_excerpt_url": "https://be.chregister.ch/cr-portal/auszug/...",
    "effective_from": "2026-06-12",
    "dataset_modified": "2026-09-23",
    "source_status": "indicative"
  },
  "notes": "Zefix ist nicht rechtsverbindlich. Massgebend sind der beglaubigte Handelsregisterauszug des Kantons und die SHAB-Publikation."
}
```

The full field list, including `need_info`, `no_match`, `out_of_scope`, and
`source_unavailable` shapes, is in `docs/prd-zefix-company-info.md` §5.3.

## Data sources

| Source | Endpoint | Auth | Licence / terms | Contributes |
|---|---|---|---|---|
| LINDAS (primary) | `lindas.admin.ch/query` | none | "Open use. Must provide the source." (`dcterms:rights` on the FOJ Zefix dataset) | Identity, legal form, seat, address, purpose. Updated daily. |
| Zefix web endpoint | `www.zefix.admin.ch/ZefixREST/api/v1` | none | Undocumented, no published terms | Enrichment only: status, SHAB date, cantonal excerpt link. Off by default. |
| Zefix PublicREST | `www.zefix.admin.ch/ZefixPublicREST/api/v1` | Basic Auth, free registration via `zefix@bj.admin.ch` | Documented (OpenAPI) | Same enrichment fields, used automatically once credentials are set. |
| Amtsblattportal | `amtsblattportal.ch/api/v1` | none | Portal GTC | UID-scoped SHAB/cantonal gazette publications. |

LINDAS is always used and is the only source required for an `answered`
result. The two Zefix backends and the gazette are enrichment: their failure
degrades fields, it never removes the answer (except branch 3b, where a UID
resolves nowhere on LINDAS and the gazette is the only source that can settle
existence — see the PRD).

## Compliance

`RESPECT_ROBOTS_TXT` defaults to `true`. This is a configuration setting, not
hardcoded behavior, so it can be switched for testing.

- `true` (default): the undocumented Zefix web endpoint is not called;
  `enrichment_status` is `"policy_robots"` and the answer loses live `status`,
  `shabDate`, and the cantonal excerpt link. LINDAS and the gazette API are
  used regardless — a published SPARQL endpoint and an API with its own GTC
  are not crawl targets.
- `false`: the Zefix web endpoint is also called for enrichment.
- Setting `ZEFIX_USERNAME`/`ZEFIX_PASSWORD` switches enrichment to the
  documented PublicREST API under either setting — the credential grant is
  the ToS acceptance.

`zefix.admin.ch` and `amtsblattportal.ch` publish `robots.txt` with
`Disallow: /` for crawlers. This server does not crawl either site: it makes
one individual, user-triggered request per tool call against a published API
endpoint, in response to a specific question, never an unattended traversal
of pages.

Outbound requests are further restricted by `ALLOWED_HOSTS`, an egress
allow-list enforced on every request (including redirects). Default:
`lindas.admin.ch`, `register.ld.admin.ch`, `www.zefix.admin.ch`,
`amtsblattportal.ch`.

## Credentials

None required. LINDAS, the Zefix web endpoint, and the Amtsblattportal API
are all keyless.

Optional: `ZEFIX_USERNAME` / `ZEFIX_PASSWORD` for the documented
ZefixPublicREST API. Register for free by emailing `zefix@bj.admin.ch`.
Without them, enrichment falls back to the undocumented web endpoint (gated
by `RESPECT_ROBOTS_TXT`, see above).

Zero secrets are committed to this repository. Put credentials in a local
`.env` file, which is gitignored (`git check-ignore .env` confirms this).

## Run locally

```bash
uv sync
uv run python -m mcp_boilerplate.main            # stdio transport (default)
```

SSE transport, for web/HTTP integration:

```bash
make run-sse
# equivalent to:
uv run --extra sse python -m mcp_boilerplate.main --transport sse --port 8000
```

### Client configuration

Claude Desktop / Claude Code (`.mcp.json`):

```json
{
  "mcpServers": {
    "mcp-swiss-info": {
      "command": "uv",
      "args": ["run", "--frozen", "python", "-m", "mcp_boilerplate.main"]
    }
  }
}
```

Codex (`.codex/config.toml`):

```toml
[mcp_servers.mcp-swiss-info]
command = "uv"
args = ["run", "--frozen", "python", "-m", "mcp_boilerplate.main"]
```

OpenCode (`opencode.json`):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "mcp-boilerplate": {
      "type": "local",
      "command": ["uv", "run", "--frozen", "python", "-m", "mcp_boilerplate.main"],
      "enabled": true
    }
  }
}
```

## Tests

```bash
uv run pytest -q                          # offline, runs against recorded fixtures
uv run pytest -m live                     # hits real upstream endpoints, run manually before submission
uv run python scripts/record_fixtures.py lindas   # refresh LINDAS fixtures
```

## Honesty and prompt-injection stance

Every string returned by an upstream source is treated as data, never as
instructions. The tool forwards only company name, purpose, and address as
free text in its answer. Gazette full text (`content`) and SHAB message
bodies (`shabPub[].message`) are read by no code path in this server and are
never returned. The server never answers from a cache: every result reflects
a live call made during that request, or an explicit `source_unavailable`.

## Attribution

Company data: Zefix, Federal Office of Justice / EHRA, via LINDAS
(lindas.admin.ch). Not legally binding; the cantonal commercial register
extract is authoritative. Official notices: SHAB via amtsblattportal.ch; the
signed PDF is the binding version.

Parts of `src/mcp_boilerplate/sources` are vendored from
`malkreide/register-mcp`, MIT, Copyright (c) 2026 Hayal Oezkan; see
`src/mcp_boilerplate/sources/LICENSE-register-mcp`.

## Limitations

- LINDAS is updated daily and can lag the register by up to one day.
- Dissolved companies are absent from the LINDAS graph; when a UID is known,
  the tool infers `DELETED` from a matching gazette deletion publication.
  Without a UID, a dissolved company simply returns `no_match`.
- Name search is exact, then prefix, then substring matching, not fuzzy. An
  exact registered name or a UID answers in well under a second. A name that
  matches nothing exhausts the 15 second LINDAS budget and returns
  `source_unavailable` with `error_class: "timeout_scan"` and a sentence asking
  for the UID, because LINDAS has no full-text index.
- One UID can have several registered seats (UBS AG: Basel and Zürich). The
  tool shows one seat and lists the others in `assumptions`.
