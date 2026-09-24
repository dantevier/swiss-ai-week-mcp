# Contratto MCP

> **Stato: v6, 212 esecuzioni su sei versioni. IL GATE È ROSSO (§8.6).** La domanda
> campione 5 produce `NONE` su Haiku 4.5 in **3 esecuzioni su 12**: il 25% sulla
> metrica fatale. Le passate precedenti "33/33" e "41/41" erano **una estrazione per
> cella** e non potevano vederlo.
>
> ⚠️ **Il test ha falsificato una riga di §1**: vedi §8.4.
>
> ⚠️ **Non esiste ancora un server.** Tutto ciò che questo documento descrive come
> comportamento a runtime è contratto, non codice: l'unico file eseguibile del
> dominio è `manifest.py`, e `src/tools.ts` contiene solo le definizioni dei tool.
>
> ⚠️ **Le descrizioni qui sotto sono una copia di lettura. La fonte è
> [`src/tools.ts`](src/tools.ts)**, che importano sia il server sia il test: le
> descrizioni testate sono le descrizioni spedite. Se le due divergono, vale il
> codice.
>
> Requisiti: [CHALLENGE.md](CHALLENGE.md) · Fonti e vincoli: [SOURCES.md](SOURCES.md)
>
> Scope dichiarato: **premi cassa malati** e **tasso di riferimento ipotecario** per tutta
> la Svizzera; **vacanze scolastiche** e **cambio patente estera** per tutti i 26 cantoni.

---

## 1. Principio di design

Swisscom testa con **2 client × 2 LLM non dichiarati**. Da cui:

> Tutto ciò che deleghiamo al modello varia su quattro configurazioni.
> Tutto ciò che decide il server è costante su quattro configurazioni.

**Server grasso, modello magro.** Al modello resta una sola decisione: quale tool
chiamare. Risoluzione della giurisdizione, ask-back, citazione, date, stato giuridico
della fonte: tutto server.

### L'asimmetria che guida le descrizioni

| Errore | Costo |
|---|---|
| Il modello non chiama nulla | **catastrofico** — allucina, ed è attribuito a noi |
| Chiama il tool tematico sbagliato | basso — `out_of_scope` con la copertura giusta |
| Chiama la copertura quando bastava un tool | minimo — una chiamata sprecata |
| Chiama un tool quando serviva la copertura | basso — il tool **riceve** `question` e potrà rispondere `out_of_scope`; il comportamento **non è implementato** (§8.4) |

Tre errori su quattro sono recuperabili dal server. Le descrizioni devono spingere verso
**"chiama qualcosa"**, non verso la precisione della scelta.

---

## 2. Superficie: cinque tool

| Tool | Compito |
|---|---|
| `swiss_school_holidays` | vacanze scolastiche, 26 cantoni |
| `swiss_health_insurance_premiums` | premi cassa malati, tutta la CH |
| `swiss_driving_licence_exchange` | cambio patente estera, federale + 26 cantoni |
| `swiss_reference_interest_rate` | tasso di riferimento ipotecario, valore nazionale |
| `check_swiss_question` | **catch-all e copertura** |

Uno per tema, corrispondenza uno a uno con la dichiarazione nel README. Il quinto esiste
perché senza di esso **una domanda sui rifiuti bypassa il server e il modello improvvisa**
— che è il fallimento peggiore possibile.

Il nome `check_swiss_question` è attivo di proposito: si legge come un'azione da compiere
su una domanda, non come un elenco di capacità. Rischio noto: può essere invocato prima
di ogni cosa, pesando sul criterio 3. Mitigato da una riga esplicita nella descrizione,
**da misurare nel test**.

---

## 3. Le descrizioni

Ogni descrizione contiene cinque cose: condizione di attivazione valutabile, cosa
restituisce, perché non improvvisare, confine con i tool vicini, **esempi di trigger nelle
quattro lingue nazionali**. Nessun dettaglio implementativo.

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

| Parametro | Descrizione |
|---|---|
| `place` | ***Optional** but almost always needed. The place exactly as the user wrote it, in any national language. Do not translate, normalise, or convert to a canton. Pass "Scuol", not "Graubünden". If the user did not name a place, call the tool anyway.* — §4.6 |
| `holiday_type` | *Optional. Cantons do not share one vocabulary, so the description lists the real names per slot: `Sportferien`/`Fasnachtsferien`/`Fasnachts- und Sportferien`/`relâches` for **sport**, `Frühlingsferien`/`Frühjahrsferien`/`Osterferien` for **spring**. Omit to get the full school year.* Vedi SOURCES §8quater.5 |
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

| Parametro | Descrizione |
|---|---|
| `place` | ***Optional** but almost always needed. The municipality exactly as the user wrote it. The premium region is a legal assignment per municipality, not per canton.* — §4.6 |
| `age` | ***Optional**, stringa. Age in years as written, e.g. "30", oppure la classe d'età se è tutto ciò che l'utente ha dato. Era `integer`, e contraddiceva la propria descrizione.* |
| `franchise` | ***Optional**. Annual deductible in CHF, e.g. 2500.* — §4.6 |
| `accident_cover` | *Optional: true or false. If omitted, both values are returned and the distinction is stated.* |
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

