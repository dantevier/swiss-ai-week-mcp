# PRD: `company_info` refactor — tool layout, dependency injection, source registry

Status: proposed, applies to PR #7 (`victor-dev` → `main`). Owner: Victor Bonilla. Baseline on `victor-dev` `e2c74e4`: 76 offline tests pass, 3 live tests deselected. Companion: `docs/prd-zefix-company-info.md` (behaviour, envelope, sources); this PRD changes structure only.

## 1. Summary

PR #7 ships `company_info` as a 915-line module under `tools/`, a 539-line `envelope.py`, and a 1,271-line `zefix_sources/` package. The repo's conventions, set by `crawler.py`, `sources.py`, `source_tools.py` and the `tools/*_tools.py` modules on `main`, are: thin `@mcp.tool` wrappers, domain logic in root modules, orchestrators with constructor-injected collaborators, one reviewed source registry in `sources.py`. This PRD moves `company_info` onto those conventions with no change to the tool's contract or output.

| Code | Decision |
|---|---|
| D1 | `tools/company_info.py` keeps only the MCP surface: signature, docstring, `@mcp.tool`, one delegate call. Everything else lives in one package, `mcp_swiss_info/zefix/`. |
| D2 | Orchestrator `CompanyLookup` in `zefix/lookup.py`, constructor-injected clients and config, mirroring `Crawler(web_fetcher, pdf_fetcher, database, embedder)`. |
| D3 | The three source clients live in `zefix/sources/` (moved from `zefix_sources/` with `git mv`) and become classes (`LindasClient`, `ZefixClient`, `GazetteClient`) whose constructors take config with defaults from `settings`. Method names and pure helpers keep their vendored names. |
| D4 | `SOURCES` is the one reviewed registry. `SOURCES["federal"]` lists Zefix/LINDAS and the gazette as three plain `Source` rows (`zefix_lindas`, `zefix_web`, `gazette`: url = API base URL, authority, `expected = NOT_A_PAGE`), so every source the server reads is reviewed and attributed in one place. The companion table `API_SOURCES: dict[str, ApiSource]` is defined first and holds the API data: `hosts` (feeding the egress allow-list `api_hosts()`) and `terms`, plus the `base_url` and `authority` the three `Source` rows are built from. Settings defaults for the three endpoints come from `API_SOURCES[*].base_url`. No consumer filters by kind (F5). |
| D5 | Step-0 gates (persons, jurisdiction, analytics, topic) move to `zefix/gates.py`, pure functions, one `classify()` entry point. `envelope.py` moves to `zefix/envelope.py` unchanged. |
| D6 | Behaviour freeze: every envelope produced from the existing fixtures is identical before and after. Tests move with the code; assertions do not change. |
| D7 | `origin/main` is merged into `victor-dev` before the refactor starts (F9). |
| D8 | Vendoring rule kept: function/method names and quirk guards unchanged; MIT notice and per-module attribution unchanged. |

## 2. Findings from the pattern audit

