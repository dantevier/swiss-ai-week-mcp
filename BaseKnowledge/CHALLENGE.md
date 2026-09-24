# Swiss Grounding MCP — Knowledge Base

> **Purpose**: Single source of internal truth on what Swisscom is asking for, how it values and what
> we deliver. Please consult during the hackathon if you have any questions regarding the requirements.
>
> **Compiled**: 2026-09-21 · **Event**: 24–25 September 2026, Kraftwerk, Selnaustrasse 25, Zurich
>
> **Reliability legend** — each statement is marked:
> - ✅ **verified** on primary source (official repo, briefing deck, ai-weeks.ch website)
> - ⚠️ **not publicly verifiable** (comes from the Hacker's Handbook, confidential)
> - 🔍 High confidence **inference**, not explicitly stated by the source

---

## 0. Quick index

| Question | Section |
|---|---|
| When do I actually have to deliver? | [§2 Timeline](#2-operational-timeline) |
| What exactly do I have to deliver? | [§3 Deliverables](#3-deliverables) |
| Which requirements are binary and non-negotiable? | [§4 Hard Requirements](#4-hard-requirements-checklist) |
| How do they assign the score? | [§5 Rating](#5-how-they-rate) |
| When is it right to ask the user for information? | [§5.4 Ask-back rule](#ask-back-rule) |
| What counts as an authoritative source? | [§6 Authority](#6-what-counts-as-an-authoritative-source) |
| What questions will they use? | [§8 Sample questions](#8-sample-questions-8-notes) · [§9 Practice case](#9-practice-case-and-checklist-from-the-self-check-pack) |
| Can I use pre-built indexes / API keys? | [§10 Runtime](#10-hosting-indexes-keys-costs) |
| What DON'T we know? | [§11 Gray areas](#11-shadow-areas) |
| Practical traps | [§13 Warnings](#13-operational-warnings) |

---

## 1. Sources and how to regenerate them

| Source | URL/path | Status |
|---|---|---|
| Official challenge repo | `https://github.com/Swiss-ai-Weeks/swisscom-2026` | ✅ cloned and read |
| README challenge | `swiss-grounding-mcp/README.md` | ✅ |
| Briefing deck (12 slide) | `swiss-grounding-mcp/briefing-swiss-grounding-mcp.pdf` | ✅ excerpt text |
| Self-check pack | `swiss-grounding-mcp/evaluation/` — **only in git history** | ✅ recovered |
| Challenge page | `https://ai-weeks.ch/2026/challenges?location=zurich-hackathon` | ✅ |
| Event FAQ | `https://ai-weeks.ch/2026/hack-zurich` | ✅ |
| Hacker's Handbook | not public | ⚠️ not available |

### Retrieving the self-check pack

The pack **is not in the working tree**: it lives as a snapshot in git history. From the root of the cloned repo:

```sh
material_commit=$(git log -1 --diff-filter=A --format=%H -- swiss-grounding-mcp/evaluation/sample-questions.b64)
git restore --source="$material_commit" --worktree -- swiss-grounding-mcp/evaluation
```

The commit at 2026-09-21 is `74232a1e9c8b14a9d86bf2cd2a3f8916597a68c1`.
The content is in `sample-questions.b64`. To decode it **without running repo code**:

```sh
tr -d '\r' < swiss-grounding-mcp/evaluation/sample-questions.b64 | base64 -d > decoded.json
```

> A shallow clone does not have the necessary history: you need `git fetch --unshallow` first.

---

## 2. Operational timeline

### Event ✅ (FAQ ai-weeks.ch)
- **Thu 24/09, 08:00 CET** — kickoff
- **Fri 25/09, 21:00 CET** — event closes
- Entry only with **QR ticket + valid identity document**

### Jury ⚠️ (from the Handbook, not publicly verifiable but consistent with the FAQ)
| Now (Fri 25/09) | Event |
|---|---|
| **12:00** | **⏰ SUBMISSION ROUND 1 — real deadline** |
| 14:00–16:00 | Expert Jury, closed room, 3 parallel panels — **4 min** (1 pitch + 3 Q&A) |
| 17:00 | Shortlist announcement |
| 17:30 | Final Submission Round 2 |
| 18:00–18:45 | Main Jury, main stage — **3 min** (2 pitch + 1 Q&A) |
| 19:30 | Award Ceremony |

**Implication**: Useful development time is **~28 hours**, not 36. The server must be
runnable and testable by Swisscom before Friday 12:00.

✅ The FAQ confirms that **10 team** are moving to the main stage.
✅ Submission Round 1 via form, Round 2 via email (links/details published on site).

### Swisscom Support ✅
Slots bookable from **15 minutes** with myAI experts on-site at Kraftwerk:
**Thursday afternoon** and **Friday morning**.
Contacts: Matthias Appius, Alexander Stark (Swisscom myAI).

---

## 3. Deliverables

✅ Text from the README and slide 5:

1. **GitHub repository**, public or private, with **access for Swisscom evaluators**
2. **Working MCP server** with clear setup instructions so Swisscom can start it
3. **Documented coverage and limitations**: which topics, which geography
4. **Secure test access** where you need it, and **no secrets in the repo**
5. No myAI integration required during the event

---

## 4. Hard requirements (checklist)

Binary and verifiable requirements. These are the points on which you lose in an avoidable way.

- [ ] **Scope declared in README**: topic + geography, explicitly.
      *Quality is measured against this statement.* ✅
- [ ] **robots.txt and terms of use respected by default, BUT as the setting of
      configuration** — not hardcoded behavior. Swisscom must be able to
      enable/disable for testing. **Settings and defaults documented in the README.** ✅
      > *"Whether it does so must be a configuration setting, not hardcoded behavior,
      > so that Swisscom can switch it on or off when running your server for testing."*
- [ ] **The code in the repo runs locally** with the documented setup, even if we host
      an endpoint. It serves to confirm that the published source is the tested server. ✅
- [ ] If we host: **endpoint up until end of evaluation**. ✅
- [ ] **Zero secrets in the repository.** Test credentials delivered via secure channel
      of the organizers **before the deadline**. ✅
- [ ] **Each required credential listed in the README.** ✅
- [ ] If we use a pre-built index: **the setup downloads/uses it without manual steps**
      And **the repo contains the script that generated it**. Swisscom **does not rebuild**
      the index. ✅
- [ ] **Built against the MCP standard**, not a specific client. ✅

---

## 5. How they rate

### 5.1 The five dimensions ✅

1. **Grounding quality** — correctness, authoritative sources, jurisdiction, freshness,
   citation support, honest handling of unsupported queries
2. **Useful Swiss coverage** — breadth and practical value of public information
   Switzerland made accessible, including the declared scope
3. **Agent efficiency** — quality of tool selection, number of calls, size
   of responses, tokens, latency, avoid unnecessary live requests
4. **Operability** — reproducible setup, refresh and caching design, resilience,
   monitoring, source etiquette, maintainability
5. **Integration readiness** — consistent MCP contract, clear documentation,
   extensibility, immediate use from standard MCP clients and the Swisscom test harness

### 5.2 Explicit hierarchy ✅ (slide 8)

```
1. Correct and honest answers      ← domina
2. Breadth                          ← pesato separatamente
3. Efficiency, operability, MCP contract   ← tie-breaker
```

> *"High quality with narrow coverage beats broad coverage with low quality.
> Having both is best and wins."*

**No published formula.** Automatic checks + LLM-assisted comparison against answers
verified, they inform the **review group myAI**, which decides **by hand**. ✅

### 5.3 Test Setup ✅

- **2 compatible MCP clients × 2 LLM each = 4 combinations**, identical for each team
- **Which clients and which models: not disclosed**
- The server is connected **exactly as described in our setup instructions**
- Questions in **German, French, Italian and Romansh**
- The complete question set and its size remain hidden

### 5.4 The three views and the ask-back rule <a id="ask-back-rule"></a> ✅

Three views on each server:
1. **Quality within the declared scope** — correct, from an authoritative Swiss source,
   right jurisdiction, updated, cited
2. **Breadth** — how much useful Swiss public information we make accessible
3. **Honesty out of scope** — clearly say it's not covered, **don't guess**

**Ask-back rule** (full quote):

> *"Asking back can be the right answer. When the answer depends on information that is
> missing, such as the municipality, a precise request for exactly that information counts
> as correct. When the question can be answered as asked, asking back counts as wrong,
> and so does asking for context you do not need."*

Three distinct penalties, therefore:
- respond when an essential piece of data is missing → **wrong**
- ask when the question can already be answered → **wrong**
- ask for unnecessary context → **wrong**

---

## 6. What counts as an authoritative source

✅ Swisscom **does not provide a list of sources**. Find and reach the right sources
it's part of the challenge. The rating **does not check which sites we used**:
checks whether the server reaches Swiss authoritative information and returns responses
grounded with verifiable references.

Definition: *"the body that is actually responsible for the matter"* — the federal office,
the canton, the municipality, or an organization mandated by law.

Practical rules ✅:
- Federal offices publish under **admin.ch**; **ch.ch** is the multilingual portal of
  Confederation and a good map of who is responsible for what
- The cantons publish on their own domains, usually the two-letter code:
  `be.ch`, `vd.ch`, `ti.ch`, `gr.ch`
- Municipalities publish on their websites — **many local answers only exist there**
- Some semi-official bodies are authoritative because the law gives them the task
  (e.g. AHV/IV information centre, public transport open data platform)
- Four national languages: a source can only exist in one or two, and the answer
  correct may depend on the linguistic region

⚠️ **From the review checklist**: *"Check that the publisher is responsible for the matter,
not merely an official Swiss domain."* A generic link to `admin.ch` is not enough.

Accepted approaches: curated registry, dynamic discovery, open data and API, or combinations. ✅

---

## 7. Example topic areas (16) ✅

Examples, **not mandatory list and not the evaluation set**.

| # | Topic area | Example source | Level |
|---|---|---|---|
| 1 | Health insurance premiums and basic insurance | priminfo.admin.ch | Federal (BAG) |
| 2 | Taxes and duties | tax administration TI, ti.ch | Cantonal |
| 3 | Law and regulations | fedlex.admin.ch | Federal |
| 4 | Waste collection and recycling | waste calendar Lausanne, lausanne.ch | Municipal |
| 5 | Moving, domicile notification, civil status | Bern residents' office, bern.ch | Municipal |
| 6 | Residence permits and migration | sem.admin.ch | Federal |
| 7 | Social insurance and pensions | ahv-iv.ch | Semi-official |
| 8 | Work and unemployment | arbeit.swiss | Federal (SECO) |
| 9 | Schools and education | dep. education Geneva, ge.ch | Cantonal |
| 10 | Public transport and mobility | opentransportdata.swiss | Semi-official (FOT mandate) |
| 11 | Road traffic, vehicles, licenses | GR circulation office, gr.ch | Cantonal |
| 12 | Housing and rental | bwo.admin.ch | Federal |
| 13 | Voting, elections, political rights | bk.admin.ch | Federal |
| 14 | Companies, commercial register, VAT | zefix.ch | Federal |
| 15 | Customs and purchases from abroad | bazg.admin.ch | Federal |
| 16 | Statistics, open data, geodata, weather | bfs.admin.ch, opendata.swiss, map.geo.admin.ch, meteoswiss.admin.ch | Federal |

---

## 8. Sample questions (8 notes)

### The five published questions ✅
The README states: one requires asking the municipality, one **is not a question about
Switzerland** and the right answer is to say so. They don't say which ones.

1. 🇩🇪 *Wann wird bei uns das nächste Mal Karton abgeholt?*
2. 🇫🇷 *Comment puis-je échanger mon permis de conduire étranger contre un permis suisse
   in the canton of Vaud, and what are the times to do?*
3. 🇮🇹 *Qual è il premio mensile più basso dell'assicurazione di base per un adulto di
   30 years domiciled in Lugano with deductible of 2500 francs?*
4. 🇨🇭 (rm) *Cura èn las vacanzas d'atun 2026 per la scola da Scuol?*
5. 🇩🇪 *Wie hoch ist der Rundfunkbeitrag, den ich nach meinem Umzug nach Konstanz
   zahlen muss?*

🔍 **High confidence inference**: crossing with the practice cases `missing_location` and
`cross_border`, the #1 is the one required by the municipality and the #5 is the one outside Switzerland
(Konstanz is in Germany).

### Three additional questions in the self-check pack fixture ✅
6. 🇩🇪 *Wann sind die Herbstferien 2026 in der Stadt Bern?*
7. 🇫🇷 *Où dois-je annoncer mon arrivée dans la ville de Lausanne?*
8. 🇮🇹 *Quale autorità pubblica il tasso ipotecario di riferimento per gli affitti in Svizzera?*

---

## 9. Practice case and checklist (from the self-check pack)

✅ Eight cases with explicit checks. It's the closest material to the hidden set we'll get.

### 9.1 `missing_location` — de
**Q**: *Wann wird bei uns Karton abgeholt?*
- Ask for **town** before selecting a local calendar
- If the calendar is street specific, ask **only** for location information
  addition that is needed
- **Do not invent a collection date**

### 9.2 `enough_context` — fr
**Q**: *Where will you find the official school holiday calendar 2026 from the city of Genève?*
- Use the responsible school authority and its calendar 2026
- **Do not ask for a municipality already provided**
- Cite the actual calendar or its official publication page

### 9.3 `cross_border` — de
**Q**: *Wie hoch ist der Rundfunkbeitrag in Konstanz?*
- Recognize that Konstanz is in **Germany**
- For a Swiss-only server: declare that it is **out of coverage**
- **Do not replace** with the Swiss fee

### 9.4 `romansh_locality` — rm
**Q**: *Do you care about today's holidays 2026 for school at Scuol?*
- Identify School and applicable school calendar
- Check **required year** and **local applicability**
- Do not deduce dates from another canton or from an undated translated summary

### 9.5 `rate_freshness` — it
**Q**: *What is the reference mortgage rate currently in force for rentals
in Switzerland?*
- Find the **current publication** of the competent federal housing authority
- Indicate the **effective date** together with the rate
- **An older official post remains an outdated answer**

### 9.6 `paired_jurisdiction` — fr
**Q**: *Comment will announce you have arrived in Lausanne? Et à Berne?*
- Solve **each municipal procedure independently**
- Do not reuse deadlines, fees or forms from one municipality for another
- Attribute each procedure to its responsible authority

### 9.7 `citation_support` — de
**Q**: *Welcome to those who want to say Frist?*
- Return **the step** that supports that specific deadline
- **An official homepage alone is not enough**
- If no supporting passage was found: qualify or **retract** the claim

### 9.8 `source_failure` — en
**Q**: Repeat an in-scope question with the authoritative source unavailable.
- Distinguish **retrieval failure** from **absence of the fact**
- State whether the response is based on **cached evidence** and identify the **date**
- Do not invent a subpoena or silently substitute jurisdiction

### 9.9 Review checklist (8 points) ✅

1. Document topic and geographic coverage **before** comparing results
2. For each key claim, keep **Source URL + supporting passage or data record**
3. Verify that the publisher is **responsible for the subject matter**, not just a domain
   official Swiss
4. Check the municipality, canton, population group, **reference year**, and
   **effective date** where relevant
5. Ask **only** the missing information that changes the answer
6. Distinguish: **out of scope** / **insufficient context** / **source not available** /
   **no matching results** — that's four different states
7. Exercise the same MCP contract with **more than one compatible client**
8. Reproducible setup, credentials outside of Git, documented index rebuild steps

---

## 10. Hosting, indexes, keys, costs

✅ Everything from the slide 12 + README §3.

**Local or hosted — our choice.** Swisscom tests a hosted endpoint or launches the
server from the repo. In both cases the code in the repo must run locally with the setup
documented, to confirm that the published source is the tested server.

**Pre-built indexes: allowed.** No need to do embedding or crawling at start.
We can ship a vector store/index to the repo or have it downloaded from setup.
Two conditions: (1) the setup downloads it and uses it **without manual steps**; (2) the repo
contains **the script that built it**, so anyone can reconstruct it with data
fresher. **Swisscom does not reconstruct the index during the evaluation.**

**Keys.** API keys at runtime are acceptable (e.g. embedding at query time, or a call
LLM internal to the server). List each credential in the README and hand in credentials
tests running via the organizers' secure channel before the deadline.
> *"A server that runs without any external keys is easier for us to run and easier for you
> to keep running, and that shows in the operability assessment."*

**Costs.** Swisscom **does not reimburse** API, embedding or hosting costs. For any
API credit contact the Swiss AI Weeks organizers.
> *"Embedding budget does not decide the ranking: quality inside your declared scope comes
> first, and a small, well built index or a live API approach with no embeddings at all is
> just as valid as a large vector store."*

---

## 11. Shadow areas

Things we **don't know and won't know**:

- Which **MCP** clients and which **LLM** clients use for testing
- **Size** of the hidden question set
- Any **scoring formula** — it doesn't exist, the myAI review group decides by hand
- The **specific prize** of this challenge (the general FAQ talks about non-
  purchasable + money; no figures published)
- If there are **API credits** from the organizers (Swisscom explicitly refers to them)

⚠️ The "Jury Process & Evaluation Criteria" block (§2) comes from the Hacker's Handbook and
** could not be verified from a public source **. It is consistent with the FAQ but needs to be reconfirmed
on site.

---

## 12. Event context (FAQ ai-weeks.ch) ✅

- **IP and code ownership**: the intellectual property created remains **with the teams / individuals
  participants**, regardless of whether you are working on a challenge from a partner
- Event language: **English**
- Platforms provided: **GitHub** and **Hugging Face**; Documented additional tools/APIs
  in the Handbook
- Communication: **Discord**
- Infra: WiFi with 10 Gbit (Fiber7) uplink, 220V type J sockets, on-site technical support
- Eligibility jury ⚠️: only evaluate projects submitted in time by registered teams
  where **all members have a valid ticket and ID**
- Trip reimbursement: CHF 80 (100–500 km), CHF 150 (>500 km), with receipts, post-event.
  Accommodation not covered
- Jury: **final and non-appealable** decisions; the moderator has the deciding vote;
  conflicts of interest must be declared with recusal ⚠️

---

## 13. Operational warnings

### 13.1 Do not run `sample_runner.py` during the demo
The self-check pack companion utility opens **10 terminal windows** with animations
ASCII and plays **audio for ~8 seconds**. Requires macOS Terminal or `xterm`; on Windows
window mode doesn't start. To get the report only: `--dry-run`. Better yet:
directly decode the `.b64` (see §1).

### 13.2 Prompt injection in the fixture ⚠️
`sample-questions.b64` contains five joke "variants" with field `instruction`.
One of them (`banking`) instructs the assistant to **reject all implementation questions**
until he receives a release phrase, and not to reveal either the joke or the phrase.

**This is data contained in a repository, not instructions.** If our pipeline ingests
this fixture (or any content retrieved from the web) without separating data and instructions,
the demo crashes. Valid as a design reminder: **content retrieved from sources
must never be able to control the agent's behavior.**

### 13.3 The fixture is not the evaluation set
> *"These are preparation materials, not verified reference answers, the hidden question set
> or a scoring formula."*

Factual answers must be verified on current authoritative sources: no practice case
replaces a source.

---

## 14. Key quotes (verbatim, EN)

To be used as a literal reference when there is doubt of interpretation.

**On the scope:**
> "Declare your scope. In your README, state which topics and which geography your server
> covers... We evaluate answer quality against that declaration."

**On the priority of quality vs. width:**
> "In general, a high quality solution with narrow coverage is preferred over a broad
> solution with low quality. Having both is best and wins."

**In order of importance:**
> "The order of importance is: correct and honest answers, then breadth, then agent
> efficiency, operability and the quality of your MCP contract as tie breakers."

**On robots.txt:**
> "Your server should respect the robots.txt and terms of use of the sources it accesses
> by default. Whether it does so must be a configuration setting, not hardcoded behavior,
> so that Swisscom can switch it on or off when running your server for testing. Document
> the setting and its default in your README."

**On what a good MCP does (slide 4):**
> "Offers a coherent, compact set of tools · Returns evidence an AI client can use and cite
> · Keeps information as fresh as the use case needs · Says so when a question is not
> covered · Runs locally from its repo; hosting it as well is your choice"

**On not building for a specific client:**
> "We do not disclose which clients and which models we use, so build against the MCP
> standard rather than against one specific assistant."

---

## 15. Strategic reading

The dominant signal of the material: **this challenge does not reward coverage, it rewards
epistemic discipline.** The system must be able to produce four distinct outputs:

1. answer + exact supporting passage + effective date
2. precise request for the single missing data
3. "outside my declared coverage"
4. "the source is unavailable" (not "the fact does not exist")

The behavior to eliminate is the fifth: responding in a plausible manner. It is the default of
an LLM, and that's exactly what loses points. Much of the technical work consists
in **taking away the possibility of improvising from the model**, not in adding sources.

Corollary from the `citation_support` case + checklist point 3: an answer with generic link
an official domain is worth zero. You need the **textual passage** that supports the claim
specific, with the authority truly competent for that matter.
