# Testplan en acceptatietests (afgeleid van Implementatieplan v3)

**Doel:** een controleerbare lijst van tests waaraan het resultaat moet voldoen. Elke test heeft een ID, een verwacht resultaat, een type en een prioriteit. Een fase is pas klaar als alle **M**-tests van die fase slagen én de regressiesuite (§2) groen is.

**Basisregel voor alle tests:** gebruik uitsluitend tijdelijke testdata (`MANILLEN_DATA_DIR`); de echte `data/` blijft ongewijzigd.

### Uitvoeringsstatus Fase 0 (2026-10-25)

- **Geslaagd:** F0-01 t/m F0-06, F0-09 en F0-10. F0-03/F0-04 zijn als handberekende golden fixture vastgelegd in `tests/expected/phase0_baseline.json`; F0-05 bevestigt dat een gescoorde speler buiten de huidige pool in de tussenstand blijft staan (de huidige bron heeft nog geen `PoolMember`-kolom).
- **Gedeeltelijk:** F0-07. De huidige CSV-routes en voorlopige versioned kandidaten staan in de output van `profile_data.py`; de definitieve migratielijst wordt vastgesteld wanneer de versiegrens in Fase 3 wordt ontworpen.
- **Open:** F0-08 en F0-11. Een gecontroleerde Lighthouse-run met mobiel Slow 4G (koud en warm) is nog niet uitgevoerd; de losse browserinspectie is geen vervanging en er wordt nog geen prestatiebudget vastgesteld.
- **Regressies:** REG-01 geslaagd (`36 passed`); REG-02 geslaagd (hashes van alle 14 bestanden onder `data/` identiek vóór en na pytest).

### Uitvoeringsstatus Fase 1 (2026-10-25)

- **Pytest:** volledige suite geslaagd (`52 passed`), inclusief helperpariteit voor klassementen, scores, paren en Hall of Fame op synthetische fixtures, F1-10 t/m F1-14, F1-16, F1-18, statische controles voor F1-17/F1-28 en drie tests voor de legacy rollback-helper.
- **Browser op fixturedata:** F1-07/F1-08, relevante F1-20 t/m F1-28 en de vijf viewports uit MOB-01 zijn lokaal gecontroleerd. Dit omvat alle zes routes, actieve/all-season- en speeldagfilters, spelerzoek inclusief toegewezen reserve, refresh/back, laadstatus, vriendelijke 404-melding, XSS-tekstweergave, buildId-query's, benodigde lazy JSON-verzoeken, eigen-origin-resources, noindex, geen overflow en geen pagina-JavaScriptfouten op normale routes.
- De ontbrekende-JSON-test forceerde bewust een 404; de UI toonde de bedoelde foutmelding. De browserconsole registreerde daarbij de verwachte 404/fetch-fout, niet een fout op een normale route.
- **Huidige gepubliceerde snapshot, read-only:** generatoruitvoer exact vergeleken met gedeelde helpers over 11 seizoensindexitems, alle 11 klassementen/awards, 33 scores, 3 actieve speeldagen, 8 legacy-speeldagrijen, Hall of Fame en parentellingen; invoerhashes gelijk gebleven.
- **Browser op huidige snapshot:** alle zes routes onder `/`, `/Manillen/` en `/Manillen-preview/` (18 combinaties) op 390 px. Alle routes hadden inhoud, geen horizontale overflow, alleen dezelfde origin, geen HTTP-fouten en geen JavaScriptfouten.
- **Export-/transfercontrole:** lokale build bevatte 3 site-assets plus 16 JSON-bestanden en geen CSV's of andere bestandstypen. Gzip-berekening voor HTML/CSS/JS, manifest en actief seizoensbestand: 10.628 bytes; dit is geen gemeten HTTP-transfer of Lighthouse-score.
- De uploadtest controleert dat alleen het JSON-archief via GitHub Contents API wordt aangeboden en dat een mislukte upload de workflow niet dispatcht. Assemblage weigert path traversal en een buildId-mismatch. De Dockerfile bevat de generator en gedeelde kern; de Shiny-app importeerde met een tijdelijke fixture.
- `service-worker-cleanup.js` is toegevoegd aan de sitebuild; de gerichte statische-snapshottest en volledige pytest-suite slagen (`12 passed`, respectievelijk `52 passed`). F1-40/F1-41/F1-42 zijn op de HTTPS-preview uitgevoerd: na bezoek aan de oude Shinylive-preview laadde dezelfde browser na de nieuwe deploy de statische site; de worker voor `/manillen-preview/` en de cache verdwenen, terwijl de worker voor `/Manillen/` bleef bestaan.
- De gedeelde PageSpeed Insights-run op de huidige Shinylive-site gaf `NO_FCP` (geen paint) en dus geen bruikbare performance-score; accessibility was 80. Dit sluit F0-08/F0-11 en F1-30 t/m F1-33 niet af.
- **Workflowvalidatie:** Python-build en assemblage van het JSON-archief slagen lokaal. De previewworkflow slaagde voor de rollback (run `40214417333`) en het herstel naar statisch (run `40214498388`); de Actions-workflow van de hoofdrepo en de NAS-publicatieworkflow zijn nog niet uitgevoerd. `actionlint` en PyYAML zijn niet beschikbaar.
- `NubroDR/manillen-preview` is publiek; Pages-run `40211116929` deployde de legacy-baseline en run `40211245371` deployde de statische preview. De previewbuild bevatte alleen 20 toegestane site-/JSON-bestanden. Op zes routes was inhoud geladen zonder console-/HTTP-fouten; 30 route-/viewportcombinaties hadden geen overflow. Touch targets en invoervelden voldeden op 360 px; hamburgermenu/Escape werkte.
- **F1-44 geslaagd op preview:** de eerste guard-iteratie liep vast op `navigator.serviceWorker.ready`; een volgende browserproef vond een top-level `return`-syntaxfout. De definitieve helper registreert de worker expliciet, wacht op activatie en herlaadt eenmalig wanneer de pagina nog niet wordt bestuurd. In run `40214417333` werd de rollbacksite na het verwijderen van alleen de previewregistratie op de eerste navigatie actief na die ene reload: controller aanwezig, Shinylive-viewer gemount, geen page errors of consolefouten.
- **Preview teruggezet:** commit `e89ec4c` / Pages-run `40214498388` herstelde de statische mirror. De route laadde met inhoud zonder page errors of consolefouten; de registratie voor `/manillen-preview/` en de caches waren weg, terwijl de productie-worker voor `/Manillen/` behouden bleef.
- **Open:** handmatige echte-telefooncontrole, gecontroleerde Lighthouse-/Slow-4G-meting en budget, F1-15 op de uiteindelijke productie-`docs/` en F1-46 live-cutover. F1-43 is read-only gecontroleerd en de bestaande Shinylive-site bleef werken. Productie is niet gewijzigd.

