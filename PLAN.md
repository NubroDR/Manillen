# Implementatieplan: seizoenen, Hall of Fame en score-invoer

## Samenvatting van de huidige code

- `app.py` is de schrijfbare NAS-app. `app_ui` bevat de tabbladen; `_read_history()` leest `pairings_history.csv`, `_score_entry_tables()` bouwt de scoreformulieren, `_standings_table()` toont de tussenstand en `_history_cards()` toont de speeldagen.
- `manillen_functions.py` schrijft de indeling naar de paringsteller en `pairings_history.csv` via `update_pairs_in_csv()` en `save_pairings_history()`. Die geschiedenis heeft nu alleen `Date`, `Table` en `Players`. `delete_pairings_by_date()` verwijdert alle tafels van een datum.
- `score_functions.py` valideert en schrijft scores. `save_scores()` vervangt momenteel alle drie de spellen van één tafel en vereist dus drie volledige scoresets. `compute_standings()` en de onderliggende pure logica staan in `mirror_app/score_helpers.py`.
- `reserve_assignments.py` bewaart namen per `Date` en `Slot`; `get_reserve_assignments()` levert bijvoorbeeld `{"Reserve 1": "Frederik VA"}`. De geschiedeniskaarten vervangen placeholders al door opgeslagen namen, maar de score-invoer en klassementberekening doen dat nog niet.
- `mirror_app/app.py` is de alleen-lezen app; `mirror_app/data_helpers.py` leest pairings, speeldagen en reserves. `publish_mirror.py` kopieert een vaste lijst CSV-snapshots en exporteert daarna de app naar `docs/`.
- De legacybestanden zijn aanwezig als `data/seasons_history.csv` (seizoenen S1–S10) en `data/seasons_playdays_legacy.csv` (speeldagen voor 2023–2024 en 2024–2025). `data/hall_of_fame_check.csv` bevat verwachte totalen, `InPool` en testverwachtingen. Alle drie moeten in Git worden opgenomen en zijn niet uitgesloten door de huidige `.gitignore`; op het moment van deze planupdate staan ze nog ongetrackt. Ze moeten dus expliciet worden toegevoegd en gecommit vóór de Portainer-build/publicatie die ervan afhankelijk is. De check-CSV blijft uitsluitend testdata.
- Er is geen bestaande pytest-suite gevonden.

### Huidige publicatiestroom (geverifieerd)

- De NAS-knop roept `trigger_mirror_workflow(DATA_DIR)` uit `github_publish.py` aan. Vóór de `workflow_dispatch` uploadt die helper via de GitHub Contents API de bestaande bestanden uit zijn `SNAPSHOT_FILES`-whitelist (`pairings.csv`, `pairings_history.csv`, `scores_history.csv`, `reserve_assignments.csv`) naar `data/` op de gekozen branch. Dit zijn commits via de API; het zijn niet alleen lokale NAS-bestanden.
- Daarna start `github_publish.py` de workflow `publish-mirror.yml` met `workflow_dispatch`.
- `.github/workflows/publish-mirror.yml` checkt de branch uit, voert `publish_mirror.py` uit en commit/pusht `docs/` en `mirror_app/data/`.
- `publish_mirror.py` leest uitsluitend `data/` in de Git-checkout, kopieert de CSV’s uit zijn eigen `SNAPSHOT_FILES` naar `mirror_app/data/` en bouwt daarna de Shinylive-export. De workflow zelf leest het NAS-volume niet.
- Dus: een workflow die rechtstreeks wordt gestart gebruikt alleen de Git-branch. Via de bestaande NAS-knop komen NAS-wijzigingen op GitHub doordat `github_publish.py` ze vóór dispatch via de API uploadt. De kleinste uitbreiding is de whitelists van beide helpers bij te werken met de benodigde seizoensbestanden. De historische CSV’s moeten daarnaast vooraf gecommit zijn, zodat de Portainer `Stack from Git repository`-build ze ook als image-seeds kan bevatten. `hall_of_fame_check.csv` wordt nooit geüpload of gepubliceerd.