| Code | Finding |
|---|---|
| F1 | Tool modules on `main` are thin. `source_tools.py` bodies are one line over `Crawler`/`KnowledgeBase`; `opendata_tools.py`, `bfs_tools.py`, `geo_tools.py` decorate an async wrapper that calls a private sync helper through `asyncio.to_thread`. `tools/company_info.py` holds four concerns: gate word lists (~230 lines), resolution (~200), envelope assembly (~250), the tool (~100). |
| F2 | Registration form differs. `main` uses the `@mcp.tool` decorator. `company_info.py` ends with `company_info_tool = mcp.tool(company_info, name="company_info")` so tests can await the undecorated function. Once logic lives in `CompanyLookup`, tests target that and the decorator form works. |
| F3 | The crawler pattern is: domain module at package root, orchestrator class with constructor-injected collaborators, collaborators as small classes with one async method, thin tools. `tests/test_crawler.py` injects fakes: `Crawler(fetcher, fetcher, db, FakeEmbedder())`. `company_info` reaches its collaborators as module globals (`lindas.find_by_uid`, `zefix.firm_detail`, `settings`); tests monkeypatch them through `conftest.patch_sources` and a `settings_override` fixture. |
| F4 | Two allow-lists. `crawler.check_url` validates every request and redirect against `sources.SOURCES`. `zefix_sources/http.py` validates every request and redirect against `settings.allowed_hosts`. Same guarantee, two registries; `sources.py` does not know Zefix, LINDAS or the gazette exist. |
| F5 | `SOURCES` is consumed by `crawler.check_url`, `Crawler.crawl` (`source="all"` iterates a level), `KnowledgeBase.get`/validation, the dashboard status and refresh endpoints, and `test_crawler.py`. A SPARQL endpoint is not a page, so a Zefix row must never save anything or resolve as crawled content. An API row is therefore a `Source` whose `expected` is `NOT_A_PAGE`, a sentinel that never occurs in fetched text: `check_url` allows its base URL like any listed URL, a crawl of it fails validation by construction and saves nothing, `get_source` answers "Source has not been crawled", and the dashboard lists it as a never-crawled source. No consumer needs a kind filter. |
| F6 | Status vocabulary. `BaseKnowledge/CONTRACT.md` §5 defines `answered`, `need_info`, `out_of_scope`, `source_unavailable`, `no_match`. `company_info` conforms. `main`'s bfs/geo/opendata/weather/health tools use `answered`, `no_data`, `not_found`, `invalid_input`, `source_unavailable`. The debt is on `main`, out of scope here (Q2). |
| F7 | HTTP stacks. `main`'s newer tools use stdlib `urllib` through `tools/_public_api.py`; the crawler uses `urllib` plus the MCP httpx client; `zefix_sources` uses async httpx. httpx is already a transitive dependency of `fastmcp`. Rewriting 1,271 vendored lines onto `urllib` buys nothing (N2). |
| F8 | Config. `main` tools use module constants; the crawler reads `.env` directly; PR #7 adds 13 pydantic settings fields. Endpoints, credentials, the compliance switch and budgets are legitimate runtime config and stay. `allowed_hosts` duplicates what the source registry should own (D4). |
| F9 | `victor-dev` is 4 commits behind `origin/main` (`2c1baa2` weather/bfs/geo/opendata tools and `_public_api.py`, README, logo). `tools/__init__.py` conflicts: 3 modules on `victor-dev`, 6 on `main`. PR #7 currently shows `tests/unit/` and `tests/integration/` as deletions against `main`. |
| F10 | `envelope.py` is already the right shape: pure, no I/O, no imports from sources or tools. It stays as is; three translated tables still in `company_info.py` (`_ASK_NAME_QUESTION`, `_ROMANSH_ASSUMPTION`, `_TIMEOUT_SCAN_SENTENCES`) belong there. |
| F11 | `_call_source` + `SourceUnavailable` is the company equivalent of `_public_api.unavailable`: exceptions never escape, each becomes a `source_unavailable` envelope. Keep, as a `CompanyLookup` method. |
| F12 | The company code is spread over three places: `tools/company_info.py`, root `envelope.py`, and the `zefix_sources/` package (named to avoid colliding with `sources.py`). `zefix_sources` is imported by 4 modules, 5 test files and `scripts/record_fixtures.py`, and named in README and the companion PRD. One package, `zefix/`, gives the feature one home and removes the naming workaround. |

## 3. Goals and non-goals

Goals:

- G1 `tools/company_info.py` is ≤ 100 lines: docstring, `@mcp.tool`, one call into `CompanyLookup`.
- G2 All company logic sits in the `zefix/` package and is testable with injected fakes, no `monkeypatch.setattr` on modules or settings.
- G3 `SOURCES` in `sources.py` is the single registry of reviewed authorities: the crawled pages plus the three commercial-register API endpoints as `Source` rows with `expected = NOT_A_PAGE`, called live by `company_info` and never through the crawler. `API_SOURCES` carries their base URL, hosts, authority and terms, and the three rows are built from it; the egress allow-list `api_hosts()` derives from it. No consumer filters by kind.
- G4 Zero behaviour change (D6). The 76 offline tests and 3 live tests pass; new tests cover registration and the registry.
- G5 `victor-dev` contains `origin/main` (D7) and `tools/__init__.py` registers all seven tool modules.

Non-goals:

- N1 No change to the five-state envelope, field names, or answer sentences.
- N2 No rewrite of the vendored clients onto `urllib`/`_public_api.py`.
- N3 No renaming of vendored functions, dataclasses or quirk guards. Paths move; names inside the modules do not.
- N4 No alignment of `main`'s other tools to the contract vocabulary (F6).
- N5 No new features, no new sources.

## 4. Target architecture

