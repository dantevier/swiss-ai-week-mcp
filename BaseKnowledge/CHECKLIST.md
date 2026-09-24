# Startup and work checklist — hackathon 24–25/09/2026

> Historical on-site checklist for the Node/TypeScript rehearsal. The current
> Python/FastMCP repository differs; use [STATUS.md](STATUS.md) for its actual state.

Personal checklist for the team lead. Work through it in order. Each stage explains
what to do and how to verify completion. Context: `TEAM.md` (team briefing),
`AGENTS.md` (rehearsal rules), `STATUS.md` (current repository state).

Rehearsal deadline: **Friday 25/09 at 12:00**, Submission Round 1 (from the non-public handbook; confirm with organizers).

---

## 0. Tonight (23/09)

- [ ] **Clarify the work-on-site rule.** Ask the organizers (Discord or
      email) what you can bring: just research and documents, or also code and data
      prepared beforehand. Decide whether to follow **track A** or **B** tomorrow morning (phase 1).
- [ ] **Check laptop:**
  ```powershell
  node --version     # must be >= 24
  python --version   # >= 3.11
  git --version
  gh auth status     # if you use GitHub CLI
  ```
- [ ] **Save the kit outside this folder**, for example on a flash drive or in
      cloud: the `kit/` folder and the three documents `CHALLENGE.md`, `CONTRACT.md`,
      `SOURCES.md`.
- [ ] Bring **Codex response** to review descriptions, if it arrives.
- [ ] Identity document and ticket QR: without, no entry and no jury.

---

## 1. Thursday 08:00–09:30 — Start of new project

### 1.1 Folder and files

The new folder **without spaces in the path**, for example `C:\hack\swiss-grounding-mcp`.

**Track A — bringing everything is allowed:**
```powershell
robocopy "C:\Users\User\Progetti\Lavoro\Hackathon\Swiss AI Zurigo\Swiss new" C:\hack\swiss-grounding-mcp /E /XD node_modules logs __pycache__ kit .venv
Copy-Item "C:\Users\User\Progetti\Lavoro\Hackathon\Swiss AI Zurigo\Swiss new\kit\*.md" C:\hack\swiss-grounding-mcp\
```
`robocopy` exits with code 1 when it copies files: that means success, not an
error. It should copy 26 files (verified with a dry run on 23/09).
After the command in the root there are `AGENTS.md`, `CLAUDE.md`, `STATUS.md`, `TEAM.md` and
`CHECKLIST.md` next to everything else.

**Track B — bring only research:** copy the three documents and the kit files.
Then rebuild in the order given in §1.5.

### 1.2 Git and `.gitignore`
```powershell
cd C:\hack\swiss-grounding-mcp
git init
@"
node_modules/
logs/
__pycache__/
.venv/
*.pyc
"@ | Out-File -Encoding utf8 .gitignore
```

### 1.3 Check it works (track A)
```powershell
npm install
npm test
```
Expected, four lines `self-check ok`, including:
`71 voci, 70 validate, 0 errori` and `server MCP su stdio, 31 casi`.

Just once, to prove that the data is reconstructed from the scripts (the network is needed,
about 35 MB):
```powershell
npm run build:data
npm test
```

### 1.4 Link to OpenCode Desktop
- [ ] Open the folder in OpenCode Desktop: `opencode.json` is already in the root.
- [ ] Ask: *"Qual è il tasso ipotecario di riferimento attuale?"*
- [ ] Check in the log that the call arrived at the server:
  ```powershell
  Get-Content -Encoding UTF8 .\logs\calls.jsonl -Tail 1
  ```
- [ ] **After every change to the server**: close OpenCode, end the process `opencode-cli`,
      then reopen. Closing the window is not enough.
  ```powershell
  Get-Process opencode-cli, node -ErrorAction SilentlyContinue | Stop-Process
  ```

### 1.5 Track B — rebuild order
Each step builds on the previous one. The specifications are in the documents.

| # | What | Specify | Done when |
|---|---|---|---|
| 1 | Manifest `coverage/*.toml` + `manifest.py` | CONTRACT §6, SOURCES §8–9 | the validator passes |
| 2 | `scripts/build_places.py` → `data/places.json` | SOURCES §3.1b, §7 | green consistency checks |
| 3 | `scripts/build_premiums.py` → `data/premiums_2026.json` | SOURCES §3.2 | 1596 combinations |
| 4 | `data/reference_rate.json` | SOURCES §3.2f | read from the BWO | page
| 5 | `src/place.ts` + test | SOURCES §3.1b | 20 green cases |
| 6 | `src/tools.ts` | CONTRACT §3 (description texts) | green routing test |
| 7 | `src/server.ts` + `test/mcp-client-test.ts` | CONTRACT §5, §9 | green end-to-end cases |

- [ ] **First commit.** Then create the repo on GitHub, private for now, and invite the team.
  ```powershell
  git add -A; git commit -m "Initial import"
  gh repo create swiss-grounding-mcp --private --source . --push
  ```

---

## 2. Thursday 09:30 — Kickoff meeting with the team (30 minutes)

- [ ] Everyone reads `TEAM.md`, about 10 minutes.
- [ ] Explain the three key ideas:
  1. honesty is valued before breadth;
  2. fat server, skinny model;
  3. five response states.
- [ ] Ask everyone what they can do and what tools they work with (Claude Code, Codex,
      Cursor…). The `AGENTS.md` file applies to all agents.
