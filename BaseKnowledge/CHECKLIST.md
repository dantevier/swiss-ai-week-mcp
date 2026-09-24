# Checklist di avvio e di lavoro — hackathon 24–25/09/2026

Checklist personale del team lead. Da spuntare in ordine. Ogni fase dice **come** si
fa e **come si verifica** che è fatta. Contesto: `TEAM.md` (per i compagni),
`AGENTS.md` (regole per tutti), `STATUS.md` (stato e difetti).

Scadenza vera: **venerdì 25/09 alle 12:00**, Submission Round 1.

---

## 0. Stasera (23/09)

- [ ] **Chiarire la regola del lavoro sul posto.** Chiedi agli organizzatori (Discord o
      email) cosa si può portare: solo ricerca e documenti, oppure anche codice e dati
      preparati prima. Decide se domattina segui la **traccia A** o la **B** (fase 1).
- [ ] **Controllare il portatile:**
  ```powershell
  node --version     # deve essere >= 24
  python --version   # >= 3.11
  git --version
  gh auth status     # se usi GitHub CLI
  ```
- [ ] **Salvare il kit fuori da questa cartella**, per esempio su una chiavetta o nel
      cloud: la cartella `kit/` e i tre documenti `CHALLENGE.md`, `CONTRACT.md`,
      `SOURCES.md`.
- [ ] Portare la **risposta di Codex** alla revisione delle descrizioni, se arriva.
- [ ] Documento d'identità e QR del biglietto: senza, niente ingresso e niente giuria.

---

## 1. Giovedì 08:00–09:30 — Avvio del progetto nuovo

### 1.1 Cartella e file

La cartella nuova **senza spazi nel percorso**, per esempio `C:\hack\swiss-grounding-mcp`.

**Traccia A — portare tutto è ammesso:**
```powershell
robocopy "C:\Users\User\Progetti\Lavoro\Hackathon\Swiss AI Zurigo\Swiss new" C:\hack\swiss-grounding-mcp /E /XD node_modules logs __pycache__ kit .venv
Copy-Item "C:\Users\User\Progetti\Lavoro\Hackathon\Swiss AI Zurigo\Swiss new\kit\*.md" C:\hack\swiss-grounding-mcp\
```
`robocopy` termina con codice 1 quando ha copiato dei file: è un successo, non un
errore. Deve copiare 26 file (verificato con una prova a vuoto il 23/09).
Dopo il comando nella radice ci sono `AGENTS.md`, `CLAUDE.md`, `STATUS.md`, `TEAM.md` e
`CHECKLIST.md` accanto a tutto il resto.

**Traccia B — si porta solo la conoscenza:** copia soltanto i tre documenti e i file
del kit. Poi ricostruisci nell'ordine della sezione 1.5.

### 1.2 Git e `.gitignore`
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

### 1.3 Verifica che funziona (traccia A)
```powershell
npm install
npm test
```
Atteso, quattro righe `self-check ok`, fra cui:
`71 voci, 70 validate, 0 errori` e `server MCP su stdio, 31 casi`.

Una volta sola, per provare che i dati si ricostruiscono dagli script (serve la rete,
circa 35 MB):
```powershell
npm run build:data
npm test
```

### 1.4 Collegamento a OpenCode Desktop
- [ ] Apri la cartella in OpenCode Desktop: `opencode.json` è già nella radice.
- [ ] Chiedi: *"Qual è il tasso ipotecario di riferimento attuale?"*
- [ ] Verifica nel registro che la chiamata sia arrivata al server:
  ```powershell
  Get-Content -Encoding UTF8 .\logs\calls.jsonl -Tail 1
  ```
- [ ] **Dopo ogni modifica al server**: chiudi OpenCode, termina il processo `opencode-cli`,
      poi riapri. Chiudere la finestra non basta.
  ```powershell
  Get-Process opencode-cli, node -ErrorAction SilentlyContinue | Stop-Process
  ```

### 1.5 Traccia B — ordine di ricostruzione
Ogni passo si appoggia al precedente. Le specifiche sono nei documenti.