## Voorgesteld datamodel en migratie

### Canonieke seizoensregistratie

Voeg `data/seasons.csv` toe als register voor seizoenen die met de tool beheerd worden, met uitsluitend deze kolommen:

| Kolom | Doel |
|---|---|
| `Season` | Bewerkbaar label dat in de UI verschijnt, initieel `2026-2027`. |
| `SeasonNumber` | Nummer als integer, initieel `11` en getoond als `S11`. |
| `SeasonStartYear` | Startjaar voor het automatisch voorstellen van het volgende label, onafhankelijk van latere labelwijzigingen. |
| `Status` | `actief` of `afgesloten`; er is één actief seizoen. |

De initiële registerrij is `2026-2027,11,2026,actief`. Awards van afgesloten tool-seizoenen worden uit de scores berekend; er worden geen medailles in het register gekopieerd. Scores zijn daarvoor de enige bron van waarheid. S1–S10 blijven in `seasons_history.csv` als afzonderlijke, alleen-lezen historische bron; ze worden niet opnieuw als tool-seizoenen geïmporteerd.

### Speeldag en scoredata

- Voeg `Season` toe aan `pairings_history.csv`, naast `Date`, `Table` en `Players`. Dit is de canonieke relatie van een speeldag naar één seizoen. Alle tafelrijen met dezelfde `Date` krijgen hetzelfde seizoenslabel.
- Laat `scores_history.csv` bij de bestaande kolommen `Date`, `Table`, `Game`, `Team1Players`, `Team2Players`, `Team1Score` en `Team2Score`. Koppel scores bij het filteren aan het seizoen van hun speeldag via `Date` in `pairings_history.csv`. Zo hoeft het seizoenslabel niet redundant in elke spelrij opgeslagen en gesynchroniseerd te worden.
- Laat `reserve_assignments.csv` ongewijzigd (`Date`, `Slot`, `Name`). De combinatie van speeldatum en slot blijft de bron voor de naam van `Reserve 1`, `Reserve 2`, enzovoort.
- `seasons_history.csv` en `seasons_playdays_legacy.csv` blijven ongewijzigde UTF-8-bronnen. `hall_of_fame_check.csv` wordt niet naar de snapshot gekopieerd en blijft uitsluitend testinvoer.

### Veilige migratie voor bestaande NAS-volumes

Voeg een idempotente migratiefunctie toe in een helpermodule voor seizoensdata en roep die vanuit de NAS-app vóór de eerste geschiedenislezing aan:

1. Maak vóór iedere eerste migratiewijziging verplicht een eenmalige backup van `pairings_history.csv`, bijvoorbeeld `pairings_history.csv.bak-pre-seasons`. Maak deze backup alleen als er nog geen bestaat en overschrijf hem nooit. Als het maken van de backup mislukt, voer de migratie niet uit.
2. Als `pairings_history.csv` geen `Season`-kolom heeft, lees alle bestaande rijen in, behoud alle oorspronkelijke kolommen/waarden en voeg `Season` toe. Vul bestaande rijen zonder seizoenswaarde met `2026-2027`. Als de kolom al bestaat, vul alleen lege seizoenswaarden op dezelfde manier in; verander niet-lege labels niet.
3. Schrijf migratie-uitvoer eerst volledig naar een tijdelijk bestand en vervang het origineel pas na een geslaagde schrijf.
4. Maak `seasons.csv` met de S11-beginrij alleen als het bestand ontbreekt of nog geen seizoenen bevat. Bestaande registerrijen worden niet vervangen.
5. `docker-entrypoint.sh` blijft seed-only: breid de lijst met ontbrekende seeds alleen uit met de historische bronbestanden `seasons_history.csv` en `seasons_playdays_legacy.csv`, zodat die ook op een bestaande `/app/data`-mount beschikbaar komen. De entrypoint kopieert ze alleen als ze ontbreken en overschrijft geen bestaande bestanden. `seasons.csv` wordt door de app aangemaakt; `hall_of_fame_check.csv` wordt nooit geseed.

