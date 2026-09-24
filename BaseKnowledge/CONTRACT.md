# MCP contract

> Historical contract and routing measurements from a separate Node/TypeScript
> rehearsal. These tools and results are not implemented in the current Python repository;
> see [STATUS.md](STATUS.md).

> **Rehearsal status: v6, 212 runs across six versions. THE GATE IS RED (§8.6).**
> Sample question 5 produced `NONE` on Haiku 4.5 in **3 of 12 runs**: a 25% rate
> on the critical metric. Earlier "33/33" and "41/41" passes used only one run
> per cell and missed it.
>
> ⚠️ **The test falsified a line of §1**: see §8.4.
>
> ⚠️ **At this rehearsal snapshot, there was no domain server yet.** Runtime behavior
> described here was a contract, not code: `manifest.py` was the only executable
> domain file, and `src/tools.ts` held only tool definitions.
>
> ⚠️ **The descriptions below are a reading copy. The rehearsal source was
> `src/tools.ts`**, imported by both server and tests. If they diverge, the
> code takes precedence.
>
> Requirements: [CHALLENGE.md](CHALLENGE.md) · Sources and constraints: [SOURCES.md](SOURCES.md)
>
> Rehearsal scope: **health insurance premiums** and **mortgage reference rate** across
> Switzerland; **school holidays** and **foreign licence exchange** in all 26 cantons.

---

## 1. Design principle

Swisscom tests with **2 clients × 2 undisclosed LLMs**. Therefore:

> Everything we delegate to the model varies across four configurations.
> Everything the server decides is constant across four configurations.

**Fat server, thin model.** The model decides which tool to call. The server
resolves jurisdiction and decides when to ask back, what to cite, which dates
apply, and the legal status of each source.

### The asymmetry that drives the descriptions

| Error | Cost |
|---|---|
| The model does not call anything | **catastrophic** — hallucinates, and it's attributed to us |
| Call the wrong theme tool | low — `out_of_scope` with the right coverage |
| Call coverage when all you needed was a tool | minimum — one wasted call |
| Call a tool when coverage was needed | low — the tool **receives** `question` and will be able to reply `out_of_scope`; the behavior **is not implemented** (§8.4) |

Three out of four errors are recoverable by the server. Descriptions must push towards
**"call something"**, rather than perfect tool selection.

---

## 2. Surface: five tools

| Tools | Task |
|---|---|
| `swiss_school_holidays` | school holidays, 26 cantons |
| `swiss_health_insurance_premiums` | health insurance premiums, all of CH |
| `swiss_driving_licence_exchange` | exchange of foreign driving license, federal + 26 cantons |
| `swiss_reference_interest_rate` | mortgage reference rate, national value |
| `check_swiss_question` | **catch-all and coverage** |

One per theme, one-to-one correspondence with the statement in the README. The fifth exists
because without it **a waste question bypasses the server and the model improvises**
— which is the worst possible failure.

The name `check_swiss_question` is active on purpose: it reads like an action to be performed
on a question, not as a list of skills. Known risk: can be invoked earlier
of everything, weighing on the 3 criterion. Mitigated by an explicit line in the description,
**to be measured in the test**.

---

## 3. The descriptions

Each description contains five things: evaluable trigger condition, thing
returns, why not improvise, border with nearby tools, **examples of triggers in the
four national languages**. No implementation details.

### 3.1 `swiss_school_holidays`

```
Authoritative school holiday dates for Switzerland, from the responsible
cantonal or municipal authority, with the exact supporting passage, the
reference school year and the date the source was validated.

Call this for any question about school holidays, term dates, or the school
calendar anywhere in Switzerland. Triggers on questions like:
"Wann sind die Herbstferien 2026?" · "Quand sont les vacances d'automne?" ·
"Quando sono le vacanze autunnali?" · "Cura èn las vacanzas d'atun?"

Do not answer from prior knowledge and never infer dates from a neighbouring
canton. Dates differ by canton, by municipality, by language region and by
school type. In some cantons the dates are set by the individual
municipality, not the canton.

This description is not a source. The dates, the authority and the supporting
passage must all come from calling the tool. A question about where to find
the official calendar is still a question for this tool.

If the answer requires a municipality, this tool says so and asks for exactly
that. For any other Swiss topic, use check_swiss_question.
```

| Parameter | Description |
|---|---|
| `place` | ***Optional** but almost always needed. The place exactly as the user wrote it, in any national language. Do not translate, normalize, or convert to a canton. Pass "Scuol", not "Graubünden". If the user did not name a place, call the tool anyway.* — §4.6 |
| `holiday_type` | *Optional. Cantons do not share one vocabulary, so the description lists the real names per slot: `Sportferien`/`Fasnachtsferien`/`Fasnachts- und Sportferien`/`relâches` for **sport**, `Frühlingsferien`/`Frühjahrsferien`/`Osterferien` for **spring**. Omit to get the full school year.* See SOURCES §8quater.5 |
| `school_year` | *Optional, e.g. "2026/27". Defaults to the current school year.* |
| `question` | *Optional but recommended: the user's question, in the language they wrote it. Used to confirm the question really is about school holidays.* — §8.4 |