| Parametro | Descrizione |
|---|---|
| `place` | ***Optional**. The canton or place of residence, exactly as the user wrote it. Omettendolo il tool risponde comunque il livello federale e dichiara che la procedura dipende dal cantone.* — §4.6 |
| `issuing_country` | *Optional. Determines whether a control drive or a theory exam is required.* |
| `question` | *Optional but recommended: the user's question, in the language they wrote it. Used to confirm the question really is about exchanging a licence, and not about another arrival formality.* — §8.4 |

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

| Parametro | Descrizione |
|---|---|
| `as_of` | *Optional date. Returns the rate that was in force on that date. Omit for the current rate.* |
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

| Parametro | Descrizione |
|---|---|
| `question` | *Optional: the user's question, in the language they wrote it. Used to give a specific rather than generic answer.* |
| `topic` | *Optional: a topic keyword, if the question is about capability rather than a specific case.* |
| `place` | *Optional: a place, to check whether that jurisdiction is covered.* |

---

## 4. Convenzioni dei parametri

1. **`place` non si traduce, non si normalizza, non si converte in cantone.** Senza questa
   regola il modello "aiuta" trasformando Scuol in Grigioni, e perdiamo la risoluzione
   comunale che è tutto il valore del tool.
2. **Ogni opzionale ha un default dichiarato nella risposta**, mai silenzioso.
3. **Assunzione dichiarata invece di ask-back quando le alternative sono enumerabili.**
   Copertura infortuni non specificata → si restituiscono entrambi i valori con la
   distinzione. 160 comuni zurighesi → si chiede.
4. **Nessun parametro è obbligatorio su nessun tool tematico.** Un parametro
   obbligatorio sposta l'ask-back dal server al client: il modello che non ha il dato o
   lo inventa, o non chiama. Non chiamare è l'unico errore che §1 classifica
   catastrofico, e con `place`, `age` e `franchise` obbligatori lo stato `need_info` di
   §5.1 era **irraggiungibile**. Chi decide cosa manca è il server, e per deciderlo deve
   prima essere chiamato. *(Corretto il 2026-09-22; numerato §4.6 nei riferimenti.)*
5. **Ogni tool tematico riceve `question`.** Deriva da §8.4: senza la domanda, un tool
   tematico può dichiarare fuori scope la giurisdizione ma mai il tema, e risponde
   correttamente a una domanda che nessuno ha fatto. È anche ciò che rende lo stato
   `out_of_scope` di §5.1 disponibile su tutti e cinque i tool, non solo sulla copertura.
6. **Il tipo di scuola non è un parametro.** Si risponde per la scuola dell'obbligo e lo
   si dichiara, segnalando se altri tipi differiscono. Deriva dal caso friburghese
   (SOURCES §8ter.8): il tipo di scuola è una dimensione di giurisdizione, ma esporlo
   come parametro produrrebbe più errori di quanti ne eviti.

---

## 5. L'inviluppo di risposta

### 5.1 I cinque stati

Se non sono espliciti nel contratto, il modello li appiattisce tutti in "non lo so".
La review checklist punto 6 ne richiede quattro; con la risposta positiva fanno cinque.

| Stato | Quando | Contenuto minimo |
|---|---|---|
| `answered` | risposta trovata | §5.2 |
| `need_info` | manca un dato che **cambia** la risposta | quale dato, perché, e i candidati se ambiguo |
| `out_of_scope` | fuori dalla copertura dichiarata | perché (tema / giurisdizione / non svizzero) + cosa copriamo |
| `source_unavailable` | fonte non raggiungibile | distinzione esplicita da "il fatto non esiste"; se si risponde da cache, la sua data |
| `no_match` | fonte raggiunta, nessun risultato | il fatto non risulta — non è un errore tecnico |

Gli ultimi due sembrano pedanteria e sono il practice case `source_failure` alla lettera.

### 5.2 Campi di una risposta positiva

Ogni campo nasce da un fallimento osservato nella ricerca.

| Campo | Perché |
|---|---|
| `passage` — passaggio probante verbatim | `citation_support`: una homepage non basta |
| `authority` + `level` | checklist punto 3: ente competente, non solo dominio ufficiale |
| `source_url` | verificabile da un umano |
| `effective_from` | il tasso di riferimento ha **quattro** date e sceglierne una sbagliata dà una risposta falsa citando la fonte giusta |
| `published_at` | distinta dalla precedente |
| `reference_year` | i premi 2026 non si mescolano con l'ordinanza 2027 |
| `source_status` — `binding` / `indicative` / `provisional` | Svitto pubblica open data che si auto-dichiara non vincolante |
| `derived` — booleano + regola applicata | SH e SG pubblicano `KW 40–42`, non le date |
| `assumptions[]` | "senza copertura infortuni", "scuola dell'obbligo", "anno 2026" |
| `source_validated_at` | tre deep link cantonali su tre erano morti |