De leeshelpers moeten daarnaast ook rechtstreeks met een oude CSV zonder `Season` kunnen werken: tijdens een geleidelijke rollout levert zo'n rij standaard seizoen `2026-2027` op. Dit maakt ook oude testfixtures en een bestaand volume leesbaar vóór/zonder migratie.

Bij het aanmaken van een speeldag wordt het actuele actieve seizoen opgeslagen in iedere `pairings_history.csv`-rij. Het seizoen wordt dus expliciet vastgelegd en niet uit de speeldatum afgeleid. Scores en reservekoppelingen volgen diezelfde speeldatum.

## Plan per feature

### 1. User-facing bewoordingen verwijderen (tekst-only)

**Bestanden:** `app.py`, `mirror_app/app.py`, `README.md`, `mirror_app/README.md`, `publish_mirror.py` (alleen beschrijvende exportmetadata), gegenereerde `docs/`-tekst.

- Verwijder de zichtbare bewoordingen “Publieke mirror” en “mirror” uit user-facing titels, navigatie, intro’s en README-tekst; vervang ze door neutrale Nederlandse teksten.
- Laat interne module-, bestands-, functie- en workflow-namen ongewijzigd. De NAS-knop **Publiceer data** en de bestaande publicatiefunctie blijven behouden.
- Dit is uitsluitend tekstwerk; regenereer zo nodig de export zodat ook de gepubliceerde user-facing tekst in deze stap wordt aangepast. Nieuwe tabs, datasnapshots en allowlists komen in een latere stap.

**Validatie:** zoek beide app-bronnen en de README’s op oude zichtbare termen; controleer dat technische identifiers en de knop **Publiceer data** behouden blijven.

### 2. Reserveweergave herstellen

**Bestanden:** `app.py`, `score_functions.py`, `mirror_app/score_helpers.py`, `mirror_app/app.py`, `README.md`; tests onder `tests/`.

- Voeg een herbruikbare omzetting toe die per speeldatum de placeholders in de spelteams vervangt door `get_reserve_assignments()`-namen. Houd de placeholder in de opgeslagen tafel- en scoredata intact; los de naam op bij het renderen/berekenen.
- Toon in `Scores invoeren` bij ieder spel de opgeslagen reservenaam in plaats van `Reserve 1`/`Reserve 2`.
- Laat de tussenstand op basis van scores en datumgebonden toewijzingen op de echte naam aggregeren. Toon een ster bij een speler die in de geselecteerde periode als reserve speelde, bijvoorbeeld `Jan*`, en onder de tabel exact `* = reservespeler`.
- Pas dezelfde naamresolutie toe op de gedeelde klassementlogica zodat de NAS-app en de read-only app niet uiteenlopen. Als er voor een placeholder geen naam is opgeslagen, behoud dan de placeholder als zichtbare fallback en markeer hem als reserve.
- Besteed aandacht aan cumulatieve standen: dezelfde persoon kan op de ene speeldag reserve zijn en op een andere dag niet; scores tellen dan onder de opgeloste naam samen en de ster wordt getoond zodra die persoon in de gefilterde periode reservebeurten heeft.
- Waarschuw bij het invoeren van een reservenaam als die overeenkomt met een poolnaam uit `AllPlayers.csv`; laat de naam corrigeren of bewust bevestigen. Reserve-invoer wordt in alle tool-awardberekeningen uitgesloten.

**Randgevallen/tests:** ontbrekende assignment-bestanden, lege naam, meerdere reserves op één datum, placeholder zonder assignment, dezelfde naam als vaste speler en reserve over verschillende dagen, en poolnaam als ingevoerde reservenaam.

### 3. Scores per spel opslaan

**Bestanden:** `app.py`, `score_functions.py`, `README.md`; tests onder `tests/`.