- [ ] **Decide the format of your holiday data before anyone starts mining.**
      Draft to be confirmed:
  ```json
  {
    "canton": "GR",
    "school_year": "2026/27",
    "source_url": "https://…",
    "retrieved_at": "2026-09-24",
    "periods": [
      { "jurisdiction": "GR", "place": "Scuol", "holiday_type": "autumn",
        "start": "2026-10-10", "end": "2026-10-25",
        "passage": "text copied word for word from the source" }
    ]
  }
  ```
      One file per canton (`data/holidays/GR.json`): two people never modify it
      same file.
- [ ] Assign roles (3 section).
- [ ] Book a **slot with Swisscom experts** (15 minutes, Thursday afternoon). From
      ask: do the test clients have web and shell active? After a `out_of_scope` thing
      do they expect me to be a model?

---

## 3. Roles

In order of priority: with fewer people, the last ones are cut, or they merge.

| # | Role | What it does | If we are in 3 |
|---|---|---|---|
| 1 | **Leads and Integration** (you) | decisions, server code, merge, `STATUS.md`, date verification script | stay |
| 2 | **Holiday dates A** | about half of 28 sources | stays, takes all sources |
| 3 | **Holiday dates B** | the other half | merged with 2 |
| 4 | **License + README** | cantonal procedures; README with scope, setup and setting robots.txt | remains, also takes the 5 |
| 5 | **Measurements + pitch** | tests in OpenCode and in a second client, routing tests, slide | merged with 4 |

**How the date extraction is divided:**
- give simple PDFs to those who are less experienced;
- keep the difficult cases for those with more experience: FR (Kerzers, Morat/Murten), VS, BE (two calendars plus Biel), SZ and AG, where the summer or sports holidays depend on the municipality.

The list of sources is in `coverage/school_holidays.toml`, field `source_url`.

---

## 4. Thursday 09:30–18:00 — Work in parallel

### 4.1 Extraction procedure (roles 2 and 3)
For each canton:
1. Open the line in the manifest and the source (`source_url`). Read the canton section in
   `SOURCES.md`: there are the already known traps.
2. For each of the five types of holidays (autumn, Christmas, sports, spring, summer),
   copy the dates **and the passage word for word**.
3. Exceptions (municipalities or regions with different dates): a separate period with the field
   `place` or a dedicated `jurisdiction`, for example `FR/Kerzers`.
4. Run the verification script. If the passage is not found in the source text, the
   row is invalid.
5. One branch per canton or group of cantons, green `npm test`, then the pull request.

⚠️ The autumn table in SOURCES §8ter.2 is a **starting point, not a given
verified**: SG is wrong by one day, and the sentence about Geneva and Vaud is false.

### 4.2 Lead (role 1), on order
- [ ] **By 10:30**: date verification script. Check that the passage is
      in the source text, that the dates are valid, that the beginning comes before the
      end, and that the school year coincides. Without the script, the data doesn't come in.
- [ ] Integration into the server: `holidays()` uses the data if it exists, otherwise it remains
      `source_unavailable` / `not_ingested` like today.
- [ ] An end-to-end case for each integrated canton, starting from Scuol (question Q4):
      expected `answered`, 10–25.10.2026.
- [ ] Apply corrections to descriptions chosen after Codex's response. Then
      remeasure (CONTRACT §8, paired A/B comparison).

### 4.3 Role 4
- [ ] Driving license procedures: first VD (question Q2), then the cantons of large cities.
- [ ] README. Mandatory contents (CHALLENGE §4):
  - scope, with the block generated by `python manifest.py --readme`;
  - setup;
  - client configuration;
  - setting robots.txt with its default;
  - no credentials needed;
  - how the data is reconstructed.

### 4.4 Role 5
- [ ] The same as passed in OpenCode **with web and shell disabled** (defect 2 in
      `STATUS.md`), reading the states from the registry.
- [ ] A second MCP client. The regulation asks for more than one client (checklist point 7).
- [ ] Draft pitch. The structure is in `TEAM.md` §2–§4.

---

## 5. Thursday 18:00 — Checkpoint

- [ ] `npm test` green on the main branch.
- [ ] How many cantons have integrated dates, and how many are missing.
- [ ] The eight sample questions (CHALLENGE §8) passed in OpenCode: status from the register,
      model response noted.
- [ ] Update `STATUS.md`. Decide what gets cut if you don't finish. A canton without
      date stay honest (`not_ingested`); a canton with incorrect dates costs points.

---

## 6. Friday — Closed

| Now | What |
|---|---|
| 08:00–10:00 | Latest fixes. Expert slots if needed. Definitive README |
| **10:00** | **Stop features.** After this time only bug fixes |
| 10:30 | **Test from clean clone**: `git clone` in a new folder, `npm install`, `npm test`, link to OpenCode, sample questions. That's what Swisscom will do |
| 11:00 | Access to the repo for Swisscom evaluators, if the repo remains private. No secrets in history |
| **11:30** | **Submission of the Round form 1**, with half an hour's margin |
| 12:00–14:00 | Pitch test: 4 minutes (1 of pitch plus 3 of questions) |

---

## 7. Rules to remember throughout the event

- A data without verified passage does not enter.
- The descriptions are changed only by measuring before and after.
- After any server changes: `npm test`, then terminate `opencode-cli`.
- Never run `sample_runner.py`.
- `logs/` does not go into the repository.
- Every new decision goes to CONTRACT §9.