### Previewfeedback: thema en awardaccenten (2026-10-25)

- **Preview geslaagd:** licht is de standaard, ongeacht OS-thema; de toegankelijke toggle wisselt en onthoudt de keuze. Lokaal controleerde Playwright alle zes routes op 360, 375, 390, 768 en 1280 px (30 combinaties): geen horizontale overflow, page errors of consolefouten. Op 360 px is de knop 44×44; donkerthema en awardrijkleuren bleven na refresh behouden. Previewcommit `7b124ba` / Pages-run `40217686913` slaagde. Op de live preview zijn de vernieuwde asset-URL's, lichte standaard, persistente toggle, gekleurde medaillerijen en Hall-of-Fame-awardkolommen bevestigd; op 360 px geen overflow.
- Klassementen tonen opnieuw 🥇/🥈/🥉 en 🏮 voor de actieve laatste plaats, met bijbehorende zachte rijachtergronden. Seizoens-awards en Hall of Fame tonen dezelfde emoji's en zachte kolomachtergronden.
- **F1-29 geslaagd:** lokale en previewbrowseracceptatie geslaagd voor licht standaard, donkere toggle, onthouden keuze, awardemoji's en gekleurde rijen/kolommen. Type E, prioriteit M.
- **F1-34 preview geslaagd:** op 1440 px staan vier tafels in één rij; de eerste speeldagkaart is 342 px hoog (voor de grid-aanpassing 1215 px). Op 1024 px staan drie tafels per rij; op 900 px en mobiel blijven ze onder elkaar. Geen horizontale overflow op 1440, 1024, 900, 768, 390 of 360 px. Previewcommit `30d631f` / Pages-run `40219277473` slaagde. Type E, prioriteit S.

### Overdracht: gewenste Speeldagen-weergave (2026-10-25)

- Destijds nog niet geïmplementeerd: per tafel vier spelers als verticale lijst, met W-L van die speeldag naast elke naam. Geen afzonderlijke matchups of ruwe scores in Speeldagen; volledige uitslagen blijven in Scores.
- De implementatie en lokale browsercontrole zijn op 2026-11-04 uitgevoerd; zie de voortgangsnotitie hieronder. Previewacceptatie blijft open.

### Voortgang Speeldagen-W-L-weergave (2026-11-04)

- De snapshotgenerator publiceert per tafel de W-L-resultaten uit de gedeelde scoreberekening. Ruwe matchups en scores staan niet langer dubbel in de `playdays[].tables[]`-gegevens; de afzonderlijke `scores`-lijst blijft volledig.
- Lokale browsercontrole op een geïsoleerde fixture: vier verticale spelersrijen met W-L, geen matchups/scores in Speeldagen, en detailmatchup plus ruwe scores zichtbaar op Scores. Geen pagina-overflow op 360, 375, 390, 768, 1024 en 1440 px; mobiel stapelt de tafels en desktop toont de bestaande auto-grid. De browser heeft fixture-JSON gebruikt; er is niet gepubliceerd naar de preview.
- Validatie: `tests/test_static_snapshot.py` geslaagd (`13 passed`) en de volledige regressiesuite geslaagd (`53 passed`). F2-43 t/m F2-45 zijn lokaal geverifieerd; de overige Fase 2-tests blijven open.

### Mobiele UI-feedback (2026-11-04)

- Donkere modus gebruikt nu ook een donkere achtergrondgloed in plaats van de lichte decoratieve cirkel. Mobiele tabellen blijven semantische tabellen in een eigen horizontaal scrollgebied met zichtbare kolomkoppen en een vaste eerste kolom; de kaartweergave is verwijderd voor Tussenstand, Seizoenen, Scores en Parenhistoriek.
- Tussenstand en Scores bieden geen filteroptie "Alle seizoenen"; oude `seizoen=all`-links vallen terug op het actieve seizoen. Seizoenen toont één overzichtsrij per seizoen met een link naar het Speeldagen-tabblad wanneer detaildagen beschikbaar zijn; legacy-seizoenen zonder die details tonen geen link. Tafelspelers in Speeldagen staan op W-L (wins, daarna games, daarna naam), zonder puntenverschil als tie-break.
- `tests/test_static_snapshot.py` en de volledige pytest-suite slagen (`13 passed`, respectievelijk `53 passed`); de snapshottest bevestigt ook W-L-sortering zonder saldo-tie-break. Browseracceptatie van deze feedback kon lokaal niet worden afgerond: de geïntegreerde browser kreeg herhaaldelijk connection resets bij de lokale fixtureserver; er is geen previewdeploy uitgevoerd. Productie en preview blijven ongewijzigd.
- Aanvullende feedback op Seizoenen: verwijderd zijn de spelers- en lange speeldagenkolommen; er is nu één rij per seizoen met een directe link naar het juiste Speeldagen-seizoen indien die weergave details heeft.

## 1. Legenda

| Code | Betekenis |
|---|---|
| **U** | pytest unit-test op pure logica |
| **I** | pytest integratietest (bestanden, scripts, processen, app-start) |
| **S** | statische code-/inhoudscontrole (grep, AST, bestandenlijst) |
| **E** | end-to-end in de browser (Playwright, optionele dev-tool) |
| **L** | Lighthouse-meting (optionele dev-tool) |
| **H** | handmatige test, bij voorkeur op een echte telefoon |
| **M / S** (prioriteit) | **M**ust: blokkeert oplevering. **S**hould: sterk gewenst, afwijking vraagt onderbouwing. |

## 2. Fixtures en regressiesuite

### 2.1 Gedeelde testdataset (`tests/fixtures/`)

De handberekende verwachte uitkomsten staan naast de fixtures (`tests/expected/`). Een fixture bevat minstens:

| ID | Inhoud |
|---|---|
| FX-01 | 10 spelers, twee actieve seizoenen en één legacyseizoen zonder individuele scores |
| FX-02 | Volledige speeldag: 2 tafels × 3 spellen, alle scores geldig |
| FX-03 | Onvolledige speeldag: één ontbrekend spel en één spel met één ontbrekende score |
| FX-04 | Speeldag met dubbele spelrij en een tafel met ≠ 4 deelnemers |
| FX-05 | Spel met gelijke score (bv. 101-101) in bestaande data |
| FX-06 | Speeldag met een reserve zonder koppeling (`Reserve 1`) en een met expliciete koppeling aan een PlayerID |
| FX-07 | Speler met `PoolMember=0` |
| FX-08 | Naamvarianten: hoofdletter-/spatieverschil, verkorte versus volledige voornaam (ambigu), expliciet goedgekeurde alias |
| FX-09 | Hall of Fame met gedeeld brons (twee spelers, zelfde seizoen) |
| FX-10 | `pairings.csv` met bewuste drift ten opzichte van `pairings_history.csv` |
| FX-11 | Speler zonder enige data en een hernoemde speler |
| FX-12 | Stresscase: naam van 25 tekens, naam met HTML-tekens (`<script>`, `"`, `&`), 12 spelers op één speeldag |
| FX-13 | Speeldag met 4+ tafels (voor `RESERVE:n` met n > 3) |
| FX-14 | Locaties met legacynaam en alias |
| FX-15 | Seizoen met slechts één speeldag en een speler met precies één spel |

### 2.2 Regressiesuite (draait bij elke fase)

| ID | Test | Verwacht | Type | Prio |
|---|---|---|---|---|
| REG-01 | Volledige bestaande pytest-suite | Groen, zonder wijziging van bestaande tests behalve gedocumenteerde import-aanpassingen | I | M |
| REG-02 | Hash van echte `data/` vóór en na de testrun | Identiek | I | M |
| REG-03 | Hoofdapp start (`shiny run app.py`) op fixturedata | Start zonder fout; alle bestaande hoofdapp-tabs laden | I | M |
| REG-04 | Klassement en partnercounts op fixture (baseline uit Fase 0) | Identiek aan baseline, tenzij een fase dit expliciet verklaart | U | M |
| REG-05 | Indelingsregels (oorspronkelijke specificatie): vier spelers per tafel, maximaal één reserve per tafel, maximaal vijf unieke configuraties | Ongewijzigd | U | M |
| REG-06 | Scoreregels: alleen volledige spellen met beide niet-negatieve gehele scores worden opgeslagen; ontbrekende/onvolledige spellen worden gemeld maar blokkeren andere volledige spellen niet; opnieuw opslaan vervangt alleen hetzelfde spel op basis van datum, tafel en spelnummer; niet-ingediende spellen blijven behouden; waarschuwing als geen score ≥ 101 | Huidige gedeeltelijke opslagsemantiek blijft behouden; gelijke score wordt vanaf Fase 2 geweigerd | I | M |
| REG-07 | Klassementsortering: gewonnen, gespeeld, saldo, naam; saldo = punten voor − punten tegen | Ongewijzigd | U | M |
| REG-08 | Paths: geen `Path.cwd()` of relatieve paden; paden gebaseerd op `Path(__file__).resolve().parent` of `data_paths.py` | Geen overtredingen | S | M |
| REG-09 | Geen nieuwe runtime-dependencies zonder akkoord; generator draait met alleen stdlib | `requirements` ongewijzigd of goedgekeurd | S | M |

## 3. Fase 0: baseline en meting

| ID | Test | Verwacht | Type | Prio |
|---|---|---|---|---|
| F0-01 | Profileringscommando draait op fixture en op kopie van echte data | Wijzigt geen bestand (hashvergelijking) | I | M |
| F0-02 | Profileringsrapport inhoud | Bevat schemas, aantallen, onbekende en dubbele namen, hoofdletter-/spatieverschillen, aliasconflicten, ongeldige verwijzingen, gelijke scores en `pairings`-drift | I | M |
| F0-03 | Baselineklassementen per seizoen en per speeldag | Opgeslagen als fixture; twee runs geven identiek resultaat | U | M |
| F0-04 | Baseline partnercounts (genormaliseerde paren) | Opgeslagen en reproduceerbaar | U | M |
| F0-05 | Gedrag van `PoolMember=0` in de Tussenstand | Vastgelegd in rapport en als test (beslissing 10) | U | M |
| F0-06 | Inventaris imports uit `mirror_app/` door `app.py` en tests | Volledige lijst in rapport | S | M |
| F0-07 | Inventaris van alle CSV's waar de app naar schrijft of die ID's gaan bevatten | Lijst voor het versioned datamodel vastgesteld | S | M |
| F0-08 | Lighthouse mobiel, Slow 4G, koud en warm, op de huidige Shinylive-export | Cijfers (LCP, transfer, performance) in meetrapport | L | M |
| F0-09 | Grootte van de huidige `docs/` | Gemeten en vastgelegd | S | M |
| F0-10 | Service worker van de huidige export | Bestandsnaam en scope vastgesteld (via `getRegistrations()` op de live site); bevestigd dat `/Manillen-preview/` buiten die scope valt | H | M |
| F0-11 | Prestatiebudget bevestigd of aangepast op basis van meting | Definitief budget in plan | H | S |

## 4. Fase 1: gedeelde kern en statische mirror

### 4.1 Pariteit met de oude mirror

| ID | Test | Verwacht | Type | Prio |
|---|---|---|---|---|
| F1-01 | Klassement per seizoen uit gegenereerde JSON versus bestaande helpers op dezelfde snapshot | Identiek (inhoud en volgorde) | U | M |
| F1-02 | Tussenstand gefilterd op één speeldag | Identiek aan oude berekening | U | M |
| F1-03 | Scores per speeldag en tafel | Identiek (teams, scores, volgorde van spellen) | U | M |
| F1-04 | Parenhistoriek incl. all-time teller en spelerzoekfilter | Identiek | U | M |
| F1-05 | Hall of Fame op FX-09 | Beide spelers staan op de gedeelde bronzen plaats (regressiecase 2024–2025) | U | M |
| F1-06 | Seizoenen: awards en speeldaggegevens, legacy en actief | Identiek | U | M |
| F1-07 | Standaardfilter Tussenstand en Speeldagen | Actief seizoen is startwaarde | E | M |
| F1-08 | Alle zes tabs bereikbaar en gevuld in de nieuwe site | Seizoenen, Hall of Fame, Tussenstand, Speeldagen, Scores, Parenhistoriek | E | M |

### 4.2 Gedeelde kern en generator

