# Fonti svizzere — analisi tecnica di accessibilità

> **Scopo**: cosa è realmente interrogabile in ~28 ore, con che sforzo, con che freschezza.
> Complementa [CHALLENGE.md](CHALLENGE.md), che copre i requisiti Swisscom.
>
> **Data verifica**: 2026-09-21 · **Metodo**: chiamate HTTP reali, non ricerca web
>
> **Legenda**: 🟢 verificato hands-on · 🟡 documentato ma non testato da noi · 🔴 verificato come bloccante

---

## 1. La legge fondamentale di questo dominio

**Dove esiste open data strutturato, non ci sono le domande campione.
Dove ci sono le domande campione, non esiste open data.**

Numeri verificati su `opendata.swiss` (16'040 dataset totali):

| Query | Dataset trovati | Comuni/cantoni in CH |
|---|---|---|
| `entsorgungskalender` | **9** | ~2'100 comuni |
| `abfall` | 122 | ~2'100 comuni |
| `schulferien` | **5** | 26 cantoni |

Swisscom ha scelto come domande campione proprio raccolta rifiuti e vacanze scolastiche
comunali. **Non sono coperte dall'open data federale.** Vivono su siti comunali e cantonali
come HTML e PDF.

Questo è esattamente il punto della slide 3 del briefing:
> *"Invisible data: the answer sits in an API, a dataset table or a PDF annex that search
> does not surface."*

**Conseguenza di design**: una strategia "wrapper su opendata.swiss" fallisce le domande
campione. Una strategia che gestisce HTML/PDF comunali le prende. La seconda è più difficile
ma è quella che il set nascosto premia.

---

## 2. Tabella maestra: 16 topic area × accessibilità reale

Effort = stima nostra per una copertura credibile, non per la perfezione.

| # | Topic | Accesso | Formato | Auth | Freschezza | Effort |
|---|---|---|---|---|---|---|
| 1 | **Premi cassa malati** | 🟢 CSV ufficiale BAG | CSV/XLSX | no | agg. 2026-09-11 | **Basso** |
| 2 | Imposte cantonali | 🔴 26 sistemi diversi | HTML/PDF/calcolatori | no | annuale | Molto alto |
| 3 | **Diritto federale** | 🟢 SPARQL Fedlex | RDF/HTML | no | continua | **Medio** |
| 4 | **Raccolta rifiuti** | 🔴 frammentato | HTML/PDF/ICS | varia | settimanale | Alto per comune |
| 5 | Notifica domicilio | 🟡 solo siti comunali | HTML | no | rara | Medio per comune |
| 6 | Permessi soggiorno | 🟡 sem.admin.ch | HTML/PDF | no | rara | Medio |
| 7 | AHV/IV pensioni | 🟡 ahv-iv.ch memento | HTML/PDF | no | annuale | Medio |
| 8 | Lavoro/disoccupazione | 🟡 arbeit.swiss | HTML | no | rara | Medio |
| 9 | **Vacanze scolastiche** | 🔴 26 cantoni, PDF | PDF/ICS parziale | no | annuale | Alto |
| 10 | **Trasporto pubblico** | 🟡 OJP 2.0 / GTFS-RT | XML/protobuf | **API key** | realtime | Medio |
| 11 | Patenti/veicoli | 🟡 26 uffici cantonali | HTML | no | rara | Alto |
| 12 | **Tasso riferimento** | 🟡 pagina BWO | HTML | no | trimestrale | **Bassissimo** |
| 13 | **Votazioni** | 🟡 VoteInfo JSON | JSON | no | per votazione | Basso |
| 14 | **Registro imprese** | 🔴 Zefix = HTTP 401 | JSON | **account** | continua | Basso + credenziale |
| 15 | Dogane | 🟡 bazg/Tares | HTML | no | rara | Medio |
| 16 | **Statistica** | 🟡 PxWeb BFS | JSON/PX | no | varia | Basso |
| — | **Geo/comuni** | 🟢 geo.admin.ch | JSON | no | continua | **Bassissimo** |
| — | **Catalogo open data** | 🟢 CKAN | JSON | no | continua | **Bassissimo** |

---

## 3. Fonti verificate hands-on

### 3.1 🟢 swisstopo SearchServer — il risolutore di giurisdizione

**Questa è la fondazione.** Risolve nome comune → numero BFS + cantone, senza auth.

```sh
curl "https://api3.geo.admin.ch/rest/services/api/SearchServer?searchText=Scuol&type=locations&origins=gg25&limit=3"
```

Risposta verificata:
- `Scuol (GR)` → `featureId: 3762`, lat/lon, bounding box
- `Lugano (TI)` → `featureId: 5192`

`featureId` = **numero UFS del comune**. `origins=gg25` limita ai confini comunali ufficiali.
Supporta anche NPA, indirizzi, distretti, particelle.

**Perché conta**: il 90% delle domande locali richiede prima di stabilire *quale* comune e
*quale* cantone. Senza questo passo, ogni risposta municipale è una scommessa. Con questo,
diventa un lookup deterministico — e permette di distinguere "comune ambiguo →
chiedi" da "comune risolto → procedi", che è la regola ask-back di §5.4 di CHALLENGE.md.

### 3.1b 🔴 swisstopo fuzzy risolve il comune sbagliato; il risolutore è offline

Verificato il 2026-09-23. `SearchServer?searchText=Wengen&origins=gg25` risponde
**`Wengi (BE)`** con `"fuzzy":"true"`. Wengen non è un comune: è una località di
**Lauterbrunnen**. La ricerca fuzzy restituisce in silenzio un comune reale e sbagliato,
e con `origins=zipcode` Wengen non dà risultati. Da qui la decisione (utente,
2026-09-23): **risolutore solo offline**, costruito in build-time da
`scripts/build_places.py` in `data/places.json`, senza fuzzy.

Fonti, tutte senza credenziali:
- **registro BFS** al 01.01.2026 (`agvchapp.bfs.admin.ch/api/communes/levels` e `/snapshot`):
  2110 comuni, cantone, regione linguistica;
- **mutazioni BFS** dal 2000 (`/mutations`): i nomi storici. Plagne → Sauge si ottiene
  seguendo la catena dei codici storici, perché le mutazioni includono anche i semplici
  cambi di distretto (stesso nome, codice storico nuovo);
- **elenco ufficiale delle località** swisstopo (`ortschaftenverzeichnis_plz`, 5718
  righe): località e NPA → comune, **con la quota di indirizzi**. Wengen → Lauterbrunnen
  100 %; Engelberg → 93 % Engelberg, il resto NW e UR;
- **SR 832.106 Anhang 1**: regione di premio per comune.

Tre trappole trovate costruendolo:
- **La tabella Fedlex va letta come tabella.** Un parser a righe di testo perdeva 43
  comuni, i nomi lunghi con `<br>` ("Neuhausen am Rheinfall"). Il primo "Anhang 1" del
  documento sta nel testo dell'art. 1, non nell'intestazione dell'allegato.
- **Ordinanza e registro divergono dove l'art. 3 lo prevede.** Fétigny-Ménières (nata il
  01.01.2026) non ha regione nell'Anhang; i suoi ex comuni sì, entrambi regione 2.
  Gurmels ha assorbito il 2278, stessa regione. Il build applica l'art. 3 e lo annota;
  se gli ex comuni avessero regioni diverse, la regione dipenderebbe dall'indirizzo.
- **Il controllo di coerenza del build ha bloccato due volte la scrittura dei dati**, ed
  entrambe le volte per un difetto reale (il parser, poi l'art. 3). Non va rimosso.

Non si risolvono, e lo si dichiara: i quartieri che non sono località ufficiali
(Oerlikon), i nomi di città in un'altra lingua (Genf come città; come cantone sì).
Fuori Svizzera (Konstanz): `not_found`, che è ciò che serve per dire "non è in
Svizzera". Self-check in `test/place-test.ts`.

### 3.2 🟢 Premi cassa malati BAG — la vittoria facile

La domanda campione #3 (Lugano, 30 anni, franchigia 2500) è **completamente risolvibile da
un CSV ufficiale**.

Dataset: `health-insurance-premiums` su opendata.swiss, publisher **Bundesamt für
Gesundheit BAG**, base legale citata (`fedlex.admin.ch/eli/cc/2015/840 art. 71`).
**Modificato 2026-09-11** — freschissimo.

File verificati dietro `opendata.bagnet.ch`:
```
/Praemien/Prämien_CH.csv          ← i premi
/Praemien/Einzugsgebiete.csv      ← aree operative assicuratori (NON le regioni di premio)
/Praemien/Tarife.csv              ← catalogo modelli assicurativi
/Praemien/Archiv_Praemien_2026.zip
/Praemien/Erläuterungen zu den Prämiendaten.xlsx
```

Header reale di `Prämien_CH.csv` (verificato):
```
Versicherer, Kanton, Hoheitsgebiet, Geschäftsjahr, Erhebungsjahr, Region,
Altersklasse, Unfalleinschluss, Tarif, Tariftyp, Altersuntergruppe,
Franchisestufe, Franchise, Prämie, isBaseP, isBaseF, Tarifbezeichnung
```

Tutte le dimensioni della domanda sono colonne: cantone, regione, classe d'età, franchigia,
premio.

> ⚠️ `Tarife.csv` **non** contiene i premi: è il catalogo dei prodotti. Il file giusto è
> `Prämien_CH.csv`.

#### 🔴 Correzione: quelli sopra sono path logici, non URL

Verificato il 2026-09-22 costruendo il manifest di copertura.
`https://opendata.bagnet.ch/Praemien/Archiv_Praemien_2026.zip` restituisce **404**, e così
ogni altra variante di caso. I file non sono serviti per path: stanno dietro un endpoint
di download che prende il path **in base64**.

```
https://opendata.bagnet.ch/?r=/download&path=<base64 del path>
L1ByYWVtaWVuL0FyY2hpdl9QcmFlbWllbl8yMDI2LnppcA%3D%3D  =  /Praemien/Archiv_Praemien_2026.zip
L1ByYWVtaWVuL1Byw6RtaWVuX0NILmNzdg%3D%3D              =  /Praemien/Prämien_CH.csv
```

Gli URL veri si ricavano dal CKAN di opendata.swiss, che li elenca tutti:

```sh
curl -sH 'User-Agent: <UA descrittivo>' \
  'https://opendata.swiss/api/3/action/package_show?id=health-insurance-premiums' \
  | grep -o 'https[^"]*bagnet[^"]*'
```

Verificato sull'archivio 2026: **31'923'906 byte**, `Content-Type: application/zip`,
magic `PK\x03\x04`.

> **Il path che un dataset documenta non è l'indirizzo da cui si scarica.** Un elenco di
> file in una scheda dataset descrive la struttura interna del deposito, non l'API di
> accesso. Vale come regola generale per i cataloghi open data svizzeri.

### 3.2b ⚠️ I file "live" sono stub vuoti — i dati stanno nello ZIP

**Correzione a quanto sopra.** Scaricando integralmente i file pubblicati:

| File pubblicato | Dimensione reale |
|---|---|
| `Prämien_CH.csv` | **201 byte — solo intestazione** |
| `Einzugsgebiete.csv` | **116 byte — solo intestazione** |
| `Prämien_CH.xlsx` | 9'426 byte — stub |
| **`Archiv_Praemien_2026.zip`** | **31'923'906 byte ← i dati veri** |

Contenuto dello ZIP (15 file, 58 MB non compressi):

```
Prämien_CH.csv                     22'545'492   ← 217'473 righe di premi
Einzugsgebiete.csv                    209'347
Tarife.csv                             20'552
Erläuterungen zu den Prämiendaten.xlsx 21'629   ← documentazione dei campi
```

**Chi si limita agli URL pubblicati su opendata.swiss ottiene intestazioni senza dati.**
Il metadato CKAN dice "modificato 2026-09-11" ed è vero, ma si riferisce al record, non al
contenuto dei file.

> ⚠️ **Separatori incoerenti dentro lo stesso archivio**: `Prämien_CH.csv` usa la virgola,
> `Einzugsgebiete.csv` usa il punto e virgola. Entrambi hanno un BOM UTF-8.

### 3.2c `Einzugsgebiete.csv` non è ciò che sembra

Header reale: `Versicherer;Kanton;Hoheitsgebiet;Geschäftsjahr;Erhebungsjahr;Region;Tarif;
Tariftyp;HMO-ID;Eingeschränkt;Gemeinden-BFS`

Non mappa comune → regione di premio. Registra **in quali regioni e con quali tariffe
ciascun assicuratore opera**, e se l'offerta è ristretta a comuni specifici.

Nell'anno 2026: **0 righe con `Eingeschränkt=J`**, quindi la colonna `Gemeinden-BFS` è
vuota ovunque. Il meccanismo esiste ma non è usato quest'anno. Serve comunque per
verificare che l'assicuratore più economico operi davvero nella regione richiesta.

### 3.2d La mappatura comune → regione di premio è un'ordinanza

Sta nel **Verordnung des EDI über die Prämienregionen, SR 832.106**, allegato 1.
Non è nell'archivio BAG.

Copia servita da BAG (26 pagine, 1.6 MB, PDF):
`bag.admin.ch/dam/en/sd-web/x8IbM-bv0Ptd/Verordnung des EDI über die Prämienregionen DE_mit Kopfzeile.pdf`

Formato: `<BFS> <Nome comune> <regione>`. Riga verificata: **`5192 Lugano 1`**.

> 🔴 **Trappola di versione, verificata.** Il PDF servito da BAG dichiara in testa:
> *"Dieser Text ist eine provisorische Fassung. Massgebend ist die definitive Fassung,
> welche unter www.fedlex.admin.ch veröffentlicht werden wird."*
> È l'**Änderung vom 28. August 2026**, che *"tritt am 1. Januar 2027 in Kraft"*.
>
> Quindi: documento giusto, autorità giusta, **anno di riferimento sbagliato** se lo si
> usa con i premi 2026. E il documento stesso dichiara che l'autorevole è Fedlex, non
> questa copia. Le regioni di premio **cambiano**: esiste un'ordinanza di modifica.

### 3.2d-bis 🟢 Fedlex è indirizzabile per data — risolve il problema delle versioni

SR 832.106 ha ELI `cc/2022/184`. Il **filestore** di Fedlex serve il testo consolidato
**in vigore a una data qualsiasi**, come HTML statico, senza SPA e senza auth:

```
https://www.fedlex.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/2022/184/<YYYYMMDD>/de/html/fedlex-data-admin-ch-eli-cc-2022-184-<YYYYMMDD>-de-html.html
```

Verificato su tre date:

| Versione in vigore il | Byte | Lugano |
|---|---|---|
| 01.01.2023 | 123'898 | **regione 1** |
| 01.01.2025 | 268'353 | **regione 1** |
| 01.01.2026 | 480'590 | **regione 1** |

**Questo è il pezzo più importante trovato finora sul piano operativo.** Vale per
qualsiasi atto del diritto federale, non solo per questa ordinanza: trasforma "quale
versione era in vigore nell'anno di riferimento" da problema difficile a **parametro
nell'URL**. È la risposta strutturale al criterio freschezza per tutto il livello
federale, e rende superflua la copia provvisoria servita da BAG.

> ⚠️ La pagina `fedlex.admin.ch/eli/...` normale è una SPA: il `<title>` è sempre
> "Fedlex" e il contenuto non si estrae con una GET. **Usare il filestore, non la SPA.**

Conferma sostanziale: Lugano è in regione di premio 1 in tutte le versioni verificate,
quindi la risposta di §3.2e non cambia. Ma la verifica va fatta, non assunta.

#### 🔴 Correzione: la data deve essere una data di consolidamento reale

Verificato su un secondo atto, **VMWG SR 221.213.11**, ELI `cc/1990/835_835_835`:

| Data richiesta | Risposta | Contenuto |
|---|---|---|
| `20251001` | HTTP 200, **45'554 byte** | testo consolidato reale, art. 12a leggibile |
| `20260101` | HTTP 200, **77'151 byte** | **shell della SPA**, con `no-script-warning` |

**Una data che non corrisponde a un consolidamento effettivo restituisce HTTP 200 con lo
scheletro JavaScript, non un errore.** Fallimento silenzioso: lo status dice OK, la
pipeline estrae zero e riporta "dato non trovato" invece di "versione inesistente".

Due difese:
1. **77'151 byte è la firma dello shell** (identica su VZV 741.51 e su questo tentativo).
   Rilevare il marcatore `no-script-warning` prima di fidarsi della risposta.
   Riconfermata il 2026-09-22 su un terzo atto, **VZV SR 741.51** (`cc/1976/2423_2423_2423`):
   `20260101` restituisce il consolidato reale, `20250101` e `20240101` restituiscono
   **77'151 byte esatti**. Anche `SR 832.106` a `20260101` è reale. Le date valide
   **differiscono da atto ad atto**: non esiste una data che funzioni per tutti.
2. Le date di consolidamento valide si ottengono dall'endpoint **SPARQL** di Fedlex; il
   filestore non le elenca.

Il filestore resta lo strumento giusto, ma **non è interrogabile con una data
arbitraria**: va prima risolta la versione, poi scaricata.

### 3.2e Domanda campione #3, risolta end-to-end

*"Qual è il premio mensile più basso dell'assicurazione di base per un adulto di 30 anni
domiciliato a Lugano con franchigia di 2500 franchi?"*

Catena: Lugano → BFS 5192 → regione di premio TI 1 → filtro su `Prämien_CH.csv`
(`Kanton=TI`, `Region=PR-REG CH1`, `Altersklasse=AKL-ERW`, `Franchise=FRA-2500`).

Risultato per l'anno **2026**:

| Interpretazione | Senza infortuni | Con infortuni |
|---|---|---|
| Qualsiasi modello (il più economico è `TAR-DIV`, AGRIsmart, assicuratore 1560) | **CHF 449.90** | CHF 473.60 |
| Solo modello standard (`TAR-BASE`, "Grundversicherung") | CHF 523.20 | CHF 550.70 |

Verificato che l'assicuratore 1560 opera in TI regione 1 con `Eingeschränkt=N`, quindi
l'offerta è disponibile a Lugano.

**Tre ambiguità che la domanda non risolve** e che cambiano la risposta:

1. **Copertura infortuni**: differenza di CHF 23.70/mese. Chi è dipendente è già coperto
   dal datore di lavoro e sceglie `OHN-UNF`.
2. **"Assicurazione di base"**: se significa l'obbligatoria (che include i modelli
   alternativi) → 449.90; se significa il modello standard → 523.20. **CHF 73/mese di
   differenza.** In italiano la prima lettura è quella corrente.