- Vervang de ene knop `Scores opslaan` door een knop per spel (per tafel/spel-card). Dit is de kleinste UX-wijziging die partiale invoer én direct opslaan per spel ondersteunt.
- Voeg een helper toe die één spel valideert en opslaat. De unieke logische sleutel is `(Date, Table, Game)`: bij opslaan verwijdert de helper alle bestaande rijen met die sleutel en schrijft precies één nieuwe rij. Andere spellen en tafels blijven ongemoeid.
- De knop is alleen succesvol als beide teamscores zijn ingevuld en niet-negatieve gehele getallen zijn. Een onvolledig spel blijft ongewijzigd; lege andere spellen blokkeren het opslaan niet.
- Gebruik dezelfde matchup- en scorevalidatie als nu. Toon de status bij de betrokken kaart of centraal met tafel/spel vermeld, en verhoog daarna de score-reactiviteit zodat de tussenstand meteen de nieuwe uitslag bevat.
- Een tweede opslag van hetzelfde spel levert geen dubbele rij op; een aangepaste score vervangt de bestaande rij. Gebruik geen aparte tijdelijke partiale-scorevorm: onvolledige input wordt niet naar de CSV geschreven.

**Randgevallen/tests:** score `0`, één ontbrekende teamscore, decimale/negatieve invoer, meerdere saves van dezelfde spelkey, overschrijven van een bestaande spelkey en behoud van alle niet-betrokken rijen.

### 4. Seizoenen, migratie en filters

**Bestanden:** nieuw `data_paths.py` en `mirror_app/season_helpers.py` (gedeelde pure helper), `app.py`, `manillen_functions.py`, `mirror_app/data_helpers.py`, `Dockerfile`, `docker-entrypoint.sh`, `.dockerignore`, `requirements-dev.txt`, `README.md`, tests onder `tests/`.

- Maak helpers voor seizoensregister, migratie, verplichte eenmalige backup, actieve seizoenkeuze, volgende seizoenssuggestie en groepering van speeldagen/scores per season label.
- Voeg `MANILLEN_DATA_DIR` toe als centrale data-directory override voor de NAS-app en persistentiehelpers, met de huidige project-`data/`-directory als standaard. Mirror-snapshots blijven onder `mirror_app/data/`.
- Voeg `requirements-dev.txt` met pytest toe en sluit `tests/` uit in `.dockerignore`; tests en testafhankelijkheden komen niet in het NAS-image.
- Breid het schrijven van `pairings_history.csv` uit zodat `Season` behouden en ingevuld wordt. Werk ook de geschiedenislezer en delete-/rewrite-paden bij zodat een nieuwe kolom niet verloren gaat. Een speeldag en alle tafels daarop horen één seizoen te hebben.
- Voeg in `Nieuwe speeldag` een Nederlandstalige seizoenskeuze toe, standaard het actieve seizoen; een gebruiker kan vóór het bewaren een ander bestaand seizoen kiezen.
- Voeg `Nieuw seizoen` toe. Stel `SeasonNumber` voor als hoogste nummer + 1, `SeasonStartYear` als hoogste startjaar + 1 en het label als `YYYY-(YYYY+1)`. Laat het label vóór bevestiging aanpassen. Toon eerst een bevestigingspreview van de eindstand en awards; pas na bevestiging wordt het oude seizoen afgesloten en het nieuwe actief.
- Voeg `Heropen seizoen` toe om een afgesloten seizoen opnieuw actief te maken. Awards blijven steeds afgeleid van scoredata. Bepaal hoe deze actie de één-actief-seizoen-regel en een eventueel al aangemaakte/gebruikte opvolger veilig afhandelt.
- Voeg een seizoensfilter toe aan `Geschiedenis` en een seizoensfilter plus de bestaande speeldagfilter aan `Tussenstand`. De filters starten op het actieve seizoen; de datumkeuze beperkt in `Tussenstand` het geselecteerde seizoen tot één specifieke speeldag. Historische seizoenen zonder scoredata tonen een passende lege toestand in plaats van de S11-scores.
- Pas `mirror_app/data_helpers.py` aan zodat historische CSV’s zonder `Season` blijven laden en gemigreerde/nieuwe rijen de expliciete waarde gebruiken.
- Houd `seasons_history.csv` en legacy-speeldagen gescheiden van het toolregister. De S1–S10-gegevens worden alleen in de aparte historische pagina gelezen.