### 5.3 Disciplina sulla dimensione

Il criterio 3 penalizza le risposte grosse.

- **Un passaggio, non il documento.**
- Campi presenti solo quando si applicano.
- Il manifest **fuori** dalle risposte positive.
- **Troncare esplicitamente, mai in silenzio**: una lista tagliata senza avviso è
  indistinguibile da una copertura incompleta, e verrebbe letta come tale.

---

## 6. Il manifest di copertura

### 6.1 Chiave e campi

> Implementato in `coverage/*.toml` (TOML, un file per tema) + `manifest.py`
> (loader, validatore, generatore del blocco README). 62 voci.

Chiave: **(tema × giurisdizione × sotto-tema)**. Non basta il tema: in BE l'autunno è
cantonale e febbraio comunale; in SO l'autunno è uniforme mentre sport e primavera
variano; in AG varia la *durata* dell'autunno.

`subtopic` è un **override, non una coordinata obbligatoria**: `"*"` vale per tutti i
sotto-temi, e si scrive una riga specifica solo dove il modello cambia. Senza questa
regola le vacanze da sole farebbero 130 righe invece di 32. Le eccezioni nominate sono
righe, non strutture annidate: `jurisdiction = "OW/Engelberg"`.

Il lookup è **most-specific-wins, con la giurisdizione che batte il sotto-tema**:

```
(OW/Engelberg, autumn) → (OW/Engelberg, *) → (OW, autumn) → (OW, *) → (CH, autumn) → (CH, *)
```

Campi per voce: `theme`, `jurisdiction`, `subtopic`, `resolution_level`,
`on_missing_place`, `authority`, `authority_level`, `source_url`, `landing_url`,
`source_status`, `validated_at`. Opzionali: `legal_basis`, `ask_back`, `derivation`,
`notes`.

`resolution_level` ∈ `national` · `cantonal_uniform` · `per_municipality_in_source` ·
`per_language_region` · `rule_with_exceptions` · `cantonal_framework_municipal_choice` ·
`delegated` — descrive **com'è fatto il mondo**, e alimenta la dichiarazione del README.

`on_missing_place` ∈ `answer` · `resolve_in_source` · `ask` — descrive **cosa fa il
server**, ed è questo campo a decidere l'ask-back, non il giudizio del modello.

**I due assi sono separati perché uno non implica l'altro.** AG, AR e SG condividono il
modello `cantonal_framework_municipal_choice` ma si comportano in tre modi diversi: AG
chiede il comune (varia la durata), AR risponde con `source_status: indicative`, SG
chiede. Un enum che descrive la struttura giuridica non può decidere il comportamento.

Due invarianti, entrambe imposte dal validatore:

- **`validated_at` vuoto = non coperto.** Una voce entra nella copertura dichiarata solo
  quando qualcuno ha aperto il documento e incollato l'URL. Un URL non validato non è
  copertura, è un buon proposito. Fallisce dalla parte giusta: FR e VS restano righe con
  la fonte identificata e la copertura non dichiarata.
- **`ask_back` obbligatorio quando `on_missing_place = "ask"`.** L'ask-back va citato,
  non asserito (SOURCES §8ter.7).

`landing_url` è separato da `source_url` perché i deep link marciscono: AR, OW e NW
davano 404 e il documento corrente si ritrovava solo dalla pagina di atterraggio
(SOURCES §8ter.9). Il validatore controlla il contenuto solo sul `source_url` — il
`landing_url` deve solo rispondere, e può legittimamente essere una SPA.

### 6.2 Due consumatori, una fonte

Il **server** lo legge per decidere ask-back e fuori scope. Il **README** lo legge al
build per la dichiarazione di copertura. Se divergono, la giuria lo vede: è esattamente
la terza vista che valutano.

Il README **non chiama il tool**, legge il file. Quindi il tool non deve mai emettere
tutto il manifest.

### 6.3 La regola che tiene compatte le risposte

> **La copertura è un'affermazione su cosa sappiamo rispondere, non un elenco di
> risposte.**

I Grigioni non sono 100 righe: sono **una riga**, "tutti i comuni, risolti nel documento
cantonale". I 100 comuni sono *dati*, non copertura. Con questa regola il manifest sta in
60–90 righe invece che migliaia.

**Se una risposta di `check_swiss_question` contiene una lista di comuni, il design è
scivolato.**

### 6.4 Tre livelli di risposta

| Chiamata | Restituisce |
|---|---|
| nessun argomento | la dichiarazione: 4 temi, estensione geografica, e cosa **non** copriamo. ~15 righe |
| `topic` | il modello di risoluzione **riassunto per eccezione** |
| `topic` + `place` | la riga precisa — **è questa che guida l'ask-back** |
| `question` | la rete di keyword: rifiuto specifico invece di generico |

Esempio del secondo livello, sei righe invece di ventisei:

> Coperto per tutti i 26 cantoni. Uniforme in 12. Per comune, nel documento cantonale,
> in 5 (GR, LU, SO, UR, SZ). Per regione linguistica in 2 (BE, VS). Uniforme con
> eccezioni nominate in 3 (FR, OW, AI). Quadro cantonale con scelta comunale in 3
> (AG, AR, SG). Delegato ai comuni in 1: **ZH richiede il comune**.

---

## 7. Regole derivate dalla ricerca

Ogni riga nasce da un fallimento reale documentato in SOURCES.md.

| Scoperta | Regola nel contratto |
|---|---|
| ZH delega, BE solo febbraio, SO solo sport/primavera; **AG, AR e SG non hanno le vacanze di sport nel documento cantonale** (SOURCES §8quinquies) | risoluzione per (giurisdizione × sotto-tema). In AG, AR e SG **cambia la classe stessa** fra tipi di vacanza: senza il sotto-tema, SG chiedeva il comune anche a Natale — un ask-back inutile, che CHALLENGE §5.4 conta come sbagliato |
| Il PDF friburghese era delle scuole professionali | il tipo di scuola è giurisdizione (§4.4) |
| Filestore Fedlex indirizzabile per data | fonti federali interrogate **per data di riferimento** |
| Svitto: open data non vincolante | `source_status` su ogni fonte |
| Il PDF bernese cita Plagne e Vauffelin, sciolti | il risolutore serve nomi storici e attuali |
| `ne.ch/…pdf` restituisce HTML con 200 | validare il **Content-Type**, mai l'estensione |
| Filestore Fedlex: data invalida → shell con 200 | validare il **contenuto**, non lo status |
| AR/OW/NW: deep link 404, v1.1 superata da v1.3 | partire dalla pagina di atterraggio; `validated_at` |
| SH e SG pubblicano `KW 40–42` | `derived` con la regola applicata |
| Tasso con quattro date | `effective_from` ≠ `published_at` |

---

## 8. Test delle descrizioni — da fare per primo

**Non serve il server.** Bastano gli schemi dei tool e un elenco di domande: si chiede a
più modelli *"quale tool chiameresti?"* e si guarda la distribuzione. Costa un'ora, si fa
**giovedì mattina prima di qualsiasi implementazione**, e misura l'unica variabile che non
controlliamo. Soddisfa anche la checklist punto 7.

### 8.1 Oracolo di routing

| # | Domanda | Lingua | Tool atteso |
|---|---|---|---|
| 1 | *Wann wird bei uns das nächste Mal Karton abgeholt?* | de | `check_swiss_question` → rifiuti, non coperto |
| 2 | *Comment puis-je échanger mon permis de conduire étranger… dans le canton de Vaud?* | fr | `swiss_driving_licence_exchange` |
| 3 | *Qual è il premio mensile più basso… a Lugano con franchigia di 2500?* | it | `swiss_health_insurance_premiums` |
| 4 | *Cura èn las vacanzas d'atun 2026 per la scola da Scuol?* | rm | `swiss_school_holidays` |
| 5 | *Wie hoch ist der Rundfunkbeitrag… nach Konstanz?* | de | `check_swiss_question` → fuori CH |
| 6 | *Wann sind die Herbstferien 2026 in der Stadt Bern?* | de | `swiss_school_holidays` |
| 7 | *Où trouver le calendrier officiel des vacances scolaires 2026 de Genève?* | fr | `swiss_school_holidays` |
| 8 | *Où dois-je annoncer mon arrivée dans la ville de Lausanne?* | fr | `check_swiss_question` → non coperto |
| 9 | *Comment annoncer mon arrivée à Lausanne? Et à Berne?* | fr | `check_swiss_question` → non coperto |
| 10 | *Qual è il tasso ipotecario di riferimento attualmente in vigore?* | it | `swiss_reference_interest_rate` |
| 11 | *Quale autorità pubblica il tasso ipotecario di riferimento?* | it | `swiss_reference_interest_rate` |

Quattro lingue, entrambi i tipi di fuori-scope, entrambi i temi federali.

### 8.2 Cosa misurare

- **Chiamate mancate**: il modello risponde senza chiamare nulla. È l'unica metrica
  fatale; tutte le altre sono recuperabili.
- **Sovra-invocazione di `check_swiss_question`**: chiamato prima di tool tematici che
  combaciavano chiaramente. Pesa sul criterio 3.
- **Confusione fra tool tematici**: recuperabile, ma segnala descrizioni sovrapposte.
- **Divario fra lingue**: se il romancio fa peggio, servono più esempi di trigger.

---

### 8.3 Risultati, 2026-09-22

Eseguito **prima** dell'evento invece che giovedì mattina: non serviva il team e non
serviva il server. Implementato in [`test/routing-test.ts`](test/routing-test.ts), dati
grezzi in [`test/answers-2026-09-22.json`](test/answers-2026-09-22.json).