| ID | Test | Verwacht | Type | Prio |
|---|---|---|---|---|
| F1-10 | Generator in schone omgeving zonder extra packages | Draait met alleen stdlib | I | M |
| F1-11 | Twee runs op dezelfde invoer | Identieke uitvoer (behalve `buildId` en tijdstempel) | I | M |
| F1-12 | Generator wijzigt geen bronbestand | Hash van invoer ongewijzigd | I | M |
| F1-13 | `manifest.json` | Bevat buildId, gegenereerd-op, actief seizoen, seizoenslijst | U | M |
| F1-14 | JSON-validatie van alle uitvoer | Geldige JSON, vast schema, geen onverwachte nulls of NaN | U | M |
| F1-15 | `docs/`-inhoud | Alleen toegestane afgeleide bestanden; geen CSV, backups, rapporten, migratiestatus | S | M |
| F1-16 | Hoofdapp en tests via re-export-shims | Importeren werken; geen circulaire imports; REG-01 en REG-03 groen | I | M |
| F1-17 | Geen dubbele rekenlogica | Berekeningen in `manillen_core/`; JavaScript bevat geen klassement- of profielberekening (codecontrole) | S | M |
| F1-18 | NAS-upload en workflow-invoer | Upload bevat één buildId-gevalideerd JSON-archief; geen bron-CSV's; mislukte upload dispatcht niet | I | M |

### 4.3 Frontend

| ID | Test | Verwacht | Type | Prio |
|---|---|---|---|---|
| F1-20 | Naam met HTML-tekens (FX-12) | Wordt als tekst getoond, geen scriptuitvoering, geen ongeëscapete HTML | E | M |
| F1-21 | Hash-routes | Elke tab via URL bereikbaar; refresh behoudt de weergave; back/forward werken | E | M |
| F1-22 | Filters seizoen, speeldag en spelerzoek | Resultaat gelijk aan verwachte fixtureuitkomst | E | M |
| F1-23 | Laadindicator en foutafhandeling | Indicator zichtbaar tijdens laden; vriendelijke melding als een JSON-bestand ontbreekt | E | M |
| F1-24 | Netwerkverzoeken | Alleen eigen origin; geen externe fonts of scripts | E | M |
| F1-25 | Cachebusting | Data-URL's volgen `buildId`; CSS/JS/HTML-deploywijzigingen krijgen bovendien een assetfingerprint zodat assets bij ongewijzigde snapshotdata ook nieuwe URL's krijgen | E | M |
| F1-26 | Console | Geen JavaScript-fouten op alle routes | E | M |
| F1-27 | Tab-inhoud wordt lui geladen | Per tab/seizoen enkel de benodigde JSON opgehaald | E | S |
| F1-28 | `noindex`-meta | Aanwezig op alle pagina's; er is geen standaard `Disallow: /` in `robots.txt` | S | M |
| F1-29 | Thema en awardaccenten | Licht is standaard, ook bij OS-dark; toggle schakelt thema en onthoudt keuze; medailles/lantaarn en gekleurde awardrijen/-kolommen blijven zichtbaar in beide thema's | E | M |
| F1-34 | Speeldagen desktop compacter | Vanaf 901 px is verticale witruimte kleiner; op mobiele breedtes blijven de bestaande afmetingen en geen-overflow-gedrag behouden | E | S |

### 4.4 Prestaties (budget uit plan; definitief na F0-11)

| ID | Test | Verwacht | Type | Prio |
|---|---|---|---|---|
| F1-30 | Lighthouse mobiel, Slow 4G, koud | Inhoud zichtbaar binnen ca. 2 s; performance ≥ 90; accessibility ≥ 95 | L | M |
| F1-31 | Lighthouse warm | Niet slechter dan koud; assets uit cache | L | S |
| F1-32 | Eerste transfer (HTML, CSS, JS, manifest en eerste data) | Ca. 150 KB gecomprimeerd | L | M |
| F1-33 | Vergelijking met baseline F0-08 | Aantoonbare verbetering in LCP en transfer | L | M |

### 4.5 Cutover en publicatie

| ID | Test | Verwacht | Type | Prio |
|---|---|---|---|---|
| F1-40 | Preview-locatie `https://nubrodr.github.io/manillen-preview/` | Geen registratie van de oude worker onder dat pad; pagina's komen van de nieuwe site | H | M |
| F1-41 | Repetitie van de cutover op het previewproject | Oude Shinylive-export in preview bezocht met testprofiel; daarna nieuwe site met opruimscript; na één bezoek toont het profiel de nieuwe site en is de oude worker uitgeschreven | H | M |
| F1-42 | Opruimscript op het pad van de oude worker | Schrijft worker en caches uit; geen fouten in console | E | M |
| F1-43 | Publieke URL | `https://nubrodr.github.io/Manillen/` blijft werken | H | M |
| F1-44 | Rollback | Terugzetten van vorige `docs/`-commit herstelt een werkende site | H | M |
| F1-45 | Workflow `publish-mirror.yml` | Geen Shinylive-installatie; duur korter dan baseline | H | S |
| F1-46 | Live cutover | Zelfde controle als F1-41 op de echte URL met een profiel dat de oude site eerder bezocht | H | M |
| F1-47 | Basepad-onafhankelijkheid | Dezelfde build werkt onder `/`, `/Manillen/` en `/manillen-preview/` (relatieve URL's, geen 404's) | E | M |

## 5. Fase 2: Speeldagen-rangschikking en scorevalidatie

### 5.1 Berekening (W-L per tafel)

| ID | Test | Verwacht | Type | Prio |
|---|---|---|---|---|
| F2-01 | Volledige tafel (FX-02) | Drie matchups AB-CD, AC-BD, AD-BC; W-L per speler gelijk aan handberekening | U | M |
| F2-02 | Som van overwinningen op een complete tafel | Altijd 6 (drie spellen × twee winnaars) | U | M |
| F2-03 | Voorbeeld uit het plan: één speler 3-0, drie spelers 1-2 | Eerste speler plaats 1; de drie anderen delen plaats 2 | U | M |
| F2-04 | Volgorde binnen een gedeelde plaats | Alfabetisch op naam; naam beïnvloedt de plaats niet | U | M |
| F2-05 | Twee spelers met gelijke W-L maar verschillend saldo | Zelfde plaats (saldo telt niet) | U | M |
| F2-06 | Gepubliceerde tafel-JSON | Bevat `place`, `wins`, `losses`, `games`, `complete`; geen `saldo` | U | M |
| F2-07 | Onvolledige dag (ontbrekend spel, FX-03) | `complete=false`, zichtbaar label, enkel geldige spellen tellen | U | M |
| F2-08 | Spel met één ontbrekende score | Spel telt niet mee; tafel als onvolledig gemarkeerd | U | M |
| F2-09 | Dubbele spelrij (FX-04) | Dubbele rij wordt niet meegeteld; tafel `complete=false` met zichtbare waarschuwing; bronbestand ongewijzigd | U | M |
| F2-10 | Tafel met ≠ 4 deelnemers (FX-04) | Geen rangschikking; duidelijke markering | U | M |
| F2-11 | Gelijke score in bestaande data (FX-05) | Spel telt niet als gewonnen of gespeeld; als ongeldig gemarkeerd; data niet aangepast | U | M |
| F2-12 | Reserve in tafelrangschikking (FX-06) | Gekoppelde reserve met naam; niet-gekoppelde als placeholdertekst zonder link | U | S |
| F2-13 | Tafel waarvan alle spellen leeg zijn | Geen rangschikking; "geen scores" label | U | M |