**Randgevallen/tests:** oude `pairings_history.csv` zonder `Season`, bestaande extra kolommen, backup één keer maken en nooit overschrijven, temp-write/replace, dubbele migratie, lege waarden, vrij bewerkbaar label, nieuw register zonder rijen, filters met lege seizoenen en geen seizoensverlies bij verwijdering. Test expliciet dat de tweede migratierun dezelfde inhoud laat staan.
- Gebruik `MANILLEN_DATA_DIR` met een tijdelijke map in tests zodat geen test de echte `data/`-bestanden opent of wijzigt.

### 5. Pagina’s Seizoenen en Hall of Fame

**Bestanden:** `mirror_app/season_helpers.py`, `data_paths.py`, `app.py`, `mirror_app/app.py`, `Dockerfile`, `publish_mirror.py`, `github_publish.py`, `README.md`, tests onder `tests/`.

- Maak een pure helper die `seasons_history.csv` leest met `encoding="utf-8"` en een read-only seizoenenoverzicht levert. Toon per aanwezige rij seizoen, `SeasonNumber`/S-nummer, poolgrootte, beker (1e/Goud), zilver, brons en rode lantaarn. Splits tie-lijsten op ` | ` en toon alle namen.
- Toon bij S9 (2023–2024) en S10 (2024–2025) de speeldagen uit `seasons_playdays_legacy.csv`, waaronder datum, locatie, aanwezigen en poolgrootte. Toon alleen seizoenen die in `seasons_history.csv` voorkomen; er worden geen lege rijen voor seizoenen zonder data toegevoegd.
- Maak een pure `compute_hall_of_fame()`-helper. Tel per seizoen elke naam in Gold/Silver/Bronze/RedLantern; ties tellen voor iedere genoemde speler. Sorteer op goud aflopend, zilver aflopend, brons aflopend en vervolgens naam voor een stabiele volgorde. Rode lantaarns staan in een aparte kolom en bepalen de sortering niet.
- Baseer de lijst op alle huidige poolspelers (`AllPlayers.csv`), ook met nul prijzen, plus voormalige poolspelers met legacyprijzen. Tool-seizoenen gebruiken alleen eligible spelers uit de awardberekening; reservebenamingen komen nooit als speler in de Hall of Fame. Gebruik `hall_of_fame_check.csv` niet in runtime-appcode.
- Voeg `Seizoenen` en `Hall of Fame` toe aan beide apps. De bestaande NAS-app blijft voor historische data read-only; de tabs in de tweede app zijn vanzelfsprekend ook alleen-lezen.
- Voeg een pytest die de legacytotalen uit `seasons_history.csv` vergelijkt met `hall_of_fame_check.csv` (`Gold`, `Silver`, `Bronze`, `RedLantern`), inclusief spelers met nul prijzen en `InPool`. Lees UTF-8 en behandel niet-voorkomende spelers als nul bij vergelijking.
- Bereken awards voor gesloten tool-seizoenen steeds uit `scores_history.csv`; er worden geen awards in `seasons.csv` of een tweede prijzenbestand opgeslagen. Legacy-awards blijven uit `seasons_history.csv` komen.
- Filter tool-awards eerst op poolnamen in `data/AllPlayers.csv`, rangschik daarna exact zoals `Tussenstand`: gewonnen spellen aflopend, gespeelde spellen aflopend, puntensaldo aflopend en naam als laatste tie-breaker. Ken één speler per goud/zilver/brons toe; de rode lantaarn gaat naar de laatste eligible poolspeler.
- Maak het minimale aantal gespeelde spellen `N` een expliciete constante. Spelers onder die drempel komen niet in aanmerking voor tool-awards. Stel het concrete getal vast vóór implementatie.
- Reserves ontvangen geen tool-awards en verschijnen niet in Hall of Fame. Ze blijven in `Tussenstand` zichtbaar met `*`.
- Breid de whitelists in `github_publish.py` en `publish_mirror.py` uit met `seasons.csv`, `seasons_history.csv` en `seasons_playdays_legacy.csv`. De bestaande NAS-knop uploadt ze via de Contents API vóór workflow-dispatch; de export neemt ze daarna op in de read-only snapshot. Voeg `hall_of_fame_check.csv` aan geen van beide lijsten toe.

