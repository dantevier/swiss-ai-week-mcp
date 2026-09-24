# Swiss Grounding MCP — Knowledge Base

> **Scopo**: unica fonte di verità interna su cosa Swisscom chiede, come valuta e cosa
> consegniamo. Da consultare durante l'hackathon per qualsiasi dubbio sui requisiti.
>
> **Compilato**: 2026-09-21 · **Evento**: 24–25 settembre 2026, Kraftwerk, Selnaustrasse 25, Zurigo
>
> **Legenda affidabilità** — ogni affermazione è marcata:
> - ✅ **verificato** su fonte primaria (repo ufficiale, briefing deck, sito ai-weeks.ch)
> - ⚠️ **non verificabile pubblicamente** (proviene dall'Hacker's Handbook, riservato)
> - 🔍 **inferenza** ad alta confidenza, non dichiarata esplicitamente dalla fonte

---

## 0. Indice rapido

| Domanda | Sezione |
|---|---|
| Quando devo consegnare davvero? | [§2 Timeline](#2-timeline-operativa) |
| Cosa devo consegnare esattamente? | [§3 Deliverables](#3-deliverables) |
| Quali requisiti sono binari e non negoziabili? | [§4 Requisiti hard](#4-requisiti-hard-checklist) |
| Come assegnano il punteggio? | [§5 Valutazione](#5-come-valutano) |
| Quando è giusto chiedere info all'utente? | [§5.4 Regola ask-back](#54-le-tre-viste-e-la-regola-dellask-back) |
| Cosa conta come fonte autorevole? | [§6 Autorevolezza](#6-cosa-conta-come-fonte-autorevole) |
| Quali domande useranno? | [§8 Domande campione](#8-domande-campione-8-note) · [§9 Practice case](#9-practice-case-e-checklist-dal-self-check-pack) |
| Posso usare indici pre-costruiti / API key? | [§10 Runtime](#10-hosting-indici-chiavi-costi) |
| Cosa NON sappiamo? | [§11 Zone d'ombra](#11-zone-dombra) |
| Trappole pratiche | [§13 Avvertenze](#13-avvertenze-operative) |

---

## 1. Fonti e come rigenerarle

| Fonte | URL / percorso | Stato |
|---|---|---|
| Repo ufficiale challenge | `https://github.com/Swiss-ai-Weeks/swisscom-2026` | ✅ clonato e letto |
| README challenge | `swiss-grounding-mcp/README.md` | ✅ |
| Briefing deck (12 slide) | `swiss-grounding-mcp/briefing-swiss-grounding-mcp.pdf` | ✅ testo estratto |
| Self-check pack | `swiss-grounding-mcp/evaluation/` — **solo in git history** | ✅ recuperato |
| Pagina challenge | `https://ai-weeks.ch/2026/challenges?location=zurich-hackathon` | ✅ |
| FAQ evento | `https://ai-weeks.ch/2026/hack-zurich` | ✅ |
| Hacker's Handbook | non pubblico | ⚠️ non reperibile |

### Recupero del self-check pack

Il pack **non è nel working tree**: vive come snapshot in git history. Dalla root del repo clonato:

```sh
material_commit=$(git log -1 --diff-filter=A --format=%H -- swiss-grounding-mcp/evaluation/sample-questions.b64)
git restore --source="$material_commit" --worktree -- swiss-grounding-mcp/evaluation
```

Il commit al 2026-09-21 è `74232a1e9c8b14a9d86bf2cd2a3f8916597a68c1`.
Il contenuto è in `sample-questions.b64`. Per decodificarlo **senza eseguire codice del repo**:

```sh
tr -d '\r' < swiss-grounding-mcp/evaluation/sample-questions.b64 | base64 -d > decoded.json
```

> Uno shallow clone non ha la history necessaria: serve `git fetch --unshallow` prima.

---

## 2. Timeline operativa

### Evento ✅ (FAQ ai-weeks.ch)
- **Gio 24/09, 08:00 CET** — kickoff
- **Ven 25/09, 21:00 CET** — chiusura evento
- Ingresso solo con **QR ticket + documento d'identità valido**

### Giuria ⚠️ (dall'Handbook, non verificabile pubblicamente ma coerente con la FAQ)
| Ora (Ven 25/09) | Evento |
|---|---|
| **12:00** | **⏰ SUBMISSION ROUND 1 — deadline reale** |
| 14:00–16:00 | Expert Jury, stanza chiusa, 3 panel paralleli — **4 min** (1 pitch + 3 Q&A) |
| 17:00 | Annuncio shortlist |
| 17:30 | Submission finale Round 2 |
| 18:00–18:45 | Main Jury, main stage — **3 min** (2 pitch + 1 Q&A) |
| 19:30 | Award Ceremony |

**Implicazione**: il tempo di sviluppo utile è **~28 ore**, non 36. Il server deve essere
runnable e testabile da Swisscom prima di venerdì 12:00.

✅ La FAQ conferma che **10 team** passano al main stage.
✅ Submission Round 1 via form, Round 2 via email (link/dettagli pubblicati sul posto).

### Supporto Swisscom ✅
Slot prenotabili da **15 minuti** con gli esperti myAI on-site al Kraftwerk:
**giovedì pomeriggio** e **venerdì mattina**.
Referenti: Matthias Appius, Alexander Stark (Swisscom myAI).

---

## 3. Deliverables

✅ Testuale dal README e dalla slide 5:

1. **Repository GitHub**, pubblico o privato, con **accesso per i valutatori Swisscom**
2. **MCP server funzionante** con istruzioni di setup chiare, così che Swisscom possa avviarlo
3. **Coverage e limitazioni documentate**: quali topic, quale geografia
4. **Accesso di test sicuro** dove serve, e **nessun secret nel repo**
5. Nessuna integrazione myAI richiesta durante l'evento

---

## 4. Requisiti hard (checklist)

Requisiti binari e verificabili. Sono i punti su cui si perde in modo evitabile.

- [ ] **Scope dichiarato nel README**: topic + geografia, esplicitamente.
      *La qualità viene misurata contro questa dichiarazione.* ✅
- [ ] **robots.txt e terms of use rispettati di default, MA come impostazione di
      configurazione** — non comportamento hardcoded. Swisscom deve poterlo
      attivare/disattivare per i test. **Setting e default documentati nel README.** ✅
      > *"Whether it does so must be a configuration setting, not hardcoded behaviour,
      > so that Swisscom can switch it on or off when running your server for testing."*
- [ ] **Il codice nel repo gira in locale** con il setup documentato, anche se hostiamo
      un endpoint. Serve a confermare che il sorgente pubblicato è il server testato. ✅
- [ ] Se hostiamo: **endpoint up fino a fine valutazione**. ✅
- [ ] **Zero secret nel repository.** Credenziali di test consegnate via canale sicuro
      degli organizzatori **prima del deadline**. ✅
- [ ] **Ogni credenziale richiesta elencata nel README.** ✅
- [ ] Se usiamo un indice pre-costruito: **il setup lo scarica/usa senza passi manuali**
      E **il repo contiene lo script che l'ha generato**. Swisscom **non ricostruisce**
      l'indice. ✅
- [ ] **Costruito contro lo standard MCP**, non contro un client specifico. ✅

---

## 5. Come valutano

### 5.1 Le cinque dimensioni ✅

1. **Grounding quality** — correttezza, fonti autorevoli, giurisdizione, freshness,
   supporto alla citazione, gestione onesta delle domande non supportate
2. **Useful Swiss coverage** — ampiezza e valore pratico dell'informazione pubblica
   svizzera resa accessibile, incluso lo scope dichiarato
3. **Agent efficiency** — qualità della tool selection, numero di chiamate, dimensione
   delle risposte, token, latenza, evitare richieste live non necessarie
4. **Operability** — setup riproducibile, design di refresh e caching, resilienza,
   monitoring, source etiquette, manutenibilità
5. **Integration readiness** — contratto MCP coerente, documentazione chiara,
   estensibilità, uso immediato da client MCP standard e dal test harness Swisscom

### 5.2 Gerarchia esplicita ✅ (slide 8)

```
1. Correct and honest answers      ← domina
2. Breadth                          ← pesato separatamente
3. Efficiency, operability, MCP contract   ← tie-breaker
```

> *"High quality with narrow coverage beats broad coverage with low quality.
> Having both is best and wins."*

**Nessuna formula pubblicata.** Check automatici + confronto LLM-assisted contro risposte
verificate informano il **review group myAI**, che decide **a mano**. ✅

### 5.3 Setup di test ✅

- **2 client MCP compatibili × 2 LLM ciascuno = 4 combinazioni**, identiche per ogni team
- **Quali client e quali modelli: non divulgati**
- Il server è collegato **esattamente come descritto nelle nostre setup instructions**
- Domande in **tedesco, francese, italiano e romancio**
- Il set completo di domande e la sua dimensione restano nascosti

### 5.4 Le tre viste e la regola dell'ask-back ✅

Tre viste su ogni server:
1. **Qualità dentro lo scope dichiarato** — corretto, da fonte autorevole svizzera,
   giurisdizione giusta, aggiornato, citato
2. **Breadth** — quanta informazione pubblica svizzera utile rendiamo accessibile
3. **Onestà fuori scope** — dire chiaramente che non è coperto, **non indovinare**

**Regola dell'ask-back** (citazione integrale):

> *"Asking back can be the right answer. When the answer depends on information that is
> missing, such as the municipality, a precise request for exactly that information counts
> as correct. When the question can be answered as asked, asking back counts as wrong,
> and so does asking for context you do not need."*

Tre penalità distinte, quindi:
- rispondere quando manca un dato essenziale → **sbagliato**
- chiedere quando la domanda è già rispondibile → **sbagliato**
- chiedere contesto che non serve → **sbagliato**

---

## 6. Cosa conta come fonte autorevole

✅ Swisscom **non fornisce una lista di fonti**. Trovare e raggiungere le fonti giuste
è parte della challenge. La valutazione **non controlla quali siti abbiamo usato**:
controlla se il server raggiunge informazione autorevole svizzera e restituisce risposte
grounded con riferimenti verificabili.

Definizione: *"the body that is actually responsible for the matter"* — l'ufficio federale,
il cantone, il comune, o un'organizzazione con mandato di legge.

Regole pratiche ✅:
- Uffici federali pubblicano sotto **admin.ch**; **ch.ch** è il portale multilingue della
  Confederazione e una buona mappa di chi è responsabile di cosa
- I cantoni pubblicano su domini propri, di solito il codice a due lettere:
  `be.ch`, `vd.ch`, `ti.ch`, `gr.ch`
- I comuni pubblicano sui propri siti — **molte risposte locali esistono solo lì**
- Alcuni enti semi-ufficiali sono autorevoli perché la legge dà loro il compito
  (es. centro informazioni AHV/IV, piattaforma open data del trasporto pubblico)
- Quattro lingue nazionali: una fonte può esistere solo in una o due, e la risposta
  corretta può dipendere dalla regione linguistica

⚠️ **Dalla review checklist**: *"Check that the publisher is responsible for the matter,
not merely an official Swiss domain."* Un link generico ad `admin.ch` non basta.

Approcci ammessi: registry curato, discovery dinamica, open data e API, o combinazioni. ✅

---

## 7. Topic areas di esempio (16) ✅

Esempi, **non lista obbligatoria e non il set di valutazione**.

| # | Topic area | Fonte esempio | Livello |
|---|---|---|---|
| 1 | Premi cassa malati e assicurazione di base | priminfo.admin.ch | Federale (BAG) |
| 2 | Imposte e tasse | amministrazione fiscale TI, ti.ch | Cantonale |
| 3 | Diritto e regolamenti | fedlex.admin.ch | Federale |
| 4 | Raccolta rifiuti e riciclaggio | calendario rifiuti Losanna, lausanne.ch | Comunale |
| 5 | Trasloco, notifica di domicilio, stato civile | controllo abitanti Berna, bern.ch | Comunale |
| 6 | Permessi di soggiorno e migrazione | sem.admin.ch | Federale |
| 7 | Assicurazioni sociali e pensioni | ahv-iv.ch | Semi-ufficiale |
| 8 | Lavoro e disoccupazione | arbeit.swiss | Federale (SECO) |
| 9 | Scuole e istruzione | dip. istruzione Ginevra, ge.ch | Cantonale |
| 10 | Trasporto pubblico e mobilità | opentransportdata.swiss | Semi-uff. (mandato UFT) |
| 11 | Circolazione stradale, veicoli, patenti | ufficio circolazione GR, gr.ch | Cantonale |
| 12 | Abitazione e locazione | bwo.admin.ch | Federale |
| 13 | Votazioni, elezioni, diritti politici | bk.admin.ch | Federale |
| 14 | Imprese, registro di commercio, IVA | zefix.ch | Federale |
| 15 | Dogane e acquisti dall'estero | bazg.admin.ch | Federale |
| 16 | Statistica, open data, geodati, meteo | bfs.admin.ch, opendata.swiss, map.geo.admin.ch, meteoswiss.admin.ch | Federale |

---

## 8. Domande campione (8 note)

### Le 5 pubblicate ✅
Il README dichiara: una richiede di chiedere il comune, una **non è una domanda sulla
Svizzera** e la risposta giusta è dirlo. Non dicono quali.

1. 🇩🇪 *Wann wird bei uns das nächste Mal Karton abgeholt?*
2. 🇫🇷 *Comment puis-je échanger mon permis de conduire étranger contre un permis suisse
   dans le canton de Vaud, et combien de temps ai-je pour le faire?*
3. 🇮🇹 *Qual è il premio mensile più basso dell'assicurazione di base per un adulto di
   30 anni domiciliato a Lugano con franchigia di 2500 franchi?*
4. 🇨🇭 (rm) *Cura èn las vacanzas d'atun 2026 per la scola da Scuol?*
5. 🇩🇪 *Wie hoch ist der Rundfunkbeitrag, den ich nach meinem Umzug nach Konstanz
   zahlen muss?*

🔍 **Inferenza ad alta confidenza**: incrociando con i practice case `missing_location` e
`cross_border`, la #1 è quella che richiede il comune e la #5 è quella fuori Svizzera
(Konstanz è in Germania).

### Le 3 aggiuntive nel fixture del self-check pack ✅
6. 🇩🇪 *Wann sind die Herbstferien 2026 in der Stadt Bern?*
7. 🇫🇷 *Où dois-je annoncer mon arrivée dans la ville de Lausanne?*
8. 🇮🇹 *Quale autorità pubblica il tasso ipotecario di riferimento per gli affitti in Svizzera?*

---

## 9. Practice case e checklist (dal self-check pack)

✅ Otto casi con i check espliciti. È il materiale più vicino al set nascosto che avremo.

### 9.1 `missing_location` — de
**Q**: *Wann wird bei uns Karton abgeholt?*
- Chiedere il **comune** prima di selezionare un calendario locale
- Se il calendario è specifico per via, chiedere **solo** l'informazione di località
  aggiuntiva che serve
- **Non inventare una data di raccolta**

### 9.2 `enough_context` — fr
**Q**: *Où trouver le calendrier officiel des vacances scolaires 2026 de la ville de Genève?*
- Usare l'autorità scolastica responsabile e il suo calendario 2026
- **Non chiedere un comune già fornito**
- Citare il calendario reale o la sua pagina di pubblicazione ufficiale

### 9.3 `cross_border` — de
**Q**: *Wie hoch ist der Rundfunkbeitrag in Konstanz?*
- Riconoscere che Konstanz è in **Germania**
- Per un server Swiss-only: dichiarare che è **fuori copertura**
- **Non sostituire** con il canone svizzero

### 9.4 `romansh_locality` — rm
**Q**: *Cura èn las vacanzas d'atun 2026 per la scola da Scuol?*
- Identificare Scuol e il calendario scolastico applicabile
- Verificare **anno richiesto** e **applicabilità locale**
- Non dedurre date da un altro cantone o da un riassunto tradotto senza data

### 9.5 `rate_freshness` — it
**Q**: *Qual è il tasso ipotecario di riferimento attualmente in vigore per gli affitti
in Svizzera?*
- Trovare la **pubblicazione corrente** dell'autorità federale competente per l'abitazione
- Indicare la **data di efficacia** insieme al tasso
- **Una pubblicazione ufficiale più vecchia resta una risposta obsoleta**

### 9.6 `paired_jurisdiction` — fr
**Q**: *Comment annoncer mon arrivée à Lausanne? Et à Berne?*
- Risolvere **ogni procedura comunale in modo indipendente**
- Non riusare scadenze, tasse o moduli di un comune per l'altro
- Attribuire ogni procedura alla sua autorità responsabile

### 9.7 `citation_support` — de
**Q**: *Welche Quelle belegt genau die von dir genannte Frist?*
- Restituire **il passaggio** che sostiene quella scadenza specifica
- **Una homepage ufficiale da sola non basta**
- Se nessun passaggio di supporto è stato trovato: qualificare o **ritrattare** la claim

### 9.8 `source_failure` — en
**Q**: ripetere una domanda in-scope con la fonte autorevole non disponibile.
- Distinguere **retrieval failure** da **assenza del fatto**
- Dichiarare se la risposta si basa su **evidenza in cache** e identificarne la **data**
- Non inventare una citazione né sostituire silenziosamente la giurisdizione

### 9.9 Review checklist (8 punti) ✅

1. Documentare topic e coverage geografica **prima** di confrontare i risultati
2. Per ogni claim chiave, conservare **URL della fonte + passaggio di supporto o record dati**
3. Verificare che l'editore sia **responsabile della materia**, non solo un dominio
   svizzero ufficiale
4. Verificare comune, cantone, gruppo di popolazione, **anno di riferimento** e
   **data di efficacia** dove rilevante
5. Chiedere **solo** l'informazione mancante che cambia la risposta
6. Distinguere: **fuori scope** / **contesto insufficiente** / **fonte non disponibile** /
   **nessun risultato corrispondente** — sono quattro stati diversi
7. Esercitare lo stesso contratto MCP con **più di un client compatibile**
8. Setup riproducibile, credenziali fuori da Git, passi di rebuild dell'indice documentati

---

## 10. Hosting, indici, chiavi, costi

✅ Tutto dalla slide 12 + README §3.

**Locale o hosted — scelta nostra.** Swisscom testa un endpoint hosted oppure avvia il
server dal repo. In entrambi i casi il codice nel repo deve girare in locale con il setup
documentato, per confermare che il sorgente pubblicato è il server testato.

**Indici pre-costruiti: ammessi.** Non serve fare embedding o crawling allo start.
Possiamo spedire un vector store/indice nel repo o farlo scaricare dal setup.
Due condizioni: (1) il setup lo scarica e lo usa **senza passi manuali**; (2) il repo
contiene **lo script che l'ha costruito**, così che chiunque possa ricostruirlo con dati
più freschi. **Swisscom non ricostruisce l'indice durante la valutazione.**

**Chiavi.** API key a runtime sono accettabili (es. embedding a query time, o una chiamata
LLM interna al server). Elencare ogni credenziale nel README e consegnare credenziali di
test funzionanti via canale sicuro degli organizzatori prima del deadline.
> *"A server that runs without any external keys is easier for us to run and easier for you
> to keep running, and that shows in the operability assessment."*

**Costi.** Swisscom **non rimborsa** costi di API, embedding o hosting. Per eventuali
API credit rivolgersi agli organizzatori Swiss AI Weeks.
> *"Embedding budget does not decide the ranking: quality inside your declared scope comes
> first, and a small, well built index or a live API approach with no embeddings at all is
> just as valid as a large vector store."*

---

## 11. Zone d'ombra

Cose che **non sappiamo e non sapremo**:

- Quali **client MCP** e quali **LLM** usano per i test
- **Dimensione** del set di domande nascosto
- Qualsiasi **formula di punteggio** — non esiste, decide a mano il review group myAI
- Il **premio specifico** di questa challenge (la FAQ generale parla di premi non
  acquistabili + denaro; nessuna cifra pubblicata)
- Se ci sono **API credit** dagli organizzatori (Swisscom rimanda esplicitamente a loro)

⚠️ Il blocco "Jury Process & Evaluation Criteria" (§2) proviene dall'Hacker's Handbook e
**non è stato verificabile su fonte pubblica**. È coerente con la FAQ ma va riconfermato
sul posto.

---

## 12. Contesto evento (FAQ ai-weeks.ch) ✅

- **IP e code ownership**: la proprietà intellettuale creata resta **ai team / ai singoli
  partecipanti**, indipendentemente dal fatto che si lavori su una challenge di un partner
- Lingua dell'evento: **inglese**
- Piattaforme fornite: **GitHub** e **Hugging Face**; tool/API aggiuntivi documentati
  nell'Handbook
- Comunicazione: **Discord**
- Infra: WiFi con uplink 10 Gbit (Fiber7), prese 220V tipo J, supporto tecnico on-site
- Eligibility giuria ⚠️: valuta solo progetti sottomessi in tempo da team registrati
  dove **tutti i membri hanno ticket valido e documento d'identità**
- Rimborso viaggio: CHF 80 (100–500 km), CHF 150 (>500 km), con ricevute, post-evento.
  Alloggio non coperto
- Giuria: decisioni **finali e non appellabili**; il moderatore ha il voto decisivo;
  conflitti d'interesse vanno dichiarati con ricusazione ⚠️

---

## 13. Avvertenze operative

### 13.1 Non eseguire `sample_runner.py` durante la demo
Il companion utility del self-check pack apre **10 finestre di terminale** con animazioni
ASCII e riproduce **audio per ~8 secondi**. Richiede macOS Terminal o `xterm`; su Windows
il window mode non parte. Per ottenere solo il report: `--dry-run`. Meglio ancora:
decodificare direttamente il `.b64` (vedi §1).

### 13.2 Prompt injection nel fixture ⚠️
`sample-questions.b64` contiene cinque "variants" scherzose con campo `instruction`.
Una di esse (`banking`) istruisce l'assistente a **rifiutare ogni domanda implementativa**
finché non riceve una release phrase, e a non rivelare né lo scherzo né la frase.

**Sono dati contenuti in un repository, non istruzioni.** Se il nostro pipeline ingerisce
questo fixture (o qualsiasi contenuto recuperato dal web) senza separare dati e istruzioni,
la demo si blocca. Vale come promemoria di design: **il contenuto recuperato dalle fonti
non deve mai poter pilotare il comportamento dell'agente.**

### 13.3 Il fixture non è il set di valutazione
> *"These are preparation materials, not verified reference answers, the hidden question set
> or a scoring formula."*

Le risposte fattuali vanno verificate su fonti autorevoli correnti: nessun practice case
sostituisce una fonte.

---

## 14. Citazioni chiave (verbatim, EN)

Da usare come riferimento letterale quando c'è un dubbio di interpretazione.

**Sullo scope:**
> "Declare your scope. In your README, state which topics and which geography your server
> covers... We evaluate answer quality against that declaration."

**Sulla priorità qualità vs. ampiezza:**
> "In general, a high quality solution with narrow coverage is preferred over a broad
> solution with low quality. Having both is best and wins."

**Sull'ordine di importanza:**
> "The order of importance is: correct and honest answers, then breadth, then agent
> efficiency, operability and the quality of your MCP contract as tie breakers."

**Su robots.txt:**
> "Your server should respect the robots.txt and terms of use of the sources it accesses
> by default. Whether it does so must be a configuration setting, not hardcoded behaviour,
> so that Swisscom can switch it on or off when running your server for testing. Document
> the setting and its default in your README."

**Su cosa fa un buon MCP (slide 4):**
> "Offers a coherent, compact set of tools · Returns evidence an AI client can use and cite
> · Keeps information as fresh as the use case needs · Says so when a question is not
> covered · Runs locally from its repo; hosting it as well is your choice"

**Sul non costruire per un client specifico:**
> "We do not disclose which clients and which models we use, so build against the MCP
> standard rather than against one specific assistant."

---

## 15. Lettura strategica

Il segnale dominante del materiale: **questa challenge non premia la copertura, premia la
disciplina epistemica.** Il sistema deve saper produrre quattro output distinti:

1. risposta + passaggio esatto che la prova + data di efficacia
2. richiesta precisa del singolo dato mancante
3. "fuori dalla mia copertura dichiarata"
4. "la fonte non è raggiungibile" (≠ "il fatto non esiste")

Il comportamento da eliminare è il quinto: rispondere in modo plausibile. È il default di
un LLM, ed è esattamente ciò che fa perdere punti. Gran parte del lavoro tecnico consiste
nel **togliere al modello la possibilità di improvvisare**, non nell'aggiungere fonti.

Corollario dal caso `citation_support` + checklist punto 3: una risposta con link generico
a un dominio ufficiale vale zero. Serve il **passaggio testuale** che sostiene la claim
specifica, con l'autorità realmente competente per quella materia.