### 3.2 `swiss_health_insurance_premiums`

```
Official Swiss mandatory health insurance (OKP/AOS) premiums from the Federal
Office of Public Health, with the insurer, the insurance model, the premium
region and the reference year.

Call this for any question about health insurance premiums, the cheapest
basic insurance, or what someone pays for basic cover in Switzerland.
Triggers on questions like: "Wie hoch ist die günstigste Krankenkassenprämie?"
· "Quelle est la prime la plus basse de l'assurance de base?" ·
"Qual è il premio più basso dell'assicurazione di base?"

Do not answer from prior knowledge. Premiums change every year and depend on
the premium region of the specific municipality, the age class, the deductible,
whether accident cover is included and the insurance model. A figure from
memory will be wrong.

For any other Swiss topic, use check_swiss_question.
```

| Parameter | Description |
|---|---|
| `place` | ***Optional** but almost always needed. The municipality exactly as the user wrote it. The premium region is a legal assignment per municipality, not per canton.* — §4.6 |
| `age` | ***Optional**, string. Age in years as written, e.g. "30", or the age class if that is all the user gave. It was `integer`, and it contradicted its own description.* |
| `franchise` | ***Optional**. Annual deductible in CHF, e.g. 2500.* — §4.6 |
| `accident_cover` | *Optional: true or false. If omitted, both values ​​are returned and the distinction is stated.* |
| `year` | *Optional. Defaults to the current premium year.* |
| `question` | *Optional but recommended: the user's question, in the language they wrote it. Used to confirm the question really is about premiums.* — §8.4 |

### 3.3 `swiss_driving_licence_exchange`

```
How to exchange a foreign driving licence for a Swiss one: the federal deadline
and rules, plus the procedure, forms, fee and office of the responsible cantonal
road traffic authority.

Call this for any question about converting, exchanging or registering a foreign
driving licence in Switzerland. Triggers on questions like:
"Wie tausche ich meinen ausländischen Führerausweis um?" · "Comment échanger
mon permis de conduire étranger?" · "Come converto la mia licenza di condurre
estera?"

Do not answer from prior knowledge. The deadline and the exam requirements are
federal law and depend on the country that issued the licence; the procedure,
the fee and the forms are cantonal and differ between cantons. A complete answer
cites both levels, each from the authority responsible for it.

For any other Swiss topic, use check_swiss_question.
```

| Parameter | Description |
|---|---|
| `place` | ***Optional**. The canton or place of residence, exactly as the user wrote it. By omitting it, the tool still responds to the federal level and declares that the procedure depends on the canton.* — §4.6 |
| `issuing_country` | *Optional. Determines whether a control drive or a theory exam is required.* |
| `question` | *Optional but recommended: the user's question, in the language they wrote it. Used to confirm the question really is about exchanging a license, and not about another arrival formality.* — §8.4 |

### 3.4 `swiss_reference_interest_rate`

```
The Swiss mortgage reference interest rate used for rent adjustments
(hypothekarischer Referenzzinssatz), published by the Federal Housing Office,
with the date it came into force, the date it was last confirmed, and the legal
basis.

Call this for any question about the reference rate, rent increases or
reductions tied to it, or what rate applied at a given time. Triggers on
questions like: "Wie hoch ist der Referenzzinssatz?" · "Quel est le taux
hypothécaire de référence?" · "Qual è il tasso ipotecario di riferimento?"

Do not answer from prior knowledge. The rate is revised quarterly and a value
from memory is likely outdated. Note that the date a value was last confirmed
is not the date it came into force: the current rate has been unchanged since
2 September 2025 but was reconfirmed on 2 September 2026, and only the first
date is relevant for a rent adjustment.

This description is not a source. The publishing authority, the rate, the dates
and the legal basis must all come from calling the tool, which returns them
with a verifiable reference. A question about which authority publishes the
rate is still a question for this tool.

This is a single national value with no regional variation. For any other Swiss
topic, use check_swiss_question.
```

| Parameter | Description |
|---|---|
| `as_of` | *Optional dates. Returns the rate that was in force on that date. Omit for the current rate.* |
| `question` | *Optional but recommended: the user's question, in the language they wrote it. Used to confirm the question really is about the reference rate.* — §8.4 |

### 3.5 `check_swiss_question`