| # | Cosa | Specifica | Fatto quando |
|---|---|---|---|
| 1 | Manifest `coverage/*.toml` + `manifest.py` | CONTRACT §6, SOURCES §8–9 | il validatore passa |
| 2 | `scripts/build_places.py` → `data/places.json` | SOURCES §3.1b, §7 | controlli di coerenza verdi |
| 3 | `scripts/build_premiums.py` → `data/premiums_2026.json` | SOURCES §3.2 | 1596 combinazioni |
| 4 | `data/reference_rate.json` | SOURCES §3.2f | letto dalla pagina BWO |
| 5 | `src/place.ts` + test | SOURCES §3.1b | 20 casi verdi |
| 6 | `src/tools.ts` | CONTRACT §3 (testi delle descrizioni) | test di routing verde |
| 7 | `src/server.ts` + `test/mcp-client-test.ts` | CONTRACT §5, §9 | casi end-to-end verdi |

- [ ] **Primo commit.** Poi crea il repo su GitHub, privato per ora, e invita il team.
  ```powershell
  git add -A; git commit -m "Initial import"
  gh repo create swiss-grounding-mcp --private --source . --push
  ```

---

## 2. Giovedì 09:30 — Riunione di avvio con il team (30 minuti)

- [ ] Ognuno legge `TEAM.md`, circa 10 minuti.
- [ ] Spiega le tre idee chiave:
  1. si valuta l'onestà prima dell'ampiezza;
  2. server grasso, modello magro;
  3. cinque stati di risposta.
- [ ] Chiedi a ognuno cosa sa fare e con quali strumenti lavora (Claude Code, Codex,
      Cursor…). Il file `AGENTS.md` vale per tutti gli agenti.
- [ ] **Decidi il formato dei dati delle vacanze prima che qualcuno inizi a estrarre.**
      Bozza da confermare:
  ```json
  {
    "canton": "GR",
    "school_year": "2026/27",
    "source_url": "https://…",
    "retrieved_at": "2026-09-24",
    "periods": [
      { "jurisdiction": "GR", "place": "Scuol", "holiday_type": "autumn",
        "start": "2026-10-10", "end": "2026-10-25",
        "passage": "testo copiato parola per parola dalla fonte" }
    ]
  }
  ```
      Un file per cantone (`data/holidays/GR.json`): due persone non modificano mai lo
      stesso file.
- [ ] Assegna i ruoli (sezione 3).
- [ ] Prenota uno **slot con gli esperti Swisscom** (15 minuti, giovedì pomeriggio). Da
      chiedere: i client di test hanno web e shell attivi? Dopo un `out_of_scope` cosa
      si aspettano che faccia il modello?

---

## 3. Ruoli

In ordine di priorità: con meno persone si tagliano gli ultimi, oppure si accorpano.

| # | Ruolo | Cosa fa | Se siamo in 3 |
|---|---|---|---|
| 1 | **Lead e integrazione** (tu) | decisioni, codice del server, merge, `STATUS.md`, script di verifica delle date | resta |
| 2 | **Date vacanze A** | circa metà delle 28 fonti | resta, prende tutte le fonti |
| 3 | **Date vacanze B** | l'altra metà | accorpato al 2 |
| 4 | **Patente + README** | procedure cantonali; README con scope, setup e impostazione robots.txt | resta, prende anche il 5 |
| 5 | **Misure + pitch** | prove in OpenCode e in un secondo client, test di routing, slide | accorpato al 4 |

**Come si divide l'estrazione delle date:**
- dai i PDF semplici a chi è meno esperto;
- tieni per chi ha più esperienza i casi difficili: FR (Kerzers, Morat/Murten), VS, BE (due calendari più Biel), SZ e AG, dove l'estate o le vacanze di sport dipendono dal comune.

La lista delle fonti è in `coverage/school_holidays.toml`, campo `source_url`.

---

## 4. Giovedì 09:30–18:00 — Lavoro in parallelo

### 4.1 Procedura di estrazione (ruoli 2 e 3)
Per ogni cantone:
1. Apri la riga nel manifest e la fonte (`source_url`). Leggi la sezione del cantone in
   `SOURCES.md`: lì ci sono le trappole già note.