**Randgevallen/tests:** legacy-ties, witruimte en accenten, poolspelers met nul prijzen, voormalige spelers met legacyprijzen, spelers onder N wedstrijden, reserve zonder award/Hall-of-Fame-rij, geen lege historische seizoenen en geen runtime-afhankelijkheid van de check-CSV.

### 6. Read-only app en snapshotpublicatie bijwerken

**Bestanden:** `mirror_app/app.py`, `Dockerfile`, `github_publish.py`, `publish_mirror.py`, `docker-entrypoint.sh`, `mirror_app/README.md` en gegenereerde export `docs/`.

- Behoud de geverifieerde gegevensstroom: NAS Contents API-uploads vóór dispatch, daarna workflow checkout, snapshotkopie, Shinylive-export en workflowcommit.
- Breid de upload-whitelist in `github_publish.py` en `SNAPSHOT_FILES` in `publish_mirror.py` uit met `seasons.csv`, `seasons_history.csv` en `seasons_playdays_legacy.csv`. De NAS-knop uploadt de actuele bestanden vóór dispatch naar `data/` op de branch; `publish_mirror.py` kopieert ze naar `mirror_app/data/`.
- Commit de drie seizoens- en testbestanden in Git zodat Portainer’s Stack-from-Git-build ze kan bevatten. Seed alleen de twee historiebronnen naar een ontbrekend `/app/data`-volume. `hall_of_fame_check.csv` wordt nooit gekopieerd door de entrypoint, `github_publish.py` of `publish_mirror.py` en komt nooit in de snapshot.
- Neem de benodigde helpers op in de expliciete `Dockerfile`-copylist voor de NAS-app; de export neemt de pure historiehelper mee als onderdeel van de app.
- Werk de read-only app bij met de nieuwe Seizoenen- en Hall-of-Fame-tabs en filters. De app gebruikt snapshots; zij schrijft geen data.
- Werk `mirror_app/README.md` bij voor de nieuwe tabs en snapshots; pas de UI-benoemingen en exportmetadata al in de tekststap 1 aan.
- Genereer `docs/` vanuit de appbron en `publish_mirror.py`; handbewerk de gegenereerde runtimebestanden niet.
- Houd de CSS-injectie in `publish_mirror.py` compatibel met de marker in de geëxporteerde appbron.

**Randgevallen/tests:** alle genoemde CSV’s zijn beschikbaar na export, bestaande snapshotregels blijven intact, de check-fixture komt nooit in de snapshot en de export houdt Shinylive/Pyodide-compatibiliteit.

### 6. README en documentatie

**Bestanden:** `README.md`, eventueel `mirror_app/README.md`.

- Werk de root-README in dezelfde featurewijziging bij: season register/kolommen, migratie en behoud van `/app/data`, seizoensfilters, legacy-overzichten, Hall of Fame, score-per-spel, reserveweergave en snapshotbestanden.
- Houd de uitgebreide README-beschrijving in lijn met de in stap 1 aangepaste Nederlandse producttekst; behoud technische bestands- en workflowreferenties waar nodig.
- Werk de gebruikersinstructies in `mirror_app/README.md` gelijk op met de gewijzigde Nederlandse producttekst en exportstappen.
- Beschrijf de datamigratie, `MANILLEN_DATA_DIR`, de handmatige kopie van de volledige map `/volume1/manillen_data` naar een veilige backup-locatie vóór de eerste redeploy, testisolatie en dat de check-CSV alleen testdata is. README-aanpassingen voor ieder featureonderdeel moeten in dezelfde implementatiestap/change worden opgenomen; dit laatste documentatiestapje controleert de integrale projectbeschrijving.

## Implementatievolgorde: afzonderlijke chat-/teststappen

