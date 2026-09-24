# Foreign driving licence exchange fees: official-source audit

Checked on 2026-09-24. The machine-readable amounts and per-fact source URLs are in
[`driving_licence_facts.json`](driving_licence_facts.json).
Amounts in that file are stored in Swiss rappen. A range is a published tariff range,
not an estimated price. A `component` is a separately listed charge; it must not be
summed with another item unless the authority states that both apply.

| Canton | Verified published item(s), CHF | Official source |
| --- | --- | --- |
| AG | Exchange application review 20; licence card 25 | [Strassenverkehrsamt](https://www.ag.ch/de/themen/mobilitaet-verkehr/strassenverkehr/steuern-gebuehren/gebuehren/lenkerinnen-und-lenker) |
| AI | Foreign-licence exchange 110; required control drive 120 | [Tariff](https://ai.clex.ch/api/de/versions/2422/pdf_file) |
| AR | New card-format licence 60; exchange-specific charge unresolved | [Strassenverkehrsamt](https://ar.ch/verwaltung/departement-inneres-und-sicherheit/strassenverkehrsamt/fuehrerausweis/fuehrerausweis-im-kreditkartenformat-fak/) |
| BL | Exchange application 45 **plus** licence card 42 | [Motorfahrzeugkontrolle](https://www.baselland.ch/politik-und-behorden/direktionen/sicherheitsdirektion/motorfahrzeugkontrolle/motorfahrzeugsteuern-und-gebuehren/gebuehren/gebuehren-und-besondere-abgaben-fuehrerzulassung) |
| GL | Exchange including application and document checks 100–400 | [Tariff](https://gesetze.gl.ch/app/de/texts_of_law/VII-D.12.3) |
| GR | Exchange 80 | [Tariff](https://www.gr-lex.gr.ch/app/de/texts_of_law/870.130) |
| JU | Exchange without exam 225.75 (215 points × CHF 1.05) | [Tariff](https://rsju.jura.ch/fr/viewdocument.html?Download=1&id=36992&idn=20021&v=18), [point value](https://www.jura.ch/fr/Autorites/Administration/DEC/OVJ/Taxe-et-emoluments/Taxe-et-emoluments.html) |
| LU | Exchange 95 | [Strassenverkehrsamt](https://strassenverkehrsamt.lu.ch/strassenverkehr/steuern_gebuehren/gebuehren_und_abgaben) |
| NW | Exchange 100–140; required category B control drive 150 | [Legal tariff](https://gesetze.nw.ch/app/de/texts_of_law/651.21), [VSZ 2026 tariff](https://www.vsz.ch/10-strasse/40-steuern-und-gebuehren/Gebuehren.pdf) |
| OW | Exchange 100–140; required category B control drive 150 | [Legal tariff](https://gdb.ow.ch/app/de/texts_of_law/771.411), [VSZ 2026 tariff](https://www.vsz.ch/10-strasse/40-steuern-und-gebuehren/Gebuehren.pdf) |
| SH | Exchange application review 30; licence card 60 | [Tariff](https://rechtsbuch.sh.ch/app/de/texts_of_law/741.012) |
| SO | Exchange 200–500 | [Current tariff](https://bgs.so.ch/app/de/texts_of_law/614.62) |
| SZ | Exchange application review 80; first licence card 45 | [Tariff](https://www.sz.ch/public/upload/assets/29546/782_311.pdf) |
| TG | Exchange application review 60; licence 40; required control drive 180 | [Tariff](https://www.rechtsbuch.tg.ch/app/de/texts_of_law/741.11) |
| UR | Exchange 100 | [2025 tariff](https://www.ur.ch/_docn/403768/Tarifordnung_2025.pdf) |
| VD | Card-format licence 45; required control drive 130–190; exchange-specific charge unresolved | [Published fees](https://www.vd.ch/mobilite/automobile-et-navigation/frais-des-prestations-du-san/permis-de-conduire), [exchange procedure](https://www.vd.ch/prestation/echanger-un-permis-de-conduire-etranger) |
| ZH | Exchange 50; identity check 20 when applicable; required control drive 134, 201 or 268 by category | [Tariff effective 2026-01-01](https://www.zh.ch/content/dam/zhweb/bilder-dokumente/organisation/sicherheitsdirektion/strassenverkehrsamt/organisation/ueber-uns-grundlagen/Geb%C3%BChrenverf%C3%BCgung%2C%20g%C3%BCltig%20ab%201.%20Januar%202026.pdf) |

## Interpretation and open items

- AR: The currently accessible cantonal procedure page does not give an exchange fee. Its linked legal tariff resolves to an older version, while the canton announced a revised tariff effective 2025-04-01. The older exchange figure was deliberately excluded. CHF 60 is only the published card fee; the full exchange price still requires a current tariff or direct confirmation from the authority.
- VD: The published canton-wide list gives a card fee and a control-drive range, but no specific exchange-processing fee. The linked form only points back to the tariff page. The total for an exchange is therefore unresolved.
- JU: The tariff gives 215 **points**, not CHF 215. The cantonal authority states CHF 1.05 per point from 2025-01-01. The converted amount applies specifically to exchange **without an exam**; other cases are not covered by that item.
- NW/OW: The exchange amount is a range in the legal tariff. The VSZ publishes a specific category B control-drive charge separately. The final invoiced exchange amount within the legal range and any additional charges are not inferred here.
- SO: A canton-hosted legislative proposal mentions CHF 100 as a *new* exchange fee and CHF 200–500 as the *previous* fee. The proposal is not used as the tariff in force; the published legal tariff still gives CHF 200–500.
- Fees for eye tests, medical examinations, translations, postage, late changes, and other exceptional services are outside this audit unless explicitly present as an exchange fee fact.