```
Checks whether this server can ground a question about Switzerland, and says
precisely what it covers and what it does not.

Call this for ANY question about Switzerland that does not clearly match one of
the four topic tools — for example waste collection and recycling, cantonal or
municipal taxes, residence registration, residence permits and migration,
public transport, the commercial register, customs, social insurance and
pensions, unemployment, housing and tenancy law, voting, or statistics.

Also call it when you are unsure whether a question is about Switzerland at
all, and when the question turns out NOT to be about Switzerland: someone
moving abroad, a fee charged by another country, a foreign town. Stating
plainly that the place is outside Switzerland is a correct and useful answer,
and this tool is what provides it.

Also call it to find out what this server covers before answering anything.

Returns either a precise statement that the topic or the jurisdiction is not
covered, together with what is covered instead, or a pointer to the tool that
does cover it. A clear "not covered" is a correct and useful answer; answering
a Swiss question from prior knowledge is not.

If the question clearly matches one of the four topic tools, call that tool
directly instead of this one.
```

| Parameter | Description |
|---|---|
| `question` | *Optional: the user's question, in the language they wrote it. Used to give a specific rather than generic answer.* |
| `topic` | *Optional: a topic keyword, if the question is about capability rather than a specific case.* |
| `place` | *Optional: a place, to check whether that jurisdiction is covered.* |

---

## 4. Parameter conventions

1. **`place` does not translate, does not normalize, does not convert into canton.** Without this
   adjust the model "aiuta" by turning Scuol into Grisons, and we lose the resolution
   municipal which is the whole value of the tool.
2. **Each optional has a default declared in the response**, never silent.
3. **Assumption stated instead of ask-back when alternatives are enumerable.**
   Accident coverage not specified → both values are returned with the
   distinction. 160 Zurich municipalities → you ask.
4. **No parameters are required on any theme tool.** One parameter
   mandatory moves the ask-back from the server to the client: the model that does not have the data or
   he invents it, or he doesn't call it. Not calling is the only mistake that §1 classifies
   catastrophic, and with `place`, `age` and `franchise` mandatory the `need_info` state of
   §5.1 was **unreachable**. The one who decides what is missing is the server, and to decide it he must
   first be called. *(Corrected to 2026-09-22; numbered §4.6 in references.)*
5. **Each thematic tool receives `question`.** Derived from §8.4: without the question, a tool
   thematic can declare the jurisdiction outside the scope but never the topic, and responds
   correctly to a question no one asked. It is also what makes the state
   `out_of_scope` of §5.1 available on all five tools, not just coverage.
6. **School type is not a parameter.** We answer for compulsory schooling and
   is declared, reporting whether other types differ. It derives from the Friborg case
   (SOURCES §8ter.8): School type is a dimension of jurisdiction, but exposing it
   as a parameter it would produce more errors than it avoids.

---

## 5. The response envelope

### 5.1 The five states

If these states are not explicit in the contract, the model collapses them into "I do not know".
The review checklist point 6 requires four; with a positive answer it's five.

| Status | When | Minimum content |
|---|---|---|
| `answered` | answer found | §5.2 |
| `need_info` | a piece of data is missing that **changes** the answer | which data, why, and candidates if ambiguous |
| `out_of_scope` | outside the declared coverage | why (topic / jurisdiction / non-Swiss) + what we cover |
| `source_unavailable` | source cannot be reached | explicitly distinguish this from "the fact does not exist"; include the cache date if answering from cache |
| `no_match` | source reached, no results | the fact does not appear - it is not a technical error |

The last two seem like pedantry and are the `source_failure` practice case to the letter.

### 5.2 Positive response fields

Each field arises from an observed failure in research.

| Field | Why |
|---|---|
| `passage` — probative passage verbatim | `citation_support`: a homepage is not enough |
| `authority` + `level` | checklist point 3: competent body, not just official domain |
| `source_url` | verifiable by a human |
| `effective_from` | the reference rate has **four** dates and choosing the wrong one gives a false answer citing the right source |
| `published_at` | distinct from the previous one |
| `reference_year` | 2026 awards do not mix with 2027 ordinance |
| `source_status` — `binding` / `indicative` / `provisional` | Schwyz publishes open data that declares itself to be non-binding |
| `derived` — boolean + rule applied | SH and SG publish `KW 40–42`, not dates |
| `assumptions[]` | "senza copertura infortuni", "scuola dell'obbligo", "anno 2026" |
| `source_validated_at` | three out of three cantonal deep links were dead |

### 5.3 Size discipline

The 3 criterion penalizes large answers.

- **A passage, not the document.**
- Fields present only when they apply.
- The manifest **out** of positive responses.
- **Truncate explicitly, never silently**: a list cut without warning is
  indistinguishable from incomplete coverage, and would be read as such.

---

## 6. The coverage manifest

### 6.1 Key and fields

> Implemented in `coverage/*.toml` (TOML, one file per theme) + `manifest.py`
> (loader, validator, README block generator). 62 entries.

Key: **(topic × jurisdiction × sub-topic)**. The theme is not enough: in BE autumn is
cantonal and municipal February; in SW autumn is uniform while sport and spring
vary; in AG the *duration* of autumn varies.