1. **User-facing bewoordingen (tekst-only):** vervang de zichtbare verwijzingen in beide app-bronnen en de README’s, behoud **Publiceer data** en alle technische identifiers, regenereer alleen tekstgerelateerde exportoutput indien nodig. Geen nieuwe tabs of dataflow.
2. **Reserveweergave:** naamresolutie in score-invoer en tussenstand; asterisk en voetnoot; waarschuwing bij poolnaam als reservenaam; gerichte tests voor datum/slot en cumulatieve aggregatie.
3. **Per-spel opslaan:** opslaghelper op `(Date, Table, Game)`, per-spelknoppen en reactieve standverversing; tests voor partials, herhaald opslaan en overschrijven.
4. **Data-isolatie en seizoensmigratie:** `MANILLEN_DATA_DIR`, dev-requirements en Docker-exclusie van tests; commit-/seedvoorbereiding; verplichte backup, veilige idempotente migratie en tests voor oude CSV’s/backups.
5. **Seizoenen op de NAS:** seizoenkeuze en filters, nieuw seizoen met eindstandpreview en bevestiging, afsluiten/heropenen; awardberekening uit scores, poolfilter, N-drempel en tests voor prijzen/reopen.
6. **Seizoenen- en Hall-of-Famepagina’s:** UTF-8-historische overzichten, twee NAS-tabs, legacy Hall of Fame-test tegen `hall_of_fame_check.csv` en awards van afgesloten tool-seizoenen.
7. **Read-only app, snapshots en README:** snapshot-allowlists/API-upload, seedgedrag, nieuwe tabs, export naar `docs/`, test-fixture uitsluiten van publicatie; documenteer alle gedrags-/datamodelwijzigingen en de handmatige NAS-backup.

Elke stap is afzonderlijk te testen en te reviewen. Werk bestaande CSV’s alleen via expliciete, behoudende migratie-/updatefuncties bij; testdata gebruikt tijdelijke directories. Werk de README in dezelfde stap bij wanneer die functionaliteit, data, deployment of workflows beschrijft; documentatie wordt niet tot stap 7 uitgesteld. `data/seasons_history.csv`, `data/seasons_playdays_legacy.csv` en `data/hall_of_fame_check.csv` zijn opgenomen in Git en worden niet door `.gitignore` uitgesloten.

## Testplan

Voeg `requirements-dev.txt` met pytest en een kleine testsuite toe, bijvoorbeeld `tests/test_seasons.py`, `tests/test_score_functions.py` en `tests/test_reserve_assignments.py`. Stel voor tests `MANILLEN_DATA_DIR` in op tijdelijke paden; voer alle reads/writes van de app tijdens tests tegen fixtures in die tijdelijke map uit. Kopieer benodigde Hall-of-Fame-testbronnen naar testfixtures in `tmp_path`; raak de echte `data/`-bestanden nooit aan. Sluit `tests/`, `requirements-dev.txt` en `data/hall_of_fame_check.csv` uit van de Docker image via `.dockerignore`; de testfixture blijft wel gecommit en lokaal beschikbaar voor pytest.