**Metodo.** Una conversazione pulita per domanda per esecuzione, mai in batch — in batch
il modello vede lo schema e si auto-corregge. Ogni contesto vedeva solo il prompt, mai
questo documento. Tre livelli di capacità: Opus 5, Sonnet 5, Haiku 4.5. **95 esecuzioni**
su tre versioni delle descrizioni.

Due file, e la distinzione conta:
[`answers-2026-09-22.json`](test/answers-2026-09-22.json) contiene **solo la versione
corrente** ed è il gate — esce 0.
[`answers-history-2026-09-22.json`](test/answers-history-2026-09-22.json) contiene tutta
la traccia v1 → v3 ed **esce 1 di proposito**, perché contiene i difetti corretti.
Mescolarli renderebbe il codice d'uscita inutile.

**Il prompt non chiede "quale tool chiameresti".** Chiederlo forza una chiamata e rende
cieca l'unica metrica fatale. Il prompt offre esplicitamente `NONE`, e il self-check
fallisce se qualcuno reintroduce la formulazione che forza.

#### Due difetti trovati, entrambi su domande campione pubblicate

| # | Sintomo | Causa | Correzione |
|---|---|---|---|
| 5 | Haiku non chiamava nulla sulla domanda Konstanz | `check_swiss_question` copriva *"unsure whether it is about Switzerland"*, **non la certezza negativa**. Una domanda palesemente sulla Germania non rientrava in nessuna clausola, e il modello concludeva correttamente che il tool non si applicava | clausola esplicita sul fuori-Svizzera |
| 11 | Haiku **e Sonnet** non chiamavano nulla su *"quale autorità pubblica il tasso?"* | **la descrizione conteneva la risposta**: *"published by the Federal Housing Office"*. Il modello aveva già tutto senza chiamare | clausola *"This description is not a source"* su questa e su `swiss_school_holidays` |

Il secondo è il difetto strutturale: **i fatti che servono a dire "non improvvisare" sono
gli stessi che permettono di rispondere senza chiamare.** Ogni descrizione che cita un
dato concreto per giustificarsi apre la stessa falla. `swiss_school_holidays` cita
*"Geneva and Vaud… do not overlap by a single day"* ed era esposta allo stesso modo.

#### Rivalidazione completa della v3

Cambiare la descrizione del catch-all tocca **tutti** gli 11 prompt, quindi due domande
non bastavano a dichiarare chiuso il lavoro. Passata completa, 11 × 3:

| Modello | Esecuzioni | Esatte | Mancate |
|---|---|---|---|
| Opus 5 | 11 | 11 | 0 |
| Sonnet 5 | 13 | 13 | 0 |
| Haiku 4.5 | 17 | 17 | 0 |
| **totale v3** | **41** | **41** | **0** |

#### Il risultato più importante non è un difetto: è la varianza

La domanda 11 ha prodotto `NONE` in **2 esecuzioni su 7 a parità di prompt e modello**, e
non solo sul modello debole. In v1 era passata; in v2 falliva; con quattro ripetizioni
tornava a passare.

> **Una singola esecuzione non è una misura.** Non distingue una descrizione rotta da un
> colpo di fortuna, e la metrica che oscilla è proprio quella fatale.

Conseguenza operativa: lo scorer accetta ripetizioni per cella.

Quanto vale la correzione della 11, in numeri: il tasso di fallimento misurato in v2 era
**2 su 7 (29%)**; in v3 la domanda 11 ha prodotto **9 esecuzioni pulite su 9**. Sotto il
tasso base, vedere nove successi di fila ha probabilità **0,71⁹ ≈ 4,8%**.

Abbastanza per procedere, **non** una dimostrazione. Per scendere sotto l'1% servirebbero
~14 esecuzioni pulite consecutive sulla stessa cella.

#### Cosa NON è stato misurato

- **Una sola famiglia di modelli.** Misura la robustezza alla forza del modello, non la
  copertura di famiglie diverse. I 2 LLM della giuria non sono dichiarati.
- **Zero sovra-invocazioni di `check_swiss_question` in 95 esecuzioni**, di cui 41 dopo
  le due clausole che ampliano il catch-all. Era il rischio previsto in §2 per il nome
  attivo, ed è l'unico che il test poteva smentire: non si è mai manifestato. Resta
  possibile che compaia su un'altra famiglia di modelli.
- **Zero confusioni fra tool tematici in 95 esecuzioni.** I confini delle quattro
  descrizioni tematiche reggono; il lavoro da fare era tutto sul catch-all.
- **Romancio: 7 esecuzioni su 7 corrette**, ma su **una sola domanda**. Nessun divario fra
  lingue osservato, e il campione non autorizza a dirlo. La domanda 4 è l'unica in rm
  dell'oracolo: se si vuole una misura sul romancio, servono altre domande, non altre
  ripetizioni.

### 8.4 🔴 Il test ha falsificato la quarta riga di §1

v4, Sonnet 5, domanda 9 — *"Comment annoncer mon arrivée à Lausanne? Et à Berne?"*,
notifica di domicilio, fuori copertura. Sonnet ha chiamato
`swiss_driving_licence_exchange`. Una volta su sei: nelle altre cinque, e in v1, v2 e v3
su tutti e tre i modelli, ha chiamato correttamente `check_swiss_question`.