`subtopic` is an **override, not a mandatory coordinate**: `"*"` applies to all
sub-themes, and a specific line is written only where the model changes. Without this
rule holidays alone would make 130 rows instead of 32. The named exceptions are
rows, not nested structures: `jurisdiction = "OW/Engelberg"`.

The lookup is **most-specific-wins, with jurisdiction beating the sub-theme**:

```
(OW/Engelberg, autumn) → (OW/Engelberg, *) → (OW, autumn) → (OW, *) → (CH, autumn) → (CH, *)
```

Fields per entry: `theme`, `jurisdiction`, `subtopic`, `resolution_level`,
`on_missing_place`, `authority`, `authority_level`, `source_url`, `landing_url`,
`source_status`, `validated_at`. Optional: `legal_basis`, `ask_back`, `derivation`,
`notes`.

`resolution_level` ∈ `national` · `cantonal_uniform` · `per_municipality_in_source` ·
`per_language_region` · `rule_with_exceptions` · `cantonal_framework_municipal_choice` ·
`delegated` — describes **what the world is like**, and powers the README statement.

`on_missing_place` ∈ `answer` · `resolve_in_source` · `ask` — describes **what the
server**, and it is this field that decides the ask-back, not the model's judgment.

**The two axes are separate because one does not imply the other.** AG, AR and SG share the
model `cantonal_framework_municipal_choice` but they behave in three different ways: AG
asks the municipality (duration varies), AR responds with `source_status: indicative`, SG
he asks. An enum that describes the legal structure cannot decide the behavior.

Two invariants, both imposed by the validator:

- **`validated_at` empty = not covered.** An entry enters the declared coverage only
  when someone opened the document and pasted the URL. An invalid URL is not
  coverage, it's a good idea. It fails on the right side: FR and VS remain lines with
  the source identified and the coverage not declared.
- **`ask_back` mandatory when `on_missing_place = "ask"`.** The ask-back must be cited,
  not asserted (SOURCES §8ter.7).

`landing_url` is separated from `source_url` because deep links rot: AR, OW and NW
they gave 404 and the current document could only be found from the landing page
(SOURCES §8ter.9). The validator checks the content only on the `source_url` — the
`landing_url` only needs to respond, and can legitimately be a SPA.

### 6.2 Two consumers, one source

The **server** reads it to decide ask-back and out of scope. The **README** reads it at
build for coverage statement. If they differ, the jury sees it: it is exactly
the third view they evaluate.

The README **does not call the tool**, it reads the file. So the tool must never output
the whole manifest.

### 6.3 The rule that keeps the answers compact

> **Coverage is a statement of what we know to answer, not a list of
> answers.**

Grisons are not 100 lines: they are **one line**, "all municipalities, resolved in the document
cantonal". municipalities 100s are *data*, not coverage. With this rule the manifest is in
60–90 lines instead of thousands.

**If an answer from `check_swiss_question` contains a list of municipalities, the design is
slipped.**

### 6.4 Three levels of response

| Call | Returns |
|---|---|
| no arguments | the statement: 4 topics, geographic scope, and what we **don't** cover. ~15 lines |
| `topic` | the resolution model **summarized by exception** |
| `topic` + `place` | the precise line — **this is what drives the ask-back** |
| `question` | the keyword network: specific rejection instead of generic |

Example of the second level, six lines instead of twenty-six:

> Covered for all 26 cantons. Uniform in 12. By municipality, in the cantonal document,
> in 5 (GR, LU, SW, UR, SZ). By language region in 2 (BE, VS). Uniform with
> exceptions named in 3 (FR, OW, AI). Cantonal framework with municipal choice in 3
> (AG, AR, SG). Delegate to municipalities in 1: **ZH requires municipality**.

---

## 7. Rules derived from research

Each line originates from a real failure documented in SOURCES.md.

| Discovery | Rule in the contract |
|---|---|
| ZH delegation, BE February only, SO sport/spring only; **AG, AR and SG do not have sports holidays in the cantonal document** (SOURCES §8quinquies) | resolution by (jurisdiction × sub-topic). In AG, AR and SG **changes the class itself** between holiday types: without the sub-theme, SG also asked the municipality at Christmas — a useless ask-back, which CHALLENGE §5.4 counts as wrong |
| The Friborg PDF was of the vocational schools | the school type is jurisdiction (§4.4) |
| Fedlex filestore addressable by date | federal sources interviewed **by reference date** |
| Schwyz: non-binding open data | `source_status` on each source |
| The Bernese PDF cites Plagne and Vauffelin, dissolved | the solver serves historical and current names |
| `ne.ch/…pdf` returns HTML with 200 | validate the **Content-Type**, never the extension |
| Fedlex filestore: invalid date → shell with 200 | validate the **content**, not the status |
| AR/OW/NW: deep link 404, v1.1 superseded by v1.3 | start from the landing page; `validated_at` |
| SH and SG publish `KW 40–42` | `derived` with the rule applied |
| Rate with four dates | `effective_from` ≠ `published_at` |