- **Data-pad:** zonder `MANILLEN_DATA_DIR` blijft de huidige `data/`-directory de default; met override lezen/schrijven alle NAS-persistentiehelpers uitsluitend de tijdelijke testmap.
- **Migratie/backup:** oude headers zonder `Season` laden; bestaande rijen en velden blijven behouden met `2026-2027`; tweede run is idempotent; bestaande seizoenslabels blijven gelijk; backup wordt bij eerste migratie één keer gemaakt en een reeds bestaande backup wordt nooit overschreven; schrijf via tempbestand en replace pas na succes. Verifieer in README ook de handmatige kopie van `/volume1/manillen_data` vóór de eerste redeploy.
- **User-facing tekst:** stap 1 haalt zichtbare wording uit beide apps, root-README, mirror-README en export; knop **Publiceer data** en technische identifiers blijven bestaan.
- **Compatibiliteit:** laad expliciet een oud `pairings_history.csv` zonder `Season` via zowel NAS- als mirrorhelper.
- **Aanmaken/filteren:** default is actieve season; keuze van ander season wordt opgeslagen; datumfilter beperkt resultaten tot de ene datum; lege historische scores geven geen cross-season resultaten.
- **Scores:** per-spel save bij incomplete dag, geen save met onvolledige teamscore, dezelfde key tweemaal opslaan laat één rij over, edit vervangt alleen het betreffende spel, scores van andere spellen blijven intact en een save ververst de tussenstand.
- **Reserves:** assignment wordt gekoppeld met `Date` + `Slot`, namen blijven datumgebonden, UI toont naam met ster en voetnoot, ontbrekende assignment geeft placeholder, reserve komt nooit in tool-awards of Hall of Fame, invoer van een `AllPlayers.csv`-naam geeft waarschuwing.
- **Historie/Hall of Fame:** beide legacy-CSV’s UTF-8; ties tellen voor elke speler; test alle Hall-of-Fame-totalen inclusief nulspelers en `InPool` tegen `hall_of_fame_check.csv`.
- **Tool-awards:** gesloten season awards berekend uit scores; alleen poolnamen, volgorde wins/games/saldo/naam, één per medaille, rode lantaarn laatste eligible poolspeler; onder N games niet eligible; expliciete tests dat reserve nooit een medaille krijgt en N-grens wordt toegepast.
- **Nieuw/heropen seizoen:** preview moet vóór afsluiten zichtbaar zijn; bevestiging sluit oud seizoen en maakt nieuw seizoen actief; `Heropen seizoen` herstelt status en awards blijven uit scores afgeleid. Test de veilige omgang met de reeds actieve opvolger.
- **Publicatie en regressie:** controleer de snapshotlijst en exportbron, bevestig dat de check-CSV niet wordt opgenomen, en run de gerichte pytest-bestanden plus een Shinylive-exportcheck wanneer mirrorbestanden wijzigen.

## Risico’s en bevestigde besluiten

- `Geschiedenis` krijgt alleen een seizoensfilter; de specifieke speeldagfilter blijft bij `Tussenstand`.
- `Nieuw seizoen` toont een bevestigingspreview, sluit daarna het huidige actieve seizoen en maakt het nieuwe seizoen actief.
- Seizoenslabels mogen vrij worden aangepast; `SeasonStartYear` blijft de bron voor het volgende jaarvoorstel.
- Tool-awards zijn afgeleid van scores en poolnamen; ze worden niet als tweede bron opgeslagen.
- `N` is 3 gespeelde spellen; spelers met minder spellen zijn niet eligible voor een tool-award.
- Bij heropenen wordt alleen toegestaan als er geen later actief seizoen bestaat. Anders wordt de actie geweigerd en blijft alle data behouden.
- De huidige lijst in `AllPlayers.csv` bepaalt poollidmaatschap voor tool-awards, ook voor afgesloten seizoenen.
- Tool-seizoenen gebruiken een unieke rangschikking; alleen legacy-ties tellen als award voor iedere genoemde speler.
- Bij minder dan vier eligible poolspelers mag dezelfde speler zowel een medaille als de rode lantaarn krijgen.
- Het optionele heatmap-idee voor Parenhistoriek is volledig buiten scope; die pagina blijft ongewijzigd.
- Hall of Fame toont alle huidige poolspelers, ook zonder prijzen, en voormalige poolspelers met legacyprijzen. Legacy-ties tellen voor alle betrokken spelers.
- De drie seizoens-/test-CSV’s zijn al opgenomen in Git en niet genegeerd; de check-CSV blijft alleen voor tests en wordt niet gekopieerd of gepubliceerd.
- De geverifieerde workflow ontvangt actuele NAS-data via de GitHub Contents API vóór dispatch; de workflow zelf gebruikt de uitgecheckte branch.
- README-onderhoud gebeurt per relevante featurewijziging, niet pas als een laatste bulk-update.
- De tests en importsmoketest gebruiken tijdelijke data via `MANILLEN_DATA_DIR`; de echte `/app/data`-mount is tijdens validatie niet gemigreerd. Maak vóór de eerste NAS-redeploy de afgesproken handmatige backup en controleer de eerste migratie op de NAS.