Il tasso è basso. Il problema non è il tasso.

**§1 classifica questo caso come "costo nullo — stessa risposta". È falso per
costruzione.** I quattro tool tematici ricevono `place`, `age`, `franchise`,
`issuing_country`, `as_of` — **mai la domanda**. Solo `check_swiss_question` ha il
parametro `question`.

Quindi `swiss_driving_licence_exchange(place="Lausanne")` non ha alcun modo di sapere che
l'utente chiedeva della notifica di domicilio: risolve Lausanne, trova la riga VD del
manifest, e **risponde correttamente a una domanda che nessuno ha fatto**. Grounded,
citato, e fuori tema.

> **Un tool che non vede la domanda non può accorgersi che la domanda non è la sua.**
> L'asimmetria di §1 regge su tre righe su quattro; la quarta presupponeva una capacità
> che il contratto non dà ai tool tematici.

La causa probabile della confusione è lessicale: la descrizione della patente dice
*"converting, exchanging or **registering** a foreign driving licence"*, e *"annoncer mon
arrivée"* è una registrazione all'arrivo. Ma **la descrizione non è il difetto** — il
difetto è che il tool non può recuperare quando la selezione sbaglia.

**Contratto corretto in v5, comportamento non ancora implementato**: i quattro tool
tematici hanno ora un parametro `question` opzionale,
con la stessa motivazione scritta nella descrizione del parametro — *"confirm the question
really is about X; if it is not, say so plainly instead of answering a question nobody
asked"*. Quello della patente nomina esplicitamente il caso confuso: *"and not about some
other kind of registration or arrival formality"*.

La riga di §1 torna *formulabile*, ma **per una ragione diversa da quella originale**:
non perché la risposta sia la stessa, ma perché il tool ha ora di che accorgersi che non
lo è. Finché non esiste il server, **è una promessa del contratto, non un fatto**.

⚠️ **Il presidio dipende da un parametro opzionale che decide il modello.** §1 stabilisce
che tutto ciò che deleghiamo al modello varia su quattro configurazioni: se `question`
non viene passata, il recupero non avviene. O diventa obbligatoria, o il recupero è
probabilistico — decisione aperta.

### 8.5 Numeri consolidati

| Versione | Cosa cambiava | Esecuzioni | Mancate |
|---|---|---|---|
| v1 | descrizioni originali | 33 | 1 (domanda 5, Haiku) |
| v2 | + clausola cross-border | 21 | 2 (domanda 11, Haiku e Sonnet) |
| v3 | + clausola "not a source" | 41 | 0 |
| v4 | + nomi reali dei tipi di vacanza | 39 | 0 |
| v5 | + `question` sui quattro tematici | 33 | 0 |
| **v6** | **+ nessun parametro obbligatorio, `age` stringa, `Februarferien`** | **45** | **3 — tutte sulla domanda 5, Haiku** |
| **totale** | | **212** | **6** |

In 167 esecuzioni: **zero sovra-invocazioni** del catch-all, **zero confusioni fra tool
tematici**, **una sola** invocazione di un tool tematico al posto del catch-all (§8.4,
v4, Sonnet, domanda 9 — poi corretta 5 volte su 5 e superata in v5).
Romancio 14 su 14, ma sempre sulla stessa unica domanda: è una costante, non una misura.

⚠️ Aggiungere `question` ai tematici li rende **più simili** al catch-all, quindi il
rischio di sovra-invocazione poteva peggiorare. Misurato in v5: **zero**. Resta la
configurazione con più superficie e meno errori osservati.

### 8.6 🔴 Il risultato che invalida la lettura delle passate precedenti

v6 aggiunge 12 ripetizioni sulla domanda 5 — *"Wie hoch ist der Rundfunkbeitrag… nach
Konstanz?"*, la domanda campione che **non è sulla Svizzera**. Haiku 4.5 risponde `NONE`
**3 volte su 12**: non chiama nulla, e risponde di suo sul canone televisivo tedesco.

**Non è dimostrabilmente una regressione di v6.** Da v2 a v5 la domanda 5 aveva 6
esecuzioni pulite su Haiku — ma erano **una estrazione per versione**. Un tasso del 25%
si nasconde benissimo in una estrazione singola: `0,75⁶ ≈ 18%` di probabilità di non
vederlo mai. Il test di Fisher su 0/6 contro 3/12 dà **p ≈ 0,52**: indistinguibile.

> **Le passate "33 su 33" e "41 su 41" non significavano quello che sembravano.**
> 33 esecuzioni distribuite su 11 domande × 3 modelli sono **una estrazione per cella**.
> Un difetto al 25% è invisibile a un campione, e il fatto che v1 lo avesse trovato è
> fortuna, non metodo. Il campo `_limite_potenza` del file risposte lo diceva dall'inizio;
> i risultati sono stati letti con più fiducia di quanta il disegno ne autorizzasse.