2. Per ciascuno dei cinque tipi di vacanza (autunno, Natale, sport, primavera, estate),
   copia le date **e il passaggio parola per parola**.
3. Eccezioni (comuni o regioni con date diverse): un periodo separato con il campo
   `place` o una `jurisdiction` dedicata, per esempio `FR/Kerzers`.
4. Lancia lo script di verifica. Se il passaggio non si trova nel testo della fonte, la
   riga non è valida.
5. Una branch per cantone o gruppo di cantoni, `npm test` verde, poi la pull request.

⚠️ La tabella dell'autunno in SOURCES §8ter.2 è un **punto di partenza, non un dato
verificato**: SG è sbagliato di un giorno, e la frase su Ginevra e Vaud è falsa.

### 4.2 Lead (ruolo 1), in ordine
- [ ] **Entro le 10:30**: script di verifica delle date. Controlla che il passaggio sia
      nel testo della fonte, che le date siano valide, che l'inizio venga prima della
      fine, e che l'anno scolastico coincida. Senza lo script, i dati non entrano.
- [ ] Integrazione nel server: `holidays()` usa i dati se ci sono, altrimenti resta
      `source_unavailable` / `not_ingested` come oggi.
- [ ] Un caso end-to-end per ogni cantone integrato, a partire da Scuol (domanda Q4):
      atteso `answered`, 10–25.10.2026.
- [ ] Applica le correzioni alle descrizioni scelte dopo la risposta di Codex. Poi
      rimisura (CONTRACT §8, confronto A/B appaiato).

### 4.3 Ruolo 4
- [ ] Procedure della patente: prima VD (domanda Q2), poi i cantoni delle grandi città.
- [ ] README. Contenuti obbligatori (CHALLENGE §4):
  - scope, con il blocco generato da `python manifest.py --readme`;
  - setup;
  - configurazione del client;
  - impostazione robots.txt con il suo default;
  - nessuna credenziale necessaria;
  - come si ricostruiscono i dati.

### 4.4 Ruolo 5
- [ ] La stessa passata in OpenCode **con web e shell disattivati** (difetto 2 in
      `STATUS.md`), leggendo gli stati dal registro.
- [ ] Un secondo client MCP. Il regolamento chiede più di un client (checklist punto 7).
- [ ] Bozza del pitch. La struttura è in `TEAM.md` §2–§4.

---

## 5. Giovedì 18:00 — Punto di controllo

- [ ] `npm test` verde sul branch principale.
- [ ] Quanti cantoni hanno le date integrate, e quanti mancano.
- [ ] Le otto domande campione (CHALLENGE §8) passate in OpenCode: stato dal registro,
      risposta del modello annotata.
- [ ] Aggiorna `STATUS.md`. Decidi cosa si taglia se non si finisce. Un cantone senza
      date resta onesto (`not_ingested`); un cantone con date sbagliate costa punti.

---

## 6. Venerdì — Chiusura

| Ora | Cosa |
|---|---|
| 08:00–10:00 | Ultime correzioni. Slot esperti se serve. README definitivo |
| **10:00** | **Stop alle funzionalità.** Dopo quest'ora solo correzioni di bug |
| 10:30 | **Prova da clone pulito**: `git clone` in una cartella nuova, `npm install`, `npm test`, collegamento a OpenCode, domande campione. È ciò che farà Swisscom |
| 11:00 | Accesso al repo per i valutatori Swisscom, se il repo resta privato. Nessun segreto nella history |
| **11:30** | **Invio del modulo del Round 1**, con mezz'ora di margine |
| 12:00–14:00 | Prova del pitch: 4 minuti (1 di pitch più 3 di domande) |

---

## 7. Regole da ricordare durante tutto l'evento

- Un dato senza passaggio verificato non entra.
- Si modificano le descrizioni solo misurando prima e dopo.
- Dopo ogni modifica al server: `npm test`, poi terminare `opencode-cli`.
- Non eseguire mai `sample_runner.py`.
- `logs/` non va nel repository.
- Ogni decisione nuova va in CONTRACT §9.