### 5.2 Gepasseerd-logica (browser, `Europe/Amsterdam`)

| ID | Test | Verwacht | Type | Prio |
|---|---|---|---|---|
| F2-20 | Datum vóór vandaag | Gepasseerd: rangschikking getoond | E | M |
| F2-21 | Datum is vandaag | Actueel: geen rangschikking van gepasseerde dag | E | M |
| F2-22 | Datum in de toekomst | Niet gepasseerd; geen rangschikking | E | M |
| F2-23 | Klok op 23:59:59 en 00:00:00 Amsterdamse tijd | Statuswissel precies om middernacht Amsterdam | E | M |
| F2-24 | Browsertijdzones UTC, America/New_York, Asia/Tokyo bij hetzelfde tijdstip | Zelfde status | E | M |
| F2-25 | Zomer-/wintertijd-overgang | Geen foutieve statuswissel | E | S |

### 5.3 Scorevalidatie in de hoofdapp

| ID | Test | Verwacht | Type | Prio |
|---|---|---|---|---|
| F2-30 | Invoer met gelijke score in de UI | Geweigerd met duidelijke Nederlandse melding | I | M |
| F2-31 | Opslagfunctie direct aangeroepen met gelijke score | Geweigerd (niet alleen in UI) | U | M |
| F2-32 | Bestaande rijen met gelijke score | Gerapporteerd, niet gewijzigd (hash) | I | M |
| F2-33 | Overige validatie | Zie REG-06 | U | M |
| F2-34 | Zelfde berekeningsfunctie in hoofdapp en generator | Eén implementatie; mock-/importtest bevestigt gedeeld gebruik | S | M |

### 5.4 Weergave

| ID | Test | Verwacht | Type | Prio |
|---|---|---|---|---|
| F2-40 | Formaat | Naam gevolgd door W-L, bv. `3-0`; geen saldo zichtbaar | E | M |
| F2-41 | Winst/verlies niet alleen door kleur | Tekst aanwezig | E | M |
| F2-42 | Weergave op 360 px | Geen horizontaal scrollen in de tafelkaart | E | M |
| F2-43 | Speeldagen per tafel | Vier spelers staan elk op een eigen verticale rij; het W-L-resultaat van de speeldag staat naast de juiste naam | E | M |
| F2-44 | Scheiding Speeldagen en Scores | Speeldagen toont geen spel-per-spel-matchups of ruwe scores; Scores blijft alle volledige matchups en scores tonen | E | M |
| F2-45 | Responsieve tafelkaarten | Desktop behoudt auto-grid; op mobiel staan tafels onder elkaar; geen pagina-overflow op 360, 390, 768, 1024 en 1440 px | E | S |

## 6. Fase 3: ID-registry en migratie

### 6.1 Dry-run, mapping en ID's

| ID | Test | Verwacht | Type | Prio |
|---|---|---|---|---|
| F3-01 | Dry-run | Wijzigt niets (hash vóór/na) | I | M |
| F3-02 | Dry-rapport | Onbekende en dubbele namen, hoofdletter-/spatieverschillen, aliasconflicten, ongeldige verwijzingen, gelijke scores, `pairings`-drift, reserve-slotformaat | I | M |
| F3-03 | Voorstelbestand | Staat buiten de actieve datastore; alle ID's botsingsvrij | I | M |
| F3-04 | ID-formaat spelers | Regex `plr_` + 5 tekens uit `abcdefghjkmnpqrstuvwxyz23456789` | U | M |
| F3-05 | ID-formaat locaties | Regex `loc_` + 5 tekens uit hetzelfde alfabet | U | M |
| F3-06 | Alfabet | Bevat geen `0`, `o`, `1`, `l`, `i` | U | M |
| F3-07 | Generatie | Gebruikt een cryptografisch sterke generator uit de stdlib; geen afleiding van de naam | S | M |
| F3-08 | Apply met gewijzigd voorstel (hash komt niet overeen met goedkeuring) | Geweigerd | I | M |
| F3-09 | Herhaalde apply op hetzelfde goedgekeurde voorstel | Dezelfde ID's en inhoud | I | M |
| F3-10 | Nieuwe voorstelrun | Mag nieuwe ID's bevatten; nooit eerder uitgegeven of ingetrokken ID's | U | M |
| F3-11 | Ambigue match (FX-08) | Blokkeert apply; niet automatisch samengevoegd | I | M |
| F3-12 | Fuzzy matching | Komt niet voor: verkorte versus volledige naam blijft ongekoppeld tot handmatige alias | U | M |
| F3-13 | Aliasnormalisatie | Hoofdletter- en spatieverschil leiden naar dezelfde alias | U | M |
| F3-14 | Tombstones | Verwijderde of samengevoegde speler/locatie blijft inactief in het register; ID nooit hergebruikt | U | M |
| F3-15 | Collisiecheck | Bij gesimuleerde botsing wordt opnieuw getrokken | U | M |

### 6.2 Backup, staging en activatie