---

## 8. Testing descriptions — do this first

**No server needed.** All you need are the tool diagrams and a list of questions: you ask
more models *"quale tool chiameresti?"* and look at the distribution. It costs an hour, it's done
**Thursday morning before any deployment**, and measures the only variable that doesn't
let's check. Also meets checklist point 7.

### 8.1 Routing oracle

| # | Question | Language | Expected tool |
|---|---|---|---|
| 1 | *Wann wird bei uns das nächste Mal Karton abgeholt?* | de | `check_swiss_question` → waste, not covered |
| 2 | *Comment can I change my permission to drive outsider… in the canton of Vaud?* | fr | `swiss_driving_licence_exchange` |
| 3 | *What is the lowest monthly premium… in Lugano with a deductible of 2500?* | it | `swiss_health_insurance_premiums` |
| 4 | *Do you care about today's holidays 2026 for school at Scuol?* | rm | `swiss_school_holidays` |
| 5 | *Wie hoch ist der Rundfunkbeitrag… nach Konstanz?* | de | `check_swiss_question` → out CH |
| 6 | *Want the summer holidays 2026 in the city of Bern?* | de | `swiss_school_holidays` |
| 7 | *Where will you find the official school holiday calendar 2026 from Genève?* | fr | `swiss_school_holidays` |
| 8 | *Where do I announce my arrival in the city of Lausanne?* | fr | `check_swiss_question` → not covered |
| 9 | *Comment will announce when you arrive in Lausanne? Et à Berne?* | fr | `check_swiss_question` → not covered |
| 10 | *What is the reference mortgage rate currently in force?* | it | `swiss_reference_interest_rate` |
| 11 | *Which authority publishes the reference mortgage rate?* | it | `swiss_reference_interest_rate` |

Four languages, both types of off-scope, both federal themes.

### 8.2 What to measure

- **Missed calls**: the model answers without calling anything. It's the only metric
  fatal; all the others are recoverable.
- **Over-invocation of `check_swiss_question`**: called before thematic tools that
  they clearly matched. Weighs on the 3 criterion.
- **Confusion between thematic tools**: recoverable, but report overlapping descriptions.
- **Gap between languages**: if Romansh does worse, more trigger examples are needed.

---

### 8.3 Results, 2026-09-22

Performed **before** the event instead of Thursday morning: it didn't serve the team and doesn't
the server was needed. Implemented in [`test/routing-test.ts`](test/routing-test.ts), data
raw in [`test/answers-2026-09-22.json`](test/answers-2026-09-22.json).

**Method.** One clean conversation per question per run, never batched — batched
the model sees the pattern and self-corrects. Each context only saw the prompt, never
this document. Three levels of capacity: Opus 5, Sonnet 5, Haiku 4.5. **95 executions**
on three versions of the descriptions.

Two rows, and the distinction matters:
[`answers-2026-09-22.json`](test/answers-2026-09-22.json) contains **only the version
current** and is the gate — exits 0.
[`answers-history-2026-09-22.json`](test/answers-history-2026-09-22.json) contains all
trace v1 → v3 and **exits 1 on purpose**, because it contains the fixed defects.
Mixing them would make the exit code useless.

**The prompt does not ask "quale tool chiameresti".** Asking it forces a call and returns
blind the only fatal metric. The prompt explicitly offers `NONE`, and self-check
it fails if someone reintroduces the forcing formulation.

#### Two defects found, both on posted sample questions

| # | Symptom | Cause | Correction |
|---|---|---|---|
| 5 | Haiku didn't call anything on the Konstanz | question `check_swiss_question` covered *"unsure whether it is about Switzerland"*, **not the negative certainty**. A question clearly about Germany did not fall under any clause, and the model correctly concluded that the tool did not apply | explicit clause on outside Switzerland |
| 11 | Haiku **and Sonnet** called nothing about *"quale autorità pubblica il tasso?"* | **the description contained the answer**: *"published by the Federal Housing Office"*. The model already had everything without calling | clause *"This description is not a source"* on this and on `swiss_school_holidays` |

The second is the structural defect: **the facts meant to say "do not improvise" are
the same ones that allow you to answer without calling.** Each description that mentions a
concrete data to justify itself opens the same hole. `swiss_school_holidays` quotes
*"Geneva and Vaud… do not overlap by a single day"* and was exposed in the same way.

#### Complete revalidation of v3

Changing the catch-all description tap **all** 11 prompts, then two questions
they were not enough to declare the work closed. Complete pass, 11 × 3:

| Model | Executions | Exact | Missed |
|---|---|---|---|
| Opus 5 | 11 | 11 | 0 |
| Sonnet 5 | 13 | 13 | 0 |
| Haiku 4.5 | 17 | 17 | 0 |
| **total v3** | **41** | **41** | **0** |