3. **Anno**: i dati disponibili al 2026-09-21 arrivano al 2026. L'archivio 2027 **non
   esiste ancora**. Il BAG pubblica i premi dell'anno successivo verso fine settembre —
   cioè **potenzialmente durante l'hackathon del 24–25 settembre 2026**.

La risposta corretta esplicita l'anno di riferimento e almeno l'assunzione sugli
infortuni. È il caso `rate_freshness` applicato a un altro tema.

### 3.2f 🟢 Tasso di riferimento ipotecario — verificato end-to-end

Secondo tema federale del nostro scope. Verificato il 2026-09-21.

**Fonte**: `referenzzinssatz.admin.ch` → redirect a `bwo.admin.ch/de/referenzzinssatz`.
Versioni DE/FR/IT. Nessun open data: `referenzzinssatz` su CKAN = **0 risultati**.

**Valore corrente**: **1,25 %**

**Base legale**, recuperata da Fedlex: **VMWG art. 12a**, *Verordnung vom 9. Mai 1990
über die Miete und Pacht von Wohn- und Geschäftsräumen*, **SR 221.213.11**,
ELI `cc/1990/835_835_835`. Testo:

> *"Für Mietzinsanpassungen aufgrund von Änderungen des Hypothekarzinssatzes gilt ein
> Referenzzinssatz. Dieser stützt sich auf den vierteljährlich erhobenen,
> volumengewichteten Durchschnittszinssatz für inländische Hypothekarforderungen und wird
> durch kaufmännische Rundung ermittelt."*

Norma complementare: *Verordnung des WBF vom 22. Januar 2008 über die Erhebung des für
die Mietzinse massgebenden hypothekarischen Durchschnittszinssatzes*. Per l'adeguamento
del canone: VMWG art. 13 cpv. 1 lett. c; CO art. 269d, 266c, 270b.

#### 🔴 Il tranello: quattro date per un numero

La tabella storica ha quattro colonne — tasso, *gültig ab*, tasso medio sottostante,
*Stichtag der Erhebung*. Le ultime righe:

| Tasso | Gültig ab | Durchschnittszinssatz | Stichtag |
|---|---|---|---|
| 1,25 % | **02.09.2026** | 1,31 % | 30.06.2026 |
| 1,25 % | 02.06.2026 | 1,31 % | 31.03.2026 |
| 1,25 % | 03.03.2026 | 1,32 % | 31.12.2025 |
| 1,25 % | 02.12.2025 | 1,33 % | 30.09.2025 |
| 1,25 % | **02.09.2025** | 1,37 % | 30.06.2025 |
| 1,5 % | 03.06.2025 | 1,44 % | 31.03.2025 |

L'ultima riga dice *"gültig ab 02.09.2026"*. Copiarla e rispondere **"1,25 % valido dal
2 settembre 2026"** è **sostanzialmente sbagliato**: quella è la data dell'ultima
pubblicazione trimestrale, che ha *confermato* il tasso. Il tasso è passato da 1,5 % a
1,25 % il **02.09.2025** ed è invariato da allora. È la data rilevante per un adeguamento
del canone.

La pagina lo dice correttamente: *"gültig seit 02.09.2025, unverändert ab 02.09.2026"*.
**Chi legge la tabella invece della frase sbaglia, pur citando la fonte giusta.**

Terza data: *"Veröffentlicht am 1. September 2026"*, la pubblicazione. Quarta: lo
*Stichtag* del rilevamento, 30.06.2026.

Nota metodologica da conservare per domande storiche: *"ab Dezember 2011 gemäss
kaufmännischer Rundung des Durchschnittszinssatzes"* — il metodo di arrotondamento è
cambiato nel dicembre 2011.

#### Freschezza

Serie completa dal 10.09.2008 (3,5 %) a oggi. Prossime pubblicazioni: **01.12.2026**,
poi 01.03/01.06/01.09/01.12.2027.

**Nessun rischio di freschezza durante l'hackathon**: la prossima variazione possibile è
a dicembre. Al contrario dei premi cassa malati, che potrebbero uscire durante l'evento.

#### ⚠️ La pagina è una SPA Nuxt

`curl` restituisce il payload JavaScript, non la tabella. Serve rendering.

Ma è **un solo numero che cambia al massimo 4 volte l'anno**: curarlo al build con URL,
valore, data di entrata in vigore e data di pubblicazione è del tutto adeguato e non
richiede un browser nel server.

### 3.3 🟢 opendata.swiss CKAN — il catalogo, non i dati

```sh
curl -A "<nostro-user-agent>" "https://ckan.opendata.swiss/api/3/action/package_search?q=<query>&rows=0"
```

16'040 dataset. Utile come **indice di discovery**, non come fonte di risposte:
la maggior parte dei record punta a file da scaricare, non a endpoint interrogabili.

🔴 **Trappola verificata**: senza `User-Agent` esplicito restituisce **HTTP 403** (nginx).
Con uno User-Agent descrittivo funziona. Vale come requisito di *source etiquette*:
identificarsi sempre.

### 3.4 🔴 Zefix — richiede credenziale

```sh
curl -X POST "https://www.zefix.admin.ch/ZefixPublicREST/api/v1/company/search" ...
→ HTTP 401
```

API REST pubblica ma con Basic auth su account gratuito. Swagger:
`https://www.zefix.admin.ch/ZefixPublicREST/swagger-ui/index.html`

**Trade-off**: copre il topic 14 con poco codice, ma introduce una credenziale da consegnare
a Swisscom via canale sicuro e penalizza l'operability (§10 CHALLENGE.md: *"a server that
runs without any external keys... shows in the operability assessment"*).

### 3.5 🟡 Fedlex — SPARQL, nessuna auth

- Endpoint: `https://fedlex.data.admin.ch/sparqlendpoint` (GET e POST)
- Modello dati JOLux, documentazione: `https://swiss.github.io/fedlex-jolux/`
- Riuso libero, anche commerciale

Copre il topic 3 con **citazioni ELI stabili** — esattamente il tipo di riferimento che il
practice case `citation_support` richiede. Costo: curva di apprendimento SPARQL/JOLux.

### 3.6 🟡 Altre confermate per documentazione

| Fonte | Endpoint | Note |
|---|---|---|
| BFS PxWeb | `https://www.pxweb.bfs.admin.ch/` | ~682 dataset, 21 temi, no auth, multilingue DE/FR/IT/EN |
| VoteInfo | via CKAN `echtzeitdaten-am-abstimmungstag-...` | JSON, storico su bfs.admin.ch, imminenti su S3 |
| OJP 2.0 / GTFS-RT | `api-manager.opentransportdata.swiss` | **richiede API key**, orario 2026 disponibile |
| Tasso riferimento | `referenzzinssatz.admin.ch` → `bwo.admin.ch/de/referenzzinssatz` | 🟢 redirect verificato. Solo HTML, nessuna API. Un singolo valore trimestrale |

---

## 4. Trappole verificate sul campo

### 4.1 🔴 Il dominio ovvio è quello sbagliato

```
scuol.ch   → HTTP 200 → redirect a engadin.com  (sito turistico)
scuol.net  → HTTP 200 → sito ufficiale del comune
```

Un'euristica "nome comune + .ch" porta a un sito turistico commerciale presentato come
autorevole. È letteralmente il fallimento descritto nel briefing. **Serve un registry
comune → dominio ufficiale verificato**, non una regola di costruzione URL.

### 4.2 🔴 La fonte autorevole è un PDF

Vacanze scolastiche di Scuol 2026, fonte ufficiale verificata:
```
https://www.gr.ch/DE/institutionen/verwaltung/ekud/avs/Volksschule/SB_Ferienplaene_2026_2027_de.pdf
→ HTTP 200, application/pdf, 77'418 byte
```

Il cantone GR pubblica il piano ferie come PDF per comune. Nessuna API, nessun ICS
cantonale. **Chi non sa leggere PDF non risponde a questa domanda campione.**

Nota: siti aggregatori come `schulferien.org`, `feiertagskalender.ch`, `localcities.ch`
hanno il dato ma **non sono autorevoli** — sono esattamente ciò che la checklist punto 3
esclude (*"not merely an official Swiss domain"* — questi non sono nemmeno quello).

### 4.3 🟡 ch.ch non serve un robots.txt reale

```
GET https://www.ch.ch/robots.txt → HTTP 200, content-type: text/html
```

Restituisce lo shell della SPA. Un parser robots.txt ingenuo lo interpreta come regole
valide o va in errore. Dato che il rispetto di robots.txt è un **requisito configurabile
obbligatorio** (§4 CHALLENGE.md), il parser deve gestire: assenza, HTML al posto di testo,
404, timeout.

### 4.4 🔴 Nessun User-Agent = 403

Verificato su `ckan.opendata.swiss`. Vale come regola generale: ogni richiesta uscente
deve avere uno UA identificabile con riferimento di contatto.

---

## 5. Panorama competitivo: MCP server svizzeri già esistenti

Rilevante su due fronti: **originalità** (criterio 4 della giuria) e **riuso**.

| Repo | Copertura |
|---|---|
| `malkreide/swiss-public-data-mcp` | portfolio, simap.ch procurement |
| `malkreide/swiss-statistics-mcp` | BFS STAT-TAB PxWeb, 682 dataset, no auth |
| `malkreide/amtsblatt-mcp` | SHAB + fogli ufficiali cantonali |
| `malkreide/zurich-opendata-mcp` | Open Data Zurigo, 20 tool |
| `JayTheSkier/fedlex-connector` | legislazione federale Fedlex |
| `vikramgorla/mcp-swiss` | trasporti, meteo, geodati, imprese, zero API key |
| `pipeworx-io/mcp-opendata-swiss` | catalogo CKAN opendata.swiss |

**Lettura**: sono in prevalenza **wrapper sottili su API già strutturate**. Nessuno, in base
alle descrizioni pubbliche, affronta il problema che Swisscom valuta davvero — risoluzione di
giurisdizione, estrazione del passaggio probante, data di efficacia, ask-back disciplinato,
onestà fuori scope. Le API facili sono già coperte da altri; il valore differenziante sta nel
livello di grounding, non nel numero di fonti.

Da verificare prima dell'evento: se le licenze permettono il riuso, prendere il layer di
trasporto da uno di questi invece di riscriverlo è coerente con il tempo disponibile.

---

## 6. Opzioni di scope — trade-off espliciti

Nessuna raccomandazione: la scelta di scope è una decisione di prodotto.
Riferimento: *"high quality with narrow coverage is preferred over a broad solution with
low quality"*.

### Opzione A — Verticale profondo su un cantone/città
*Es.: "tutti i temi comunali per la Città di Zurigo/Losanna"*
- **Pro**: open data municipale ricco (Zurigo ha Open ERZ API per i rifiuti, dataset
  vacanze scolastiche fino al 2029/30); qualità dimostrabile; freschezza controllabile
- **Contro**: breadth minima; molte domande del set nascosto cadranno fuori scope, quindi
  il punteggio dipende quasi interamente dalla qualità dell'onestà fuori scope
- **Rischio**: se il set nascosto è distribuito su tutta la CH, si risponde a pochissimo