Conseguenza operativa: **un verde su una estrazione per cella non è una prova.** Per
dichiarare chiusa una cella servono ~20 ripetizioni, e il budget non consente di farlo su
tutte e 33. La scelta ragionevole è concentrare le ripetizioni sulle celle che pesano:
le domande dove l'attesa è il catch-all e il modello è il più debole.

Ipotesi sulla causa, **non verificata**: la descrizione di `check_swiss_question` non è
cambiata da v2, ma il prompt complessivo è cresciuto a ogni versione, e la clausola
cross-border compete con sempre più testo. Se fosse così, la cura sarebbe accorciare le
descrizioni, non allungarle ancora.

---

### 8.7 🔴 v7, 2026-09-23: Sonnet manca il catch-all anche sul testo di v6

**Modifica v7**: tolta da `swiss_school_holidays` la frase *"Geneva and Vaud share a
border and their 2026 autumn holidays do not overlap by a single day"*. Era **falsa**:
l'autunno VD 10–25.10.2026 contiene l'autunno GE 19–23.10.2026 (SOURCES §8septies.1).

| Configurazione | Esito |
|---|---|
| v7 Opus 5, 11 domande | **11/11** |
| v7 Sonnet 5, 11 domande | 9/11 al primo giro: NONE sulle domande **1** e **5** |
| v7 Sonnet, domande 1 e 5, 4 esecuzioni ciascuna | domanda 1: **2 NONE su 4** · domanda 5: **2 NONE su 4** |
| **v6c** Sonnet (controllo: stessi prompt con la frase rimessa, stessa sessione) | domanda 1: **1 NONE su 3** · domanda 5: **1 NONE su 3** |

Due conclusioni, entrambe da leggere con §8.6 in mente:

1. **La modifica non è la causa.** Il NONE compare anche sul controllo, che ha il testo di
   v6 byte per byte. 4/8 contro 2/6 non è distinguibile con questi numeri. La frase
   rimossa era falsa, quindi va tolta comunque.
2. 🔴 **"Sonnet è pulito sulle domande a catch-all" era una stima da poche estrazioni, ed è
   falsa oggi.** Su 14 esecuzioni odierne delle domande 1 e 5, entrambe le versioni
   insieme, Sonnet ha dato NONE **6 volte**. Nel registro di v6 le stesse celle avevano
   1 e 2 estrazioni. Il difetto non riguarda più solo il modello debole: riguarda **le due
   domande fuori scope** (rifiuti, Konstanz) sul modello più vicino alla popolazione della
   giuria. Le domande tematiche restano pulite su entrambi i modelli.

Haiku non è stato eseguito in questa passata. Registro completo in
`test/answers-history-2026-09-22.json`, chiavi `v7 …` e `v6c …`.

### 8.8 Prova generale in OpenCode Desktop, 2026-09-23

Prima prova con il client della giuria. OpenCode Desktop 2.0.15 su Windows 11, modello
**MiMo-V2.6-Flash Free** (prima misura fuori dalla famiglia Claude). Riportata
dall'utente con l'aiuto di un assistente; **il JSON grezzo delle risposte non era
visibile nell'interfaccia** per quasi tutte le chiamate, quindi gli stati sono verificati
solo dove indicato.

**Collegamento: funziona.** `opencode.json` alla radice del progetto, percorso relativo
`["node", "src/server.ts"]`, senza `cwd`, anche con gli spazi nel percorso. La schermata
dei server MCP globali era vuota: la configurazione di progetto basta. La CLI
`opencode-ai` 1.18.32 installata accanto al Desktop 2.0.15 falliva con *"Database is not
empty and has no session table"*: versioni diverse sullo stesso database locale. È stata
rimossa; il Desktop funziona da solo.

| # | Domanda | Tool chiamati | Stato MCP | Risposta finale |
|---|---|---|---|---|
| 1 | tasso | `swiss_reference_interest_rate` | non visibile | ✅ 1,25 % dal 02.09.2025 |
| 2 | premi Lugano | `check_swiss_question` → una ricerca → `swiss_health_insurance_premiums` | non visibile | ✅ 679–826,50, mediana 740,20, 21 offerte |
| 3 | patente VD | `swiss_driving_licence_exchange` → `check_swiss_question`, più webfetch | `answered` visibile | ✅ |
| 4 | cartone | uno strumento non identificabile | non visibile | ❌ chiede il comune invece di dire "non coperto" |
| 5 | Konstanz | `check_swiss_question` | non visibile | ⚠️ riconosce che è fuori Svizzera, poi **risponde lo stesso** (18,36 €/mese) da conoscenza propria e dal web |
| 6 | Scuol | `check_swiss_question` → `swiss_school_holidays` | non visibile | ⚠️ scarica il PDF cantonale con la shell e dà 10–25.10.2026, che coincide con la nostra nota GR |
| 7 | Winterthur | `swiss_school_holidays` | **`out_of_scope` / `set_by_municipality` visibile** | ⚠️ poi consulta fonti comunali sul web e dà le date |