```
src/mcp_swiss_info/
  sources.py              SOURCES (pages + NOT_A_PAGE rows zefix_lindas, zefix_web, gazette); API_SOURCES (base_url, hosts, authority, terms); api_hosts()
  zefix/                  NEW package: everything company_info needs except the MCP surface
    __init__.py           exports CompanyLookup
    gates.py              NEW  step-0 classification, pure: classify(question, uid, canton) -> reason | None
    lookup.py             NEW  CompanyLookup orchestrator: resolution §5.2 steps 1-6, envelope assembly
    envelope.py           moved from root, unchanged + the three translated tables from company_info.py
    sources/              moved from zefix_sources/ with git mv
      __init__.py
      http.py             allowed_hosts() reads API_SOURCES; make_client(), classify_error() unchanged
      lindas.py           LindasClient(endpoint, timeout_s) + module-level SPARQL templates, escaping, Company
      zefix.py            ZefixClient(base_url, username, password, timeout_s, respect_robots_txt)
                          + module-level normalize_uid, format_uid, zefix_detail_url, CANTON_CODES, Enrichment
      gazette.py          GazetteClient(base_url) + module-level retry policy, quirk guards, Publication, is_deletion
      LICENSE-register-mcp
  tools/company_info.py   signature + docstring + @mcp.tool + `return await CompanyLookup().lookup(...)`
  tools/__init__.py       bfs, company_info, geo, health_insurance, opendata, source, weather
```

Path moves (`git mv`, history preserved) and the files whose imports or text change:

| From | To |
|---|---|
| `src/mcp_swiss_info/envelope.py` | `src/mcp_swiss_info/zefix/envelope.py` |
| `src/mcp_swiss_info/zefix_sources/{__init__,http,lindas,zefix,gazette}.py`, `LICENSE-register-mcp` | `src/mcp_swiss_info/zefix/sources/` |
| `tests/test_zefix_sources_{lindas,zefix,gazette}.py` | unchanged names; imports updated |

Import rewrites: `mcp_swiss_info.zefix_sources` → `mcp_swiss_info.zefix.sources`, `mcp_swiss_info.envelope` → `mcp_swiss_info.zefix.envelope`, in `tools/company_info.py`, `scripts/record_fixtures.py`, `tests/conftest.py`, `tests/test_company_info.py`, `tests/test_live.py`, the three `tests/test_zefix_sources_*.py`. Text references in `README.md` (lines naming `zefix_sources/`) and `docs/prd-zefix-company-info.md` §8 are rewritten to the new paths. Inside the package, relative imports change depth: `..config.settings` becomes `...config.settings` in `zefix/sources/*`.

Symbol map, `tools/company_info.py` today → destination:

| Today | Destination |
|---|---|
| `_PERSON_TERMS`, `_ANALYTICS_TERMS`, `_TOPIC_HINTS`, `_LEGAL_FORM_SUFFIXES`, `_FOREIGN_REGISTER_IDS`, `_COUNTRY_NAMES`, `_SWISS_WORDS`, `_CANTON_NAMES`, `_FOREIGN_UID_PREFIX_RE` | `zefix/gates.py` constants |
| `_uid_is_foreign`, `_has_swiss_anchor`, `_has_persons_terms`, `_is_jurisdiction_gate`, `_has_analytics_terms`, `_looks_company_like` | `zefix/gates.py`, behind `classify()`; individual predicates stay importable for the existing gate tests |
| `_ASK_NAME_QUESTION`, `_ROMANSH_ASSUMPTION`, `_TIMEOUT_SCAN_SENTENCES` | `zefix/envelope.py` static content |
| `AUTHORITY` | `API_SOURCES["zefix_lindas"].authority` |
| `REGISTER_RUBRICS` | `zefix/lookup.py` constant |
| `_call_source`, `_safe_dataset_modified`, `_run_enrichment`, `_resolve_company`, `_build_answered_envelope`, `_build_derived_deleted_envelope`, `_remaining` | `CompanyLookup` methods |
| `_group_by_uid`, `_seats_of`, `_resolve_seat_group`, `_candidate_dict_for_group`, `_build_company_dict`, `_build_derived_company_dict`, `_publication_dict`, `_map_status`, `_legal_form_label`, `_display_name` | `zefix/lookup.py` module-level private functions (dataclass → envelope dict serializers) |
| body of `company_info()` | `CompanyLookup.lookup()` |
| `company_info_tool = mcp.tool(company_info, ...)` | `@mcp.tool` on `company_info` |

## 5. Interfaces