#### The most important result is not a defect: it is the variance

The 11 application produced `NONE` in **2 runs on 7 with the same prompt and model**, and
not just on the weak model. In v1 it was over; in v2 it failed; with four repetitions
came back to pass.

> **A single execution is not a measurement.** It does not distinguish a broken description from a
> stroke of luck, and the metric that fluctuates is precisely the fatal one.

Operational consequence: the scorer accepts repetitions per cell.

How much is the 11 fix worth, in numbers: The failure rate measured in v2 was
**2 to 7 (29%)**; in v3 the 11 question resulted in **9 clean runs on 9**. Under the
base rate, seeing nine successes in a row has probability **0,71⁹ ≈ 4,8%**.

Enough to move on, **not** a demonstration. To get below the 1% they would be needed
~14 consecutive clean runs on the same cell.

#### What was NOT measured

- **One family of models.** Measures the model's robustness to strength, not its
  coverage of different families. The jury's 2 LLMs are not declared.
- **Zero over-invocations of `check_swiss_question` in 95 executions**, of which 41 after
  the two clauses that expand the catch-all. It was the risk foreseen in §2 for the name
  active, and it is the only one that the test could disprove: it never manifested itself. Stay
  It may appear on another model family.
- **Zero confusion between thematic tools in 95 executions.** The boundaries of the four
  thematic descriptions hold up; the work to be done was all on the catch-all.
- **Romansh: 7 executions on 7 correct**, but on **only one question**. No gap between
  languages observed, and the sample does not authorize us to say so. The question 4 is the only one in rm
  of the oracle: if you want a measure on Romansh, you need other questions, not others
  repetitions.

### 8.4 🔴 The test falsified the fourth line of §1

v4, Sonnet 5, question 9 — *"Comment annoncer mon arrivée à Lausanne? Et à Berne?"*,
domicile notification, out of coverage. Sonnet called
`swiss_driving_licence_exchange`. Once in six: in the other five, and in v1, v2 and v3
on all three models, it correctly called `check_swiss_question`.

The rate is low. The problem is not the rate.

**§1 classifies this case as "costo nullo — stessa risposta". It is false for
construction.** The four thematic tools receive `place`, `age`, `franchise`,
`issuing_country`, `as_of` — **never the question**. Only `check_swiss_question` has the
parameter `question`.

So `swiss_driving_licence_exchange(place="Lausanne")` has no way of knowing that
the user asked about the domicile notification: solve Lausanne, find the VD line of
manifest, and **correctly answers a question no one asked**. Grounded,
quoted, and off topic.

> **A tool that does not see the question cannot realize that the question is not its own.**
> The asymmetry of §1 holds on three out of four lines; the fourth presupposed a capacity
> that the contract does not give to thematic tools.

The probable cause of the confusion is lexical: the description of the license says
*"converting, exchanging or **registering** a foreign driving licence"*, and *"annoncer mon
arrivée"* is a registration upon arrival. But **the description is not the flaw** — the
flaw is that the tool cannot recover when the selection is wrong.

**Contract corrected in v5, behavior not yet implemented**: the four topic
tools now have an optional `question` parameter,
with the same rationale in the parameter description — *"confirm the question
really is about X; if it is not, say so plainly instead of answering a question nobody
asked"*. The licence tool explicitly names the confusing case: *"and not about some
other kind of registration or arrival formality"*.

The §1 statement is now *defensible*, but **for a different reason**:
the answer may differ, but the tool now has enough context to detect that.
Until implemented in the server, **this is a contract promise, not an observed fact**.

⚠️ **The protection depends on an optional parameter that decides the model.** §1 establishes
that everything we delegate to the model varies across four configurations: if `question`
is not passed, recovery does not occur. Either it becomes mandatory, or recovery is
probabilistic — open decision.

### 8.5 Consolidated numbers

| Version | What changed | Executions | Missed |
|---|---|---|---|
| v1 | original descriptions | 33 | 1 (question 5, Haiku) |
| v2 | + cross-border clause | 21 | 2 (question 11, Haiku and Sonnet) |
| v3 | + "not a source" clause | 41 | 0 |
| v4 | + real names of holiday types | 39 | 0 |
| v5 | + `question` on the four thematics | 33 | 0 |
| **v6** | **+ no mandatory parameters, `age` string, `Februarferien`** | **45** | **3 — all on the question 5, Haiku** |
| **total** | | **212** | **6** |

In 167 executions: **zero over-invocations** of the catch-all, **zero confusions between tools
thematic**, **only one** invocation of a thematic tool instead of the catch-all (§8.4,
v4, Sonnet, question 9 — then corrected 5 times on 5 and passed in v5).
Romansh 14 on 14, but always on the same single question: it is a constant, not a measure.

