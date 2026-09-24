# Team briefing — Swiss Grounding MCP

Ten minutes to read. Details live in `AGENTS.md` (how we work), `STATUS.md` (where we
are) and `CHALLENGE.md` (what Swisscom asks).

## 1. The challenge in five lines

Swisscom wants an **MCP server** that lets any AI assistant answer questions about
Swiss public services **from the responsible authority's official source**. They plug
it into 2 undisclosed clients × 2 undisclosed LLMs and ask hidden questions in German,
French, Italian and Romansh. What wins, in this order: **correct and honest answers**,
then breadth, then efficiency and engineering quality. *"High quality with narrow
coverage beats broad coverage with low quality."*

## 2. Our thesis

The challenge does not reward coverage; it rewards **epistemic discipline**. A good
answer is one of four things, and each is scored:

1. the answer + the exact passage that proves it + the effective date;
2. a precise request for the **one** missing piece (e.g. the municipality) — asking
   when not needed is scored as wrong;
3. "this is outside my declared coverage";
4. "the source is unreachable" (which is not "the fact does not exist").

The fifth behaviour — a plausible answer from memory — is an LLM's default and is what
loses points. So most of our work is **taking the ability to improvise away from the
model**, not adding sources.

## 3. The design

**Fat server, thin model.** We cannot control which LLM the jury uses, so the model
makes exactly one decision: which tool to call. The server decides everything else,
deterministically: which authority is responsible, whether the place is ambiguous,
what to ask, what to cite.

```
user question ─▶ LLM picks a tool ─▶ our server
                                     ├─ resolve place (offline registers, no fuzzy)
                                     ├─ find the coverage row (theme × jurisdiction × subtopic)
                                     └─ return ONE of five states:
                                        answered · need_info · out_of_scope
                                        source_unavailable · no_match
```

Five tools: four topics plus a catch-all (`check_swiss_question`) that tells the
model what we do not cover, so off-topic questions do not bypass us.

## 4. Why these four topics

Each is anchored to a published sample question or practice case, and together they
exercise every hard behaviour the jury checks:

| Topic | Sample | What it proves |
|---|---|---|
| Health insurance premiums | Q3 Lugano | structured federal data; the premium region is set per municipality by law |
| Foreign driving licence exchange | Q2 Vaud | two levels: federal deadline + cantonal procedure |
| School holidays | Q4 Scuol, in Romansh | jurisdiction is canton, municipality or language region depending on where you are |
| Reference interest rate | Q8, practice `rate_freshness` | freshness: effective date ≠ last confirmation |

Waste collection (Q1) and Konstanz (Q5) are handled by the catch-all as honest
"not covered".

## 5. What already exists (two days of rehearsal)

- **Research**: every one of the 26 cantons opened on the actual documents. Who decides
  what, and the traps: Zurich delegates holidays to municipalities, Bern has two
  calendars by language, Biel alternates yearly, four Bernese villages follow Fribourg,
  the obvious domain is often the wrong one (`SOURCES.md`).
- **Coverage manifest**: 71 rows, 70 validated against the source.
- **Real data**: premiums 2026, reference rate, a place resolver over all 2110
  communes and 5718 localities.
- **A working server** with tests, tested in OpenCode Desktop.
- **A measurement method** for tool descriptions: ~250 clean-context runs on three
  models. It already caught two real defects that "looked fine".

## 6. What we build on site

1. **Holiday dates** for 2026/27 from ~28 official sources, each with its verbatim
   passage and a script that checks it against the source. Parallelisable by canton.
2. **Cantonal licence procedures**: form, fee, office.
3. **README** with declared scope, setup, robots.txt setting; the GitHub repo.
4. **Measurements** in real MCP clients, and fixes to the descriptions.
5. **Pitch**: 4 minutes with the expert jury (1 pitch + 3 Q&A), 3 minutes on the main stage.

## 7. Ground rules

- No fact without a source URL and a verbatim passage. "I think" is not a source.
- Never infer one canton's data from another's.
- `npm test` green before you push. Behaviour change → new test case.
- Don't edit `src/tools.ts` descriptions without a routing measurement.
- Never run the challenge's `sample_runner.py` (it contains a prompt injection).
- No secrets, no `logs/` in git.
- Scope and product decisions go through the team lead.