```python
# sources.py
@dataclass(frozen=True)
class Source:
    url: str
    authority: str
    expected: str               # text a fetched page must contain to pass validation

@dataclass(frozen=True)
class ApiSource:
    base_url: str
    hosts: tuple[str, ...]      # every host a request or redirect may reach
    authority: str
    terms: str                  # licence / terms sentence used in README attribution

API_SOURCES: dict[str, ApiSource] = {
    "zefix_lindas": ApiSource(
        "https://lindas.admin.ch/query",
        ("lindas.admin.ch", "register.ld.admin.ch"),
        "Eidgenössisches Amt für das Handelsregister (EHRA), Bundesamt für Justiz",
        "LINDAS: open use, provide the source. Not legally binding.",
    ),
    "zefix_web": ApiSource(
        "https://www.zefix.admin.ch/ZefixREST/api/v1",
        ("www.zefix.admin.ch",),
        "Eidgenössisches Amt für das Handelsregister (EHRA), Bundesamt für Justiz",
        "Undocumented web endpoint; called only when RESPECT_ROBOTS_TXT=false or credentials are set.",
    ),
    "gazette": ApiSource(
        "https://amtsblattportal.ch/api/v1",
        ("amtsblattportal.ch",),
        "Schweizerisches Handelsamtsblatt (SHAB), SECO",
        "The signed PDF is the binding version.",
    ),
}

def api_hosts() -> frozenset[str]: ...   # union of API_SOURCES[*].hosts; http.allowed_hosts() returns this

NOT_A_PAGE = "..."              # sentinel that never occurs in fetched text

SOURCES: dict[str, dict[str, Source]] = {
    "federal": {
        "zefix_lindas": Source(API_SOURCES["zefix_lindas"].base_url, API_SOURCES["zefix_lindas"].authority, NOT_A_PAGE),
        "zefix_web": Source(API_SOURCES["zefix_web"].base_url, API_SOURCES["zefix_web"].authority, NOT_A_PAGE),
        "gazette": Source(API_SOURCES["gazette"].base_url, API_SOURCES["gazette"].authority, NOT_A_PAGE),
        # ... page rows
    },
    # "cantonal", "municipal": page rows
}
```

```python
# zefix/sources/lindas.py
class LindasClient:
    def __init__(self, endpoint: str = settings.lindas_endpoint, timeout_s: float = settings.lindas_timeout_s): ...
    async def find_by_uid(self, uid: str, *, budget_s: float) -> Company | None: ...
    async def search_by_name(self, name: str, *, canton: str | None = None, limit: int = 10, budget_s: float) -> list[Company]: ...
    async def dataset_modified(self) -> str | None: ...

# zefix/sources/zefix.py
class ZefixClient:
    def __init__(self, base_url=..., username=..., password=..., timeout_s=..., respect_robots_txt=...): ...
    def enrichment_allowed(self) -> bool: ...
    async def firm_detail(self, ehraid: int, *, budget_s: float) -> Enrichment: ...

# zefix/sources/gazette.py
class GazetteClient:
    def __init__(self, base_url: str = settings.gazette_base_url): ...
    async def publications_for_uid(self, uid: str, *, limit: int, budget_s: float, language: str, rubrics: list[str]) -> list[Publication]: ...
    async def rubrics(self) -> dict: ...

# zefix/gates.py
Reason = Literal["persons", "jurisdiction", "analytics", "topic"]
def classify(question: str | None, uid: str | None, canton: str | None, has_identifier: bool) -> Reason | None: ...

# zefix/lookup.py
class CompanyLookup:
    def __init__(self, lindas: LindasClient | None = None, zefix: ZefixClient | None = None,
                 gazette: GazetteClient | None = None, config: Settings | None = None): ...
    async def lookup(self, *, question, name, uid, canton, language, include_publications, max_publications) -> dict: ...

# tools/company_info.py
@mcp.tool
async def company_info(question=None, name=None, uid=None, canton=None, language="de",
                       include_publications=True, max_publications=5) -> dict:
    """<docstring unchanged>"""
    return await CompanyLookup().lookup(question=question, name=name, uid=uid, canton=canton,
                                        language=language, include_publications=include_publications,
                                        max_publications=max_publications)
```

Rules:

- Constructors take plain values, default from `settings` at construction time. Nothing reads `settings` at call time after construction, so a test constructs `ZefixClient(respect_robots_txt=False)` instead of patching settings.
- `CompanyLookup(config=...)` needs only `call_budget_s`, `lindas_timeout_s`, `zefix_timeout_s`, `lindas_endpoint`; pass a `Settings` instance, defaults to the module `settings`.
- `settings.allowed_hosts` is removed; `http.allowed_hosts()` returns `sources.api_hosts()`. An endpoint override in settings must stay within a registered host or every call is `egress_denied` (already the crawler's rule).
- `settings.lindas_endpoint`, `zefix_base_url`, `gazette_base_url` default to the matching `API_SOURCES[*].base_url`.
- Module-level pure helpers and dataclasses keep their vendored names and positions so `diff` against `register-mcp` stays readable (D8).

## 6. Tests

| Code | Change |
|---|---|
| T1 | `tests/conftest.py`: `patch_sources` and `settings_override` replaced by `FakeLindas`, `FakeZefix`, `FakeGazette` (same method names, canned returns or raised `SourceUnavailable`) and a `lookup(**fakes)` helper that builds `CompanyLookup(lindas=..., zefix=..., gazette=..., config=Settings(...))`. |
| T2 | `tests/test_company_info.py`: every test calls `CompanyLookup.lookup()` through T1; assertions unchanged. Gate tests import `zefix.gates`. |
| T3 | `tests/test_zefix_sources_*.py`: imports point at `zefix.sources`; instantiate the client class; respx routes unchanged. |
| T4 | New `tests/test_company_info_registration.py`: `mcp.get_tool("company_info")` is registered, its input schema lists the seven parameters, one fixture-backed call through the tool wrapper returns `status="answered"`. Follows `test_public_data_tools_are_registered`. |
| T5 | New `tests/test_sources.py`: every `API_SOURCES` host is in `http.allowed_hosts()`; `crawler.check_url("federal", API_SOURCES["zefix_lindas"].base_url)` allows the URL; a `Crawler.crawl` of `"zefix_lindas"` fails validation and saves nothing. |
| T6 | Acceptance: `uv run --frozen --extra dev pytest` green; `uv run --frozen --extra dev pytest -m live` green; opencode smoke (`opencode run --auto`, server `mcp-swiss-info`) answers Q1, Q3, Q5, Q7 of the companion PRD §4 with the same envelopes as before the refactor. |

## 7. Risks

| Code | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Submission round 1 closes Fri 2026-09-25 12:00. A half-done refactor on `victor-dev` ships broken. | medium | high | Work on a branch off `victor-dev`; merge only when T6 is green. If not green by Thu 22:00, PR #7 ships as is and the branch lands after. |
| R2 | Merge conflicts in D7: `tools/__init__.py`, `README.md`, `tests/` layout, `pyproject.toml`. | certain | low | Resolve once, first (S1), before any file moves. |
| R3 | Behaviour drift while moving ~600 lines. | medium | high | D6: move, do not edit. Run the suite after each step. Compare the four smoke envelopes field by field. |
| R4 | Turning vendored module functions into methods weakens `diff` against `register-mcp`. | certain | low | Keep names; a one-line note in each module header states the class wrapper. |
| R5 | `settings` defaults now import from `sources.py`; an import cycle if `sources.py` ever imports settings. | low | low | `sources.py` stays import-free (it is today). |

## 8. Open questions

| Code | Question | Default |
|---|---|---|
| Q1 | Rename `zefix/sources/zefix.py` to `rest.py` to remove the `zefix.sources.zefix` stutter? File name only; vendored names inside stay (N3). | Yes, during S2, while paths move anyway. |
| Q2 | Align `main`'s bfs/geo/opendata/weather/health tools to the contract's five states? | Separate PRD after submission. |
| Q3 | Land the refactor before or after the Friday submission? | Before, gated by R1. |

## 9. Plan

| Step | Work | Est. |
|---|---|---|
| S1 | Merge `origin/main` into `victor-dev`; resolve `tools/__init__.py`, README, tests; suite green | 0.5 h |
| S2 | Create `zefix/`; move `envelope.py` and `zefix_sources/` into it with history; rewrite the imports listed in §4; no other edits; suite green; own commit | 0.5 h |
| S3 | `sources.py`: `ApiSource`, `API_SOURCES`, `api_hosts()`; `zefix/sources/http.allowed_hosts()` reads it; settings defaults from it; drop `allowed_hosts` field; T5 | 0.5 h |
| S4 | `LindasClient`, `ZefixClient`, `GazetteClient`; T3 | 1.5 h |
| S5 | `zefix/gates.py` with `classify()`; move the three translated tables to `zefix/envelope.py` | 0.5 h |
| S6 | `zefix/lookup.py`: `CompanyLookup` with the resolution and envelope assembly; T1, T2 | 1.5 h |
| S7 | `tools/company_info.py` reduced to the wrapper; `@mcp.tool`; T4 | 0.25 h |
| S8 | Rewrite `docs/prd-zefix-company-info.md` §8 and README "Data sources" to the new tree; live tests; opencode smoke (T6) | 0.75 h |

Total ≈ 6 h. S2 is a pure move and lands as its own commit. S3, S4, S5 are independent after S2; S6 depends on S3–S5; S7 on S6; S8 last.

Verification rule: the implementer's report is a claim; the suite, the live run and the smoke envelopes are the evidence.