| ID | Test | Verwacht | Type | Prio |
|---|---|---|---|---|
| F3-20 | Backup vóór wijziging | Unieke volledige backup; bestaande backup nooit overschreven | I | M |
| F3-21 | Backupfout (bv. schrijfbare doelmap ontbreekt) | Migratie stopt vóór enig schrijven | I | M |
| F3-22 | Onvoldoende opslagruimte (gesimuleerd) | Stopt vóór schrijven | I | S |
| F3-23 | Staging | Naast de actieve versie; actieve versie ongewijzigd (hash) tot activatie | I | M |
| F3-24 | Validatie faalt (schema, referentiële integriteit, rijaantallen, baselines) | Geen activatie; actieve versie intact | I | M |
| F3-25 | Proces gestopt tijdens staging | Oude versie actief; incomplete staging niet actief | I | M |
| F3-26 | Proces gestopt direct vóór de manifest-rename | Oude versie actief | I | M |
| F3-27 | Manifest-switch | Via tijdelijk bestand en atomische rename op hetzelfde bestandssysteem; een gelijktijdige lezer ziet nooit een half manifest | I | M |
| F3-28 | `data_paths.py` | Leest enkel de versie waarnaar het manifest wijst | U | M |
| F3-29 | Opstartcontrole | Ontbrekende of inconsistente actieve versie: app start niet met een gemengde dataset, expliciete foutmelding | I | M |
| F3-30 | Oorspronkelijke bestanden in de root | Blijven staan, niet verplaatst of verwijderd (hash) | I | M |
| F3-31 | Wat wordt geversioneerd | Enkel de vastgestelde CSV-lijst; `Scorebladen.xlsx` en `Scorebladen/` niet gekopieerd of gewijzigd | I | M |
| F3-32 | Legacybronnen (`seasons_history.csv`, `seasons_playdays_legacy.csv`) | Ongewijzigd (hash) | I | M |
| F3-33 | Rollback zonder nieuwe data | Manifest atomisch teruggezet naar vorige versie | I | M |
| F3-34 | Rollback met nieuwe data na activatie | Commando meldt de later toegevoegde rijen en weigert zonder expliciete bevestiging | I | M |
| F3-35 | Opschoning | Geen versie wordt automatisch verwijderd | I | M |
| F3-36 | Verouderde root-bestanden | `LEGACY-NOT-ACTIVE.txt` aanwezig; waarschuwing als geversioneerde bestandsnamen in de root na activatie nog wijzigen | I | M |
| F3-37 | Publicatiepaden en grens naar GitHub | NAS-generator `publish_mirror.py` leest uitsluitend de actieve versie via `data_paths.py`; bij verschillende inhoud in root en actieve versie wordt alleen de actieve data verwerkt. `github_publish.py` uploadt alleen de gevalideerde publieke JSON-snapshot, geen bron-CSV's, backups of migratierapporten. GitHub Actions leest geen NAS-datastore en genereert niet uit bron-CSV's | I | M |
| F3-39 | Onderbroken snapshot-upload | Een onvolledige upload activeert geen nieuwe manifestversie en start geen deploy; de vorige publieke snapshot blijft geselecteerd | I | M |
| F3-38 | Docker-entrypoint | Overschrijft nooit bestaande bestanden; nieuwe installatie wordt in een initiële versie geseed; herhaalde start verandert niets | I | M |

### 6.3 Verificatie en schema's

| ID | Test | Verwacht | Type | Prio |
|---|---|---|---|---|
| F3-40 | Klassement per gemapte speler vóór/na | Identiek | U | M |
| F3-41 | Genormaliseerde partnercounts vóór/na | Identiek | U | M |
| F3-42 | Verschil door een expliciete mappingbeslissing (bv. samengevoegde alias) | Enkel toegestaan en verklaard in het verificatierapport | U | M |
| F3-43 | Volledigheid | Elke oude rij is terug te vinden (aantallen, scores, namen via de adapter) | I | M |
| F3-44 | `pairings_history.csv` | Vier tokens in de bestaande pipe-notatie; token is PlayerID of `RESERVE:n`; `Location` is LocationID of leeg | U | M |
| F3-45 | `scores_history.csv` | Twee tokens per team; reservepersoon niet gekopieerd in historische uitslag; koppeling via datumgebonden assignment | U | M |
| F3-46 | `reserve_assignments.csv` | Kolommen `Date`, `Slot`, `PlayerID`; onbekende vrije tekst gerapporteerd en niet automatisch gekoppeld | U | M |
| F3-47 | `RESERVE:n` | n ≥ 1 en niet groter dan het aantal tafels van die speeldag (FX-13); afwijking wordt gemeld | U | M |
| F3-48 | `pairings.csv` | `Player1` en `Player2` bevatten PlayerID's; reserve-placeholders worden niet als persoonspaar geteld | U | M |
| F3-49 | Paarsleutel | `(a,b)` en `(b,a)` geven dezelfde gesorteerde sleutel | U | M |
| F3-50 | Drift (FX-10) | Gerapporteerd, niet automatisch gecorrigeerd | I | M |
| F3-51 | Locaties | LocationID in `pairings_history`; legacynamen via `location_aliases.csv`; legacybron read-only | U | M |
| F3-52 | Onbekend ID of ongeldige verwijzing | Gedetecteerd en gerapporteerd | U | M |
| F3-53 | Dubbele canonieke namen | Gerapporteerd; blokkeert apply | U | M |

## 7. Fase 4: hoofdapp, scoreopslag en Excel op ID's

| ID | Test | Verwacht | Type | Prio |
|---|---|---|---|---|
| F4-01 | Nieuwe speeldag-indeling opslaan | `pairings_history` en `pairings` bevatten ID's; paringen met reserves genegeerd | I | M |
| F4-02 | Indelingsregels op ID-data | REG-05 blijft groen | U | M |
| F4-03 | Scoreopslag | Per tafel op ID's; vervangt alle drie spellen | I | M |
| F4-04 | Speeldag verwijderen | Partnercounts correct gedecrementeerd (alleen echte spelers) | I | M |
| F4-05 | Reservenamen per datum | Koppeling naar bestaand PlayerID; vrije tekst niet geaccepteerd zonder mapping | I | M |
| F4-06 | `Reserve 1` | Heeft geen persoons-ID | U | M |
| F4-07 | Reservepersoon | Wordt alleen via expliciete koppeling herkend | U | M |
| F4-08 | Nieuw gegenereerd Excelscoreblad | Toont namen; geen cel met `plr_` of `loc_`; reserves met afwijkende achtergrond- en tekstkleur | I | M |
| F4-09 | Bestaande Excelbestanden in `Scorebladen/` | Onveranderd (hash) | I | M |
| F4-10 | GUI van de hoofdapp | Toont overal namen; HTML-scan bevat geen ID-patroon | E | M |
| F4-11 | Naamwijziging via het offline commando | Werkt door in hoofdapp, nieuwe Excel en publieke JSON na regeneratie; oude Excel ongewijzigd; ID's en deep links ongewijzigd | I | M |
| F4-12 | Oude naam als alias | Legacybronnen met de oude naam verwijzen nog naar dezelfde PlayerID | U | M |
| F4-13 | Adaptertest | Geen directe CSV-lees- of schrijftoegang buiten de adapterlaag | S | M |
| F4-14 | Naamgebaseerde bestanden | Worden niet meer geschreven | S | M |
| F4-15 | `PoolMember=0` | Niet in de standaardpool bij nieuwe indeling; wel meegeteld in statistieken volgens F0-05 | U | M |
| F4-16 | Publieke JSON na een naamwijziging | Eén generatorrun volstaat; geen verouderde naam meer | I | M |
| F4-17 | Hoofdapp op gemigreerde fixture | Alle tabs laden zonder fout | I | M |