### Opzione B — Orizzontale su temi federali strutturati
*Es.: "premi cassa malati, diritto federale, statistica, votazioni, per tutta la CH"*
- **Pro**: tutto il paese coperto; dati strutturati e freschi; effort basso per tema;
  citazioni forti (ELI Fedlex, CSV BAG con base legale)
- **Contro**: **manca tutto il livello comunale**, che è dove Swisscom ha messo 2 domande
  campione su 5; rischia di sembrare il wrapper che altri hanno già fatto
- **Rischio**: originalità bassa, e il caso `missing_location` non si esercita mai

### Opzione C — Ibrido: spina dorsale federale + profondità municipale selettiva
*Es.: "temi federali per tutta la CH + rifiuti/scuola/domicilio per N comuni dichiarati"*
- **Pro**: copre entrambe le famiglie di domande campione; esercita ask-back, risoluzione
  di giurisdizione e lettura PDF; breadth reale e qualità dimostrabile
- **Contro**: il più costoso; richiede sia pipeline strutturata sia estrazione da HTML/PDF
- **Rischio**: in 28h si rischia di fare male due cose invece che bene una

### Opzione D — Meta-layer di routing verso l'autorità competente
*Es.: "per qualsiasi domanda svizzera, identifica l'autorità responsabile e la pagina
esatta, con estrazione del passaggio dove possibile"*
- **Pro**: breadth massima dichiarabile; sfrutta ch.ch come mappa di competenza; originale
- **Contro**: rischia di restituire "vai qui" invece di una risposta; la giuria valuta
  *risposte corrette*, e un puntatore non è una risposta
- **Rischio**: il criterio 1 penalizza esattamente questo

**Dimensione trasversale a ogni opzione**: qualunque scope scegliamo, i quattro
comportamenti di §15 di CHALLENGE.md (risposta citata / ask-back preciso / fuori scope /
fonte irraggiungibile) vanno implementati. Sono il vero prodotto.

---

## 7. Dati di riferimento sulle giurisdizioni 🟢

Tutti i numeri di questa sezione vengono dal **registro ufficiale BFS dei comuni**
(standard eCH-0071), snapshot **01-01-2026**, scaricato e contato da noi.

### 7.1 Fonte e comandi riproducibili

```sh
# registro ufficiale, snapshot datato, CSV, nessuna auth
curl -A "<nostro-user-agent>" \
  "https://www.agvchapp.bfs.admin.ch/api/communes/levels?date=01-01-2026" -o comuni.csv
```

Colonne rilevanti: `BfsCode` (numero UFS), `Name`, `Canton`, `District`,
`SPRGEB2020` (regione linguistica: `1`=DE, `2`=FR, `3`=IT, `4`=RM).

```sh
awk -F',' 'NR>1 {c[$5]++} END {for (k in c) print k, c[k]}' comuni.csv   # per cantone
awk -F',' 'NR>1 {s[$20]++} END {for (k in s) print k, s[k]}' comuni.csv  # per lingua
```

> ⚠️ Il campo lingua è la **colonna 20**, non la 21 (la 21 è `AGKSA2020`, agglomerati).
> Verifica di sanità: Bern→1, Lausanne→2, Lugano→3, Scuol→4.

### 7.2 Totale: 2'110 comuni

Il numero cala nel tempo per fusioni comunali: qualsiasi conteggio trovato altrove va
datato. Fonti secondarie citano 2'202 (2020) e 2'172 (2021).

### 7.3 Comuni per cantone

Ordinati per costo di copertura completa. **Somma verificata = 2'110.**

| Cantone | Comuni | | Cantone | Comuni | | Cantone | Comuni |
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

**Cantoni completabili** entro un budget di ricerca realistico (≤26 comuni): BS, GL, AI,
OW, NW, ZG, UR, AR, NE, SH. I sei più piccoli insieme fanno **40 comuni**, ma sono tutti
germanofoni tranne NE.

### 7.4 Comuni per regione linguistica

| Regione | Comuni | Costo di una rivendicazione "area completa" |
|---|---|---|
| Tedesca | 1'374 | fuori portata |
| Francese | 606 | fuori portata |
| Italiana | 115 | al limite |
| **Romancia** | **15** | **alla portata** |

**Somma verificata = 2'110.**

### 7.5 I 15 comuni della regione linguistica romancia

Tutti nei Grigioni, concentrati in **3 cluster amministrativi**. Include Scuol, che
Swisscom ha messo tra le domande campione.

| BFS | Comune | Regione |
|---|---|---|
| 3981 | Breil/Brigels | Surselva |
| 3982 | Disentis/Mustér | Surselva |
| 3572 | Falera | Surselva |
| 3618 | Lumnezia | Surselva |
| 3983 | Medel (Lucmagn) | Surselva |
| 3581 | Sagogn | Surselva |
| 3582 | Schluein | Surselva |
| 3985 | Sumvitg | Surselva |
| 3987 | Trun | Surselva |
| 3986 | Tujetsch | Surselva |
| **3762** | **Scuol** | Engiadina Bassa / Val Müstair |
| 3847 | Val Müstair | Engiadina Bassa / Val Müstair |
| 3764 | Valsot | Engiadina Bassa / Val Müstair |
| 3746 | Zernez | Engiadina Bassa / Val Müstair |
| 3788 | S-chanf | Maloja |

Possibile aggregatore regionale da verificare: `regiunebvm.ch` (Regiun Engiadina Bassa
Val Müstair) potrebbe coprire 4 dei 15 con una fonte sola.

### 7.6 Competenza sui rifiuti: cantonale per legge, comunale nei fatti

**USG art. 31b** assegna ai cantoni la responsabilità dello smaltimento dei rifiuti urbani,
ma i cantoni **delegano ai comuni** raccolta e finanziamento. Base legale: USG (SR 814.01)
art. 30 ss., VVEA (SR 814.600).

Conseguenza operativa: **il calendario di raccolta è pubblicato dal comune o da un
consorzio intercomunale. Non esiste un calendario rifiuti cantonale da interrogare.**
Qualsiasi strategia "rifiuti a livello cantonale" è priva di fonte.

### 7.7 Nessun moltiplicatore per i rifiuti

Cercato un fornitore dominante da integrare una volta per coprirne molti: **non esiste**.
Il mercato è frammentato tra Trennio, Sammelkalender, A-Region e le soluzioni proprie
delle città grandi. Il costo per comune resta lineare.

### 7.8 ⚠️ La trappola Localcities

`Localcities` copre tutti i ~2'200 comuni con calendario rifiuti incluso, ed è di
**Swisscom Directories**. È la scorciatoia più comoda del dominio ed è **la risposta
sbagliata**: è un aggregatore, non l'ente responsabile della materia. La review checklist
punto 3 lo esclude esplicitamente.

Vale lo stesso per `schulferien.org`, `feiertagskalender.ch`, `localcities.ch` sulle
vacanze scolastiche: hanno il dato, non hanno l'autorità.

---

## 8. Campionamento cantonale: vacanze scolastiche 🟢

Cinque cantoni in tre lingue, verificati scaricando e leggendo le fonti il 2026-09-21.
**Risultato: cinque cantoni, cinque modelli diversi. Nessuna omogeneità.**

### 8.1 I cinque modelli

| Cantone | Modello | Granularità | Formato | Vacanze d'autunno 2026 |
|---|---|---|---|---|
| **VD** | tabella pluriennale unica 2022→2031 | uniforme sul cantone | PDF 1 pagina | **10–25 ottobre** |
| **TI** | elenco in prosa, un anno per documento | uniforme sul cantone | PDF 1 pagina | **31 ottobre – 8 novembre** |
| **GR** | tabella per comune, 164 righe | per comune | PDF 8 pagine, trilingue | Scuol **10–25 ottobre** |
| **BE** | regola DIN + date risolte + eccezioni | mista | 2 PDF | **19.09 – 11.10.2026** |
| **ZH** | delega ai comuni scolastici | comune scolastico | pagina HTML | **non determinabile** |

### 8.2 Fonti verificate

| Cantone | URL | Stato |
|---|---|---|
| VD | `vd.ch/fileadmin/user_upload/themes/formation/Vacances_scolaires/def_calendrier_vacances_scolaires_2023_2031.pdf` | 200, PDF, 124 KB |
| TI | `www4.ti.ch/fileadmin/DECS/calendario_scolastico/Calendario_scolastico_2026_2027.pdf` | 200, PDF, 178 KB |
| GR | `gr.ch/DE/institutionen/verwaltung/ekud/avs/Volksschule/SB_Ferienplaene_2026_2027_de.pdf` | 200, PDF, 77 KB |
| BE regola | `akvb-gemeinden.bkd.be.ch/.../schulferien-kanton-bern-d.pdf` | 200, PDF, 122 KB |
| BE eccezioni | `akvb-gemeinden.bkd.be.ch/.../schulferien-kanton-bern-bewilligte-ausnahmen-d.pdf` | 200, PDF, 116 KB |
| ZH | `zh.ch/de/bildung/bildungssystem/schulferien.html` | 200, HTML |

> Le pagine HTML di `ti.ch` hanno protezione anti-bot, ma **il PDF si scarica senza
> ostacoli**. Verificare sempre la risorsa finale, non la pagina che la ospita.

### 8.3 Prova che l'inferenza tra cantoni è letale

Stesso anno, stesso paese, stesso tema:

- Vaud: 10–25 ottobre (2 settimane)
- Ticino: 31 ottobre – 8 novembre (1 settimana, **3 settimane più tardi**)
- Berna: 19 settembre – 11 ottobre (3 settimane, **la più lunga e la più precoce**)

Il practice case `romansh_locality` vieta di dedurre da un altro cantone. Questi sono i
numeri che mostrano l'entità dell'errore.

### 8.4 Berna: la regola e le sue riserve

Il PDF contiene sia la regola sia le date risolte fino al 2031/32:

```
Herbstferien     Wochen 39 bis 41
Winterferien     Wochen 52 und 1
Februar-Ferien   Woche frei wählbar (DIN-Wochen 2 bis 14)
Frühlingsferien  Wochen 15 und 16
Sommerferien     Wochen 28 bis 32

2026/27  Herbstferien  Sa, 19.09.2026 - So, 11.10.2026
```

Riserve, tutte verificate nel documento:

- vale **solo per la parte germanofona**; la francofona segue BEJUNE, documento separato
- **le vacanze di febbraio le sceglie ogni comune** (DIN 2–14) → non cantonale
- i comuni turistici alpini scelgono le vacanze di primavera (DIN 15–21)
- **Biel + Evilard, Orvin, Plagne, Romont, Vauffelin alternano** sistema tedesco (anni
  pari) e francese (anni dispari)
- un secondo PDF elenca ~16 comuni con eccezioni: Boltigen, Gsteig b/Gstaad, Lauenen,
  Saanen, St. Stephan, Zweisimmen, Lenk, Adelboden, Erlenbach, Därstetten, Diemtigen,
  Oberwil i/S, Golaten, Gurbrü, Münchenwiler, Wil…

**Nello stesso cantone, per lo stesso tema, la granularità cambia secondo il tipo di
vacanza**: Herbstferien è cantonale, Februar-Ferien è comunale.

### 8.4b Berna ha DUE calendari, per regione linguistica