⚠️ Adding `question` to thematics makes them **more similar** to catch-all, so the
risk of over-invocation could worsen. Measured in v5: **zero**. Stay there
configuration with more surface area and fewer errors observed.

### 8.6 🔴 The result that invalidates the reading of previous passes

v6 adds 12 repetitions on question 5 — *"Wie hoch ist der Rundfunkbeitrag… nach
Konstanz?"*, the sample question which **is not about Switzerland**. Haiku 4.5 replies `NONE`
**3 times on 12**: he doesn't call anything, and answers on his own on the German television license.

**It is demonstrably not a regression of v6.** From v2 to v5 the question 5 had 6
clean runs on Haiku — but they were **one draw per version**. A rate of 25%
hides very well in a single extraction: `0,75⁶ ≈ 18%` probability of not
never see him. Fisher's test on 0/6 versus 3/12 gives **p ≈ 0,52**: indistinguishable.

> **The passages "33 su 33" and "41 su 41" did not mean what they seemed.**
> 33 runs distributed across 11 questions × 3 models are **one draw per cell**.
> A flaw at 25% is invisible to a sample, and the fact that v1 found it is
> luck, not method. The `_limite_potenza` field in the response file said so from the beginning;
> the results were read with more confidence than the design warranted.

Operational consequence: **a green on a cell draw is not proof.** Per
declaring a cell closed requires ~20 repetitions, and the budget does not allow it to be done on
all and 33. The reasonable choice is to concentrate the repetitions on the cells that weigh:
the questions where waiting is the catch-all and the model is the weakest.

Hypothesis on the cause, **unverified**: the description of `check_swiss_question` is not
changed from v2, but the overall prompt has grown with each version, and the clause
cross-border competes with more and more text. If this were the case, the cure would be to shorten the
descriptions, don't make them any longer.

---

### 8.7 🔴 v7, 2026-09-23: Sonnet missing catch-all also on v6 text

**Change v7**: removed from `swiss_school_holidays` the phrase *"Geneva and Vaud share a
border and their 2026 autumn holidays do not overlap by a single day"*. It was **false**:
VD Autumn 10–25.10.2026 contains GE Autumn 19–23.10.2026 (SOURCES §8septies.1).

| Configuration | Outcome |
|---|---|
| v7 Opus 5, 11 questions | **11/11** |
| v7 Sonnet 5, 11 questions | 9/11 in the first round: NONE on the questions **1** and **5** |
| v7 Sonnet, questions 1 and 5, 4 runs each | question 1: **2 NONE on 4** · question 5: **2 NONE on 4** |
| **v6c** Sonnet (control: same prompts with the remitted sentence, same session) | question 1: **1 NONE on 3** · question 5: **1 NONE on 3** |

Two conclusions, both to be read with §8.6 in mind:

1. **The change is not the cause.** The NONE also appears on the control, which has the text of
   v6 byte for byte. 4/8 vs 2/6 is not distinguishable with these numbers. The phrase
   removed it was false, so it should be removed anyway.
2. 🔴 **"Sonnet is reliable on catch-all questions" was an estimate from too few runs, and it is
   false today.** On 14 today's executions of questions 1 and 5, both versions
   together, Sonnet gave NONE **6 times**. In the v6 registry the same cells had
   1 and 2 extractions. The flaw no longer concerns only the weak model: it concerns **the two
   out-of-scope questions** (waste, Konstanz) on the model closest to the population of
   jury. Thematic questions remain clean on both models.

Haiku was not played in this pass. Complete register in
`test/answers-history-2026-09-22.json`, keys `v7 …` and `v6c …`.

### 8.8 General test in OpenCode Desktop, 2026-09-23

First test with the jury client. OpenCode Desktop 2.0.15 on Windows 11, template
**MiMo-V2.6-Flash Free** (first measure out of the Claude family). Reported
by the user with the help of an assistant; **the raw JSON of the responses was not
visible in the interface** for almost all calls, so the states are verified
only where indicated.

**Link: Works.** `opencode.json` to project root, relative path
`["node", "src/server.ts"]`, without `cwd`, even with spaces in the path. The screen
of the global MCP servers was empty: the project configuration is enough. The CLI
`opencode-ai` 1.18.32 installed next to the Desktop 2.0.15 failed with *"Database is not
empty and has no session table"*: different versions on the same local database. It was
removed; the Desktop works by itself.