## 8. Fase 5: spelersprofielen en links

### 8.1 Links en navigatie

| ID | Test | Verwacht | Type | Prio |
|---|---|---|---|---|
| F5-01 | Alle oppervlakken met namen (Speeldagen-deelnemers, Scores-teams, Tussenstand, Parenhistoriek, awards in Seizoenen, Hall of Fame, tafelrangschikking) | Elke naam van een speler met ID is een `<a>` naar `#/speler/<PlayerID>` | E | M |
| F5-02 | Filterkeuzes | Blijven filters; aparte knop **Open profiel** navigeert | E | M |
| F5-03 | Reserve-placeholder en niet-gekoppelde reserve | Geen link, geen profiel | E | M |
| F5-04 | Onbekende of ongeldige `player`-ID | Vriendelijke melding; geen JavaScript-fout | E | M |
| F5-05 | Speler zonder data (FX-11) | Duidelijke lege status | E | M |
| F5-06 | Hernoemde speler | Oude URL werkt; nieuwe naam getoond | E | M |
| F5-07 | Deep link | Werkt bij direct openen, refresh, delen (nieuwe browsercontext) en back/forward | E | M |

### 8.2 Statistieken (Must)

| ID | Test | Verwacht | Type | Prio |
|---|---|---|---|---|
| F5-10 | Samenvatting: speeldagen, gewonnen, verloren, winstpercentage, saldo | Gelijk aan handberekende fixture, all-time en per seizoen | U | M |
| F5-11 | Speler zonder gespeelde spellen | Geen deling door nul; winstpercentage toont "niet beschikbaar" | U | M |
| F5-12 | Ongeldige (gelijke-score) spellen | Tellen niet mee | U | M |
| F5-13 | Seizoensposities | Enkel bij individuele score- en deelnemersdata; legacy zonder die data toont "niet beschikbaar" | U | M |
| F5-14 | Hall-of-Fame-vermeldingen | Via goedgekeurde alias; gedeeld brons (FX-09) correct voor beide spelers | U | M |
| F5-15 | Hernoemde speler | Statistieken blijven aan hetzelfde ID gekoppeld | U | M |

### 8.3 Statistieken (Should)

| ID | Test | Verwacht | Type | Prio |
|---|---|---|---|---|
| F5-20 | Rankingverloop per speeldag | Reeks gelijk aan handberekening; geen grafiek zonder data | U | S |
| F5-21 | Grafiek | Inline SVG met tabel-/lijstalternatief | E | S |
| F5-22 | Recente vorm | W-L per speeldag over de laatste vijf speeldagen; correct bij minder dan vijf | U | S |
| F5-23 | Aantal 3-0-tafels | Gelijk aan handberekende fixture; geen winstreeks-statistiek op het profiel (buiten scope) | U | S |
| F5-24 | Partneroverzicht | Meest gespeeld en winstpercentage per partner gelijk aan handberekening | U | S |
| F5-25 | Toon | Pagina bevat geen "nemesis" of "slechtste partner"; positieve formulering | S | M |

### 8.4 Scope en privacy

| ID | Test | Verwacht | Type | Prio |
|---|---|---|---|---|
| F5-30 | Could-onderdelen (head-to-head, aanwezigheid, beste/slechtste speeldag, fun facts, reserve-optredens) | Niet aanwezig in de eerste release, tenzij apart goedgekeurd | S | M |
| F5-31 | Aanwezigheidspercentage bij bron met enkel aantallen | Niet getoond | U | M |
| F5-32 | Profiel-JSON | Bevat enkel publieke velden | S | M |

## 9. Fase 6: opruimen, publicatie en documentatie