Cosa insegna:
- **Il server fa ciò che deve** dove lo stato è visibile (3, 7). Non è emerso nessun difetto
  del server.
- **Il client ha altri strumenti**: ricerca web, webfetch, shell. Il modello li usa **dopo**
  il nostro tool per andare oltre la sua risposta. Con `not_ingested` è coerente con il
  nostro stesso testo (*"use the source below"*). Con `out_of_scope` su Konstanz produce
  proprio la risposta non fondata che il fuori scope dovrebbe evitare.
- **Non sappiamo se la giuria abiliterà questi strumenti.** Il comportamento misurato qui
  è quello di un client con il web attivo.
- **Senza vedere il JSON, uno stato non si può verificare.** Serve un registro lato
  server delle chiamate, altrimenti ogni prova in OpenCode resta una lettura di
  schermate.

#### Seconda passata, con il registro delle chiamate

Stesso client, stesso modello, stesse 7 domande, server riavviato con il registro
`logs/calls.jsonl`. Tutti gli stati ora sono letti dal registro, non dalle schermate.

| # | Chiamate MCP (in ordine) | Stato dal registro | Server | Modello |
|---|---|---|---|---|
| 1 | tasso | `answered` | ✅ | ✅ |
| 2 | catch-all → premi | `answered`, `answered` | ✅ | ✅ 679–826,50 |
| 3 | patente → catch-all | `answered`, `answered` | ✅ | ✅ aggiunge dettagli VD via webfetch dai link forniti dal tool |
| 4 | catch-all | `out_of_scope` / `topic_not_covered` | ✅ | ✅ dice che non può rispondere, non cerca |
| 5 | catch-all | `out_of_scope` / `place_not_in_switzerland` | ✅ | ❌ webfetch, risponde 18,36 €/mese |
| 6 | vacanze | `source_unavailable` / `not_ingested` | ✅ | ❌ scarica il PDF con la shell, dà le date |
| 7 | catch-all → vacanze | `answered`, `out_of_scope` / `set_by_municipality` | ✅ | ❌ PDF comunali via webfetch e shell, dà le date |

- **Server: 7 su 7.** Ogni stato è quello atteso dal test automatico.
- **Modello: 4 su 7.** I tre casi negativi hanno la stessa forma: il nostro stato dice
  "non da qui", e il modello usa webfetch o la shell per rispondere lo stesso. Nel caso 6
  il nostro testo lo invita (*"use the source below"*).
- **Il cartone è cambiato fra le due passate**: nella prima il modello chiedeva il comune,
  nella seconda chiama il catch-all e si ferma. Una sola estrazione per passata (§8.6).
- **Il catch-all viene chiamato in più**: in 3 domande su 7, accanto al tool tematico
  giusto. Innocuo per l'esito, ma è una chiamata in più per risposta.
- **Riavvio del server**: chiudere la finestra di OpenCode Desktop non ferma il backend
  `opencode-cli.exe`, che continua a usare il server già avviato. Dopo ogni modifica si
  termina `opencode-cli` e si controlla che lo `StartTime` di `node` sia successivo alla
  modifica di `src/server.ts`.
- **Caratteri accentati sbagliati in PowerShell** (`Ã¼`): il registro è UTF-8 e
  PowerShell 5.1 lo legge come ANSI se non si specifica la codifica. Il file è corretto;
  si legge con `Get-Content -Encoding UTF8`.

## 9. Decisioni prese e alternative scartate

| Decisione | Alternativa scartata | Perché |
|---|---|---|
| Un tool per tema + copertura | Un solo tool con enum dei temi | Il tool unico richiede NLU nel server: credenziale a runtime, latenza, non-determinismo |
| Un tool per tema + copertura | Solo quattro tool tematici | Una domanda sui rifiuti bypasserebbe il server |
| Un tool per tema + copertura | Venti tool, uno per fonte | È ciò che fanno i server MCP svizzeri esistenti: superficie larga = tool selection instabile su 4 configurazioni |
| Classificazione al modello | Keyword lato server | Con un tool per tema la selezione **è** la classificazione; e il keyword fallirebbe sul romancio e sulle formulazioni oblique |
| Keyword solo in `check_swiss_question` | Nessun keyword | Rete di sicurezza che degrada bene: se non riconosce, il rifiuto resta valido, solo generico |
| Keyword di tema coperto ed escluso insieme: `answered` + `use_tool` + `also_mentions_not_covered` (2026-09-23) | Vince il coperto · vince l'escluso | Il coperto instradava "Prämie von den Steuern abziehen" al tool premi, che non controlla `question` (§1) e risponde `answered` con dati estranei; l'escluso rifiutava "depuis mon arrivée… échanger mon permis". Una lista di keyword non sa di cosa parla la domanda: il server dichiara i due fatti, decide il modello. Da misurare in un client |
| Nome attivo `check_swiss_question` | `swiss_coverage` | Il nome passivo si legge come "elenca capacità" e invita a non chiamarlo |