| # | Question | Tools called | MCP Status | Final Answer |
|---|---|---|---|---|
| 1 | rate | `swiss_reference_interest_rate` | not visible | ✅ 1,25 % from 02.09.2025 |
| 2 | premiums Lugano | `check_swiss_question` → a search → `swiss_health_insurance_premiums` | not visible | ✅ 679–826,50, median 740,20, 21 offers |
| 3 | VD license | `swiss_driving_licence_exchange` → `check_swiss_question`, more webfetch | `answered` visible | ✅ |
| 4 | cardboard | an unidentified tool | not visible | ❌ asks for the municipality instead of saying "not covered" |
| 5 | Konstanz | `check_swiss_question` | not visible | ⚠️ recognizes that he is outside Switzerland, then **answers the same** (18,36 €/month) from his own knowledge and from the web |
| 6 | School | `check_swiss_question` → `swiss_school_holidays` | not visible | ⚠️ download the cantonal PDF with the shell and give 10–25.10.2026, which coincides with our note GR |
| 7 | Winterthur | `swiss_school_holidays` | **`out_of_scope` / `set_by_municipality` visible** | ⚠️ then consult municipal sources on the web and give the dates |

What it teaches:
- **Server does what it's supposed to do** where status is visible (3, 7). No defects emerged
  of the server.
- **Client has other tools**: web search, webfetch, shell. The model uses them **after**
  our tool to go beyond your answer. With `not_ingested` is consistent with the
  our own text (*"use the source below"*). With `out_of_scope` on Konstanz produces
  precisely the unfounded response that the out-of-scope should avoid.
- **We don't know if the jury will enable these tools.** The behavior measured here
  it is that of a client with the web active.
- **Without seeing the JSON, a state cannot be verified.** Need a log side
  call server, otherwise every test in OpenCode remains a reading of
  screens.

#### Second pass, with the call log

Same client, same model, same 7 questions, rebooted server with log
`logs/calls.jsonl`. All states are now read from the log, not from the screens.

| # | MCP calls (in order) | Status from registry | Server | Model |
|---|---|---|---|---|
| 1 | rate | `answered` | ✅ | ✅ |
| 2 | catch-all → press | `answered`, `answered` | ✅ | ✅ 679–826,50 |
| 3 | driving license → catch-all | `answered`, `answered` | ✅ | ✅ adds VD details via webfetch from the links provided by the tool |
| 4 | catch-all | `out_of_scope` / `topic_not_covered` | ✅ | ✅ says he can't answer, doesn't search |
| 5 | catch-all | `out_of_scope` / `place_not_in_switzerland` | ✅ | ❌ webfetch, replies 18,36 €/month |
| 6 | holidays | `source_unavailable` / `not_ingested` | ✅ | ❌ download the PDF with the shell, gives the dates |
| 7 | catch-all → holidays | `answered`, `out_of_scope` / `set_by_municipality` | ✅ | ❌ Municipal PDFs via webfetch and shell, gives the dates |

- **Server: 7 on 7.** Each state is the one expected by the automatic test.
- **Model: 4 on 7.** The three negative cases have the same shape: our state says
  "not from here", and the model still uses webfetch or a shell to answer. In case 6
  our text invites it (*"use the source below"*).
- **The cartoon changed between the two passes**: in the first the model asked for the municipality,
  in the second he calls the catch-all and stops. Only one extraction per pass (§8.6).
- **The catch-all is called additionally**: in 3 questions about 7, next to the thematic tool
  right. Harmless to the outcome, but it's one more call to answer.
- **Restart server**: Closing the OpenCode Desktop window does not stop the backend
  `opencode-cli.exe`, which continues to use the already started server. After every change yes
  ends `opencode-cli` and checks that the `StartTime` of `node` is subsequent to the
  modification of `src/server.ts`.
- **Wrong accented characters in PowerShell** (`Ã¼`): the registry is UTF-8 and
  PowerShell 5.1 reads it as ANSI if you don't specify the encoding. The file is correct;
  read with `Get-Content -Encoding UTF8`.

## 9. Decisions made and alternatives discarded

| Decision | Alternative discarded | Why |
|---|---|---|
| One theme + coverage tool | One tool with theme enum | The unique tool requires NLU in the server: runtime credential, latency, non-determinism |
| One theme + coverage tool | Only four thematic tools | A garbage question would bypass the server |
| One theme + coverage tool | Twenty tools, one per source | This is what existing Swiss MCP servers do: large surface area = unstable tool selection on 4 configurations |
| Model classification | Server-side keywords | With a theme tool, selection **is** classification; and the keyword would fail on Romansh and oblique formulations |
| Keyword only in `check_swiss_question` | No keywords | Safety net that degrades well: if it does not recognize, the refusal remains valid, only generic |
| Theme keywords covered and excluded together: `answered` + `use_tool` + `also_mentions_not_covered` (2026-09-23) | The covered one wins · the excluded one wins | The cover routed "Prämie von den Steuern abziehen" to the press tool, which does not check `question` (§1) and responds `answered` with extraneous data; the excluded refused "depuis mon arrivée… échanger mon permis". A list of keywords doesn't know what the question is about: the server declares the two facts, the model decides. To be measured in a client |
| Active name `check_swiss_question` | `swiss_coverage` | The passive name reads as "elenca capacità" and encourages you not to call it |