| ID | Test | Verwacht | Type | Prio |
|---|---|---|---|---|
| F6-01 | End-to-end publicatie: NAS-knop → JSON-generator → upload van uitsluitend publieke JSON → `workflow_dispatch` → deploy → live site | Slaagt; site bevat de nieuwste volledige snapshot en de workflow heeft geen bron-CSV's nodig | H | M |
| F6-02 | GitHub-publicatie | Gebruikt `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, `GITHUB_WORKFLOW`, optioneel `GITHUB_REF` (standaard `main`); getest met mocks; geen secrets in repo of `docs/` | I | M |
| F6-03 | `docs/` bevat geen interne bestanden | Geen backups, rapporten, migratiestatus, `versions/`, `active-version.json` | S | M |
| F6-04 | Seedlogica | Overschrijft nooit bestaande bestanden (getest met tijdelijk volume) | I | M |
| F6-05 | Shinylive en `mirror_app/` | Verwijderd of naar `legacy/` verplaatst; geen resterende imports of verwijzingen; REG-01 groen | S | M |
| F6-06 | Dependencies | Geen Shinylive meer in de publicatiepijplijn | S | M |
| F6-07 | `README.md` en mirror-README | Beschrijven backup, dry-run, verificatie, rollback (inclusief begrenzing), lokaal testen en naamwijziging | H | M |
| F6-08 | Opruimscript van de oude service worker | Aanwezig tot de geplande verwijderdatum; daarna bewust verwijderd | H | S |
| F6-09 | Volledige regressiesuite en alle fase-tests op de eindstaat | Groen | I | M |

## 10. Dwarsdoorsnijdende tests

### 10.1 Mobiel en toegankelijkheid (Playwright, elke route × 360, 375, 390 en 768 px)

| ID | Test | Verwacht | Type | Prio |
|---|---|---|---|---|
| MOB-01 | Paginaoverflow | `document.scrollWidth <= innerWidth` | E | M |
| MOB-02 | Touch targets | Navigatie, filters, knoppen en spelerlinks ≥ 44×44 px | E | M |
| MOB-03 | Invoervelden en selects | Berekende lettergrootte ≥ 16 px | E | M |
| MOB-04 | Tabellen | Onder het breakpoint kaartweergave (`data-label`) of scrollcontainer met scrollhint en sticky eerste kolom | E | M |
| MOB-05 | Viewport | Meta met `viewport-fit=cover`; safe-area-regels aanwezig | S | M |
| MOB-06 | Hamburgermenu | Opent en sluit; Escape en buitenklik sluiten; focus terug naar menuknop; maximale hoogte met scroll in landscape (bv. 667×375) | E | M |
| MOB-07 | Toetsenbord | Logische tabvolgorde; zichtbare focus op alle interactieve elementen | E | M |
| MOB-08 | Contrast (licht en donker) | WCAG AA gehaald (axe of Lighthouse) | E | M |
| MOB-09 | Axe-controle | 0 *serious* of *critical* bevindingen | E | M |
| MOB-10 | Semantiek | `th scope`, koppenhiërarchie, `aria-current` op actieve tab, `aria-label`s waar nodig | E | M |
| MOB-11 | Donkere modus (`prefers-color-scheme: dark`) | Alle routes leesbaar | E | M |
| MOB-12 | `prefers-reduced-motion` | Animaties uitgeschakeld | E | S |
| MOB-13 | Grafiek | Responsief; tikken toont waarde; toetsenbordfocus; tabelalternatief aanwezig | E | M |
| MOB-14 | Stresscase FX-12 | Lange namen en 12 spelers veroorzaken geen overflow | E | M |
| MOB-15 | Rotatie portrait ↔ landscape | Geen layoutbreuk | E | S |
| MOB-16 | Paginazoom 200% | Geen verlies van inhoud of functionaliteit | E | S |
| MOB-17 | Systeemfonts | Geen externe fontverzoeken | E | M |

### 10.2 Handmatige test op echte toestellen

Lokaal serveren met `python -m http.server --bind 0.0.0.0` in `docs/` en openen via het lokale netwerk (er is geen service worker meer, dus geen HTTPS nodig). Controleer op minstens één iPhone (Safari) en één Android-toestel (Chrome), plus een tablet indien beschikbaar:

| ID | Controle | Verwacht | Prio |
|---|---|---|---|
| H-01 | Eerste laadtijd op mobiel netwerk | Voelbaar snel; laadindicator zichtbaar | M |
| H-02 | Alle tabs, filters en menu met duim bedienbaar | Geen foutieve taps, geen onverwachte zoom | M |
| H-03 | Profiellink delen (bv. via berichtenapp) en openen | Opent het juiste profiel | M |
| H-04 | Browser-terugknop | Gaat naar vorige weergave, niet uit de site | M |
| H-05 | Notch en landscape | Inhoud niet onder systeembalken | S |
| H-06 | Donkere modus en vergrote systeemtekst | Leesbaar en bruikbaar | S |
| H-07 | Terugkerende bezoeker van de oude site | Ziet na één bezoek de nieuwe site | M |

### 10.3 Privacy en beveiliging

| ID | Test | Verwacht | Type | Prio |
|---|---|---|---|---|
| PRIV-01 | Gepubliceerde bestanden | Alleen goedgekeurde afgeleide JSON en site-assets (zie F1-15 en F6-03) | S | M |
| PRIV-02 | Geheimen | Geen tokens of credentials in repo, `docs/` of logs (patroonscan) | S | M |
| PRIV-03 | XSS | Zie F1-20 | E | M |
| PRIV-04 | Publieke JSON | Alles in `docs/` is publiek opvraagbaar; test gaat niet uit van afscherming door `noindex` | S | M |

## 11. Vastgelegde definities

Deze punten waren in het plan nog open en zijn nu besloten; de tests hierboven toetsen ze.

| Punt | Besluit | Tests |
|---|---|---|
| Dubbele spelrij (zelfde datum, tafel en spelnummer meerdere keren) | Dubbele rij wordt niet meegeteld; tafel gemarkeerd als onvolledig met waarschuwing; bronbestand niet aangepast | F2-09 |
| Speeldag in de toekomst | Niet gepasseerd; geen rangschikking | F2-22 |
| Reserve in de tafelrangschikking | Gekoppelde reserve met naam; niet-gekoppelde als tekst zonder link | F2-12 |
| Reeksen op het profiel | Enkel recente vorm (W-L over de laatste vijf speeldagen) en aantal 3-0-tafels; winstreeksen vallen buiten scope | F5-22, F5-23 |
| Winstpercentage bij 0 spellen | "Niet beschikbaar" | F5-11 |
| Exacte prestatiecijfers | Bevestigen na de meting in Fase 0 (F0-11) | F1-30 t/m F1-33 |

## 12. Dekking per planonderdeel

| Plan | Tests |
|---|---|
| Statische mirror en laadtijd (beslissing 1) | F0-08, F1-01 t/m F1-33 |
| Gedeelde kern (beslissing 2) | F1-16, F1-17, F2-34 |
| `docs/` blijft (beslissing 3) en alleen afgeleide JSON (4) | F1-15, F6-03, PRIV-01 |
| Geen naamexports (5), ID-formaat (6) | F3-04 t/m F3-07, F4-13, F4-14 |
| Tafelrangschikking zonder saldo (7) | F2-03 t/m F2-06, F2-40 |
| Donkere modus en beweging (8) | MOB-11, MOB-12 |
| Toon van profielstatistieken (9) | F5-25 |
| `PoolMember=0` (10) | F0-05, F4-15 |
| Versioned staging en atomische activatie (11) | F3-23 t/m F3-36 |
| Profiel-MoSCoW (12) | F5-10 t/m F5-32 |
| Testtools optioneel (13) | Playwright en Lighthouse enkel lokaal/dev; pytest-tests moeten zonder ze draaien |
| Rollback begrensd, service worker, `RESERVE:n` | F3-33, F3-34, F1-40 t/m F1-44, F3-47 |
| Gelijke scores | F2-11, F2-30 t/m F2-32, F5-12 |
| Hall of Fame gedeeld brons | F1-05, F5-14 |

## 13. Uitvoering

- **pytest-markers:** `unit`, `integration`, `static`. Deze draaien zonder Playwright of Lighthouse en vormen de verplichte basis in elke fase.
- **E-tests (Playwright)** en **L-tests (Lighthouse)** zijn optionele dev-tools (beslissing 13): lokaal uitvoerbaar, CI-installatie niet vereist. De **M**-tests van type E, L en H worden vóór het mergen van de bijbehorende fase uitgevoerd en het resultaat wordt in de pull request genoteerd.
- **Definition of Done per fase:** alle **M**-tests van de fase slagen, REG-01 t/m REG-09 zijn groen, MOB-01 t/m MOB-11 en MOB-14 slagen voor elke nieuwe of gewijzigde route, en het gedrag voldoet aan de vastgelegde definities in §11.
