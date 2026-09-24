# Swiss sources — technical accessibility analysis

> Research from a separate Node/TypeScript rehearsal. Source findings remain useful,
> but the referenced datasets, scripts, and server are not present in the current Python
> repository; see [STATUS.md](STATUS.md). Quoted source passages stay in their original
> language so they can be checked against the source.

> **Purpose**: what can actually be queried in ~28 hours, with what effort, with what freshness.
> Complements [CHALLENGE.md](CHALLENGE.md), which covers Swisscom requirements.
>
> **Verified date**: 2026-09-21 · **Method**: Real HTTP calls, not web search
>
> **Legend**: 🟢 verified hands-on · 🟡 documented but not tested by us · 🔴 verified as a blocker

---

## 1. The fundamental law of this domain

**Where structured open data exists, there are no sample questions.
Where there are sample questions, there is no open data.**

Numbers verified on `opendata.swiss` (16'040 total datasets):

| Queries | Datasets found | Municipalities/cantons in CH |
|---|---|---|
| `entsorgungskalender` | **9** | ~2'100 municipalities |
| `abfall` | 122 | ~2'100 municipalities |
| `schulferien` | **5** | 26 cantons |

Swisscom chose municipal waste collection and school holidays as sample topics.
**Federal open data does not cover them.** The answers live on municipal and cantonal
websites, often in HTML or PDFs.

This is exactly the point of slide 3 in the briefing:
> *"Invisible data: the answer sits in an API, a dataset table or a PDF annex that search
> does not surface."*

**Design consequence**: a wrapper around `opendata.swiss` misses these sample questions.
A server that reads municipal HTML and PDFs can answer them. That takes more work,
but addresses the harder cases in the hidden set.

---

## 2. Master table: 16 topic area × real accessibility

Effort is our estimate for credible coverage, not perfection.

| # | Topic | Access | Format | Auth | Freshness | Effort |
|---|---|---|---|---|---|---|
| 1 | **Health insurance premiums** | 🟢 Official CSV BAG | CSV/XLSX | no | updated 2026-09-11 | **Low** |
| 2 | Cantonal taxes | 🔴 26 different systems | HTML/PDF/calculators | no | annual | Very high |
| 3 | **Federal law** | 🟢 SPARQL Fedlex | RDF/HTML | no | continuous | **Medium** |
| 4 | **Waste collection** | 🔴 fragmented | HTML/PDF/ICS | varies | weekly | High for municipality |
| 5 | Domicile notification | 🟡 municipal sites only | HTML | no | rare | Medium per municipality |
| 6 | Residence permits | 🟡 sem.admin.ch | HTML/PDF | no | rare | Medium |
| 7 | AHV/IV pensions | 🟡 ahv-iv.ch memento | HTML/PDF | no | annual | Medium |
| 8 | Work/unemployment | 🟡 arbeit.swiss | HTML | no | rare | Medium |
| 9 | **School holidays** | 🔴 26 cantons, PDF | Partial PDF/ICS | no | annual | High |
| 10 | **Public transport** | 🟡 OJP 2.0 / GTFS-RT | XML/protobuf | **API key** | realtime | Medium |
| 11 | Licenses/vehicles | 🟡 26 cantonal offices | HTML | no | rare | High |
| 12 | **Reference rate** | 🟡 BWO page | HTML | no | quarterly | **Very low** |
| 13 | **Voting** | 🟡 VoteInfo JSON | JSON | no | by vote | Low |
| 14 | **Business register** | 🔴 Zefix = HTTP 401 | JSON | **account** | continue | Low + credential |
| 15 | Customs | 🟡 bazg/Tares | HTML | no | rare | Medium |
| 16 | **Statistics** | 🟡 PxWeb BFS | JSON/PX | no | varies | Low |
| — | **Geo/municipalities** | 🟢 geo.admin.ch | JSON | no | continuous | **Very low** |
| — | **Open data catalog** | 🟢 CKAN | JSON | no | continuous | **Very low** |

---

## 3. Hands-on verified sources

### 3.1 🟢 swisstopo SearchServer — the jurisdiction resolver

**This is the foundation.** Resolves municipality name → BFS number + canton, without auth.

```sh
curl "https://api3.geo.admin.ch/rest/services/api/SearchServer?searchText=Scuol&type=locations&origins=gg25&limit=3"
```

Verified Answer:
- `Scuol (GR)` → `featureId: 3762`, lat/lon, bounding box
- `Lugano (TI)` → `featureId: 5192`

`featureId` = **UFS number of the municipality**. `origins=gg25` limits to official municipal boundaries.
It also supports postcodes, addresses, districts, parcels.

**Why it matters**: 90% of local questions ask first to establish *which* municipality and
*which* canton. Without this step, every municipal response is a gamble. With this,
becomes a deterministic lookup — and allows you to distinguish "ambiguous municipality →
ask" da "municipality solved → proceed", which is the ask-back rule of §5.4 of CHALLENGE.md.

### 3.1b 🔴 swisstopo fuzzy solves the wrong municipality; the resolver is offline

Verified the 2026-09-23. `SearchServer?searchText=Wengen&origins=gg25` replies
**`Wengi (BE)`** with `"fuzzy":"true"`. Wengen is not a municipality: it is a locality of
**Lauterbrunnen**. Fuzzy search silently returns a real and wrong municipality,
and with `origins=zipcode` Wengen gives no results. Hence the decision (user,
2026-09-23): **offline-only solver**, built in build-time by
`scripts/build_places.py` to `data/places.json`, without fuzzy.

Sources, all without credentials:
- **BFS register** at 01.01.2026 (`agvchapp.bfs.admin.ch/api/communes/levels` and `/snapshot`):
  2110 municipalities, canton, linguistic region;
- **BFS mutations** from 2000 (`/mutations`): the historical names. Plagne → Sauge is obtained
  following the chain of historical codes, because the mutations also include the simple ones
  district changes (same name, new historical code);
- **official location list** swisstopo (`ortschaftenverzeichnis_plz`, 5718
  rows): locality and postcode → municipality, **with the share of addresses**. Wengen → Lauterbrunnen
  100 %; Engelberg → 93 % Engelberg, the rest NW and UR;
- **SR 832.106 Anhang 1**: premium region by municipality.

Three traps found while building it:
- **The Fedlex table should be read as a table.** A text line parser was missing 43
  municipalities, long names with `<br>` ("Neuhausen am Rheinfall"). The first "Anhang 1" of
  document is in the text of the art. 1, not in the attachment header.
- **Ordinance and register diverge where the art. 3 predicts it.** Fétigny-Ménières (born on
  01.01.2026) has no region in Anhang; its former municipalities yes, both 2 region.
  Gurmels absorbed the 2278, same region. The build applies the art. 3 and notes it;
  if the former municipalities had different regions, the region would depend on the address.
- **Build consistency check blocked data writing twice**, ed
  both times for a real defect (the parser, then the item 3). It should not be removed.

They are not resolved, and it is declared: the neighborhoods that are not official locations
(Oerlikon), city names in another language (Genf as city; as canton yes).
Outside Switzerland (Konstanz): `not_found`, which is what it takes to say "it is not in
Switzerland". Self-check in `test/place-test.ts`.

### 3.2 🟢 BAG health insurance premiums — the easy victory

The sample question #3 (Lugano, 30 years, deductible 2500) is **completely resolvable by
an official CSV**.

Dataset: `health-insurance-premiums` on opendata.swiss, publisher **Bundesamt für
Gesundheit BAG**, legal basis cited (`fedlex.admin.ch/eli/cc/2015/840 art. 71`).
**Edited 2026-09-11** — very fresh.

Verified files behind `opendata.bagnet.ch`:
```
/Praemien/Prämien_CH.csv          ← premiums
/Praemien/Einzugsgebiete.csv      ← insurer operating areas (NOT premium regions)
/Praemien/Tarife.csv              ← insurance model catalogue
/Praemien/Archiv_Praemien_2026.zip
/Praemien/Erläuterungen zu den Prämiendaten.xlsx
```

Real header of `Prämien_CH.csv` (verified):
```
Versicherer, Kanton, Hoheitsgebiet, Geschäftsjahr, Erhebungsjahr, Region,
Altersklasse, Unfalleinschluss, Tarif, Tariftyp, Altersuntergruppe,
Franchisestufe, Franchise, Prämie, isBaseP, isBaseF, Tarifbezeichnung
```

All question dimensions are columns: canton, region, age class, deductible,
premium.

> ⚠️ `Tarife.csv` **does not** contain the premiums: it is the product catalogue. The right file is
> `Prämien_CH.csv`.

#### 🔴 Correction: the above are logical paths, not URLs

Verified the 2026-09-22 by building the coverage manifest.
`https://opendata.bagnet.ch/Praemien/Archiv_Praemien_2026.zip` returns **404**, and so
any other case variant. The files are not used for path: they are behind an endpoint
of download which takes the path **in base64**.

```
https://opendata.bagnet.ch/?r=/download&path=<base64 of the path>
L1ByYWVtaWVuL0FyY2hpdl9QcmFlbWllbl8yMDI2LnppcA%3D%3D  =  /Praemien/Archiv_Praemien_2026.zip
L1ByYWVtaWVuL1Byw6RtaWVuX0NILmNzdg%3D%3D              =  /Praemien/Prämien_CH.csv
```

The real URLs are obtained from the CKAN of opendata.swiss, which lists them all:

```sh
curl -sH 'User-Agent: <UA descrittivo>' \
  'https://opendata.swiss/api/3/action/package_show?id=health-insurance-premiums' \
  | grep -o 'https[^"]*bagnet[^"]*'
```

Verified on archive 2026: **31'923'906 byte**, `Content-Type: application/zip`,
magic `PK\x03\x04`.

> **The path that a dataset documents is not the address from which it is downloaded.** A list of
> file in a dataset tab describes the internal structure of the repository, not the API of
> access. This applies as a general rule for Swiss open data catalogues.

### 3.2b ⚠️ "live" files are empty stubs — the data is in the ZIP

**Correction to the above.** By downloading the published files in full:

| Published file | Actual size |
|---|---|
| `Prämien_CH.csv` | **201 byte — header only** |
| `Einzugsgebiete.csv` | **116 byte — header only** |
| `Prämien_CH.xlsx` | 9'426 byte — stub |
| **`Archiv_Praemien_2026.zip`** | **31'923'906 bytes ← the real data** |

Contents of the ZIP (15 file, 58 uncompressed MB):

```
Prämien_CH.csv                     22'545'492   ← 217'473 premium rows
Einzugsgebiete.csv                    209'347
Tarife.csv                             20'552
Erläuterungen zu den Prämiendaten.xlsx 21'629   ← field documentation
```

**Those who limit themselves to the URLs published on opendata.swiss get headers without data.**
The CKAN metadata says "modificato 2026-09-11" and that's true, but it refers to the record, not the
contents of the files.

> ⚠️ **Inconsistent separators within the same archive**: `Prämien_CH.csv` uses comma,
> `Einzugsgebiete.csv` uses semicolons. Both have a BOM UTF-8.

### 3.2c `Einzugsgebiete.csv` is not what it seems

Real header: `Versicherer;Kanton;Hoheitsgebiet;Geschäftsjahr;Erhebungsjahr;Region;Tarif;
Tariftyp;HMO-ID;Eingeschränkt;Gemeinden-BFS`

This is not a municipality → premium region map. Register **in which regions and with which rates
each insurer operates**, and if the offer is restricted to specific municipalities.

In the year 2026: **0 rows with `Eingeschränkt=J`**, so the column `Gemeinden-BFS` is
empty everywhere. The mechanism exists but is not used this year. However, it is useful for
check that the cheapest insurer actually operates in the requested region.

### 3.2d The municipality mapping → premium region is an ordinance

It lies in the **Verordnung des EDI über die Prämienregionen, SR 832.106**, attachment 1.
It is not in the BAG archive.

Copy served by BAG (26 pages, 1.6 MB, PDF):
`bag.admin.ch/dam/en/sd-web/x8IbM-bv0Ptd/Verordnung des EDI über die Prämienregionen DE_mit Kopfzeile.pdf`

Format: `<BFS> <Municipality name> <region>`. Verified row: **`5192 Lugano 1`**.

> 🔴 **Version trap, verified.** The PDF served by BAG states at the top:
> *"Dieser Text ist eine provisorische Fassung. Massgebend ist die definitive Fassung,
> welche unter www.fedlex.admin.ch veröffentlicht werden wird."*
> This is the **Änderung vom 28. August 2026**, which *"tritt am 1. Januar 2027 in Kraft"*.
>
> So: right document, right authority, **wrong reference year** if so
> use with 2026 premiums. And the document itself states that the authoritative one is Fedlex, not
> this copy. The premium regions **change**: there is a modification ordinance.

### 3.2d-bis 🟢 Fedlex is addressable by date — solves versioning problem

SR 832.106 has ELI `cc/2022/184`. The Fedlex **filestore** serves the consolidated text
**effective as of any date**, as static HTML, without SPA and without auth:

```
https://www.fedlex.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/2022/184/<YYYYMMDD>/de/html/fedlex-data-admin-ch-eli-cc-2022-184-<YYYYMMDD>-de-html.html
```

Verified on three dates:

| Version in force on | Bytes | Lugano |
|---|---|---|
| 01.01.2023 | 123'898 | **region 1** |
| 01.01.2025 | 268'353 | **region 1** |
| 01.01.2026 | 480'590 | **region 1** |

**This is the most important piece operationally found so far.** Applies to
any act of federal law, not only for this ordinance: transform "which
version was in effect in the reporting year" from hard problem to **parameter
in the URL**. It is the structural response to the freshness criterion for the entire level
federal, and makes the provisional copy served by BAG superfluous.

> ⚠️ The normal `fedlex.admin.ch/eli/...` page is a SPA: the `<title>` is always
> "Fedlex" and the content is not extracted with a GET. **Use the filestore, not the SPA.**

Substantial confirmation: Lugano is in the 1 premium region in all verified versions,
so the response of §3.2e does not change. But the verification must be done, not assumed.

#### 🔴 Fix: The date must be a real consolidation date

Verified on a second act, **VMWG SR 221.213.11**, ELI `cc/1990/835_835_835`:

| Requested date | Answer | Contents |
|---|---|---|
| `20251001` | HTTP 200, **45'554 byte** | real consolidated text, art. 12a readable |
| `20260101` | HTTP 200, **77'151 byte** | **SPA shell**, with `no-script-warning` |

**A date that does not correspond to an actual consolidation returns HTTP 200 with the
JavaScript skeleton, not an error.** Silent failure: status says OK, the
pipeline extracts no rows and reports "data not found" instead of "version does not exist".

Two defenses:
1. **77'151 byte is the shell signature** (identical on VZV 741.51 and on this attempt).
   Detect the `no-script-warning` marker before trusting the response.
   2026-09-22 reconfirmed on a third act, **VZV SR 741.51** (`cc/1976/2423_2423_2423`):
   `20260101` returns the real consolidated, `20250101` and `20240101` return
   **77'151 exact bytes**. `SR 832.106` to `20260101` is also real. Valid dates
   **differ from act to act**: there is no one date that works for everyone.
2. Valid consolidation dates are obtained from the Fedlex **SPARQL** endpoint; the
   filestore doesn't list them.

The filestore remains the right tool, but **it cannot be queried with a date
arbitrary**: the version must be resolved first, then downloaded.

### 3.2e Sample question #3, resolved end-to-end

*"What is the lowest monthly basic insurance premium for an adult aged 30
domiciled in Lugano with an excess of 2500 francs?"*

Chain: Lugano → BFS 5192 → TI premium region 1 → filter on `Prämien_CH.csv`
(`Kanton=TI`, `Region=PR-REG CH1`, `Altersklasse=AKL-ERW`, `Franchise=FRA-2500`).

Result for the year **2026**:

| Interpretation | Injury-free | With injuries |
|---|---|---|
| Any model (the cheapest is `TAR-DIV`, AGRIsmart, insurer 1560) | **CHF 449.90** | CHF 473.60 |
| Standard model only (`TAR-BASE`, "Grundversicherung") | CHF 523.20 | CHF 550.70 |

Verified that the insurer 1560 operates in TI region 1 with `Eingeschränkt=N`, therefore
the offer is available in Lugano.

**Three ambiguities that the question does not resolve** and which change the answer:

1. **Accident cover**: difference of CHF 23.70/month. Anyone who is dependent is already covered
   by the employer and chooses `OHN-UNF`.
2. **"Assicurazione di base"**: if it means compulsory (which includes models
   alternatives) → 449.90; if it means the standard model → 523.20. **CHF 73/month of
   difference.** In Italian the first reading is the current one.
3. **Year**: Data available at 2026-09-21 arrives at 2026. The archive 2027 **not
   still exists**. The BAG publishes the following year's premiums towards the end of September —
   i.e. **potentially during the 24–25 September 2026 hackathon**.

The correct answer specifies the reference year and at least the assumption on
injuries. This is the case `rate_freshness` applied to another theme.

### 3.2f 🟢 Mortgage Reference Rate — verified end-to-end

Second federal theme of our scope. Verified the 2026-09-21.

**Source**: `referenzzinssatz.admin.ch` → redirect to `bwo.admin.ch/de/referenzzinssatz`.
DE/FR/IT versions. No open data: `referenzzinssatz` on CKAN = **0 results**.

**Current value**: **1,25 %**

**Legal basis**, retrieved from Fedlex: **VMWG art. 12a**, *Verordnung vom 9. Never 1990
über die Miete und Pacht von Wohn- und Geschäftsräumen*, **SR 221.213.11**,
ELI `cc/1990/835_835_835`. Text:

> *"Für Mietzinsanpassungen aufgrund von Änderungen des Hypothekarzinssatzes gilt ein
> Referenzzinssatz. Dieser stützt sich auf den vierteljährlich erhobenen,
> volumengewichteten Durchschnittszinssatz für inländische Hypothekarforderungen und wird
> durch kaufmännische Rundung ermittelt."*

Complementary standard: *Verordnung des WBF vom 22. Januar 2008 beyond the Erhebung des für
die Mietzinse massgebenden hypothekarischen Durchschnittszinssatzes*. For adaptation
of the fee: VMWG art. 13 para. 1 read. c; CO art. 269d, 266c, 270b.

#### 🔴 The catch: four dates for one number

The historical table has four columns — rate, *gültig ab*, average underlying rate,
*Stichtag der Erhebung*. The last lines:

| Rate | Gültig ab | Durchschnittszinssatz | Stichtag |
|---|---|---|---|
| 1,25 % | **02.09.2026** | 1,31 % | 30.06.2026 |
| 1,25 % | 02.06.2026 | 1,31 % | 31.03.2026 |
| 1,25 % | 03.03.2026 | 1,32 % | 31.12.2025 |
| 1,25 % | 02.12.2025 | 1,33 % | 30.09.2025 |
| 1,25 % | **02.09.2025** | 1,37 % | 30.06.2025 |
| 1,5 % | 03.06.2025 | 1,44 % | 31.03.2025 |

The last line says *"gültig ab 02.09.2026"*. Copy it and reply **"1,25 % valid from
2 September 2026"** is **substantially wrong**: that is the date of the last
quarterly publication, which *confirmed* the rate. The rate went from 1,5 % to
1,25 % on **02.09.2025** and has been unchanged since then. This is the relevant date for an adjustment
of the fee.

The page says it correctly: *"gültig seit 02.09.2025, unverändert ab 02.09.2026"*.
**Whoever reads the table instead of the sentence is wrong, even though he cites the right source.**

Third date: *"Veröffentlicht am 1. September 2026"*, the publication date. Fourth: the
Detection *Stichtag*, 30.06.2026.

Methodological note to keep for historical questions: *"ab Dezember 2011 gemäss
kaufmännischer Rundung des Durchschnittszinssatzes"* — the rounding method is
changed in December 2011.

#### Freshness

Complete series from 10.09.2008 (3,5 %) to today. Upcoming publications: **01.12.2026**,
then 01.03/01.06/01.09/01.12.2027.

**No risk of freshness during the hackathon**: The next possible variation is
in December. Unlike health insurance premiums, which could be released during the event.

#### ⚠️ The page is a Nuxt SPA

`curl` returns the JavaScript payload, not the table. Rendering needed.

But it is **only one number that changes at most 4 times a year**: take care of it at the build with URL,
value, effective date and publication date is entirely appropriate and not
requires a browser on the server.

### 3.3 🟢 opendata.swiss CKAN — the catalog, not the data

```sh
curl -A "<nostro-user-agent>" "https://ckan.opendata.swiss/api/3/action/package_search?q=<query>&rows=0"
```

16'040 dataset. Useful as a **discovery index**, not as a source of answers:
most records point to files to download, not queryable endpoints.

🔴 **Checked Trap**: Without explicit `User-Agent` returns **HTTP 403** (nginx).
With a descriptive User-Agent it works. Valid as a *source etiquette* requirement:
always identify yourself.

### 3.4 🔴 Zefix — requires credential

```sh
curl -X POST "https://www.zefix.admin.ch/ZefixPublicREST/api/v1/company/search" ...
→ HTTP 401
```

Public REST API but with Basic auth on free account. Swagger:
`https://www.zefix.admin.ch/ZefixPublicREST/swagger-ui/index.html`

**Trade-off**: covers the 14 topic with little code, but introduces a credential to deliver
to Swisscom via secure channel and penalizes operability (§10 CHALLENGE.md: *"a server that
runs without any external keys... shows in the operability assessment"*).

### 3.5 🟡 Fedlex — SPARQL, no auth

- Endpoint: `https://fedlex.data.admin.ch/sparqlendpoint` (GET and POST)
- JOLux data model, documentation: `https://swiss.github.io/fedlex-jolux/`
- Free reuse, including commercial

Covers topic 3 with **stable ELI citations** — exactly the kind of reference that the
practice case `citation_support` requires. Cost: SPARQL/JOLux learning curve.

### 3.6 🟡 More confirmed for documentation

| Source | Endpoints | Notes |
|---|---|---|
| BFS PxWeb | `https://www.pxweb.bfs.admin.ch/` | ~682 dataset, 21 themes, no auth, multilingual DE/FR/IT/EN |
| VoteInfo | via CKAN `echtzeitdaten-am-abstimmungstag-...` | JSON, historical on bfs.admin.ch, upcoming on S3 |
| OJP 2.0 / GTFS-RT | `api-manager.opentransportdata.swiss` | **requires API key**, time 2026 available |
| Reference rate | `referenzzinssatz.admin.ch` → `bwo.admin.ch/de/referenzzinssatz` | 🟢 redirect verified. HTML only, no API. A single quarterly value |

---

## 4. Traps verified in the field

### 4.1 🔴 The obvious domain is the wrong one

```
scuol.ch   → HTTP 200 → redirect to engadin.com (tourism site)
scuol.net  → HTTP 200 → official municipal site
```

A "municipality name + .ch" heuristic leads to a commercial tourism site presented as
authoritative. It is literally the failure described in the briefing. **A registry is required
municipality → verified official domain**, not a URL construction rule.

### 4.2 🔴 The authoritative source is a PDF

Scuol school holidays 2026, verified official source:
```
https://www.gr.ch/DE/institutionen/verwaltung/ekud/avs/Volksschule/SB_Ferienplaene_2026_2027_de.pdf
→ HTTP 200, application/pdf, 77'418 byte
```

The canton GR publishes the holiday plan as a PDF per municipality. No API, no ICS
cantonal. **Anyone who can't read PDFs won't answer this sample question.**

Note: aggregator sites such as `schulferien.org`, `feiertagskalender.ch`, `localcities.ch`
they have the data but **are not authoritative** — they are exactly what the checklist points out 3
excludes (*"not merely an official Swiss domain"* — these aren't even that).

### 4.3 🟡 ch.ch doesn't need a real robots.txt

```
GET https://www.ch.ch/robots.txt → HTTP 200, content-type: text/html
```

Returns the SPA shell. A naive robots.txt parser interprets this as rules
valid or it goes into error. Since compliance with robots.txt is a **configurable requirement
mandatory** (§4 CHALLENGE.md), the parser must handle: absence, HTML instead of text,
404, timeout.

### 4.4 🔴 No User-Agent = 403

Verified on `ckan.opendata.swiss`. As a general rule: every outgoing request
must have an identifiable UA with contact reference.

---

## 5. Competitive landscape: Existing Swiss MCP servers

Relevant on two fronts: **originality** (jury criterion 4) and **reuse**.

| Repo | Coverage |
|---|---|
| `malkreide/swiss-public-data-mcp` | portfolio, simap.ch procurement |
| `malkreide/swiss-statistics-mcp` | BFS STAT-TAB PxWeb, 682 dataset, no auth |
| `malkreide/amtsblatt-mcp` | SHAB + cantonal official sheets |
| `malkreide/zurich-opendata-mcp` | Open Data Zurich, 20 tool |
| `JayTheSkier/fedlex-connector` | federal legislation Fedlex |
| `vikramgorla/mcp-swiss` | transport, weather, geodata, businesses, zero API key |
| `pipeworx-io/mcp-opendata-swiss` | CKAN catalog opendata.swiss |

**Reading**: They are mostly **thin wrappers on already structured APIs**. None, basically
to public descriptions, addresses the problem that Swisscom really values — resolution of
jurisdiction, extraction of the evidentiary passage, effective date, regulated ask-back,
honesty out of scope. Easy APIs are already covered by others; the differentiating value lies in
level of grounding, not in the number of sources.

To check before the event: if the licenses allow reuse, take the layer of
transport from one of these instead of rewriting it is consistent with the available time.

---

## 6. Scope options — explicit trade-offs

No recommendation: Scope choice is a product decision.
Reference: *"high quality with narrow coverage is preferred over a broad solution with
low quality"*.

### Option A — Deep vertical on a canton/city
*E.g.: "all municipal topics for the City of Zurich/Lausanne"*
- **Pro**: rich municipal open data (Zurich has Open ERZ API for waste, dataset
  school holidays until 2029/30); demonstrable quality; controllable freshness
- **Cons**: minimum breadth; many questions from the hidden set will fall out of scope, therefore
  the score depends almost entirely on the quality of the off-scope honesty
- **Risk**: if the hidden set is distributed throughout the CH, very little is responded to

### Option B — Horizontal on structured federal issues
*E.g.: "health insurance premiums, federal law, statistics, voting, across Switzerland"*
- **Pro**: the whole country covered; structured and fresh data; low effort per theme;
  strong quotes (ELI Fedlex, CSV BAG with legal basis)
- **Cons**: **all municipal level is missing**, which is where Swisscom put 2 questions
  sample on 5; it risks looking like the wrapper that others have already done
- **Risk**: Low originality, and the `missing_location` case never gets exercised

### Option C — Hybrid: federal backbone + selective municipal depth
*E.g.: "federal topics across Switzerland + waste/schools/residence for N declared municipalities"*
- **Pro**: covers both families of sample questions; exercises ask-back,resolution
  of jurisdiction and PDF reading; real breadth and demonstrable quality
- **Cons**: the most expensive; requires both structured pipeline and HTML/PDF extraction
- **Risk**: in 28h you risk doing two things badly instead of doing one well

### Option D — Meta-layer routing to the competent authority
*E.g.: "for any Swiss question, identify the responsible authority and the page
exact, with extraction of the passage where possible"*
- **Pro**: maximum breadth that can be declared; use ch.ch as a competence map; original
- **Cons**: risks returning "vai qui" instead of an answer; the jury evaluates
  *correct answers*, and a pointer is not an answer
- **Risk**: the 1 criterion penalizes exactly this

**Dimension transversal to each option**: whatever scope we choose, the four
§15 behaviors of CHALLENGE.md (quoted response / precise ask-back / out of scope /
unreachable source) must be implemented. They are the real product.

---

## 7. Reference data on jurisdictions 🟢

All numbers in this section come from the **official BFS register of municipalities**
(standard eCH-0071), snapshot **01-01-2026**, downloaded and counted by us.

### 7.1 Reproducible source and commands

```sh
# official register, dated snapshot, CSV, no authentication
curl -A "<nostro-user-agent>" \
  "https://www.agvchapp.bfs.admin.ch/api/communes/levels?date=01-01-2026" -o comuni.csv
```

Relevant columns: `BfsCode` (UFS number), `Name`, `Canton`, `District`,
`SPRGEB2020` (language region: `1`=DE, `2`=FR, `3`=IT, `4`=RM).

```sh
awk -F',' 'NR>1 {c[$5]++} END {for (k in c) print k, c[k]}' comuni.csv   # by canton
awk -F',' 'NR>1 {s[$20]++} END {for (k in s) print k, s[k]}' comuni.csv  # by language
```

> ⚠️ The language field is the **column 20**, not the 21 (the 21 is `AGKSA2020`, agglomerations).
> Health audit: Bern→1, Lausanne→2, Lugano→3, Scuol→4.

### 7.2 Total: 2'110 municipalities

The number drops over time due to municipal mergers: any count found elsewhere goes
dated. Secondary sources cite 2'202 (2020) and 2'172 (2021).

### 7.3 Municipalities by canton

Sorted by cost of full coverage. **Verified sum = 2'110.**

| Canton | Municipalities | | Canton | Municipalities | | Canton | Municipalities |
|---|---|---|---|---|---|---|---|
| BS | **3** | | SH | 26 | | BL | 86 |
| GL | **3** | | SZ | 30 | | GR | 100 |
| AI | **5** | | GE | 45 | | TI | 100 |
| OW | **7** | | JU | 51 | | SO | 104 |
| NW | **11** | | SG | 75 | | FR | 119 |
| ZG | **11** | | LU | 79 | | VS | 122 |
| UR | **19** | | TG | 80 | | ZH | 160 |
| AR | **20** | | | | | AG | 196 |
| NE | 24 | | | | | VD | 300 |
| | | | | | | BE | 334 |

**Completable cantons** within a realistic research budget (≤26 municipalities): BS, GL, AI,
OW, NW, ZG, UR, AR, NE, SH. The six smallest together make **40 municipalities**, but they are all
German speakers except NE.

### 7.4 Municipalities by linguistic region

| Region | Municipalities | Cost of a “full area” claim |
|---|---|---|
| German | 1'374 | out of reach |
| French | 606 | out of reach |
| Italian | 115 | to the limit |
| **Romance** | **15** | **within reach** |

**Verified sum = 2'110.**

### 7.5 The 15 municipalities of the Romansh linguistic region

All in Grisons, concentrated in **3 administrative clusters**. Includes Scuol, which
Swisscom has included sample questions.

| BFS | Municipality | Region |
|---|---|---|
| 3981 | Breil/Brigels | Surselva |
| 3982 | Disentis/Muster | Surselva |
| 3572 | Falera | Surselva |
| 3618 | Lumnezia | Surselva |
| 3983 | Medel (Lucmagn) | Surselva |
| 3581 | Sagogn | Surselva |
| 3582 | Schluein | Surselva |
| 3985 | Sumvitg | Surselva |
| 3987 | Trun | Surselva |
| 3986 | Tujetsch | Surselva |
| **3762** | **School** | Lower Engiadina / Val Müstair |
| 3847 | Val Müstair | Lower Engiadina / Val Müstair |
| 3764 | Valsot | Lower Engiadina / Val Müstair |
| 3746 | Zernez | Lower Engiadina / Val Müstair |
| 3788 | S-chanf | Maloja |

Possible regional aggregator to check: `regiunebvm.ch` (Regiun Engiadina Bassa
Val Müstair) could cover 4 of 15 with a single source.

### 7.6 Competence over waste: cantonal by law, municipal in fact

**USG art. 31b** assigns responsibility for the disposal of urban waste to the cantons,
but the cantons **delegate collection and financing to the municipalities. Legal basis: USG (SR 814.01)
art. 30 ss., VVEA (SR 814.600).

Operational consequence: **the collection calendar is published by the municipality or by a
intermunicipal consortium. There is no cantonal waste calendar to query.**
Any "cantonal waste" strategy is unsourced.

### 7.7 No waste multiplier

Searched for a dominant provider to integrate once to cover many: **does not exist**.
The market is fragmented between Trennio, Sammelkalender, A-Region and its own solutions
of large cities. The cost per municipality remains linear.

### 7.8 ⚠️ The Localcities Trap

`Localcities` covers all municipalities ~2'200 with waste calendar included, and is
**Swisscom Directories**. It's the most convenient shortcut in the domain and it's **the answer
wrong**: it is an aggregator, not the body responsible for the matter. The review checklist
dot 3 explicitly excludes it.

The same applies to `schulferien.org`, `feiertagskalender.ch`, `localcities.ch` on
school holidays: they have the data, they don't have the authority.

---

## 8. Cantonal sampling: school holidays 🟢

Five cantons in three languages, verified by downloading and reading the sources on 2026-09-21.
**Result: five cantons, five different models. No homogeneity.**

### 8.1 The five models

| Canton | Model | Granularity | Format | Autumn holidays 2026 |
|---|---|---|---|---|
| **VD** | single multi-year table 2022→2031 | uniform on the canton | PDF 1 page | **10–25 October** |
| **TI** | list in prose, one year per document | uniform on the canton | PDF 1 page | **31 October – 8 November** |
| **GR** | table by municipality, 164 rows | by municipality | PDF 8 pages, trilingual | School **10–25 October** |
| **BE** | DIN rule + resolved dates + exceptions | mixed | 2 PDF | **19.09 – 11.10.2026** |
| **ZH** | delegation to school municipalities | school municipality | HTML page | **not determinable** |

### 8.2 Sources verified

| Canton | URL | Status |
|---|---|---|
| VD | `vd.ch/fileadmin/user_upload/themes/formation/Vacances_scolaires/def_calendrier_vacances_scolaires_2023_2031.pdf` | 200, PDF, 124 KB |
| TI | `www4.ti.ch/fileadmin/DECS/calendario_scolastico/Calendario_scolastico_2026_2027.pdf` | 200, PDF, 178 KB |
| GR | `gr.ch/DE/institutionen/verwaltung/ekud/avs/Volksschule/SB_Ferienplaene_2026_2027_de.pdf` | 200, PDF, 77 KB |
| BE rule | `akvb-gemeinden.bkd.be.ch/.../schulferien-kanton-bern-d.pdf` | 200, PDF, 122 KB |
| BE exceptions | `akvb-gemeinden.bkd.be.ch/.../schulferien-kanton-bern-bewilligte-ausnahmen-d.pdf` | 200, PDF, 116 KB |
| ZH | `zh.ch/de/bildung/bildungssystem/schulferien.html` | 200, HTML |

> `ti.ch` HTML pages have anti-bot protection, but **the PDF can be downloaded without
> obstacles**. Always check the final resource, not the page that hosts it.

### 8.3 Proof that canton inference is lethal

Same year, same country, same theme:

- Vaud: 10–25 October (2 weeks)
- Ticino: 31 October – 8 November (1 week, **3 weeks later**)
- Bern: 19 September – 11 October (3 weeks, **the longest and earliest**)

The `romansh_locality` practice case prohibits deductions from another canton. These are the
numbers showing the magnitude of the error.

### 8.4 Bern: the rule and its reservations

The PDF contains both the rule and the resolved dates up to 2031/32:

```
Herbstferien     Wochen 39 bis 41
Winterferien     Wochen 52 und 1
Februar-Ferien   Woche frei wählbar (DIN-Wochen 2 bis 14)
Frühlingsferien  Wochen 15 und 16
Sommerferien     Wochen 28 bis 32

2026/27  Herbstferien  Sa, 19.09.2026 - So, 11.10.2026
```

Reserves, all verified in the document:

- applies **only for the German-speaking part**; the francophone follows BEJUNE, separate document
- **the February holidays are chosen by each municipality** (DIN 2–14) → non-cantonal
- Alpine tourist municipalities choose spring holidays (DIN 15–21)
- **Biel + Evilard, Orvin, Plagne, Romont, Vauffelin alternate** German system (years
  even) and French (odd years)
- a second PDF lists ~16 municipalities with exceptions: Boltigen, Gsteig b/Gstaad, Lauenen,
  Saanen, St. Stephan, Zweisimmen, Lenk, Adelboden, Erlenbach, Därstetten, Diemtigen,
  Oberwil i/S, Golaten, Gurbrü, Münchenwiler, Wil…

**In the same canton, for the same theme, the granularity changes according to the type of
holiday**: Herbstferien is cantonal, Februar-Ferien is municipal.

### 8.4b Bern has TWO calendars, per linguistic region

Verified French-speaking source (2 pages, 5'216 characters, 200):
`akvb-gemeinden.bkd.be.ch/.../fr/.../schulferien-kanton-bern-f.pdf`

Identical legal basis, different name: **LEO art. 8 al. 3, RSB 432.210** (in German:
VSG, BSG 432.210). Holidays are *"harmonisées par région linguistique"*.

| | German-speaking part | Francophone part |
|---|---|---|
| Municipalities (BFS register) | **299** | **35**, all in the Arrondissement Jura bernois |
| Reference | DIN perpetual calendar | **BEJUNE space** |
| **Autumn 2026** | **19.09 – 11.10** (3 week, week 39–41) | **05.10 – 16.10** (2 week, week 41–42) |
| Winter 2026/27 | 24.12.2026 – 10.01.2027 | 25.12.2026 – 08.01.2027 |
| Spring 2027 | 10.04 – 25.04 | 26.03 – 09.04 |
| White week | free (DIN 2–14) | free |

**Same canton, same theme, same year: two different answers, out of phase by two
weeks and of different lengths.** The key to solving school holidays
it is not the canton, nor even the municipality: it is **(canton × linguistic region × parity
of the school year × list of exceptions)**.

### 8.4c Biel/Bienne: bilingual, but classified as German-speaking

The alternation rule concerns Biel and five neighboring municipalities. Comparison with the register
BFS:

| Municipality cited | BFS | BFS linguistic region |
|---|---|---|
| Biel/Bienne | 371 | **1 = German** (although officially bilingual) |
| Evilard | 372 | 1 = German |
| Orvin | 438 | 2 = French |
| Romont (BE) | 442 | 2 = French |
| Plagne | — | **no longer exists** |
| Vauffelin | — | **no longer exists** |

For the year 2026/27 (starting in an even year) these municipalities follow the **German-speaking plan**:
Biel, autumn 2026 = 19.09 – 11.10.2026.

Attention: Biel's BFS language classification is "tedesca", therefore a routing
based only on that field it would give the right answer by chance, and the wrong one by chance
odd years. **The alternation rule must be read, not deduced.**

### 8.4d ⚠️ The cantonal document mentions municipalities that no longer exist

`Plagne` and `Vauffelin` **are not in the BFS register at 01-01-2026**: they merged into
**Sauge** (BFS 449). The Bernese document is dated 1° June / 1° July 2026 and lists them
again.

An authoritative and current source may contain **outdated jurisdiction names**. A
lookup by name fails on "Plagne", and the person asking for "Sauge" is not found in the document.

Defense: The **Historical Gemeindeverzeichnis** of the BFS maps dissolved municipalities to successors.
Endpoint already identified in §7.1:
`agvchapp.bfs.admin.ch/api/communes/mutations?...`
The jurisdiction resolver must handle both directions — historical name → municipality
current, and current municipality → historical names cited in documents.

### 8.4e BEJUNE: a calendar for three cantons (to be confirmed)

The French-speaking part of BE declares alignment with the space **BEJUNE** = Bern, Jura,
Neuchatel. Preliminary feedback for autumn 2026:

- French-speaking BE: 05.10 – 16.10.2026 ✅ *verified on the cantonal PDF*
- Neuchâtel: 5–16 October 2026 ⚠️ *only from aggregators*
- Jura: 5–16 October 2026 ⚠️ *only from aggregators*

If confirmed on authoritative sources, **only one calendar covers the French-speaking part of BE
plus all NE and all JU**, i.e. 35 + 24 + 51 = 110 municipalities with a single source.

> **Do not use this alignment until verified on `ne.ch` and `jura.ch`.**
> The sources found so far (`vacances-scolaires.ch`, `profcalendar.org`,
> `feiertagskalender.ch`) are aggregators, excluded from the checklist point 3. For the Jura
> the authoritative source is an arrêté from the cantonal government.

### 8.5 Zurich: total delegation

Text from the cantonal page:

> *"Im Kanton Zürich bestimmen die Volksschulen ihre Ferien und schulfreien Tage selbst.
> Nur der Schulbeginn und die Weihnachtsferien sind verbindlich."*

In the most populous canton of Switzerland, **only are binding at cantonal level
the start of the school year and the Christmas holidays**. 160 decides everything else
school municipalities. The «ewiger Ferienkalender» exists but is declared *Planungshilfe*,
not norm. Legal basis: BiG §7, VSV §32 para. 2 (LS 412.101).

**For a question scoped only to Zurich canton, the correct response is to ask back, not say "I do not know"**:
"in the canton of Zurich, each school municipality sets its own holidays; which municipality?", with
reference the page that states this. According to the rubric it is a correct answer.

### 8.6 Traps in the Grisons PDF

The case with the most pitfalls in the sample. All verified.

1. **Codes are not BFS numbers.** School in PDF is `330`, real BFS is `3762`.
   Verified on municipalities 7 (Arosa 107/3921, Bonaduz 115/3721, Zernez 335/3746,
   Valsot 328/3764…). **The join must be done by name, not by ID.**
2. **Duplicate rows**: 164 rows for municipalities 100, because the PDF contains both the table
   cantonal and tables by district. Needs dedup.
3. **Private schools with different dates**: `Privat Scoula Rudolf Steiner Scuol` has the
   sports holidays 27.02–07.03, the public school of Scuol 06.03–14.03. "The school from
   Scuol" is ambiguous, and the wrong line gives the wrong date **with the right source**.
4. **Noisy extraction**: `05.01.2 7`, `16. 08.27` — spurious spaces inside dates.
   Normalize before interpreting.
5. **Headings are trilingual, including Romansh**: `vacanzas d'atun`,
   `vacanzas da Nadal`, `vacanzas da sport`, `vacanzas da primavaira`. The exact formula
   of sample question #4 is **in the source text**. For this theme the problem
   Romansh retrieval does not exist and Supertext is not needed.

### 8.7 Architectural consequence: the "livello di risoluzione" field

You cannot know in advance whether a question needs a municipality: it depends on the canton **and**
by the type of holiday. The manifest must then record,for each pair
(canton × type of holiday), at what level the answer is determined:

| Value | Behavior | Verified Examples |
|---|---|---|
| `cantonale_uniforme` | reply | VD, TI |
| `per_comune_in_fonte_cantonale` | solve the municipality in the table, then answer | GR |
| `regola_con_eccezioni` | reply, but check the exceptions list | BE, Herbstferien |
| `delegato` | **ask the municipality**, citing the delegating law | ZH; BE, Februar-Ferien |

The ask-back becomes the reading of a field, decided by the server: identical on all four
client×LLM configurations. It's the "server grasso, modello magro" principle applied to the
case worth more points.

### 8.8 Semantic details to cite along with the date

- Bern: *"Die Daten enthalten den ersten und letzten vollen Ferientag"*
- Ticino: *"(dal – al compresi)"*

Different definitions of beginning and end. They change the answer one day.

### 8.9 Revised research estimate

Real times of this sampling: VD ~5 min, TI ~5 min, GR ~20 min, BE ~25 min,
ZH ~15 min. **Average ~14 min** against the estimated 12: for 26 cantons ago **~6 hours**, therefore
the order of magnitude holds.

But the variance is high and **the difficult cases are the large cantons**. The estimate just holds up
accepting the ask-back for the delegating cantons. If you wanted to *answer* also for
ZH, municipalities 160 would be needed — out of scope due to decision taken.

---

## 8bis. Extended sample: 10 cantons and model taxonomy 🟢

Verified the 2026-09-21. After ten cantons, **no cluster reduces work: every
canton must be opened individually.**

### 8bis.1 BEJUNE: confirmed on authoritative sources, but only partially

| Canton | Authoritative source | Autumn holidays 2026 |
|---|---|---|
| BE francophone | Cantonal PDF (§8.4b) | **05.10 – 16.10** |
| Neuchatel | `ne.ch/themes/scolarite-et-formation/calendrier-et-vacances-scolaires` (`dateModified` 17.08.2026) | **5 – 16 October** |
| Jura | `jura.ch/fr/Autorites/Administration/DFNS/SEN/Vacances-scolaires/` | **5 – 16 October** |

Autumn coincides. **Winter not:**

| Canton | Winter holidays 2026/27 |
|---|---|
| Neuchatel | 21.12.2026 – 01.01.2027 |
| Jura | 24.12.2026 – 08.01.2027 |
| BE francophone | 25.12.2026 – 08.01.2027 |

**Three cantons, three different dates.** Plus Neuchâtel has the *"Vacances du 1er mars"*, a
cantonal anniversary that the other two do not have.

> 🔴 **BEJUNE only harmonizes some holidays.** Treat it as "one source for 110 municipalities"
> produces wrong winter dates for two out of three cantons. The alignment must be recorded
> **by type of holiday**, not by canton.

### 8bis.2 Two access traps on Romande sources

| Resource | Outcome | Pitfall |
|---|---|---|
| `jura.ch/.../220531_Arrete_Vacances_scolaires-2023---2028...pdf` | **HTTP 410**, body "Erreur 404" | Deep link from search engine, document **replaced** by a new arrêté 2025–2028 of 13.03.2026, reachable only from the landing page |
| `ne.ch/autorites/DFDS/SEEO/Documents/Plan_Vac_Scol.pdf` | **HTTP 200**, `Content-Type: text/html` | URL with extension `.pdf` serving a web page. Status OK, PDF extension, HTML content |

The second is the worst: a naive pipeline passes HTML to a PDF parser and gets
no results, then reports "data not found" instead of "retrieval failed" — that is,
exactly the confusion that the `source_failure` practice case prohibits.

**Derived rule: always start from the authority landing page, never from the deep
link returned from a search.** Deep links rot, landing pages don't.
And validate the actual `Content-Type`, not the extension.

### 8bis.3 Model taxonomy, on 10 cantons

| Model | Cantons | Required behavior |
|---|---|---|
| **Cantonal uniform** | VD, TI, NE, JU | reply |
| **By municipality in cantonal document** | GR, LU | solve the municipality in the table |
| **By linguistic region** | BE, VS | solve the language region, then answer |
| **Cantonal with municipal variation** | SG | reply with reserve, or ask |
| **Delegate to the municipalities** | ZH, (AG to be confirmed) | **ask the municipality**, citing the law |

### 8bis.4 Bilingual cantons publish two calendars

It's not a Bernese quirk. **Valais** publishes two separate plans:

- `Plan de scolarite valais romand 2026-2027.pdf` (Roman Valais)
- `Schul- und Ferienplan 2026-2027.pdf` (Oberwallis)

Same structure as Bern. The key (canton × linguistic region) of §8.4b is therefore a
**pattern**, not an isolated case.

Note: Grisons, trilingual, do the opposite — **one document** with all
municipalities areas and headings in three languages (§8.6). Multilingualism does not predict the
model.

### 8bis.5 Other findings from the extended sample

- **Luzern**: two documents — one multi-year cantonal 2026/27→2031/32 and one
  **by municipality** (`ferienplan_gemeinden_sj26_27.pdf`, 6 pages). The municipalities diverge:
  Adligenswil and Aesch have autumn 26.09–18.10, Alberswil closes 11.10. Model
  "5/3" (5 weeks of summer, 3 of autumn).
- **St. Gallen**: The Bildungsrat sets the framework, but the City of St. Gallen publishes the
  own plan **and an open data dataset with ICS export**
  (`daten.stadt.sg.ch/.../schulferien-feiertage-stadt-stgallen/exports/ical`). He's the only one
  case of machine-readable school data encountered so far.
- **Aargau**: No holiday plans identifiable on `ag.ch` via search. They just emerge
  the legal bases (Schulgesetz SAR 401.100, Volksschulverordnung SAR 421.315), which
  suggests delegation to the municipalities as in ZH. **To be confirmed with direct access.**

### 8bis.6 Cost Impact

Ten cantons, five models, no predictive rules: neither language nor size,
nor does the geographic region predict which model a canton uses.

**The cost of ~14 min per canton cannot be reduced with shortcuts.** The 16 cantons
remaining ones must be opened one by one.

> ✅ **Facts**: The census has been completed on all and 26. Results in **§8ter**,
> which replaces this partial estimate.

---

## 8ter. Complete coverage: all 26 cantons 🟢/🟡

Completed the 2026-09-21.

> **Confidence.** All the cantons in this section have been verified **by downloading and
> reading the authoritative document or API**, except FR and VS, for which the reason for the
> missing data is documented in §8ter.8. No data comes from research summaries.

### 8ter.1 Final taxonomy, 26 cantons on 6 models

| Model | Cantons | n |
|---|---|---|
| **Cantonal uniform** | VD, TI, NE, JU, GE, ZG, BS, BL, TG, SH, NW, GL | 12 |
| **By municipality, in cantonal document** | GR, LU, SO, UR, SZ | 5 |
| **By linguistic region** | BE, VS | 2 |
| **Uniform with exceptions named** | FR, OW, AI | 3 |
| **Cantonal framework + municipal choice** | AG, AR, SG | 3 |
| **Delegate to the municipalities** | ZH | 1 |

### 8ter.2 Autumn holidays 2026, verified on the document

Sort by start date. Each row comes from the authority's document or API.

| Canton | Start – end 2026 | Sept. | Source read |
|---|---|---|---|
| **BE** German-speaking | **19.09 – 11.10** | 3 | Cantonal PDF |
| OW (except Engelberg) | 25.09 – 11.10 | 2 | PDF `ow.ch/_doc/454867` |
| **NW** | from **26.09** | 2 | PDF `nw.ch/_doc/456520` |
| **BS** | **26.09 – 11.10** | 2 | API `data.bs.ch` |
| **BL** | **26.09 – 11.10** | 2 | API `data.bl.ch` |
| BL — Gymnasium Laufental-Thierstein | 26.09 – 18.10 | 3 | API, exception declared |
| **SH** | **26.09 – 18.10** | 3 | page `schule.sh.ch` |
| AI — Bezirk Oberegg | 26.09 – 18.10 | 3 | PDF `ferienplan-ai_2026-2029` |
| UR — Seelisberg | 26.09 – 11.10 | 2 | Cantonal PDF |
| **SO** | **28.09 – 16.10** | 3 | Cantonal PDF, 8 pages |
| **SZ** (the majority) | **28.09 – 16.10** | 3 | Cantonal PDF |
| SZ — Gersau, Küssnacht, Schwyz, Illgau | 28.09 – 09.10 | 2 | Cantonal PDF |
| SG | 28.09 – 18.10 *(by KW rule 40–42)* | 3 | page `sg.ch` |
| **GL** | **03.10 – 18.10** | 2 | PDF `Ferienpläne_2026-2029` |
| **ZG** | **03.10 – 18.10** | 2 | PDF `Schulferien 202627-203031` |
| **UR** (cantonal framework) | **03.10 – 18.10** | 2 | PDF `..._nach_Gemeinden` |
| AI — Innerer Landesteil | 03.10 – 18.10 | 2 | Cantonal PDF |
| OW — Engelberg | 03.10 – 25.10 | 3 | Cantonal PDF |
| **BE** French-speaking / **NE** / **JU** | **05.10 – 16.10** | 2 | PDF + cantonal pages |
| **AR** | **05.10 – 16.10** | 2 | PDF `Ferienrichtdaten v1.3` |
| **TG** | **05.10 – 18.10** | 2 | PDF `Ferienplan_SJ_2026_2027` |
| **VD** | **10.10 – 25.10** | 2 | Multi-year PDF |
| **GR** — Scuol | **10.10 – 25.10** | 2 | Cantonal PDF, 164 lines |
| **GE** | **19.10 – 23.10** | **1** | page `ge.ch` |
| **TI** | **31.10 – 08.11** | **1** | Cantonal PDF |
| **ZH** | — | — | delegate to the municipalities |
| **AG** | variable duration per municipality | 2 or 3 | page `schulen-aargau.ch` |
| **LU** | variable per municipality, model 5/3 | 2 or 3 | PDF for municipality, 6 pages |
| FR, VS | not captured — see §8ter.8 | | |

**From 19 September to 8 November: seven weeks of dispersal.** Lasts from **one
week** (GE, TI) to **three**. Geneva and Vaud border and do not overlap by one
only day. Basel City and Basel Country coincide; Appenzell Innerrhoden divides
two inside.

Any geographic, linguistic, or proximity inference is wrong.

### 8ter.2b Corrections that emerged when opening documents

Compared to what I had deduced from the research summaries:

| Canton | Given second hand | Verified data |
|---|---|---|
| **ZG** | "2–17 ottobre **2027**" | **03.10 – 18.10.2026** — was the following year's column |
| **SG** | "3–24 ottobre **2027**" | rule **KW 40–42**, cantonal framework |
| **AI** | dates taken from `gymnasium.ai.ch` | the high school is a **different column**: two areas, Innerer Landesteil and Oberegg |
| **SO** | "varies by municipality" | **autumn uniform**; vary Sport- and Frühlingsferien |
| **AG** | "l'autunno è cantonale" | the **duration** of autumn varies per municipality (2 or 3 weeks) |
| **AR** | PDF v1.1 of 2025-04-01 | that file gives **404**: the current version is **v1.3 of the 2026-06-23** |

Five out of six statements were wrong or inaccurate. Second-hand sampling
it serves to size the work, **never to answer**.

### 8ter.3 Named exceptions: the single municipality within a uniform canton

- **OW**: The plan applies to the *"Volksschule ohne Engelberg"*. Engelberg has
  **03.10 – 25.10.2026** against **25.09 – 11.10.2026** of the rest of the canton.
- **FR**: **three** variants — majority calendar, more adaptations for the regions
  by **Morat/Murten** and **Kerzers**. Bilingual canton, documents in FR and DE.
- **AI**: different dates between the internal part of the canton and Oberegg.

A "uniforme" canton can contain a municipality with completely different dates, declared
in the title of the document itself. Read the title, not just the table.

### 8ter.4 Cantonal framework + municipal choice: three different variants

- **AG**: the Bildungsrat fixes 2 weeks each for spring, autumn and Christmas plus
  3 in summer; **the remaining 4 weeks are set by the municipalities**. Autumn is then
  cantonal, the rest not.
- **AR**: the cantonal document is called **`Ferienrichtdaten`** — *indicative* data, not
  binding. The municipalities independently set **2 of the 13 weeks**.
- **SG**: Bildungsrat sets the framework, municipalities vary. The City of St. Gallen publishes
  your own plan.

### 8ter.5 🔴 The school portal is almost never on the cantonal domain

The reason why my first search on `ag.ch` found nothing:

| Canton | Authoritative school portal domain |
|---|---|
| AG | `schulen-aargau.ch` |
| SH | `schule.sh.ch` |
| TG | `av.tg.ch` |
| LU | `volksschulbildung.lu.ch` |
| ZH | `vsa.zh.ch` |
| BE | `akvb-gemeinden.bkd.be.ch` |
| GE | `ge.ch` + `edu.ge.ch` |
| AI | `ai.ch` + `gymnasium.ai.ch` |

**A source registry built on the `<canton-code>.ch` pattern fails.** The domain
it must be verified manually for each canton, as for the municipalities (§4.1).

⚠️ 2026-09-22 Update: `vsa.zh.ch` replies but **redirects** to
`www.zh.ch/de/bildungsdirektion/volksschulamt.html`. The short domain remains valid as
entry point, but the page to be cited is the destination page. `www.vsa.zh.ch`
with the prefix `www.` instead gives **hostname mismatch on the certificate**: the subdomain
should be used exactly as published, without adding `www.`.

### 8ter.6 Five machine-readable sources — and one with a warning

| Canton | Source | Format |
|---|---|---|
| BS | `data.bs.ch/explore/assets/100397/` | open data + iCal |
| BL | `data.bl.ch/explore/assets/13350/` | open data + iCal, covers 2026/27–2031/32 |
| SZ | `data.sz.ch/explore/dataset/ferienplan-kanton-schwyz/` | open data |
| SG (city) | `daten.stadt.sg.ch/.../schulferien-feiertage-stadt-stgallen/exports/ical` | ICS |
| VD | import to agenda via QR | ICS alleged |

> 🔴 **The Schwyz dataset claims to be non-binding**: the data is provided without
> guarantee, and *"i piani vincolanti sono quelli emanati dalle autorità scolastiche"*.
>
> An official cantonal source, machine-readable and convenient, which **self-declares not
> authoritative**. It should be used for the lookup, but the citation must point to the binding PDF.
> It's the most subtle case of the entire collection: here you don't get the source or version wrong — you make a mistake
> *legal status* of the source.
>
> Similarly **BL explicitly excludes** the Regionales from its calendar
> Gymnasium Laufental-Thierstein, and **AR** publishes indicative "Richtdaten".

### 8ter.6b ⚠️ No other open data sources exist: verified, not assumed

2026-09-22 and 26 candidate cantonal open data portals scanned, with pagination
complete with the Opendatasoft catalog where it exists (not just the first page).

**Alive: six.** `data.bl.ch` (184 dataset), `data.bs.ch` (361), `data.sz.ch` (363),
`data.tg.ch` (456), `daten.sg.ch` (225), `data.gr.ch` (51). The other twenty hostnames
they don't resolve at all, or they don't expose that API.

**School holidays dataset found: three, and they are the three already known** — BL 13350,
BS 100397, SZ `ferienplan-kanton-schwyz`. Thurgau, Grisons and the cantonal portal of
St. Gallen has plenty of school datasets (students, locations, statistics) but **none
holiday calendar**. `opendata.swiss` also does not index any: the search
`vacances scolaires` gives 71 results and neither is a calendar.

> For the driving license only one source covered 26 cantons (§9.7). **For the holidays that
> shortcut does not exist**, and is now verified rather than assumed: the remaining cantons
> they must be opened one by one, as §8ter.10 had estimated.

### 8ter.7 Cantonal legal bases identified

Useful because the ask-back should be mentioned, not asserted:

| Canton | Norm |
|---|---|
| BE | LEO/VSG art. 8 para. 3 — RSB/BSG 432.210 |
| ZH | BiG §7; VSV §32 para. 2 — LS 412.101 |
| SH | SHR 410.114, *Verfügung über die Festlegung der Schulferien* |
| AG | ⚠️ **corrected 2026-09-22**: Volksschulgesetz (VSG) of 23.09.2025, **SAR 421.100 §§ 61 and 63**; Volksschulverordnung (V VSG) of 18.02.2026, SAR 421.315 § 48. The previous entry said `SAR 401.100` and *Schulgesetz*: wrong. **The VSG took effect on 1 August 2026** and the cantonal holiday plan was adjusted that day — §8quinquies |
| OW | Bildungsgesetz GDB 410.1 |

### 8ter.8 The two cantons that remain open, and why

**Freiburg — the document that seemed right was from another type of school.**
The URL `fr.ch/sites/default/files/2024-02/calendrier-scolaire-2026--2027.pdf` has a name
perfect and is under cantonal dominion. Opening it you discover that it is the calendar of
**professional schools**, issued by the *Service de la formation professionnelle*:
*"Ecoles professionnelles – Berufsfachschulen"*, *"Accueil des personnes en formation de
1re année"*. It's not compulsory school.

The correct page is `fr.ch/dfac/vacances-scolaires` and confirms **multiple variants**:
for 2027, both *"du Lu 18. octobre au Ven 29. octobre"* and *"du Lu 4. octobre au
Ven 22. octobre"* appear — two weeks apart and different durations within the same canton and
year. 2026 dates were not captured.

> **Right domain + right file name + right year ≠ right document.** The type of
> school is a dimension of jurisdiction like the territory.

**Valais — dates do not exist as text.**
The `Plan de scolarité valais romand 2026/2027` is a **monthly coloring grid**
(*"Colorier en bleu les jours entiers de classe et en jaune les demi-jours"*): the days
holidays are graphically marked with asterisks and bold. Text extraction
returns the grid of numbers but not which days are holidays.

You need layout analysis or OCR, or a different source. It is the only case encountered where
the authoritative source is **unreadable to a text pipeline**.

### 8ter.9 Operational notes from the verification

- **Deep link rot, confirmed three times**: AR, OW and NW PDFs indexed by
  engines damage **404**. In all three cases the current document is found alone
  passing through the landing page. For AR the indexed file was the **version
  v1.1 superseded by v1.3**.
- **Schaffhausen explicitly asks not to copy its calendar**: *"Bitte bilden Sie
  auf Schulwebseiten keinen eigenen Ferienkalender ab, sondern verweisen auf diese
  Seite."* An authority asking for the link instead of the copy — yet another argument against it
  the aggregators.
- **The two Basels have clean APIs**: `data.bs.ch` and `data.bl.ch` respond in JSON via
  `/api/explore/v2.1/catalog/datasets/<id>/records`, with exceptions declared as
  separate records (e.g. *"Herbstferien Gymnasium Laufental-Thierstein
  (Ausnahmeregelung)"*). It is the best format encountered.
- **Week number rules**: BE (DIN 39–41), SH (KW 40–42), SG (KW 40–42) and OW
  (*"sei settimane dopo l'inizio dell'anno, durata due settimane"*) publish rules
  in addition to the dates. The rules must be resolved on dates, and the resolution must be cited as
  derivative.

### 8ter.10 Consolidated cost

26 cantons, 6 models, no predictors. The real time of this census confirms this
**~12–15 min per canton** to identify source and model, **plus** an equivalent time
to open and validate each document (the 🟡 in this section).

**Final estimate for the school holidays theme: ~6 hours for identification, ~6 hours for
document validation. ~12 person-hours in total**, versus the ~6 initially estimated.
The doubling is due to named exceptions, regional variations and status verification
legal sources - all things that were not seen in the sample.

---

## 8quater. sample on the second type of holiday 🟢

Verified the 2026-09-22 by opening the authoritative sources, never summarized. It helps to decide one
one thing: **the `subtopic = "*"` lines of the manifest are a defensible statement, or
do they over-report?** All §8ter is a census from **fall only**; each line `*` extends
that result to the other four types without having looked at them.

Sampled **three out of six resolution classes**, not random cantons: it is the class that yes
wants to falsify. Type chosen: **sport/carnival**, where the divergence is already known (BE
February municipal, SO sports and spring variable). Christmas would have been the best sample
compliant.

### 8quater.1 Result: the class holds up, the detail doesn't

| Canton | Class | I hesitate on all types |
|---|---|---|
| **BS** | uniform | 🟢 **1 variant by type, 8 years, zero exceptions** |
| **BL** | uniform | 🟢 1 variant for type, 6 years — but the school type exception applies to **two** types |
| **NW** | uniform | 🟢 1 variant by type, 6 years, even merged school types |
| **SZ** | by municipality in the source | 🟡 holds up, but the **number of variants changes by type and by year** |
| **OW** | uniform with exceptions | 🔴 the named exception applies to **3 types to 5** |

**In the three classes above the CLASS does not change between types of holiday.** One canton
uniform in autumn is also uniform at Christmas and carnival. This is the result that
authorizes the `*` line for `resolution_level` and `on_missing_place` — **for those classes**.

But inside the classroom, **the detail is by type**, and the fall census loses it.

> ⚠️ **§8quinquies denies the extension to all classes.** In the *framework class
> cantonal + municipal choice* (AG, AR, SG) the class **changes** between types, in all three
> the cantons. §8quater.6's prediction was right.

### 8quater.2 🔴 OW: Named exception exists for some types and not others

From PDF `ow.ch/_doc/454867`, `Schulferienplan_2026-27`, two tables in the same sheet:

| Type | Volksschule (ohne Engelberg) | Engelberg | Do they diverge? |
|---|---|---|---|
| Herbstferien | 25.09 – 11.10.2026 | 03.10 – 25.10.2026 | **yes** |
| Weihnachtsferien | 24.12.2026 – 06.01.2027 | 24.12.2026 – 06.01.2027 | **no, identical** |
| Fasnachtsferien | 30.01 – 14.02.2027 | 04.02 – 14.02.2027 | **yes** |
| Osterferien | 26.03 – 11.04.2027 | 26.03 – 11.04.2027 | **no, identical** |
| Summer holidays | 03.07 – 15.08.2027 | 26.06 – 08.08.2027 | **yes** |

> **A named exception is not the property of the municipality: it is the property of the couple
> (municipality × type of holiday).** Engelberg is an exception in autumn, at carnival and
> in summer, and not at Christmas and Easter.

In the OW case it is harmless, because both tables are in the same PDF and cite the
same authority: answer from the Engelberg line for Christmas gives the right date and source
right. **It becomes dangerous when the exception has its own source**, because then yes
cites a document that is not competent for that type.

The symmetric risk is worse and this sample does not exclude it: a municipality that diverges
**only** at carnival, in a uniform canton in autumn, **does not appear at all** in a
autumn census. The server would respond confidently and wrong.

### 8quater.3 BL: Exception was under-logged

§8ter.6 records the exclusion of the Regionales Gymnasium Laufental-Thierstein **only for
autumn**, because only autumn had been watched. The `data.bl.ch` API `13350` dataset
shows that it also exists for **summer**, and in all six published school years:

```
Herbstferien                                                    2026-09-26 -> 2026-10-11
Herbstferien Gymnasium Laufental-Thierstein (Ausnahmeregelung)  2026-09-26 -> 2026-10-18
Sommerferien                                                    2027-07-03 -> 2027-08-15
Sommerferien Gymnasium Laufental-Thierstein (Ausnahmeregelung)  2027-07-10 -> 2027-08-15
```

Christmas, carnival and spring are no exception. Three out of five guys are clean, two aren't.

### 8quater.4 SZ: The number of variants changes by type AND by year

Dataset `ferienplan-kanton-schwyz`, filtered to compulsory school only (32 unit
scholastic; the type of school is jurisdiction, CONTRACT §4.4):

| Type | variants 2025/26 | variants 2026/27 |
|---|---|---|
| Herbstferien | **1** | **2** |
| Weihnachtsferien | **3** | **6** |
| Sportferien | 2 | 2 |
| Frühlingsferien | 1 | 1 |
| Summer holidays | *absent from dataset* | *absent from dataset* |

Christmas has **six** different calendars in the same canton and in the same year; spring
he has one. And autumn goes from 1 variant to 2 **changing year**.

> **A validation is valid for a school year, not for the canton.** `validated_at`
> alone does not capture it: it must be read together with the reference year of the document.

⚠️ The dataset **does not contain summer holidays**. A convenient machine-readable source can
be incomplete on a type, and the gap is not seen if only the autumn is queried.

### 8quater.5 🔴 Vacation type names are not a shared taxonomy

Collected from the sources of this sample:

| Slots | Real names encountered |
|---|---|
| sports / carnival | `Sportferien` (SZ) · `Fasnachtsferien` (BL, OW, NW) · `Fasnachts- und Sportferien` (BS) |
| spring | `Frühlingsferien` (SZ) · `Frühjahrsferien` (BS, BL) · **`Osterferien`** (OW) · `Ostern` (NW) |

`Osterferien` is anchored to Easter, not to the month: calling it "primavera" is our
convention, not theirs. A user who writes *"Wann sind die Osterferien?"* is asking
the same slot as the writer *"Frühjahrsferien"*, and the parameter `holiday_type` must
map them both. Also valid for French (`relâches`, `vacances de Pâques`) and
Italian (`vacanze di carnevale`).

### 8quater.6 What this sample does NOT cover

- **5 cantons on 26**, and **3 classes on 6**. `per_regione_linguistica` is missing,
  `quadro cantonale + scelta comunale` and `delegato`.
- The **framework + municipal choice** class is the one where collapse is expected, and it is
  the only one not tested: §8ter.4 says that in **AG** the Bildungsrat sets 2 weeks for
  spring, autumn and Christmas plus 3 in summer, and that **the remaining 4 weeks are set by
  municipalities**. If this is correct, in AG the class *changes* between types. The manifest already holds AG up
  `ask` for everything, which is the conservative choice and remains valid in both cases.
- **Only one alternative type looked at thoroughly** (sports/carnival), more than the sources
  multi-type they gave free. Summer and Christmas are covered only where the source listed them.

---

## 8quinquies. The class that changes by type: AG, AR, SG 🟢

Verified the 2026-09-22 by opening the documents, reached ** starting from the page
landing** and not from guessed URLs (§8ter.9). §8quater.6 declared this class not
tested and expected it to be the one where the class itself could change. **The
prediction was right, and applies to all three cantons.**

### 8quinquies.1 Sports holidays are not in the cantonal document. In none of the three.

| Canton | Types set by the canton | Type left to the municipalities | Source read |
|---|---|---|---|
| **AG** | autumn, Christmas, spring, summer | **Sportferien** — absent from the cantonal PDF | PDF Erziehungsrat, 3 pages |
| **AR** | autumn, Christmas, spring, summer (11 weeks) | **2 weeks on 13** | PDF `Ferienrichtdaten v1.3` |
| **SG** | autumn, Christmas, spring, summer | **Sports- bzw. Winter holidays** | page `sg.ch` |

The three sources say it, each in their own way:

> **AG** — *"Je zwei Wochen Frühlings-, Herbst- und Weihnachtsferien sowie drei Wochen
> Sommerferien werden einheitlich durch den Erziehungsrat festgelegt. Die restlichen vier
> Ferienwochen legen die Gemeinden selber fest."* · *"Regionale Unterschiede gibt es bei
> den Sportferien sowie der Dauer der Sommerbzw. Herbstferien."*
>
> **SG** — *"Die Sport- bzw. Winterferien werden durch die Schulträger (Gemeinde)
> festgelegt und unterscheiden sich je nach Schulort."*
>
> **AR** — PDF lists fall, Christmas, spring, and summer only; the 2 weeks
> municipal ones do not appear.

> **The cantonal document is not incomplete due to sloppiness: it is complete with respect to what
> the canton decides.** Looking for sports holidays in there and not finding them is the
> correct behavior of the source, not its defect. A `no_match` on that source
> does not mean "the fact does not exist" (CONTRACT §5.1).

### 8quinquies.2 AG: the canton sets the start, the municipality the duration

It's the open contradiction in §10, and it dissolves: **both readings were true.**

- The canton sets the **start** of autumn and a **minimum of two weeks**
  (2026/27: KW 40/41, 28.09 – 09.10.2026).
- The municipality can use its four free weeks to **extend** autumn to 3
  weeks or summer at 5: *"Dies betrifft den Beginn der zweiwöchigen Sportferien und die
  Dauer der Sommerferien (4 oder 5 Wochen) bzw. Herbstferien (2 or 3 Wochen)."*

So for autumn in AG **the start date can be answered without the municipality, the date of
end no**. An answer that gives only the beginning is correct and incomplete; one who also gives the
end without the municipality is wrong in half the cases.

The PDF ends with *"Wir bitten um Kenntnisnahme und Einhaltung dieser **verbindlichen**
Daten"*: binding, unlike AR.

### 8quinquies.3 🔴 SG: The date in §8ter.2 is off by one day

§8ter.2 reports for SG **28.09 – 18.10.2026**, *derived* from the KW rule 40–42. The
cantonal page publishes the dates, and they are **Sunday 27.09.26 – Sunday 18.10.26**.

The rule says KW 40–42; the canton allows holidays to begin on the **Sunday** that opens
week 40, not Monday. Deriving a rule in dates without reading the convention
start and end moves the answer one day — it is §8.8 applied to a new case.

**Operational rule**: when the source publishes both the rule and the dates, the
**date**, and the rule only serves to explain them.

### 8quinquies.4 AR remains indicative, and now we know how much

The document is called `Ferienrichtdaten` and is not binding (§8ter.4). But list
**11 of 13 weeks** with precise dates over four school years. The 2 weeks
municipal offices are the only part that is truly open.

Autumn 2026/27: **Mo 05.10 – Fri 16.10.2026**, consistent with §8ter.2. Note which AR uses
Monday–Friday as the first and last day of vacation, while SG uses Sunday–Sunday and
BE *"den ersten und letzten vollen Ferientag"*: **three different agreements in three cantons**.

### 8quinquies.5 Consequence on the manifest, and a mistake that costs points

The `subtopic = "*"` lines for these three cantons were all wrong, in two directions
opposite:

| Canton | Before | After | Why |
|---|---|---|---|
| **AG** | `ask` on everything | `ask` on `*`, **`answer` on Christmas and Spring** | Christmas and spring are entirely cantonal: asking the municipality is penalized |
| **AR** | `answer` on everything | `answer` on `*`, **`ask` on sports** | sports holidays are not in the cantonal source |
| **SG** | `ask` on everything | `answer` on `*`, **`ask` on sports** | four out of five types were answerable, and we asked |

The SG case is the most expensive: CHALLENGE §5.4 says that **ask when the question is already
answerable counts as wrong**, on a par with answering without an essential piece of data.
A question about the Christmas holidays in St. Gallen received a useless ask-back.

---

## 8sexies. The sample's three open risks, closed 🟢

Verified the 2026-09-22. Closes the three points that §10 kept open on holidays: the
risk St. Gallen, Friborg and Valais. **Two out of three denied what the
document said about them**, and in both cases the error was in the same direction:
a source had been described without having been read thoroughly.

### 8sexies.1 🟢 St. Gallen: the risk does not exist, and we know why

§9 of the handoff asked: **the plan of the City of St. Gallen differs on the four types
cantonal?** If yes, the line `SG` over-declares, because it responds `answer` with the dates
cantonal also for those who live in the capital.

The city publishes `schulferien-feiertage-stadt-stgallen` on `daten.stadt.sg.ch`
(Opendatasoft, no auth). Thirty records, from 2022 to July 2025.

**The two sources do not overlap in time**: the city stops in July 2025, the
canton publishes from 2026/27 to 2029/30. A direct comparison of the dates 2026 is
impossible. We then compare the **rule**, and it is a valid comparison because the
cantonal rule is expressed in ISO weeks.

First you need the convention of the municipal dataset, and two holiday records set it without
ambiguity: `Auffahrt 2025-05-29 → 2025-05-30` (the Ascension 2025 is Thursday 29) and
`Pfingstmontag 2025-06-09 → 2025-06-10` (Monday 9). In both **`endet_am` is
exclusive**, such as the `DTEND` of an ICS all-day event.

With that agreement, the school weeks actually free in the city:

| type | city ​​of St. Gallen, 2022–2025 | cantonal rule |
|---|---|---|
| Herbstferien | KW 40, 41, 42 | KW 40–42 ✅ |
| Frühlingsferien | KW 15, 16 | KW 15 and 16 ✅ |
| Summer holidays | KW 28–32 | KW 28–32 ✅ |
| Weihnachtsferien | KW 52 + KW 1 | 2 weeks ✅ |
| Winter holidays | KW 5, one week, 4 years on 4 | **not in the cantonal plan** |

The only differences are of form, not of substance: the city registers as the first day
on **Saturday** adjacent, which is already non-scholastic, while the canton publishes
Sunday–Sunday; and two extensions to movable holidays (Karfreitag on 07.04.2023,
Ostermontag on 21.04.2025), which are public holidays and not holidays.

> **The `SG` line does not over-declare.** The `Winterferien`s are the only thing the city
> decides for itself, and they are exactly the `sport` type already covered by the `ask` override
> introduced in §8quinquies.5. The risk is closed by confirming the line, not correcting it.

Two details emerged when reading the cantonal table in full:

- **Christmas in SG is not a rule in weeks.** Note 1 says: *"Die
  Weihnachtsferien dauern 2 Wochen. The first Weihnachtstag (25. Dezember) is in der
  ersten Ferienwoche."* It is pegged to the December 25, not to a KW.
- **Spring gives way to Easter.** The note 3 on the 2029/30: *"Ferienende ist der
  Ostersonntag."* The KW 15–16 rule is therefore derogable, and the document declares it.

Cantonal dates 2026/27, to be cited as they are: autumn 27.09–18.10.26, Christmas
20.12.26–03.01.27, spring 11.04–25.04.27, summer 11.07–15.08.27.

### 8sexies.2 🔴 Freiburg: Divergence was attributed to the wrong region

The 2026 dates were missing because a PDF was searched. **Not needed**: `fr.ch/dfac/vacances-scolaires`
publishes all three variants in text-based HTML, with PDF and ICS by year, up to 2029/30.

§8ter.8 recorded that *"per il 2027 coesistono du Lu 18. octobre e du Lu 4. octobre"* and
the `FR/Morat-Murten` line of the manifest bore the trace. Opening the page, those
two dates are **majoritaire against Kerzers**. Morat/Murten has nothing to do with it.

| 2026/27 | majoritaire | Morat/Murten | Kerzers |
|---|---|---|---|
| rentree | 27.08.26 | = | **24.08.26** |
| automatically | 12–23.10.26 | = | = |
| Noël | 21.12.26–01.01.27 | = | = |
| carnaval | 08–12.02.27 | = | **22–26.02.27** |
| Pâques | 26.03–09.04.27 | = | **26.03–16.04.27** |

| 2027/28 | majoritaire | Morat/Murten | Kerzers |
|---|---|---|---|
| automatically | 18–29.10.27 | = | **04–22.10.27**, three weeks versus two |
| Noël | 20–31.12.27 | = | = |
| carnaval | 28.02–03.03.28 | = | **21–25.02.28** |
| Pâques | 14–28.04.28 | = | **10–21.04.28** |

Three consequences:

1. **Morat/Murten is not a holiday variant**, in either year. It differs
   in *jours fériés* (no Toussaint, Immaculée Conception, Fête-Dieu; plus the
   *Jour après la Solemnity*) and has two *jours joker* instead of one. The line is held there
   itself: it is a school region declared by the canton, and point 2 says why.
2. **Which types diverge changes by year.** In 2026/27 the Kerzers autumn coincides
   with the majoritaire; in the 2027/28 it is two weeks away and lasts one week longer. It is
   same pattern as SZ (§8quater.4), on a different canton. A sample of just one year
   it doesn't say which types are stable.
3. ⚠️ **The Kerzers region contains four Bernese municipalities**: Gurbrü, Wileroltigen,
   Golaten, Ferenbalm, next to Kerzers, Fräschels and Ried b. Kerzers. For those four
   the right answer lies in the **Fribourg** calendar. It is the first case encountered in
   where the border of the school jurisdiction cuts a cantonal border, and the
   place solver must know: a lookup by canton would send them to BE.

Summer is not listed as a period, but is unambiguously derivable from the two heads
(*Dernier jour de scuola* → *Début de l'année scolaire* next), and the page
publish enough years for both leaders to always exist.

### 8sexies.3 🔴 Valais: it's not an OCR problem, the data isn't there

§8ter.8 called it *"the only case in which the authoritative source is illegible to a
text pipeline"* and involved OCR or layout analysis. **Both would have been
wasted work.** The `Plan de scolarité valais romand` is not a poorly rendered calendar:
it is an **empty form**.

The extracted text says: *"Colorier en bleu les jours entiers de classe et
en jaune les demi-jours"*, and the legend says bold dates are *"Samedis,
dimanches et jours fériés"* — **not** the holidays. The only figures in the document are i
monthly counts of school days and the total (165.5, *Solde* −1). No OCR can
extract a date that was never written in the document.

The cantonal page confirms that it is desired:

> *"Attention, les plans sont indicatifs. Pour toutes dates de vacances plus précises,
> s'adresser directement à la Direction d'école (ou Commune) concernée."*

**The other half of the canton is resolved**, and the source was just one click away:

- `Schul- und Ferienplan 2026-2027.pdf` — PDF **image**, `pypdf` extracts 0 characters on
  2 pages. It is the document that the name makes it sound like the right one.
- `Übersicht Schul- und Ferienplan 2026-2027.pdf` — **text table, one line per
  municipality, all types**, drawn clean. It is the source to use.

> ⚠️ The `Übersicht` is listed **only on the German landing page** `vs.ch/de/web/se/plans-de-scolarite`.
> The French landing, same path without `/de/`, does not show it. In a bilingual canton the
> two site languages do not serve the same set of documents: changing the language is a
> search step, not a translation.

Majority values 2026/27 and variants:

| | Schulbeginn | Herbst | Weihnachten | Fasnacht/Sports | Ostern | Maiferien |
|---|---|---|---|---|---|---|
| majority | 17.08. | 09.10.–26.10. | 18.12.–04.01. | 19.02.–08.03. | 25.03.–30.03. | 30.04.–10.05. |
| Leukerbad, Zermatt, Saas | 17.08. | = | = | **26.02.**–08.03. | = | **23.04.**–10.05. |

Two things that this table teaches and which are valid beyond Valais:

- 🔴 **There is a sixth type of holiday.** The `Maiferien` column does not have a slot
  in the `holiday_type` enum of `src/tools.ts`. A question about the May holidays in
  Valais has nowhere to go. It's §8quater.5 on a new case, and this time it's not a name
  local for an existing slot: it is an extra period.
- **A fourth convention of extrema.** Columns are *Beginn **abends*** / *Ende
  **morgens***: `Herbst 09.10.–26.10.` means that the holidays begin on the evening of 9
  and end on the morning of 26, i.e. full days are **10.10.–25.10.** After SG
  (Sunday–Sunday), AR (Monday–Friday) and BE (first and last full day), is the
  fourth in four cantons. Citing the raw date without the convention makes a mistake
  day to extreme.

The scope of the `Übersicht` is *deutschsprachige Primar- und Orientierungsschulen*:
type of school as well as territory (CONTRACT §4.4). This is why it contains lines for
German schools of **Siders and Sitten**, which are in Roman territory.

---

## 8septies. All the holiday lines, open on the document 🟢

Verified the 2026-09-23. Any still empty row of `coverage/school_holidays.toml` is
closed by opening the document and reading **all five types**. Result: all
validated lines except **`SZ/summer`**, left blank on purpose (below). The dates are
in the `notes` of each row; here lies what is worth beyond the single line.

### 8septies.1 🔴 Seven statements believed to have been verified were wrong

| Line | What he said | What the source says |
|---|---|---|
| **`SO/autumn`** | override: uniform autumn, `answer` | **3 variants on 85 entities**, same structure on 2025/26 and 2026/27. With the 6 override, entities received the wrong date without being asked for the location. Uniform is **Christmas** (85/85, two years): the override is now there |
| **ZH, ask-back** | *"set by each municipality (VSV §32 para. 2)"* | §32 para. 2 VSV allows municipalities **four days off**; it does not establish who sets the holidays. The supposed citation did not support the claim. |
| **ZH, Christmas** | covered by the ask-back | **cantonal and binding** (*"im Kanton einheitlich festgelegt"*). Asking the municipality was the move that CHALLENGE §5.4 penalizes. New override `ZH/christmas` |
| **GE** | *"does not overlap with VD by even a day"* | GE autumn 19–23.10.26 falls **within** VD autumn 10–25.10.26 |
| **SH** | publish the rule, not the dates | publish **both**, until 2034/35 |
| **AI** | high school is a different column | in the document 2026–2029 the Gymnasium is **included** in the internal Landesteil |
| **§8.4c, Biel** | bilingual, classified as German-speaking | **alternates**: DE calendar in school years starting in even-numbered years, BEJUNE in odd-numbered ones. Also applies to Evilard, Orvin, Plagne, Romont, Vauffelin |

Three of these came from a single extraction or a single year read (§7.3
of the handoff): SO, GE, Biel. The SO case is the most instructive: §8ter.2b had discarded
as false a research summary that told the truth.

### 8septies.2 🔴 "Hiver" is not a slot: it's a false friend

| Local name | Canton | Slots |
|---|---|---|
| *Hiver holidays* | **NE, VD, BE French-speaking** | **christmas** |
| *Winterferien* | GL, SO, City of SG | **sport** |
| *Winterferien* | BE German speaker | **christmas** |
| *Holidays du 1er mars* | NE | sports |
| *Relâches* | VD | sports |
| *White week* | BE francophone | sports (delegate) |

The same word indicates the opposite slot depending on the canton, and even within BE. The
parameter `holiday_type` must be mapped **per canton**, never by translation (§8quater.5).

### 8septies.3 ⚠️ Periods that do not fit into the five slots

| Period | Where | Status |
|---|---|---|
| `Maiferien` | VS German speaker | **decided 2026-09-23: not covered** |
| `Pfingstferien` | TG, 06.05–17.05.2027 | **decided 2026-09-23: not covered** |
| `Auffahrtsferien` | ZG, 06.05–09.05.2027 | **decided 2026-09-23: not covered** |

Pfingst- and Auffahrtsferien are the same case as Maiferien. The decision made for
the latter does not extend on its own: it remains open in §10.

### 8septies.4 Three school jurisdictions crossing a cantonal border

- **FR/Kerzers** contains four Bernese municipalities (§8sexies.2), already decided.
- **TG/Neunforn**: **secondary** students attend in Ossingen (ZH) and follow
  the dates — different sport, **no** spring break, different Pentecost. Le
  elementary school follows TG. It's more common school type, so not a common line:
  treated as BL (CONTRACT §4.4).
- **LU**: a category of municipalities *"richtet sich nach den Ferien des Kt. Zug"*. The dates
  they are however printed by municipality; the category is marked **only with color** and the
  extracted text does not bring it.

### 8septies.5 Summer is almost always derivative, and once you can't

FR, TI, GR, UR and SZ do not list summer as a period: they give the last day of school and
the beginning of the following year. We derive it, and where necessary we read the document of the year
next (TI, UR). **SZ cannot be**: neither the cantonal PDF nor the dataset gives the former
day 2027/28. For this reason `SZ/*` is validated on the other four types and `SZ/summer` is
an **unvalidated** override, so `lookup(SZ, summer)` doesn't fall on a covered row.

### 8septies.6 Sources that declare themselves non-binding, or drafts

- **SO**: *"Die Veröffentlichung erfolgt ohne Gewähr"* → `indicative`.
- **SZ**: the cantonal PDF is also *"Zusammenstellung ohne Gewähr. Verbindlich sind die
  von den Schulräten erlassenen Ferienpläne"*. The cantonal binding PDF that the old one
  note asked to find **does not exist**.
- **ZH**: the date document is headed **Entwurf** (26.06.2023). It is used only for
  date of Christmas, which coincides with the *verbindlich* rule of the page.
- **JU**: the arrêté of the 10.03.2026 **repeals** that of the 2022, which already covered up to
  2027/28. The dates were redone halfway through the period.

### 8septies.7 New entry traps

- **SH**: page rendered via JavaScript, `curl` sees 12 rows. You need a browser.
- **notes.zh.ch**: the link to the law text returns 200 with 156 bytes of HTML and a
  JavaScript redirects. The PDF is on the redirect path.
- **UR**: the deep link `_doc/432274` indexed by the engines gives 404; the live one is `_doc/449362`.
- **UR**: the cells contain only the day; the month is in the header.
- **JU**: PDF served as `application/octet-stream`.
- **TI**: A search summary declared pages protected by CAPTCHA. The PDF yes
  download without, and the landing responds 200.

### 8septies.8 ⚠️ Exceptions that the source admits but does not name

**BE**: municipalities in the Alpine tourist region *can* move the spring between
weeks 15 and 21, and neither document says which. The `BE/*` line responds with the
cantonal date; for those municipalities it could be wrong. Opened in §10.

---

## 9. Cantonal sampling: foreign driving license 🟢

Same five cantons, verified 2026-09-21. **Result opposite to holidays
schools: here the model is homogeneous, because the substance is federal.**

### 9.1 The substance is federal, the procedure is cantonal

Verified legal basis: **VZV / OAC, SR 741.51**, articles 29, 42–44, 150.
ELI: `https://www.fedlex.admin.ch/eli/cc/1976/2423_2423_2423/de` (200, HTML).

The **term of 12 months** from entry into Switzerland is federal law. All five
sampled cantons report it identical — because they repeat it, not because they establish it.
Also federal is the rule on which countries require a check ride.

**Consequence**: one federal source covers the substantive rule for all 26 cantons.
The 26 cantonal documents are used only for the procedure.

### 9.2 What really varies, by canton

| Canton | Office | Verified cantonal elements |
|---|---|---|
| VD | SAN | form **220**; locations Aigle, Lausanne, Nyon, Yverdon; 2–3 working days |
| TI | Circulation section | online form; **CHF 150** (200 with professional categories); 1–2 weeks |
| ZH | Strassenverkehrsamt | control drive rules by country; headquarters Zürich-Albisgütli |
| BE | SVSA | form + photo; **eye test** by a Swiss optician or ophthalmologist; Schermenweg 5 |
| GR | STVA | Ringstrasse 2, Chur; **form also in Romansh** |

### 9.3 Sample question #2 requires both levels

> *"Comment puis-je échanger mon permis de conduire étranger contre un permis suisse dans
> le canton de Vaud, **et combien de temps ai-je pour le faire**?"*

The "how" is cantonal (form 220, SAN offices). The "how long" is **federal** (VZV).

Citing the Vaud page as the source of the term of 12 months attributes a federal regulation
to the wrong authority. The review checklist point 3 asks you to verify exactly that
the publisher is responsible for the matter. A complete response cites **two sources by two
levels**, each for the part for which it is competent.

### 9.4 ⚠️ Verified freshness trap on Bern

The same office appears on two domains:

| URL | Outcome |
|---|---|
| `svsa.sid.be.ch/.../umtausch-fuehrerausweis-ausland.html` | **HTTP 200**, 180 KB — current |
| `svsa.pom.be.ch/svsa_pom/de/.../umtausch-auslaendischer-fuehrerausweis.html` | **HTTP 000** — dead domain |

Bern has reorganized the directions (POM → SID) and the old domain no longer responds.
**But the web search still returns both**, and the dead page appears as authoritative as the
alive.

It is literally the failure of the briefing slide 3: *"An old page outranks the
current one."* Mandatory defense: **validate that each URL in the registry matches the
build time**, and record the validation date next to the source.

### 9.5 Native Romansh, again

Graubünden publishes `Antrag_und_Umtausch_Führerausweis_RM.pdf` — exchange form
of the driving license **in Romansh**, 786 KB, verified 200.

It is the **second theme out of two** in which the authoritative source serves Romansh natively
(the first is the trilingual GR holiday plan, §8.6). Working hypothesis: in Graubünden the
Romansh coverage is an administrative practice, not an exception — which makes the
Romansh much less expensive than feared, as long as the sources are the cantonal GR ones.

### 9.4b Two more hostnames that don't hold up, verified 2026-09-22

Emerged by validating the coverage manifest against the network:

| Hostname | Outcome | Reading |
|---|---|---|
| `strassenverkehrsamt.zh.ch` | **getaddrinfo failed** — does not resolve | The obvious office name is not a domain. The page should be searched under `zh.ch` |
| `www.stva.gr.ch` | **incomplete SSL chain** (`unable to get local issuer certificate`) | The site exists and the DNS resolves; the server does not serve the intermediate chain. A pipeline with standard TLS verification discards it, a browser does not |

The second case is new compared to §9.4: there the domain was **dead**, here it is **alive but
not validatable**. They are two different failures and must be distinguished in the register, because the
the first must be replaced and the second must only be checked by hand.

### 9.6 Cost of research and comparison between the two cantonal themes

| | School holidays | Foreign driving license |
|---|---|---|
| Model | **5 cantons, 5 models** | **homogeneous** |
| Substance | cantonal or municipal | **federal** (VZV) |
| What varies | granularity, format, rules | form, fee, location, channel |
| Inference between cantons | **lethal** (3 weeks waste) | safe on the substance, prohibited on the procedure |
| Ask-back needed | yes, in ZH and BE-February | **no** |
| Cost per canton | ~14 min, high variance | **~8–10 min, low variance** |
| Estimate 26 cantons | ~6h | **~4h** |

The foreign driving license is the cheaper and more predictable cantonal issue of the two, and the estimate
initial of 4.5h holds. School holidays are the opposite: they cost more and
require the "livello di risoluzione" field of §8.7.

---

### 9.7 🟢 The 26 offices from one registry only, instead of 21 searches

§10 listed *"21 cantoni restanti, meccanici"*. They weren't 21 searches: they were one.
The association of cantonal traffic offices publishes the complete list on
`asa.ch/strassenverkehrsaemter/adressen/`, with office name, telephone, email and link
to the site for all cantons plus Liechtenstein.

**The register does not declare the cantonal acronyms**: the blocks are in alphabetical order
German and the label is the long name. Assigning by position is fragile, and it is
seen immediately: a cross-check with domain and email showed a mismatch of
a line from Obwalden onwards. The reason is in the data, not in the parser — see below.
The final assignment is made on the **extended name inside the link label**, which
name the canton, with domain and email as second confirmation.

The 26 landings are in `coverage/driving_licence.toml`, each verified with a
requested and **registered to the final URL after redirects**. `validated_at` remains empty on
all: the office landing is verified, not the procedure page.

Four things that the register taught, and which are valid beyond this topic:

- 🔴 **Obwalden does not exist in the registry.** `NidwaldenVerkehrssicherheitszentrum OW/NW`:
  a single block, labeled Nidwalden, and only the *office name* reveals that it is needed
  also Obwalden. A census that counts the register entries finds 25 cantons and not if
  he notices it. It is the second intercantonal office of the project, after the calendar
  BEJUNE (§8bis.1).
- 🔴 **The authoritative registry contains a dead hostname.** For Thurgau it points to
  `www.stva.tg.ch`, which does not connect at all (`curl` 000). The living is
  `strassenverkehrsamt.tg.ch`. It is the second case after `svsa.pom.be.ch` (§9.4), but that
  it came from a search engine: **here the dead link is in the category register.**
- ⚠️ **Basel Countryside responds 403 to the automatons.** `baselland.ch` also rejects `curl`
  with a full browser User-Agent, while the page opens normally in the
  bread browser. It's not a rotten URL - it's a WAF. A pipeline that decides the validity of
  a source from HTTP code would wrongly discard it — and a server that would fetch **a
  runtime** on this source would fail in production.
- **Seven out of twenty-six landings redirect elsewhere** (AG, AR, BS, FR, JU, LU, VS). The
  registry is updated just enough to take you to the right site, not to give the URL
  current.

🟢 **An open thread closes along the way**: §10 recorded that `stva.gr.ch` has a
incomplete SSL chain. The register gives for Grisons
`gr.ch/DE/institutionen/verwaltung/djsg/stva/Seiten/Start.aspx`, which responds 200 without
certificate problems. The Graubünden source was not unreachable: it was reached
from the wrong hostname.

Five cantons do not have an office on the cantonal domain: **FR** (`ocn.ch`), **NE**
(`scan-ne.ch`), **NW/OW** (`vsz.ch`), **TG** (`strassenverkehrsamt.tg.ch`), **LU**
(`strassenverkehrsamt.lu.ch`). It is §8ter.5 confirmed on a second topic: the portal of
service almost never stands on `<sigla>.ch`.

---

### 9.8 🟢 The 27 lines of the license, open on the source

2026-09-23 verified: the federal line on the consolidated text of the VZV, the 26
cantonal information on the **procedure page** of each office (not the landing page). The
detail of each canton is in `notes`; here what is worth beyond the line.

**Three corrections to the federal line.**

- **The term does not start from entry.** Art. 42 par. 3bis lit. to VZV: you need it
  Swiss driving license for those who have *lived* in Switzerland for twelve months without having been abroad
  more than three months in a row. Almost all the cantons write "12 mesi dall'ingresso": it is the
  their simplification, not the norm.
- **The list of countries is not in the VZV.** The art. 44 forces control travel to
  everyone; the art. 150 para. 5 read. and authorizes ASTRA to exempt. The list goes
  in the **Anhang 2 of Weisung ASTRA** *Führerausweise von Personen mit Wohnsitz im
  Ausland* (01.10.2013, Stand 15.07.2021), which SVSA Bern links. A post from the ASTRA blog of
  2023 reports the same lists but omits a reservation: **Taiwan applies only to A1 and B**.
- **Two groups, not one.** Group A (EU/EFTA plus Grossbritannien): exempt from racing **and**
  from professional theory. Group B (including USA, Canada, Japan, Australia): exempt
  **only** from running.

**⚠️ The five-year rule, no federal source found.** LU, TG, VD and ZG
they declare that those who convert more than five years after entry make the race of
check even if you come from an exempt country (VD and ZG: unless you have a regular driving certificate).
It is not in the Anhang 2 nor in the rest of Weisung. Four independent cantons make it
a local invention is unlikely, but until the source is found it should be attributed to
cantons that write it, not to the Confederation. Opened in §10.

**Taxes are a cantonal data and are often absent.** Printed by 8 cantons on 26:

| Canton | Shiftless shift | Notes |
|---|---|---|
| FR | Fr. 80 flat rate | with stroke B Fr. 260 |
| SG | Br. 80–100 | separate race |
| ZG | Br. 75 | race B Fr. 90 |
| VS | CHF 70 + 53.50 | race B CHF 90 |
| NE | Br. 105 | race Fr. 120 more |
| BE | CHF 120 | |
| GE | CHF 150 | CHF 200 for C, C1, D |
| TI | Br. 150 | Fr. 200 with professional categories |

The others refer to a separate price list. An answer about the tax must say **from
where** comes the number, and for 18 cantons today we don't have it.

**Procedures that a generic answer gets wrong.**
- **TI** from 17.11.2025 accepts the request **online only**.
- **BS** wants the Gesuch **at least one month before** the expiration of the 12 months.
- **NW/OW**: the ride must be made **within three months** of deposit.
- **SH**: the municipality **can invoice** the identification.
- **ZG**: the office does not provide the vehicle for the ride.
- **VD**: the permit must have been obtained **before** entering Switzerland.
- **SG** cites art. for the non-repeatability of the race. 29 para. 4 VZV; for permits
  foreign countries the norm is art. 44 para. 1bis. Cantonal citation not to be taken back.

**New entry traps.** SH (FAQ in accordion via JS: the text is in the
`textContent`, not in `innerText`) and SO can only be read in the browser; BL remains behind the
WAF (§9.7). The Merkblatt UR indexed by the engines gives 404.

---

## 10. What remains to be verified

**Scope Decision Blocker:**
- **Feasibility of 15 Romansh municipalities**: do they publish a waste calendar? in what format?
  Check 4-5 of them before committing to a "Romansh area" claim
  complete". A missed declaration is worse than one not made.

**Open:**
- **If the 2027 premiums are released during the hackathon** (the BAG publishes towards the end of September):
  decide in advance how the server will respond — state the year explicitly, and
  which year is the default.
- ~~`holiday_type` does not have a slot for `Maiferien`~~ → **decided 2026-09-23: declared type
  not covered** (`scope.toml`, `subtopics`). No new slots, routing gate remains valid
- **Location solver maps Gurbrü, Wileroltigen, Golaten and Ferenbalm to `FR/Kerzers`**
  for school holidays: **decided 2026-09-23** (§8sexies.2). To be implemented with the solver
- ~~`Pfingstferien` (TG) and `Auffahrtsferien` (ZG)~~ → **decided 2026-09-23: not covered**, as
  the Maiferien (`scope.toml`, `subtopics`)
- ~~BE, spring in the Alpine tourist municipalities~~ → **decided 2026-09-23: the municipality asks**.
  Override `BE/spring` with ask-back (§8septies.8)
- **`SZ/summer`**: not validatable until the canton publishes 2027/28 on the first day
  (§8septies.5)
- **Romanian Valais**: open, but it is no longer a technical problem. The cantonal plan is a
  blank form and the canton refers you to the school or municipality (§8sexies.3). It just closes
  deciding whether to sample Romande municipal sources or leave the ask-back
- **Other holidays beyond autumn**: sampled on 8 cantons and 4 classes
  (§8quater, §8quinquies). Outcome in two parts: in *uniform* classes, *for municipality in
  source* and *uniform with exceptions* the class holds between types and only the detail changes;
  in the class *framework + municipal choice* **the class changes**, in all three cantons,
  and sports holidays are not in the cantonal document.
  The classes **by linguistic region** (BE, VS) and **delegate** remain unsampled
  (ZH), but both are already asking for the location for each type: the risk is low
- **Taxonomy of holiday types** (§8quater.5): `Osterferien` in OW and NW is not
  `Frühlingsferien`, and is anchored to Easter. The `holiday_type` parameter must map
  real names, not our slots
- ~~Foreign driving licence, 27 lines~~ → **closed 2026-09-23** (§9.8), all validated
- ~~License, five-year rule~~ → **decided 2026-09-23: remains cantonal**, attributed
  only to LU, TG, VD, ZG in the respective lines (§9.8)
- **License, taxes**: printed by 8 cantons on 26; for others you need the price list (§9.8)
- ~~Aargau, internal contradiction~~ → **closed in §8quinquies.2**: both readings
  they were true. The canton sets the start and a minimum of 2 weeks, the municipality can
  extend to 3. The body is the **Erziehungsrat**, not the Bildungsrat
- Existing MCP repo licenses, to evaluate reuse
- If ch.ch offers a structured search or just the SPA
- Quota and rate limit of `api3.geo.admin.ch` for intensive use

**Resolved**:
- There is no municipality official dataset → website (`behördenverzeichnis` on CKAN =
  `count: 0`); the municipalities registry with BFS numbers exists and is in §7
- **French-speaking part of the canton of Bern** → §8.4b–8.4e, closed
- **Romansh coverage of GR sources**: the cantonal holiday plan is trilingual with
  headings in Romansh (§8.6) and the STVA publishes the driving license form in Romansh
  (§9.5). Two out of two themes served natively
- **Waste calendars**: no longer relevant, municipal area out of scope by decision
- **`Einzugsgebiete.csv`** → §3.2c: it is not the mapping of the premium regions, but the
  insurers' operational areas. The actual mapping is the SR order 832.106 (§3.2d).
  Sample question #3 solved end-to-end in §3.2e
- **Version of SR 832.106 for the reference year** → §3.2d-bis: the Fedlex filestore
  It is addressable by date. Lugano is 1 region in all verified versions
- **BEJUNE alignment** → §8bis.1: confirmed on `ne.ch` and `jura.ch` **only for
  autumn**. Winter diverges in the three cantons
- **City of St. Gallen** → §8sexies.1: **does not diverge**. Follows the cantonal weeks on
  all four types; his `Winterferien` are the type `sport`, already covered
  from the override. The `SG` line is confirmed, not corrected
- **Freiburg** → §8sexies.2: closed on two school years, all types, in HTML
  textual. However, §8ter.8 attributed the divergence to the wrong region: it is **Kerzers**,
  not Morat/Murten
- **Valais, half German-speaking** → §8sexies.3: closed. The source is the `Übersicht Schul- und
  Ferienplan`, textual table by municipality, listed **only on the German landing page**