Fonte francofona verificata (2 pagine, 5'216 caratteri, 200):
`akvb-gemeinden.bkd.be.ch/.../fr/.../schulferien-kanton-bern-f.pdf`

Base legale identica, nome diverso: **LEO art. 8 al. 3, RSB 432.210** (in tedesco:
VSG, BSG 432.210). Le vacanze sono *"harmonisées par région linguistique"*.

| | Parte germanofona | Parte francofona |
|---|---|---|
| Comuni (registro BFS) | **299** | **35**, tutti nell'Arrondissement Jura bernois |
| Riferimento | calendario perpetuo DIN | **spazio BEJUNE** |
| **Autunno 2026** | **19.09 – 11.10** (3 sett., sem. 39–41) | **05.10 – 16.10** (2 sett., sem. 41–42) |
| Inverno 2026/27 | 24.12.2026 – 10.01.2027 | 25.12.2026 – 08.01.2027 |
| Primavera 2027 | 10.04 – 25.04 | 26.03 – 09.04 |
| Settimana bianca | libera (DIN 2–14) | libera |

**Stesso cantone, stesso tema, stesso anno: due risposte diverse, sfasate di due
settimane e di lunghezza diversa.** La chiave di risoluzione per le vacanze scolastiche
non è il cantone, e nemmeno il comune: è **(cantone × regione linguistica × parità
dell'anno scolastico × lista eccezioni)**.

### 8.4c Biel/Bienne: bilingue, ma classificata germanofona

La regola di alternanza riguarda Biel e cinque comuni vicini. Confronto con il registro
BFS:

| Comune citato | BFS | Regione linguistica BFS |
|---|---|---|
| Biel/Bienne | 371 | **1 = tedesca** (benché ufficialmente bilingue) |
| Evilard | 372 | 1 = tedesca |
| Orvin | 438 | 2 = francese |
| Romont (BE) | 442 | 2 = francese |
| Plagne | — | **non esiste più** |
| Vauffelin | — | **non esiste più** |

Per l'anno 2026/27 (inizio in anno pari) questi comuni seguono il **piano germanofono**:
Biel, autunno 2026 = 19.09 – 11.10.2026.

Attenzione: la classificazione linguistica BFS di Biel è "tedesca", quindi un routing
basato solo su quel campo darebbe la risposta giusta per caso, e quella sbagliata negli
anni dispari. **La regola di alternanza va letta, non dedotta.**

### 8.4d ⚠️ Il documento cantonale cita comuni che non esistono più

`Plagne` e `Vauffelin` **non sono nel registro BFS al 01-01-2026**: sono confluiti in
**Sauge** (BFS 449). Il documento bernese è datato 1° giugno / 1° luglio 2026 e li elenca
ancora.

Una fonte autorevole e corrente può contenere **nomi di giurisdizione obsoleti**. Un
lookup per nome fallisce su "Plagne", e chi chiede di "Sauge" non si trova nel documento.

Difesa: il **Gemeindeverzeichnis storico** del BFS mappa i comuni sciolti ai successori.
Endpoint già individuato in §7.1:
`agvchapp.bfs.admin.ch/api/communes/mutations?...`
Il risolutore di giurisdizione deve gestire entrambe le direzioni — nome storico → comune
attuale, e comune attuale → nomi storici citati nei documenti.

### 8.4e BEJUNE: un calendario per tre cantoni (da confermare)

La parte francofona di BE dichiara di allinearsi allo spazio **BEJUNE** = Berna, Giura,
Neuchâtel. Riscontro preliminare per l'autunno 2026:

- BE francofono: 05.10 – 16.10.2026 ✅ *verificato sul PDF cantonale*
- Neuchâtel: 5–16 ottobre 2026 ⚠️ *solo da aggregatori*
- Jura: 5–16 ottobre 2026 ⚠️ *solo da aggregatori*

Se confermato su fonti autorevoli, **un solo calendario copre la parte francofona di BE
più tutto NE e tutto JU**, cioè 35 + 24 + 51 = 110 comuni con una fonte sola.

> **Non usare questo allineamento finché non è verificato su `ne.ch` e `jura.ch`.**
> Le fonti trovate finora (`vacances-scolaires.ch`, `profcalendar.org`,
> `feiertagskalender.ch`) sono aggregatori, esclusi dalla checklist punto 3. Per il Giura
> la fonte autorevole è un arrêté del Governo cantonale.

### 8.5 Zurigo: delega totale

Testuale dalla pagina cantonale:

> *"Im Kanton Zürich bestimmen die Volksschulen ihre Ferien und schulfreien Tage selbst.
> Nur der Schulbeginn und die Weihnachtsferien sind verbindlich."*

Nel cantone più popoloso della Svizzera, a livello cantonale sono vincolanti **solo
l'inizio dell'anno scolastico e le vacanze di Natale**. Tutto il resto lo decidono i 160
comuni scolastici. L'«ewiger Ferienkalender» esiste ma è dichiarato *Planungshilfe*,
non norma. Base legale: BiG §7, VSV §32 cpv. 2 (LS 412.101).

**La risposta corretta con scope cantonale non è "non lo so", è l'ask-back citato**:
"nel canton Zurigo le vacanze le decide il singolo comune scolastico, quale?", con
riferimento alla pagina che lo afferma. Secondo il rubric è una risposta corretta.

### 8.6 Trappole nel PDF grigionese

Il caso più ricco di insidie del campione. Tutte verificate.

1. **I codici non sono numeri BFS.** Scuol nel PDF è `330`, il BFS reale è `3762`.
   Verificato su 7 comuni (Arosa 107/3921, Bonaduz 115/3721, Zernez 335/3746,
   Valsot 328/3764…). **Il join va fatto per nome, non per ID.**
2. **Righe duplicate**: 164 righe per 100 comuni, perché il PDF contiene sia la tabella
   cantonale sia tabelle per distretto. Serve dedup.
3. **Scuole private con date diverse**: `Privat Scoula Rudolf Steiner Scuol` ha le
   vacanze sportive 27.02–07.03, la scuola pubblica di Scuol 06.03–14.03. "La scola da
   Scuol" è ambiguo, e la riga sbagliata dà una data errata **con la fonte giusta**.
4. **Estrazione rumorosa**: `05.01.2 7`, `16. 08.27` — spazi spuri dentro le date.
   Normalizzare prima di interpretare.
5. **Le intestazioni sono trilingui, romancio incluso**: `vacanzas d'atun`,
   `vacanzas da Nadal`, `vacanzas da sport`, `vacanzas da primavaira`. La formula esatta
   della domanda campione #4 è **nel testo della fonte**. Per questo tema il problema
   del retrieval romancio non esiste e Supertext non serve.

### 8.7 Conseguenza architetturale: il campo "livello di risoluzione"

Non si può sapere a priori se una domanda richiede il comune: dipende dal cantone **e**
dal tipo di vacanza. Il manifest deve quindi registrare, per ogni coppia
(cantone × tipo di vacanza), a che livello la risposta è determinata:

| Valore | Comportamento | Esempi verificati |
|---|---|---|
| `cantonale_uniforme` | rispondi | VD, TI |
| `per_comune_in_fonte_cantonale` | risolvi il comune nella tabella, poi rispondi | GR |
| `regola_con_eccezioni` | rispondi, ma verifica la lista eccezioni | BE, Herbstferien |
| `delegato` | **chiedi il comune**, citando la norma che delega | ZH; BE, Februar-Ferien |

L'ask-back diventa la lettura di un campo, decisa dal server: identica su tutte e quattro
le configurazioni client×LLM. È il principio "server grasso, modello magro" applicato al
caso che vale più punti.

### 8.8 Dettagli semantici da citare insieme alla data

- Berna: *"Die Daten enthalten den ersten und letzten vollen Ferientag"*
- Ticino: *"(dal – al compresi)"*

Definizioni diverse di inizio e fine. Cambiano la risposta di un giorno.

### 8.9 Stima di ricerca rivista

Tempi reali di questo campionamento: VD ~5 min, TI ~5 min, GR ~20 min, BE ~25 min,
ZH ~15 min. **Media ~14 min** contro i 12 stimati: per 26 cantoni fa **~6 ore**, quindi
l'ordine di grandezza regge.

Ma la varianza è alta e **i casi difficili sono i cantoni grandi**. La stima regge solo
accettando l'ask-back per i cantoni che delegano. Se si volesse *rispondere* anche per
ZH, servirebbero 160 comuni — fuori scope per decisione presa.

---

## 8bis. Campione esteso: 10 cantoni e la tassonomia dei modelli 🟢

Verificato il 2026-09-21. Dopo dieci cantoni, **nessun cluster riduce il lavoro: ogni
cantone va aperto singolarmente.**

### 8bis.1 BEJUNE: confermato su fonti autorevoli, ma solo in parte

| Cantone | Fonte autorevole | Vacanze d'autunno 2026 |
|---|---|---|
| BE francofono | PDF cantonale (§8.4b) | **05.10 – 16.10** |
| Neuchâtel | `ne.ch/themes/scolarite-et-formation/calendrier-et-vacances-scolaires` (`dateModified` 17.08.2026) | **5 – 16 ottobre** |
| Jura | `jura.ch/fr/Autorites/Administration/DFNS/SEN/Vacances-scolaires/` | **5 – 16 ottobre** |

L'autunno coincide. **L'inverno no:**

| Cantone | Vacanze d'inverno 2026/27 |
|---|---|
| Neuchâtel | 21.12.2026 – 01.01.2027 |
| Jura | 24.12.2026 – 08.01.2027 |
| BE francofono | 25.12.2026 – 08.01.2027 |

**Tre cantoni, tre date diverse.** In più Neuchâtel ha le *"Vacances du 1er mars"*, una
ricorrenza cantonale che gli altri due non hanno.

> 🔴 **BEJUNE armonizza solo alcune vacanze.** Trattarlo come "una fonte per 110 comuni"
> produce date invernali sbagliate per due cantoni su tre. L'allineamento va registrato
> **per tipo di vacanza**, non per cantone.

### 8bis.2 Due trappole di accesso sulle fonti romande

| Risorsa | Esito | Insidia |
|---|---|---|
| `jura.ch/.../220531_Arrete_Vacances_scolaires-2023---2028...pdf` | **HTTP 410**, corpo "Erreur 404" | Deep link da motore di ricerca, documento **sostituito** da un nuovo arrêté 2025–2028 del 13.03.2026, raggiungibile solo dalla pagina di atterraggio |
| `ne.ch/autorites/DFDS/SEEO/Documents/Plan_Vac_Scol.pdf` | **HTTP 200**, `Content-Type: text/html` | URL con estensione `.pdf` che serve una pagina web. Status OK, estensione PDF, contenuto HTML |

Il secondo è il peggiore: una pipeline ingenua passa HTML a un parser PDF e ottiene
zero risultati, poi riporta "dato non trovato" invece di "recupero fallito" — cioè
esattamente la confusione che il practice case `source_failure` vieta.

**Regola derivata: partire sempre dalla pagina di atterraggio dell'autorità, mai dal deep
link restituito da una ricerca.** I deep link marciscono, le pagine di atterraggio no.
E validare il `Content-Type` effettivo, non l'estensione.

### 8bis.3 Tassonomia dei modelli, su 10 cantoni

| Modello | Cantoni | Comportamento richiesto |
|---|---|---|
| **Uniforme cantonale** | VD, TI, NE, JU | rispondi |
| **Per comune in documento cantonale** | GR, LU | risolvi il comune nella tabella |
| **Per regione linguistica** | BE, VS | risolvi la regione linguistica, poi rispondi |
| **Cantonale con variazione comunale** | SG | rispondi con riserva, o chiedi |
| **Delegato ai comuni** | ZH, (AG da confermare) | **chiedi il comune**, citando la norma |

### 8bis.4 I cantoni bilingui pubblicano due calendari

Non è una stranezza bernese. Il **Vallese** pubblica due piani separati:

- `Plan de scolarite valais romand 2026-2027.pdf` (Vallese romando)
- `Schul- und Ferienplan 2026-2027.pdf` (Oberwallis)

Stessa struttura di Berna. La chiave (cantone × regione linguistica) di §8.4b è quindi un
**pattern**, non un caso isolato.

Nota: i Grigioni, trilingui, fanno il contrario — **un solo documento** con tutti i
comuni e le intestazioni in tre lingue (§8.6). Nemmeno il multilinguismo predice il
modello.

### 8bis.5 Altri riscontri del campione esteso

- **Luzern**: due documenti — uno cantonale pluriennale 2026/27→2031/32 e uno
  **per comune** (`ferienplan_gemeinden_sj26_27.pdf`, 6 pagine). I comuni divergono:
  Adligenswil e Aesch hanno l'autunno 26.09–18.10, Alberswil chiude l'11.10. Modello
  "5/3" (5 settimane d'estate, 3 d'autunno).
- **St. Gallen**: il Bildungsrat fissa il quadro, ma la Città di San Gallo pubblica il
  proprio piano **e un dataset open data con export ICS**
  (`daten.stadt.sg.ch/.../schulferien-feiertage-stadt-stgallen/exports/ical`). È l'unico
  caso di dato scolastico machine-readable incontrato finora.
- **Aargau**: nessun piano ferie individuabile su `ag.ch` tramite ricerca. Emergono solo
  le basi legali (Schulgesetz SAR 401.100, Volksschulverordnung SAR 421.315), il che
  suggerisce delega ai comuni come in ZH. **Da confermare con accesso diretto.**

### 8bis.6 Conseguenza sul costo

Dieci cantoni, cinque modelli, nessuna regola predittiva: né la lingua, né la dimensione,
né la regione geografica anticipano quale modello usi un cantone.

**Il costo di ~14 min per cantone non è comprimibile con scorciatoie.** I 16 cantoni
rimanenti vanno aperti uno per uno.

> ✅ **Fatti**: il censimento è stato completato su tutti e 26. Risultati in **§8ter**,
> che sostituisce questa stima parziale.

---

## 8ter. Copertura completa: tutti i 26 cantoni 🟢/🟡

Completato il 2026-09-21.

> **Confidenza.** Tutti i cantoni di questa sezione sono stati verificati **scaricando e
> leggendo il documento o l'API autorevole**, salvo FR e VS, per i quali il motivo del
> mancato dato è documentato in §8ter.8. Nessun dato proviene da riassunti di ricerca.

### 8ter.1 Tassonomia finale, 26 cantoni su 6 modelli

| Modello | Cantoni | n |
|---|---|---|
| **Uniforme cantonale** | VD, TI, NE, JU, GE, ZG, BS, BL, TG, SH, NW, GL | 12 |
| **Per comune, in documento cantonale** | GR, LU, SO, UR, SZ | 5 |
| **Per regione linguistica** | BE, VS | 2 |
| **Uniforme con eccezioni nominate** | FR, OW, AI | 3 |
| **Quadro cantonale + scelta comunale** | AG, AR, SG | 3 |
| **Delegato ai comuni** | ZH | 1 |

### 8ter.2 Vacanze d'autunno 2026, verificate sul documento

Ordinate per data d'inizio. Ogni riga proviene dal documento o dall'API dell'autorità.

| Cantone | Inizio – fine 2026 | Sett. | Fonte letta |
|---|---|---|---|
| **BE** germanofono | **19.09 – 11.10** | 3 | PDF cantonale |
| OW (salvo Engelberg) | 25.09 – 11.10 | 2 | PDF `ow.ch/_doc/454867` |
| **NW** | dal **26.09** | 2 | PDF `nw.ch/_doc/456520` |
| **BS** | **26.09 – 11.10** | 2 | API `data.bs.ch` |
| **BL** | **26.09 – 11.10** | 2 | API `data.bl.ch` |
| BL — Gymnasium Laufental-Thierstein | 26.09 – 18.10 | 3 | API, eccezione dichiarata |
| **SH** | **26.09 – 18.10** | 3 | pagina `schule.sh.ch` |
| AI — Bezirk Oberegg | 26.09 – 18.10 | 3 | PDF `ferienplan-ai_2026-2029` |
| UR — Seelisberg | 26.09 – 11.10 | 2 | PDF cantonale |
| **SO** | **28.09 – 16.10** | 3 | PDF cantonale, 8 pagine |
| **SZ** (la maggioranza) | **28.09 – 16.10** | 3 | PDF cantonale |
| SZ — Gersau, Küssnacht, Schwyz, Illgau | 28.09 – 09.10 | 2 | PDF cantonale |
| SG | 28.09 – 18.10 *(da regola KW 40–42)* | 3 | pagina `sg.ch` |
| **GL** | **03.10 – 18.10** | 2 | PDF `Ferienpläne_2026-2029` |
| **ZG** | **03.10 – 18.10** | 2 | PDF `Schulferien 202627-203031` |
| **UR** (quadro cantonale) | **03.10 – 18.10** | 2 | PDF `..._nach_Gemeinden` |
| AI — Innerer Landesteil | 03.10 – 18.10 | 2 | PDF cantonale |
| OW — Engelberg | 03.10 – 25.10 | 3 | PDF cantonale |
| **BE** francofono / **NE** / **JU** | **05.10 – 16.10** | 2 | PDF + pagine cantonali |
| **AR** | **05.10 – 16.10** | 2 | PDF `Ferienrichtdaten v1.3` |
| **TG** | **05.10 – 18.10** | 2 | PDF `Ferienplan_SJ_2026_2027` |
| **VD** | **10.10 – 25.10** | 2 | PDF pluriennale |
| **GR** — Scuol | **10.10 – 25.10** | 2 | PDF cantonale, 164 righe |
| **GE** | **19.10 – 23.10** | **1** | pagina `ge.ch` |
| **TI** | **31.10 – 08.11** | **1** | PDF cantonale |
| **ZH** | — | — | delegato ai comuni |
| **AG** | durata variabile per comune | 2 o 3 | pagina `schulen-aargau.ch` |
| **LU** | variabile per comune, modello 5/3 | 2 o 3 | PDF per comune, 6 pagine |
| FR, VS | non catturate — vedi §8ter.8 | | |

**Dal 19 settembre all'8 novembre: sette settimane di dispersione.** Durate da **una
settimana** (GE, TI) a **tre**. Ginevra e Vaud confinano e non si sovrappongono di un
solo giorno. Basilea Città e Basilea Campagna coincidono; Appenzello Interno si divide
in due al suo interno.

Qualsiasi inferenza geografica, linguistica o di vicinanza è sbagliata.

### 8ter.2b Correzioni emerse aprendo i documenti

Rispetto a quanto avevo dedotto dai riassunti di ricerca:

| Cantone | Dato di seconda mano | Dato verificato |
|---|---|---|
| **ZG** | "2–17 ottobre **2027**" | **03.10 – 18.10.2026** — era la colonna dell'anno successivo |
| **SG** | "3–24 ottobre **2027**" | regola **KW 40–42**, quadro cantonale |
| **AI** | date prese da `gymnasium.ai.ch` | il liceo è una **colonna diversa**: due zone, Innerer Landesteil e Oberegg |
| **SO** | "varia per comune" | **autunno uniforme**; variano Sport- e Frühlingsferien |
| **AG** | "l'autunno è cantonale" | varia la **durata** dell'autunno per comune (2 o 3 settimane) |
| **AR** | PDF v1.1 del 2025-04-01 | quel file dà **404**: la versione corrente è **v1.3 del 2026-06-23** |

Cinque affermazioni su sei erano sbagliate o imprecise. Il campionamento di seconda mano
serve a dimensionare il lavoro, **mai a rispondere**.

### 8ter.3 Eccezioni nominate: il singolo comune dentro un cantone uniforme

- **OW**: il piano vale per la *"Volksschule ohne Engelberg"*. Engelberg ha
  **03.10 – 25.10.2026** contro **25.09 – 11.10.2026** del resto del cantone.
- **FR**: **tre** varianti — calendario di maggioranza, più adattamenti per le regioni
  di **Morat/Murten** e **Kerzers**. Cantone bilingue, documenti in FR e DE.
- **AI**: date diverse tra la parte interna del cantone e Oberegg.

Un cantone "uniforme" può contenere un comune con date completamente diverse, dichiarato
nel titolo stesso del documento. Leggere il titolo, non solo la tabella.

### 8ter.4 Quadro cantonale + scelta comunale: tre varianti diverse

- **AG**: il Bildungsrat fissa 2 settimane ciascuna per primavera, autunno e Natale più
  3 d'estate; **le restanti 4 settimane le fissano i comuni**. L'autunno è quindi
  cantonale, il resto no.
- **AR**: il documento cantonale si chiama **`Ferienrichtdaten`** — dati *indicativi*, non
  vincolanti. I comuni fissano autonomamente **2 delle 13 settimane**.
- **SG**: il Bildungsrat fissa il quadro, i comuni variano. La Città di San Gallo pubblica
  il proprio piano.

### 8ter.5 🔴 Il portale scolastico non sta quasi mai sul dominio cantonale

Il motivo per cui la mia prima ricerca su `ag.ch` non trovò nulla:

| Cantone | Dominio del portale scolastico autorevole |
|---|---|
| AG | `schulen-aargau.ch` |
| SH | `schule.sh.ch` |
| TG | `av.tg.ch` |
| LU | `volksschulbildung.lu.ch` |
| ZH | `vsa.zh.ch` |
| BE | `akvb-gemeinden.bkd.be.ch` |
| GE | `ge.ch` + `edu.ge.ch` |
| AI | `ai.ch` + `gymnasium.ai.ch` |

**Un registro di fonti costruito sul pattern `<codice-cantone>.ch` fallisce.** Il dominio
va verificato a mano per ogni cantone, come per i comuni (§4.1).

⚠️ Aggiornamento 2026-09-22: `vsa.zh.ch` risponde ma **redirige** a
`www.zh.ch/de/bildungsdirektion/volksschulamt.html`. Il dominio corto resta valido come
punto di ingresso, ma la pagina da citare è quella di destinazione. `www.vsa.zh.ch`
con il prefisso `www.` dà invece **hostname mismatch sul certificato**: il sottodominio
va usato esattamente come pubblicato, senza aggiungere `www.`.

### 8ter.6 Cinque fonti machine-readable — e una con un avvertimento

| Cantone | Fonte | Formato |
|---|---|---|
| BS | `data.bs.ch/explore/assets/100397/` | open data + iCal |
| BL | `data.bl.ch/explore/assets/13350/` | open data + iCal, copre 2026/27–2031/32 |
| SZ | `data.sz.ch/explore/dataset/ferienplan-kanton-schwyz/` | open data |
| SG (città) | `daten.stadt.sg.ch/.../schulferien-feiertage-stadt-stgallen/exports/ical` | ICS |
| VD | import in agenda via QR | ICS presunto |

> 🔴 **Il dataset di Schwyz dichiara di non essere vincolante**: i dati sono forniti senza
> garanzia e *"i piani vincolanti sono quelli emanati dalle autorità scolastiche"*.
>
> Una fonte cantonale ufficiale, machine-readable e comoda, che **si auto-dichiara non
> autoritativa**. Va usata per il lookup, ma la citazione deve puntare al PDF vincolante.
> È il caso più sottile di tutta la raccolta: qui non sbagli fonte né versione — sbagli
> *status giuridico* della fonte.
>
> Analogamente **BL esclude esplicitamente** dal proprio calendario il Regionales
> Gymnasium Laufental-Thierstein, e **AR** pubblica "Richtdaten" indicativi.

### 8ter.6b ⚠️ Non esistono altre fonti open data: verificato, non supposto

Scansionati il 2026-09-22 i 26 portali open data cantonali candidati, con paginazione
completa del catalogo Opendatasoft dove esiste (non solo la prima pagina).

**Vivi: sei.** `data.bl.ch` (184 dataset), `data.bs.ch` (361), `data.sz.ch` (363),
`data.tg.ch` (456), `daten.sg.ch` (225), `data.gr.ch` (51). Gli altri venti hostname
non risolvono affatto, o non espongono quell API.

**Dataset di vacanze scolastiche trovati: tre, e sono i tre già noti** — BL 13350,
BS 100397, SZ `ferienplan-kanton-schwyz`. Turgovia, Grigioni e il portale cantonale di
San Gallo hanno dataset scolastici in quantità (allievi, sedi, statistiche) ma **nessun
calendario delle vacanze**. Anche `opendata.swiss` non ne indicizza: la ricerca
`vacances scolaires` dà 71 risultati e nessuno è un calendario.

> Per la patente una sola fonte ha coperto 26 cantoni (§9.7). **Per le vacanze quella
> scorciatoia non esiste**, ed è ora verificato invece che supposto: i cantoni restanti
> vanno aperti uno per uno, come §8ter.10 aveva stimato.

### 8ter.7 Basi legali cantonali individuate

Utili perché l'ask-back va citato, non asserito:

| Cantone | Norma |
|---|---|
| BE | LEO/VSG art. 8 cpv. 3 — RSB/BSG 432.210 |
| ZH | BiG §7; VSV §32 cpv. 2 — LS 412.101 |
| SH | SHR 410.114, *Verfügung über die Festlegung der Schulferien* |
| AG | ⚠️ **corretto 2026-09-22**: Volksschulgesetz (VSG) del 23.09.2025, **SAR 421.100 §§ 61 e 63**; Volksschulverordnung (V VSG) del 18.02.2026, SAR 421.315 § 48. La voce precedente diceva `SAR 401.100` e *Schulgesetz*: sbagliata. **Il VSG è entrato in vigore il 1° agosto 2026** e il piano ferie cantonale è stato riadattato quel giorno — §8quinquies |
| OW | Bildungsgesetz GDB 410.1 |

### 8ter.8 I due cantoni che restano aperti, e perché

**Friburgo — il documento che sembrava giusto era di un altro tipo di scuola.**
L'URL `fr.ch/sites/default/files/2024-02/calendrier-scolaire-2026--2027.pdf` ha un nome
perfetto ed è su dominio cantonale. Aprendolo si scopre che è il calendario delle
**scuole professionali**, emanato dal *Service de la formation professionnelle*:
*"Ecoles professionnelles – Berufsfachschulen"*, *"Accueil des personnes en formation de
1re année"*. Non è la scuola dell'obbligo.

La pagina corretta è `fr.ch/dfac/vacances-scolaires` e conferma le **varianti multiple**:
per il 2027 coesistono *"du Lu 18. octobre au Ven 29. octobre"* e *"du Lu 4. octobre au
Ven 22. octobre"* — due settimane di scarto e durate diverse, nello stesso cantone e
anno. Le date 2026 non sono state catturate.

> **Dominio giusto + nome file giusto + anno giusto ≠ documento giusto.** Il tipo di
> scuola è una dimensione di giurisdizione al pari del territorio.

**Vallese — le date non esistono come testo.**
Il `Plan de scolarité valais romand 2026/2027` è una **griglia mensile da colorare**
(*"Colorier en bleu les jours entiers de classe et en jaune les demi-jours"*): i giorni
di vacanza sono segnati graficamente con asterischi e grassetto. L'estrazione testo
restituisce la griglia dei numeri ma non quali giorni siano vacanza.

Serve analisi di layout o OCR, oppure una fonte diversa. È l'unico caso incontrato in cui
la fonte autorevole è **illeggibile a una pipeline testuale**.

### 8ter.9 Note operative dalla verifica

- **Marciume dei deep link, confermato tre volte**: i PDF di AR, OW e NW indicizzati dai
  motori danno **404**. In tutti e tre i casi il documento corrente si trova solo
  passando dalla pagina di atterraggio. Per AR il file indicizzato era la **versione
  v1.1 superata dalla v1.3**.
- **Sciaffusa chiede esplicitamente di non copiare il suo calendario**: *"Bitte bilden Sie
  auf Schulwebseiten keinen eigenen Ferienkalender ab, sondern verweisen auf diese
  Seite."* Un'autorità che chiede il link invece della copia — argomento in più contro
  gli aggregatori.
- **Le due Basilea hanno API pulite**: `data.bs.ch` e `data.bl.ch` rispondono in JSON via
  `/api/explore/v2.1/catalog/datasets/<id>/records`, con le eccezioni dichiarate come
  record separati (es. *"Herbstferien Gymnasium Laufental-Thierstein
  (Ausnahmeregelung)"*). È il formato migliore incontrato.
- **Regole a numero di settimana**: BE (DIN 39–41), SH (KW 40–42), SG (KW 40–42) e OW
  (*"sei settimane dopo l'inizio dell'anno, durata due settimane"*) pubblicano regole
  oltre alle date. Le regole vanno risolte in date, e la risoluzione va citata come
  derivata.

### 8ter.10 Costo consolidato

26 cantoni, 6 modelli, nessun predittore. Il tempo reale di questo censimento conferma
**~12–15 min per cantone** per identificare fonte e modello, **più** un tempo equivalente
per aprire e validare ogni documento (i 🟡 di questa sezione).

**Stima finale per il tema vacanze scolastiche: ~6 ore per l'identificazione, ~6 ore per
la validazione documentale. ~12 ore-persona in totale**, contro le ~6 stimate all'inizio.
Il raddoppio è dovuto a eccezioni nominate, varianti regionali e verifica dello status
giuridico delle fonti — tutte cose che a campione non si vedevano.

---

## 8quater. Campione sul secondo tipo di vacanza 🟢

Verificato il 2026-09-22 aprendo le fonti autorevoli, mai riassunti. Serve a decidere una
cosa sola: **le righe `subtopic = "*"` del manifest sono un'affermazione sostenibile, o
sovra-dichiarano?** Tutto §8ter è un censimento del **solo autunno**; ogni riga `*` estende
quel risultato agli altri quattro tipi senza averli guardati.

Campionate **tre classi di risoluzione su sei**, non cantoni a caso: è la classe che si
vuole falsificare. Tipo scelto: **sport/carnevale**, dove la divergenza è già nota (BE
febbraio comunale, SO sport e primavera variabili). Natale sarebbe stato il campione più
compiacente.

### 8quater.1 Esito: la classe regge, il dettaglio no

| Cantone | Classe | Esito su tutti i tipi |
|---|---|---|
| **BS** | uniforme | 🟢 **1 variante per tipo, 8 anni, zero eccezioni** |
| **BL** | uniforme | 🟢 1 variante per tipo, 6 anni — ma l'eccezione di tipo di scuola vale su **due** tipi |
| **NW** | uniforme | 🟢 1 variante per tipo, 6 anni, tipi di scuola persino accorpati |
| **SZ** | per comune nella fonte | 🟡 regge, ma il **numero di varianti cambia per tipo e per anno** |
| **OW** | uniforme con eccezioni | 🔴 l'eccezione nominata vale su **3 tipi su 5** |

**Nelle tre classi qui sopra la CLASSE non cambia fra tipi di vacanza.** Un cantone
uniforme in autunno è uniforme anche a Natale e a carnevale. Questo è il risultato che
autorizza la riga `*` per `resolution_level` e `on_missing_place` — **per quelle classi**.

Ma dentro la classe, **il dettaglio è per tipo**, e il censimento dell'autunno lo perde.

> ⚠️ **§8quinquies smentisce l'estensione a tutte le classi.** Nella classe *quadro
> cantonale + scelta comunale* (AG, AR, SG) la classe **cambia** fra tipi, in tutti e tre
> i cantoni. La previsione di §8quater.6 era giusta.

### 8quater.2 🔴 OW: l'eccezione nominata esiste per alcuni tipi e non per altri

Dal PDF `ow.ch/_doc/454867`, `Schulferienplan_2026-27`, due tabelle nello stesso foglio:

| Tipo | Volksschule (ohne Engelberg) | Engelberg | Divergono? |
|---|---|---|---|
| Herbstferien | 25.09 – 11.10.2026 | 03.10 – 25.10.2026 | **sì** |
| Weihnachtsferien | 24.12.2026 – 06.01.2027 | 24.12.2026 – 06.01.2027 | **no, identiche** |
| Fasnachtsferien | 30.01 – 14.02.2027 | 04.02 – 14.02.2027 | **sì** |
| Osterferien | 26.03 – 11.04.2027 | 26.03 – 11.04.2027 | **no, identiche** |
| Sommerferien | 03.07 – 15.08.2027 | 26.06 – 08.08.2027 | **sì** |

> **Un'eccezione nominata non è una proprietà del comune: è una proprietà della coppia
> (comune × tipo di vacanza).** Engelberg è un'eccezione in autunno, a carnevale e
> d'estate, e non lo è a Natale e a Pasqua.

Nel caso OW è innocuo, perché entrambe le tabelle stanno nello stesso PDF e citano la
stessa autorità: rispondere dalla riga Engelberg per Natale dà la data giusta e la fonte
giusta. **Diventa pericoloso quando l'eccezione ha una fonte propria**, perché allora si
cita un documento che per quel tipo non è competente.

Il rischio simmetrico è peggiore e questo campione non lo esclude: un comune che diverge
**solo** a carnevale, in un cantone uniforme in autunno, **non compare affatto** in un
censimento dell'autunno. Il server risponderebbe con sicurezza e sbagliato.

### 8quater.3 BL: l'eccezione era sotto-registrata

§8ter.6 registra l'esclusione del Regionales Gymnasium Laufental-Thierstein **solo per
l'autunno**, perché solo l'autunno era stato guardato. L'API `data.bl.ch` dataset `13350`
mostra che esiste anche per l'**estate**, e in tutti e sei gli anni scolastici pubblicati:

```
Herbstferien                                                    2026-09-26 -> 2026-10-11
Herbstferien Gymnasium Laufental-Thierstein (Ausnahmeregelung)  2026-09-26 -> 2026-10-18
Sommerferien                                                    2027-07-03 -> 2027-08-15
Sommerferien Gymnasium Laufental-Thierstein (Ausnahmeregelung)  2027-07-10 -> 2027-08-15
```

Natale, carnevale e primavera non hanno eccezione. Tre tipi su cinque puliti, due no.

### 8quater.4 SZ: il numero di varianti cambia per tipo E per anno

Dataset `ferienplan-kanton-schwyz`, filtrato alla sola scuola dell'obbligo (32 unità
scolastiche; il tipo di scuola è giurisdizione, CONTRACT §4.4):

| Tipo | varianti 2025/26 | varianti 2026/27 |
|---|---|---|
| Herbstferien | **1** | **2** |
| Weihnachtsferien | **3** | **6** |
| Sportferien | 2 | 2 |
| Frühlingsferien | 1 | 1 |
| Sommerferien | *assenti dal dataset* | *assenti dal dataset* |

Natale ha **sei** calendari diversi nello stesso cantone e nello stesso anno; la primavera
ne ha uno. E l'autunno passa da 1 variante a 2 **cambiando anno**.

> **Una validazione è valida per un anno scolastico, non per il cantone.** `validated_at`
> da solo non lo cattura: va letto insieme all'anno di riferimento del documento.

⚠️ Il dataset **non contiene le vacanze estive**. Una fonte machine-readable comoda può
essere incompleta su un tipo, e la lacuna non si vede se si interroga solo l'autunno.

### 8quater.5 🔴 I nomi dei tipi di vacanza non sono una tassonomia condivisa

Raccolti dalle fonti di questo campione:

| Slot | Nomi reali incontrati |
|---|---|
| sport / carnevale | `Sportferien` (SZ) · `Fasnachtsferien` (BL, OW, NW) · `Fasnachts- und Sportferien` (BS) |
| primavera | `Frühlingsferien` (SZ) · `Frühjahrsferien` (BS, BL) · **`Osterferien`** (OW) · `Ostern` (NW) |

`Osterferien` è ancorata alla Pasqua, non al mese: chiamarla "primavera" è una nostra
convenzione, non la loro. Un utente che scrive *"Wann sind die Osterferien?"* sta chiedendo
lo stesso slot di chi scrive *"Frühjahrsferien"*, e il parametro `holiday_type` deve
mapparli entrambi. Vale anche per il francese (`relâches`, `vacances de Pâques`) e
l'italiano (`vacanze di carnevale`).

### 8quater.6 Cosa NON copre questo campione

- **5 cantoni su 26**, e **3 classi su 6**. Mancano `per_regione_linguistica`,
  `quadro cantonale + scelta comunale` e `delegato`.
- La classe **quadro + scelta comunale** è quella dove ci si aspetta il crollo, ed è
  l'unica non testata: §8ter.4 dice che in **AG** il Bildungsrat fissa 2 settimane per
  primavera, autunno e Natale più 3 d'estate, e che **le restanti 4 settimane le fissano i
  comuni**. Se è esatto, in AG la classe *cambia* fra tipi. Il manifest tiene già AG su
  `ask` per tutto, che è la scelta conservativa e resta valida in entrambi i casi.
- **Un solo tipo alternativo guardato a fondo** (sport/carnevale), più quello che le fonti
  multi-tipo davano gratis. Estate e Natale sono coperti solo dove la fonte li elencava.

---

## 8quinquies. La classe che cambia per tipo: AG, AR, SG 🟢

Verificato il 2026-09-22 aprendo i documenti, raggiunti **partendo dalla pagina di
atterraggio** e non da URL indovinati (§8ter.9). §8quater.6 dichiarava questa classe non
testata e prevedeva che fosse quella dove la classe stessa poteva cambiare. **La
previsione era giusta, e vale per tutti e tre i cantoni.**

### 8quinquies.1 Le vacanze di sport non sono nel documento cantonale. In nessuno dei tre.

| Cantone | Tipi fissati dal cantone | Tipo lasciato ai comuni | Fonte letta |
|---|---|---|---|
| **AG** | autunno, Natale, primavera, estate | **Sportferien** — assenti dal PDF cantonale | PDF Erziehungsrat, 3 pagine |
| **AR** | autunno, Natale, primavera, estate (11 settimane) | **2 settimane su 13** | PDF `Ferienrichtdaten v1.3` |
| **SG** | autunno, Natale, primavera, estate | **Sport- bzw. Winterferien** | pagina `sg.ch` |

Le tre fonti lo dicono, ciascuna a modo suo:

> **AG** — *"Je zwei Wochen Frühlings-, Herbst- und Weihnachtsferien sowie drei Wochen
> Sommerferien werden einheitlich durch den Erziehungsrat festgelegt. Die restlichen vier
> Ferienwochen legen die Gemeinden selber fest."* · *"Regionale Unterschiede gibt es bei
> den Sportferien sowie der Dauer der Sommer- bzw. Herbstferien."*
>
> **SG** — *"Die Sport- bzw. Winterferien werden durch die Schulträger (Gemeinde)
> festgelegt und unterscheiden sich je nach Schulort."*
>
> **AR** — il PDF elenca solo autunno, Natale, primavera ed estate; le 2 settimane
> comunali non compaiono.

> **Il documento cantonale non è incompleto per sciatteria: è completo rispetto a ciò che
> il cantone decide.** Cercare le vacanze di sport lì dentro e non trovarle è il
> comportamento corretto della fonte, non un suo difetto. Un `no_match` su quella fonte
> non significa "il fatto non esiste" (CONTRACT §5.1).

### 8quinquies.2 AG: il cantone fissa l'inizio, il comune la durata

È la contraddizione aperta in §10, e si scioglie: **entrambe le letture erano vere.**

- Il cantone fissa **l'inizio** dell'autunno e un **minimo di due settimane**
  (2026/27: KW 40/41, 28.09 – 09.10.2026).
- Il comune può usare le sue quattro settimane libere per **estendere** autunno a 3
  settimane o estate a 5: *"Dies betrifft den Beginn der zweiwöchigen Sportferien und die
  Dauer der Sommerferien (4 oder 5 Wochen) bzw. Herbstferien (2 oder 3 Wochen)."*

Quindi per l'autunno in AG **la data d'inizio è rispondibile senza il comune, la data di
fine no**. Una risposta che dà solo l'inizio è corretta e incompleta; una che dà anche la
fine senza il comune è sbagliata nella metà dei casi.

Il PDF chiude con *"Wir bitten um Kenntnisnahme und Einhaltung dieser **verbindlichen**
Daten"*: vincolante, a differenza di AR.

### 8quinquies.3 🔴 SG: la data in §8ter.2 è sbagliata di un giorno

§8ter.2 riporta per SG **28.09 – 18.10.2026**, *derivata* dalla regola KW 40–42. La
pagina cantonale pubblica le date, e sono **domenica 27.09.26 – domenica 18.10.26**.

La regola dice KW 40–42; il cantone fa iniziare le vacanze la **domenica** che apre la
settimana 40, non il lunedì. Derivare una regola in date senza leggere la convenzione di
inizio e fine sposta la risposta di un giorno — è §8.8 applicato a un caso nuovo.

**Regola operativa**: quando la fonte pubblica sia la regola sia le date, si citano le
**date**, e la regola serve solo a spiegarle.

### 8quinquies.4 AR resta indicativo, e ora si sa quanto

Il documento si chiama `Ferienrichtdaten` e non è vincolante (§8ter.4). Ma elenca
**11 delle 13 settimane** con date precise su quattro anni scolastici. Le 2 settimane
comunali sono l'unica parte davvero aperta.

Autunno 2026/27: **Lu 05.10 – Ve 16.10.2026**, coerente con §8ter.2. Nota che AR usa
lunedì–venerdì come primo e ultimo giorno di vacanza, mentre SG usa domenica–domenica e
BE *"den ersten und letzten vollen Ferientag"*: **tre convenzioni diverse in tre cantoni**.

### 8quinquies.5 Conseguenza sul manifest, e un errore che costa punti

Le righe `subtopic = "*"` per questi tre cantoni erano tutte sbagliate, in due direzioni
opposte:

| Cantone | Prima | Dopo | Perché |
|---|---|---|---|
| **AG** | `ask` su tutto | `ask` su `*`, **`answer` su Natale e primavera** | Natale e primavera sono interamente cantonali: chiedere il comune è penalizzato |
| **AR** | `answer` su tutto | `answer` su `*`, **`ask` su sport** | le vacanze di sport non sono nella fonte cantonale |
| **SG** | `ask` su tutto | `answer` su `*`, **`ask` su sport** | quattro tipi su cinque erano rispondibili, e chiedevamo |

Il caso SG è il più caro: CHALLENGE §5.4 dice che **chiedere quando la domanda è già
rispondibile conta come sbagliato**, alla pari del rispondere senza un dato essenziale.
Una domanda sulle vacanze di Natale a San Gallo riceveva un ask-back inutile.

---

## 8sexies. I tre rischi aperti del campione, chiusi 🟢

Verificato il 2026-09-22. Chiude i tre punti che §10 teneva aperti sulle vacanze: il
rischio San Gallo, Friburgo e il Vallese. **Due su tre hanno smentito ciò che il
documento diceva di loro**, e in entrambi i casi l'errore era nella stessa direzione:
una fonte era stata descritta senza essere stata letta fino in fondo.

### 8sexies.1 🟢 San Gallo: il rischio non esiste, e si sa perché

§9 dell'handoff chiedeva: **il piano della Città di San Gallo diverge sui quattro tipi
cantonali?** Se sì, la riga `SG` sovra-dichiara, perché risponde `answer` con le date
cantonali anche a chi vive nel capoluogo.

La città pubblica `schulferien-feiertage-stadt-stgallen` su `daten.stadt.sg.ch`
(Opendatasoft, nessuna auth). Trenta record, dal 2022 al luglio 2025.

**Le due fonti non si sovrappongono nel tempo**: la città si ferma a luglio 2025, il
cantone pubblica da 2026/27 a 2029/30. Un confronto diretto delle date 2026 è
impossibile. Si confronta quindi la **regola**, ed è un confronto valido perché la
regola cantonale è espressa in settimane ISO.

Prima serve la convenzione del dataset comunale, e due record festivi la fissano senza
ambiguità: `Auffahrt 2025-05-29 → 2025-05-30` (l'Ascensione 2025 è giovedì 29) e
`Pfingstmontag 2025-06-09 → 2025-06-10` (lunedì 9). In entrambi **`endet_am` è
esclusivo**, come il `DTEND` di un evento ICS all-day.

Con quella convenzione, le settimane scolastiche effettivamente libere in città:

| tipo | città di San Gallo, 2022–2025 | regola cantonale |
|---|---|---|
| Herbstferien | KW 40, 41, 42 | KW 40–42 ✅ |
| Frühlingsferien | KW 15, 16 | KW 15 e 16 ✅ |
| Sommerferien | KW 28–32 | KW 28–32 ✅ |
| Weihnachtsferien | KW 52 + KW 1 | 2 settimane ✅ |
| Winterferien | KW 5, una settimana, 4 anni su 4 | **non nel piano cantonale** |

Le uniche differenze sono di forma, non di sostanza: la città registra come primo giorno
il **sabato** adiacente, che è già non scolastico, mentre il cantone pubblica
domenica–domenica; e due estensioni ai festivi mobili (Karfreitag il 07.04.2023,
Ostermontag il 21.04.2025), che sono giorni festivi e non vacanze.

> **La riga `SG` non sovra-dichiara.** Le `Winterferien` sono l'unica cosa che la città
> decide da sé, e sono esattamente il tipo `sport` già coperto dall'override `ask`
> introdotto in §8quinquies.5. Il rischio si chiude confermando la riga, non correggendola.

Due dettagli emersi leggendo la tabella cantonale per intero:

- **Il Natale a SG non è una regola in settimane.** La nota 1 dice: *"Die
  Weihnachtsferien dauern 2 Wochen. Der erste Weihnachtstag (25. Dezember) ist in der
  ersten Ferienwoche."* È ancorato al 25 dicembre, non a una KW.
- **La primavera cede alla Pasqua.** La nota 3 sul 2029/30: *"Ferienende ist der
  Ostersonntag."* La regola KW 15–16 è quindi derogabile, e il documento lo dichiara.

Date cantonali 2026/27, da citare così come sono: autunno 27.09–18.10.26, Natale
20.12.26–03.01.27, primavera 11.04–25.04.27, estate 11.07–15.08.27.

### 8sexies.2 🔴 Friburgo: la divergenza era attribuita alla regione sbagliata

Le date 2026 mancavano perché si era cercato un PDF. **Non serve**: `fr.ch/dfac/vacances-scolaires`
pubblica tutte e tre le varianti in HTML testuale, con PDF e ICS per anno, fino al 2029/30.

§8ter.8 registrava che *"per il 2027 coesistono du Lu 18. octobre e du Lu 4. octobre"* e
la riga `FR/Morat-Murten` del manifest ne portava la traccia. Aprendo la pagina, quelle
due date sono **majoritaire contro Kerzers**. Morat/Murten non c'entra.

| 2026/27 | majoritaire | Morat/Murten | Kerzers |
|---|---|---|---|
| rentrée | 27.08.26 | = | **24.08.26** |
| automne | 12–23.10.26 | = | = |
| Noël | 21.12.26–01.01.27 | = | = |
| carnaval | 08–12.02.27 | = | **22–26.02.27** |
| Pâques | 26.03–09.04.27 | = | **26.03–16.04.27** |

| 2027/28 | majoritaire | Morat/Murten | Kerzers |
|---|---|---|---|
| automne | 18–29.10.27 | = | **04–22.10.27**, tre settimane contro due |
| Noël | 20–31.12.27 | = | = |
| carnaval | 28.02–03.03.28 | = | **21–25.02.28** |
| Pâques | 14–28.04.28 | = | **10–21.04.28** |

Tre conseguenze:

1. **Morat/Murten non è una variante di vacanze**, in nessuno dei due anni. Differisce
   nei *jours fériés* (niente Toussaint, Immaculée Conception, Fête-Dieu; in più il
   *Jour après la Solennité*) e ha due *jours joker* invece di uno. La riga si tiene lo
   stesso: è una regione scolastica dichiarata dal cantone, e il punto 2 dice perché.
2. **Quali tipi divergono cambia per anno.** Nel 2026/27 l'autunno di Kerzers coincide
   col majoritaire; nel 2027/28 dista due settimane e dura una settimana in più. È lo
   stesso pattern di SZ (§8quater.4), su un cantone diverso. Un campione su un anno solo
   non dice quali tipi sono stabili.
3. ⚠️ **La regione di Kerzers contiene quattro comuni bernesi**: Gurbrü, Wileroltigen,
   Golaten, Ferenbalm, accanto a Kerzers, Fräschels e Ried b. Kerzers. Per quei quattro
   la risposta giusta sta nel calendario **friburghese**. È il primo caso incontrato in
   cui il confine della giurisdizione scolastica taglia un confine cantonale, e il
   risolutore di luogo deve saperlo: un lookup per cantone li manderebbe su BE.

L'estate non è elencata come periodo, ma è derivabile senza ambiguità dai due capi
(*Dernier jour de classe* → *Début de l'année scolaire* successivo), e la pagina
pubblica abbastanza anni perché entrambi i capi esistano sempre.

### 8sexies.3 🔴 Vallese: non è un problema di OCR, il dato non c'è

§8ter.8 lo chiamava *"l'unico caso in cui la fonte autorevole è illeggibile a una
pipeline testuale"* e prevedeva OCR o analisi di layout. **Entrambi sarebbero stati
lavoro sprecato.** Il `Plan de scolarité valais romand` non è un calendario reso male:
è un **modulo vuoto**.

Il testo estratto lo dice per intero: *"Colorier en bleu les jours entiers de classe et
en jaune les demi-jours"*, e la legenda dichiara che il grassetto sono *"Samedis,
dimanches et jours fériés"* — **non** le vacanze. Le uniche cifre nel documento sono i
conteggi mensili di giorni di scuola e il totale (165.5, *Solde* −1). Nessun OCR può
estrarre una data che nel documento non è mai stata scritta.

La pagina cantonale conferma che è voluto:

> *"Attention, les plans sont indicatifs. Pour toutes dates de vacances plus précises,
> s'adresser directement à la Direction d'école (ou Commune) concernée."*

**L'altra metà del cantone invece è risolta**, e la fonte era a un clic di distanza:

- `Schul- und Ferienplan 2026-2027.pdf` — PDF **immagine**, `pypdf` estrae 0 caratteri su
  2 pagine. È il documento che il nome fa sembrare quello giusto.
- `Übersicht Schul- und Ferienplan 2026-2027.pdf` — **tabella testuale, una riga per
  comune, tutti i tipi**, estratta pulita. È la fonte da usare.

> ⚠️ L'`Übersicht` è elencata **solo sulla landing tedesca** `vs.ch/de/web/se/plans-de-scolarite`.
> La landing francese, stesso path senza `/de/`, non la mostra. In un cantone bilingue le
> due lingue del sito non servono lo stesso insieme di documenti: cambiare lingua è un
> passo di ricerca, non una traduzione.

Valori di maggioranza 2026/27 e le varianti:

| | Schulbeginn | Herbst | Weihnachten | Fasnacht/Sport | Ostern | Maiferien |
|---|---|---|---|---|---|---|
| maggioranza | 17.08. | 09.10.–26.10. | 18.12.–04.01. | 19.02.–08.03. | 25.03.–30.03. | 30.04.–10.05. |
| Leukerbad, Zermatt, Saas | 17.08. | = | = | **26.02.**–08.03. | = | **23.04.**–10.05. |

Due cose che questa tabella insegna e che valgono oltre il Vallese:

- 🔴 **Esiste un sesto tipo di vacanza.** La colonna `Maiferien` non ha uno slot
  nell'enum `holiday_type` di `src/tools.ts`. Una domanda sulle vacanze di maggio in
  Vallese non ha dove andare. È §8quater.5 su un caso nuovo, e stavolta non è un nome
  locale per uno slot esistente: è un periodo in più.
- **Una quarta convenzione di estremi.** Le colonne sono *Beginn **abends*** / *Ende
  **morgens***: `Herbst 09.10.–26.10.` significa che le vacanze cominciano la sera del 9
  e finiscono la mattina del 26, cioè i giorni pieni sono **10.10.–25.10.** Dopo SG
  (domenica–domenica), AR (lunedì–venerdì) e BE (primo e ultimo giorno pieno), è la
  quarta in quattro cantoni. Citare la data grezza senza la convenzione sbaglia di un
  giorno per estremo.

Il perimetro dell'`Übersicht` è *deutschsprachige Primar- und Orientierungsschulen*:
tipo di scuola oltre che territorio (CONTRACT §4.4). Per questo contiene righe per le
scuole tedesche di **Siders e Sitten**, che stanno in territorio romando.

---

## 8septies. Tutte le righe delle vacanze, aperte sul documento 🟢

Verificato il 2026-09-23. Ogni riga ancora vuota di `coverage/school_holidays.toml` è
stata chiusa aprendo il documento e leggendo **tutti e cinque i tipi**. Esito: tutte le
righe validate tranne **`SZ/summer`**, lasciata vuota di proposito (sotto). Le date sono
nelle `notes` di ogni riga; qui sta ciò che vale oltre la singola riga.

### 8septies.1 🔴 Sette affermazioni date per verificate erano sbagliate

| Riga | Cosa diceva | Cosa dice la fonte |
|---|---|---|
| **`SO/autumn`** | override: autunno uniforme, `answer` | **3 varianti su 85 enti**, stessa struttura su 2025/26 e 2026/27. Con l'override 6 enti ricevevano una data sbagliata senza che si chiedesse il luogo. Uniforme è il **Natale** (85/85, due anni): l'override ora sta lì |
| **ZH, ask-back** | *"set by each municipality (VSV §32 para. 2)"* | §32 cpv. 2 VSV permette ai comuni **quattro giorni liberi**, non fissa chi decide le vacanze. Citazione falsa nel punto dove il principio era "citare, non asserire" |
| **ZH, Natale** | coperto dall'ask-back | **cantonale e vincolante** (*"im Kanton einheitlich festgelegt"*). Chiedere il comune era la mossa che CHALLENGE §5.4 penalizza. Nuovo override `ZH/christmas` |
| **GE** | *"confina con VD e non si sovrappone di un giorno"* | l'autunno GE 19–23.10.26 sta **dentro** l'autunno VD 10–25.10.26 |
| **SH** | pubblica la regola, non le date | pubblica **entrambe**, fino al 2034/35 |
| **AI** | il liceo è una colonna diversa | nel documento 2026–2029 il Gymnasium è **incluso** nel Landesteil interno |
| **§8.4c, Biel** | bilingue, classificata germanofona | **alterna**: calendario DE negli anni scolastici che iniziano in anno pari, BEJUNE in quelli dispari. Vale anche per Evilard, Orvin, Plagne, Romont, Vauffelin |

Tre di queste venivano da una sola estrazione o da un solo anno letto (§7.3
dell'handoff): SO, GE, Biel. Il caso SO è il più istruttivo: §8ter.2b aveva scartato
come falso un riassunto di ricerca che diceva il vero.

### 8septies.2 🔴 "Hiver" non è uno slot: è un falso amico

| Nome locale | Cantone | Slot |
|---|---|---|
| *Vacances d'hiver* | **NE, VD, BE francofono** | **christmas** |
| *Winterferien* | GL, SO, città di SG | **sport** |
| *Winterferien* | BE germanofono | **christmas** |
| *Vacances du 1er mars* | NE | sport |
| *Relâches* | VD | sport |
| *Semaine blanche* | BE francofono | sport (delegata) |

La stessa parola indica lo slot opposto a seconda del cantone, e perfino dentro BE. Il
parametro `holiday_type` va mappato **per cantone**, mai per traduzione (§8quater.5).

### 8septies.3 ⚠️ Periodi che non stanno nei cinque slot

| Periodo | Dove | Stato |
|---|---|---|
| `Maiferien` | VS germanofono | **deciso 2026-09-23: non coperto** |
| `Pfingstferien` | TG, 06.05–17.05.2027 | **deciso 2026-09-23: non coperto** |
| `Auffahrtsferien` | ZG, 06.05–09.05.2027 | **deciso 2026-09-23: non coperto** |

Pfingst- e Auffahrtsferien sono lo stesso caso delle Maiferien. La decisione presa per
queste ultime non si estende da sola: resta aperta in §10.

### 8septies.4 Tre giurisdizioni scolastiche che attraversano un confine cantonale

- **FR/Kerzers** contiene quattro comuni bernesi (§8sexies.2), già deciso.
- **TG/Neunforn**: gli allievi di **secondaria** frequentano a Ossingen (ZH) e ne seguono
  le date — sport diverso, **nessuna** vacanza di primavera, Pentecoste diversa. Le
  elementari seguono TG. È tipo di scuola più comune, quindi non una riga di comune:
  trattato come BL (CONTRACT §4.4).
- **LU**: una categoria di comuni *"richtet sich nach den Ferien des Kt. Zug"*. Le date
  sono comunque stampate per comune; la categoria è segnata **solo col colore** e il
  testo estratto non la porta.

### 8septies.5 L'estate è quasi sempre derivata, e una volta non si può

FR, TI, GR, UR e SZ non elencano l'estate come periodo: danno l'ultimo giorno di scuola e
l'inizio dell'anno dopo. Si deriva, e dove serve si legge il documento dell'anno
successivo (TI, UR). **SZ non si può**: né il PDF cantonale né il dataset danno il primo
giorno 2027/28. Per questo `SZ/*` è validata sugli altri quattro tipi e `SZ/summer` è
un override **non validato**, così `lookup(SZ, summer)` non cade su una riga coperta.

### 8septies.6 Fonti che si dichiarano non vincolanti, o bozze

- **SO**: *"Die Veröffentlichung erfolgt ohne Gewähr"* → `indicative`.
- **SZ**: anche il PDF cantonale è *"Zusammenstellung ohne Gewähr. Verbindlich sind die
  von den Schulräten erlassenen Ferienpläne"*. Il PDF vincolante cantonale che la vecchia
  nota chiedeva di trovare **non esiste**.
- **ZH**: il documento delle date è intestato **Entwurf** (26.06.2023). Si usa solo per la
  data del Natale, che coincide con la regola *verbindlich* della pagina.
- **JU**: l'arrêté del 10.03.2026 **abroga** quello del 2022, che copriva già fino al
  2027/28. Le date sono state rifatte a metà periodo.

### 8septies.7 Trappole di accesso nuove

- **SH**: pagina renderizzata via JavaScript, `curl` vede 12 righe. Serve un browser.
- **notes.zh.ch**: il link al testo di legge restituisce 200 con 156 byte di HTML e un
  redirect JavaScript. Il PDF sta sul path del redirect.
- **UR**: il deep link `_doc/432274` indicizzato dai motori dà 404; il vivo è `_doc/449362`.
- **UR**: le celle contengono solo il giorno; il mese sta nell'intestazione.
- **JU**: PDF servito come `application/octet-stream`.
- **TI**: un riassunto di ricerca dichiarava le pagine protette da CAPTCHA. Il PDF si
  scarica senza, e la landing risponde 200.

### 8septies.8 ⚠️ Eccezioni che la fonte ammette ma non nomina

**BE**: i comuni in regione turistica alpina *possono* spostare la primavera fra le
settimane 15 e 21, e nessuno dei due documenti dice quali. La riga `BE/*` risponde con la
data cantonale; per quei comuni potrebbe essere sbagliata. Aperto in §10.

---

## 9. Campionamento cantonale: patente estera 🟢

Stessi cinque cantoni, verificati il 2026-09-21. **Risultato opposto alle vacanze
scolastiche: qui il modello è omogeneo, perché la sostanza è federale.**

### 9.1 La sostanza è federale, la procedura è cantonale

Base legale verificata: **VZV / OAC, SR 741.51**, articoli 29, 42–44, 150.
ELI: `https://www.fedlex.admin.ch/eli/cc/1976/2423_2423_2423/de` (200, HTML).

Il **termine di 12 mesi** dall'entrata in Svizzera è diritto federale. Tutti e cinque i
cantoni campionati lo riportano identico — perché lo ripetono, non perché lo stabiliscano.
Federale è anche la regola su quali paesi richiedono una corsa di controllo.

**Conseguenza**: una sola fonte federale copre la sostanza per tutti e 26 i cantoni.
I 26 documenti cantonali servono solo per la procedura.

### 9.2 Cosa varia davvero, per cantone

| Cantone | Ufficio | Elementi cantonali verificati |
|---|---|---|
| VD | SAN | modulo **220**; sedi Aigle, Lausanne, Nyon, Yverdon; 2–3 giorni lavorativi |
| TI | Sezione della circolazione | modulo online; **CHF 150** (200 con categorie professionali); 1–2 settimane |
| ZH | Strassenverkehrsamt | regole corsa di controllo per paese; sede Zürich-Albisgütli |
| BE | SVSA | modulo + foto; **test della vista** da ottico o oculista svizzero; Schermenweg 5 |
| GR | STVA | Ringstrasse 2, Chur; **modulo anche in romancio** |

### 9.3 La domanda campione #2 richiede entrambi i livelli

> *"Comment puis-je échanger mon permis de conduire étranger contre un permis suisse dans
> le canton de Vaud, **et combien de temps ai-je pour le faire**?"*

Il "come" è cantonale (modulo 220, sedi SAN). Il "quanto tempo" è **federale** (VZV).

Citare la pagina vodese come fonte del termine di 12 mesi attribuisce una norma federale
all'autorità sbagliata. La review checklist punto 3 chiede esattamente di verificare che
l'editore sia responsabile della materia. Una risposta completa cita **due fonti a due
livelli**, ciascuna per la parte di cui è competente.

### 9.4 ⚠️ Trappola di freschezza verificata su Berna

Lo stesso ufficio compare su due domini:

| URL | Esito |
|---|---|
| `svsa.sid.be.ch/.../umtausch-fuehrerausweis-ausland.html` | **HTTP 200**, 180 KB — attuale |
| `svsa.pom.be.ch/svsa_pom/de/.../umtausch-auslaendischer-fuehrerausweis.html` | **HTTP 000** — dominio morto |

Berna ha riorganizzato le direzioni (POM → SID) e il vecchio dominio non risponde più.
**Ma la ricerca web restituisce ancora entrambi**, e il morto sembra autorevole quanto il
vivo.

È letteralmente il fallimento della slide 3 del briefing: *"An old page outranks the
current one."* Difesa obbligatoria: **validare che ogni URL del registro risponda al
momento del build**, e registrare la data di validazione accanto alla fonte.

### 9.5 Romancio nativo, di nuovo

I Grigioni pubblicano `Antrag_und_Umtausch_Führerausweis_RM.pdf` — modulo per il cambio
della patente **in romancio**, 786 KB, verificato 200.

È il **secondo tema su due** in cui la fonte autorevole serve il romancio nativamente
(il primo è il piano ferie GR trilingue, §8.6). Ipotesi di lavoro: nei Grigioni la
copertura romancia è una prassi amministrativa, non un'eccezione — il che rende il
romancio molto meno costoso di quanto temuto, purché le fonti siano quelle cantonali GR.

### 9.4b Altri due hostname che non reggono, verificati 2026-09-22

Emersi validando il manifest di copertura contro la rete:

| Hostname | Esito | Lettura |
|---|---|---|
| `strassenverkehrsamt.zh.ch` | **getaddrinfo failed** — non risolve | Il nome ovvio dell'ufficio non è un dominio. La pagina va cercata sotto `zh.ch` |
| `www.stva.gr.ch` | **catena SSL incompleta** (`unable to get local issuer certificate`) | Il sito esiste e il DNS risolve; il server non serve la catena intermedia. Una pipeline con verifica TLS standard lo scarta, un browser no |

Il secondo caso è nuovo rispetto a §9.4: lì il dominio era **morto**, qui è **vivo ma
non validabile**. Sono due fallimenti diversi e vanno distinti nel registro, perché il
primo va sostituito e il secondo va solo verificato a mano.

### 9.6 Costo di ricerca e confronto tra i due temi cantonali

| | Vacanze scolastiche | Patente estera |
|---|---|---|
| Modello | **5 cantoni, 5 modelli** | **omogeneo** |
| Sostanza | cantonale o comunale | **federale** (VZV) |
| Cosa varia | granularità, formato, regole | modulo, tassa, sede, canale |
| Inferenza tra cantoni | **letale** (3 settimane di scarto) | sicura sulla sostanza, vietata sulla procedura |
| Ask-back necessario | sì, in ZH e BE-febbraio | **no** |
| Costo per cantone | ~14 min, varianza alta | **~8–10 min, varianza bassa** |
| Stima 26 cantoni | ~6h | **~4h** |

La patente estera è il tema cantonale più economico e prevedibile dei due, e la stima
iniziale di 4.5h regge. Le vacanze scolastiche sono l'opposto: costano di più e
richiedono il campo "livello di risoluzione" di §8.7.

---

### 9.7 🟢 I 26 uffici da un registro solo, invece di 21 ricerche

§10 elencava *"21 cantoni restanti, meccanici"*. Non erano 21 ricerche: erano una.
L'associazione degli uffici cantonali della circolazione pubblica l'elenco completo su
`asa.ch/strassenverkehrsaemter/adressen/`, con nome dell'ufficio, telefono, email e link
al sito per tutti i cantoni più il Liechtenstein.

**Il registro non dichiara le sigle cantonali**: i blocchi sono in ordine alfabetico
tedesco e l'etichetta è il nome esteso. Assegnare per posizione è fragile, e lo si è
visto subito: un controllo incrociato con dominio ed email ha mostrato uno sfasamento di
una riga da Obvaldo in poi. Il motivo è nel dato, non nel parser — vedi sotto.
L'assegnazione finale è fatta sul **nome esteso dentro l'etichetta del link**, che
nomina il cantone, con dominio ed email come seconda conferma.

Le 26 landing sono in `coverage/driving_licence.toml`, ciascuna verificata con una
richiesta e **registrata all'URL finale dopo i redirect**. `validated_at` resta vuoto su
tutte: è verificata la landing dell'ufficio, non la pagina di procedura.

Quattro cose che il registro ha insegnato, e che valgono oltre questo tema:

- 🔴 **Obvaldo non esiste nel registro.** `NidwaldenVerkehrssicherheitszentrum OW/NW`:
  un blocco solo, etichettato Nidwalden, e solo il *nome dell'ufficio* rivela che serve
  anche Obvaldo. Un censimento che conta le voci del registro trova 25 cantoni e non se
  ne accorge. È il secondo ufficio intercantonale del progetto, dopo il calendario
  BEJUNE (§8bis.1).
- 🔴 **Il registro autorevole contiene un hostname morto.** Per Turgovia punta a
  `www.stva.tg.ch`, che non si connette affatto (`curl` 000). Il vivo è
  `strassenverkehrsamt.tg.ch`. È il secondo caso dopo `svsa.pom.be.ch` (§9.4), ma quello
  veniva da un motore di ricerca: **qui il link morto sta nel registro di categoria.**
- ⚠️ **Basilea Campagna risponde 403 agli automi.** `baselland.ch` rifiuta `curl` anche
  con uno User-Agent di browser completo, mentre la pagina si apre normalmente nel
  browser pane. Non è un URL marcio: è un WAF. Una pipeline che decide la validità di
  una fonte dal codice HTTP la scarterebbe a torto — e un server che facesse fetch **a
  runtime** su questa fonte fallirebbe in produzione.
- **Sette landing su ventisei redirigono altrove** (AG, AR, BS, FR, JU, LU, VS). Il
  registro è aggiornato quanto basta a portare sul sito giusto, non a dare l'URL
  corrente.

🟢 **Un thread aperto si chiude per strada**: §10 registrava che `stva.gr.ch` ha una
catena SSL incompleta. Il registro dà per i Grigioni
`gr.ch/DE/institutionen/verwaltung/djsg/stva/Seiten/Start.aspx`, che risponde 200 senza
problemi di certificato. La fonte grigionese non era irraggiungibile: era raggiunta
dall'hostname sbagliato.

Cinque cantoni non hanno l'ufficio sul dominio cantonale: **FR** (`ocn.ch`), **NE**
(`scan-ne.ch`), **NW/OW** (`vsz.ch`), **TG** (`strassenverkehrsamt.tg.ch`), **LU**
(`strassenverkehrsamt.lu.ch`). È §8ter.5 confermato su un secondo tema: il portale del
servizio quasi mai sta su `<sigla>.ch`.

---

### 9.8 🟢 Le 27 righe della patente, aperte sulla fonte

Verificato il 2026-09-23: la riga federale sul testo consolidato della VZV, le 26
cantonali sulla **pagina di procedura** di ciascun ufficio (non la landing). Il
dettaglio di ogni cantone sta nelle `notes`; qui ciò che vale oltre la riga.

**Tre correzioni alla riga federale.**

- **Il termine non decorre dall'ingresso.** Art. 42 cpv. 3bis lett. a VZV: serve la
  patente svizzera a chi *abita* in Svizzera da dodici mesi senza essere stato all'estero
  più di tre mesi di fila. Quasi tutti i cantoni scrivono "12 mesi dall'ingresso": è la
  loro semplificazione, non la norma.
- **La lista dei paesi non sta nella VZV.** L'art. 44 impone la corsa di controllo a
  tutti; l'art. 150 cpv. 5 lett. e autorizza ASTRA a esentare. La lista sta
  nell'**Anhang 2 della Weisung ASTRA** *Führerausweise von Personen mit Wohnsitz im
  Ausland* (01.10.2013, Stand 15.07.2021), che SVSA Bern linka. Un post del blog ASTRA del
  2023 riporta le stesse liste ma omette una riserva: **Taiwan vale solo per A1 e B**.
- **Due gruppi, non uno.** Gruppo A (UE/AELS più Grossbritannien): esenti da corsa **e**
  da teoria professionale. Gruppo B (tra cui USA, Canada, Giappone, Australia): esenti
  **solo** dalla corsa.

**⚠️ La regola dei cinque anni, senza fonte federale trovata.** LU, TG, VD e ZG
dichiarano che chi converte più di cinque anni dopo l'ingresso fa la corsa di
controllo anche se viene da un paese esente (VD e ZG: salvo attestato di guida regolare).
Non sta nell'Anhang 2 né nel resto della Weisung. Quattro cantoni indipendenti rendono
improbabile un'invenzione locale, ma finché la fonte non è trovata va attribuita ai
cantoni che la scrivono, non alla Confederazione. Aperto in §10.

**Le tasse sono un dato cantonale e spesso assente.** Stampate da 8 cantoni su 26:

| Cantone | Cambio senza corsa | Note |
|---|---|---|
| FR | Fr. 80 forfait | con corsa B Fr. 260 |
| SG | Fr. 80–100 | corsa a parte |
| ZG | Fr. 75 | corsa B Fr. 90 |
| VS | CHF 70 + 53.50 | corsa B CHF 90 |
| NE | Fr. 105 | corsa Fr. 120 in più |
| BE | CHF 120 | |
| GE | CHF 150 | CHF 200 per C, C1, D |
| TI | Fr. 150 | Fr. 200 con categorie professionali |

Gli altri rimandano a un tariffario separato. Una risposta sulla tassa deve dire **da
dove** viene il numero, e per 18 cantoni oggi non ce l'abbiamo.

**Procedure che una risposta generica sbaglia.**
- **TI** dal 17.11.2025 accetta la richiesta **solo online**.
- **BS** vuole il Gesuch **almeno un mese prima** della scadenza dei 12 mesi.
- **NW/OW**: la corsa va fatta **entro tre mesi** dal deposito.
- **SH**: il comune **può fatturare** l'identificazione.
- **ZG**: l'ufficio non fornisce il veicolo per la corsa.
- **VD**: il permesso deve essere stato preso **prima** dell'ingresso in Svizzera.
- **SG** cita per la non ripetibilità della corsa l'art. 29 cpv. 4 VZV; per i permessi
  esteri la norma è l'art. 44 cpv. 1bis. Citazione cantonale da non riprendere.

**Trappole di accesso nuove.** SH (FAQ in accordion via JS: il testo sta nel
`textContent`, non nell'`innerText`) e SO si leggono solo nel browser; BL resta dietro il
WAF (§9.7). Il Merkblatt UR indicizzato dai motori dà 404.

---

## 10. Cosa resta da verificare

**Bloccante per la decisione di scope:**
- **Fattibilità dei 15 comuni romanci**: pubblicano un calendario rifiuti? in che formato?
  Da controllare su 4-5 di essi prima di impegnarsi su una rivendicazione "area romancia
  completa". Una dichiarazione mancata è peggio di una non fatta.

**Aperto:**
- **Se i premi 2027 escono durante l'hackathon** (il BAG pubblica verso fine settembre):
  decidere in anticipo come si comporta il server — anno esplicito nella risposta, e
  quale anno è il default.
- ~~`holiday_type` non ha uno slot per le `Maiferien`~~ → **deciso 2026-09-23: tipo dichiarato
  non coperto** (`scope.toml`, `subtopics`). Nessuno slot nuovo, il gate di routing resta valido
- **Il risolutore di luogo mappa Gurbrü, Wileroltigen, Golaten e Ferenbalm su `FR/Kerzers`**
  per le vacanze scolastiche: **deciso 2026-09-23** (§8sexies.2). Da implementare col risolutore
- ~~`Pfingstferien` (TG) e `Auffahrtsferien` (ZG)~~ → **deciso 2026-09-23: non coperti**, come
  le Maiferien (`scope.toml`, `subtopics`)
- ~~BE, primavera nei comuni turistici alpini~~ → **deciso 2026-09-23: si chiede il comune**.
  Override `BE/spring` con ask-back (§8septies.8)
- **`SZ/summer`**: non validabile finché il cantone non pubblica il primo giorno 2027/28
  (§8septies.5)
- **Vallese romando**: aperto, ma non è più un problema tecnico. Il piano cantonale è un
  modulo vuoto e il cantone rimanda a scuola o comune (§8sexies.3). Si chiude solo
  decidendo se campionare fonti comunali romande o lasciare l'ask-back
- **Le altre vacanze oltre l'autunno**: campionate su 8 cantoni e 4 classi
  (§8quater, §8quinquies). Esito in due parti: nelle classi *uniforme*, *per comune nella
  fonte* e *uniforme con eccezioni* la classe regge fra tipi e cambia solo il dettaglio;
  nella classe *quadro + scelta comunale* **la classe cambia**, in tutti e tre i cantoni,
  e le vacanze di sport non stanno nel documento cantonale.
  Restano non campionate le classi **per regione linguistica** (BE, VS) e **delegato**
  (ZH), ma entrambe chiedono già il luogo per ogni tipo: il rischio è basso
- **Tassonomia dei tipi di vacanza** (§8quater.5): `Osterferien` in OW e NW non è
  `Frühlingsferien`, ed è ancorata alla Pasqua. Il parametro `holiday_type` deve mappare
  i nomi reali, non i nostri slot
- ~~Patente estera, 27 righe~~ → **chiuse 2026-09-23** (§9.8), tutte validate
- ~~Patente, regola dei cinque anni~~ → **deciso 2026-09-23: resta cantonale**, attribuita
  solo a LU, TG, VD, ZG nelle rispettive righe (§9.8)
- **Patente, tasse**: stampate da 8 cantoni su 26; per gli altri serve il tariffario (§9.8)
- ~~Argovia, contraddizione interna~~ → **chiusa in §8quinquies.2**: entrambe le letture
  erano vere. Il cantone fissa l'inizio e un minimo di 2 settimane, il comune può
  estendere a 3. L'organo è l'**Erziehungsrat**, non il Bildungsrat
- Licenze dei repo MCP esistenti, per valutare il riuso
- Se ch.ch espone una ricerca strutturata o solo la SPA
- Quota e rate limit di `api3.geo.admin.ch` per uso intensivo

**Risolto**:
- Non esiste un dataset ufficiale comune → sito web (`behördenverzeichnis` su CKAN =
  `count: 0`); il registro comuni con numeri BFS esiste ed è in §7
- **Parte francofona del canton Berna** → §8.4b–8.4e, chiusa
- **Copertura romancia delle fonti GR**: il piano ferie cantonale è trilingue con
  intestazioni in romancio (§8.6) e lo STVA pubblica il modulo patente in romancio
  (§9.5). Due temi su due serviti nativamente
- **Calendari rifiuti**: non più rilevante, ambito comunale fuori scope per decisione
- **`Einzugsgebiete.csv`** → §3.2c: non è la mappatura delle regioni di premio, ma le
  aree operative degli assicuratori. La mappatura vera è l'ordinanza SR 832.106 (§3.2d).
  Domanda campione #3 risolta end-to-end in §3.2e
- **Versione di SR 832.106 per l'anno di riferimento** → §3.2d-bis: il filestore Fedlex
  è indirizzabile per data. Lugano è regione 1 in tutte le versioni verificate
- **Allineamento BEJUNE** → §8bis.1: confermato su `ne.ch` e `jura.ch` **solo per
  l'autunno**. L'inverno diverge nei tre cantoni
- **Città di San Gallo** → §8sexies.1: **non diverge**. Segue le settimane cantonali su
  tutti e quattro i tipi; le sue `Winterferien` sono il tipo `sport`, già coperto
  dall'override. La riga `SG` si conferma, non si corregge
- **Friburgo** → §8sexies.2: chiuso su due anni scolastici, tutti i tipi, in HTML
  testuale. §8ter.8 attribuiva però la divergenza alla regione sbagliata: è **Kerzers**,
  non Morat/Murten
- **Vallese, metà germanofona** → §8sexies.3: chiuso. La fonte è l'`Übersicht Schul- und
  Ferienplan`, tabella testuale per comune, elencata **solo sulla landing tedesca**
