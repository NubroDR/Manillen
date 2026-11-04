# Implementatieplan v3: snelle statische mirror, Speeldagen, ID's en spelersprofielen

**Status:** implementatie gestart — Fase 0 en Fase 1 niet volledig afgerond; statische preview live; Speeldagen-W-L-weergave lokaal geïmplementeerd, previewacceptatie open
**Scope:** publieke read-only mirror (herbouw als statische site), gedeelde berekeningen, centrale referentiedata, Speeldagen-rangschikking, spelersprofielen en mobile-first ontwerp.  
**Belangrijke randvoorwaarde:** bestaande gebruikersdata in `data/` blijft onaangeroerd totdat een migratie expliciet is goedgekeurd, geback-upt en geverifieerd.

### Overdracht voor volgende sessie (2026-10-25)

- **Speeldagen-weergave lokaal afgerond (2026-11-04):** per tafel staan de spelers verticaal met hun W-L-resultaat; de gedeelde `compute_standings`-berekening levert de tabelspecifieke waarden. Speeldagen bevat geen matchups of ruwe scores meer; de detailuitslagen blijven op Scores. De desktop-grid en mobiele stapeling zijn lokaal in de browser gecontroleerd; de aangepaste build is nog niet op de preview uitgerold.
- De desktop-grid staat al live in de aparte preview: commit `30d631f` / Pages-run `40219277473`. Vier tafels naast elkaar op 1440 px, drie op 1024 px; op 900 px en smaller gestapeld. Productie-URL `/Manillen/` en hoofdrepo-`docs/` zijn niet aangepast.
- De previewwijziging is door browsercontrole bevestigd op 1440, 1024, 900, 768, 390 en 360 px zonder horizontale overflow. `.venv\Scripts\python.exe -m pytest tests\test_static_snapshot.py` slaagde: 12 passed.
- De hoofdwerkboom bevat veel al bestaande wijzigingen uit de implementatie. Controleer `git status` bij hervatten; behoud deze wijzigingen en commit niet de volledige werkboom als onderdeel van een kleine vervolgtaak. De previewwijziging is apart gecommit in `NubroDR/manillen-preview`; root-code en plannen staan lokaal gewijzigd/ongetrackt.
- **Daarna nog open:** previewacceptatie van deze wijziging; overige Fase 2-acceptatie; Fase 0 Lighthouse/Slow-4G-meting en budget; resterende Fase 1-acceptatie en uiteindelijke productie-`docs/`-controle; expliciete productiecutovergoedkeuring (F1-46); daarna ID-migratie, ID-gebaseerde schrijfstromen en spelersprofielen (Fase 3–5). Geen migratie toepassen op de echte `data/` zonder goedgekeurde mapping, backup en aparte toestemming.

### Voortgang Fase 0 (2026-10-25)

- Geïmplementeerd: `profile_data.py` rapporteert read-only JSON; namen zijn standaard geredigeerd en alleen expliciet met `--include-names` zichtbaar. De commandoregel is getest op synthetische data en op een tijdelijke kopie van de repository-CSV's. SHA-256-hashes van de bronbestanden bleven gelijk.
- Geïmplementeerd: handberekende klassementbaselines per seizoen en speeldag, genormaliseerde partnercounts en het huidige gedrag voor een gescoorde speler buiten de pool zijn met pytest vastgelegd.
- Nulmeting: `docs/` bevat 66 bestanden (38.949.823 bytes). De live site registreert `shinylive-sw.js` met scope `/Manillen/`; `/Manillen-preview/` valt buiten die scope. Dit is geen gecontroleerde Lighthouse- of Slow-4G-meting.
- Dataprofilering op de tijdelijke kopie: 0 schema-issues, 0 dubbele poolgroepen, 0 schrijfwijzegroepen, 5 onbekende naamgroepen, 0 ongeldige reserveslots, 0 gelijke scores en 0 verschillen tussen partnercounts en pairing history. De waarden zijn niet als rapport met namen opgeslagen.
- De inventaris levert 11 imports uit `mirror_app/` op en de voorlopige versioned CSV-kandidaten staan in de profileringsuitvoer.
- Nog open: gecontroleerde Lighthouse-meting koud/warm op mobiel met Slow 4G en de prestatiebudgetbeslissing op basis daarvan. Fase 0 is daarom nog niet afgerond.

### Voortgang Fase 1 (2026-10-25)

- Geïmplementeerd: pure helpers staan in `manillen_core/`; bestaande `mirror_app/*_helpers.py` zijn compatibiliteits-shims en de NAS-app importeert uit de gedeelde kern.
- Geïmplementeerd: `generate_static_snapshot.py` bouwt een deterministische JSON-snapshot en `build_static_site.py` assembleert de zes views als statische preview. Uitvoer moet naar een nieuwe/lege map. De nieuwe site is alleen naar de afzonderlijke previewrepo gedeployed; productie-`docs/` is niet aangepast.
- Geïmplementeerd en op HTTPS-preview gecontroleerd: `service-worker-cleanup.js` schrijft alleen de legacy Shinylive-worker voor het huidige app-pad uit en verwijdert de bijbehorende cache-items. Fouten worden zichtbaar gemeld.
- De NAS-publicatiecode verpakt de afgeleide JSON in één `static_snapshot.zip`, zodat de actieve snapshot als één GitHub-bestand wordt bijgewerkt; de workflow start pas na een geslaagde upload. Dit vervangt de oorspronkelijk beschreven set JSON-uploads met manifest als laatste stap door een atomische archiefupload. De Actions-workflow is omgezet naar statische assemblage zonder Shinylive, maar is nog niet uitgevoerd.
- Geautomatiseerd: volledige pytest-suite groen (`49 passed`), inclusief gedeelde helper-pariteit op fixtures, determinisme, stdlib-only generatie, brondatahashes, weigeren van overschrijven, JSON-schema/integriteitscontrole en de mock-uploadflow. De Shiny-app importeert succesvol met geïsoleerde fixturedata.
- Browser op synthetische fixturedata: alle zes routes, filter op alle seizoenen/speeldag/speler (incl. ingevulde reserve), directe route en refresh, terugnavigatie, mobiele navigatie/focus, foutmelding bij ontbrekende JSON, XSS-tekstweergave en netwerkverzoeken uitsluitend naar dezelfde origin zijn gecontroleerd. Geen pagina-JavaScriptfouten op normale routes.
- Mobiele preview: op 360, 375, 390, 768 en 1280 px is op alle zes routes geen horizontale pagina-overflow gezien.
- Extra pariteitscontrole op de bestaande, gepubliceerde `mirror_app/data`-snapshot: alle 11 seizoensindexitems, klassementen en awards, alle 33 scores, 3 actieve speeldagen met tafels/reserves, 8 legacy-speeldagrijen, Hall of Fame en parentellingen kwamen overeen met de gedeelde helpers. De invoerbestanden bleven byte-identiek; dit is geen controle van de NAS-datamap.
- Browser op dezelfde bestaande snapshot: alle zes routes werkten onder `/`, `/Manillen/` en `/Manillen-preview/` (18 routecombinaties); op 390 px waren alle views gevuld zonder horizontale overflow, externe-originresources, HTTP-fouten of JavaScriptfouten.
- De volledige lokale build bevatte 3 site-assets en 16 JSON-bestanden, zonder CSV of andere bestandstypen. De geschatte gzip-grootte van HTML/CSS/JS, manifest en actief seizoen samen was 10.628 bytes (48.691 bytes onbewerkt); dit is een bestandsschatting, geen Lighthouse- of netwerkmeting.
- Publisher-tests bevestigen dat alleen het JSON-archief wordt geüpload, dat een mislukte upload geen workflowdispatch doet, en dat ongeldige archiefpaden of gewijzigde inhoud vóór assemblage worden geweigerd. De Dockerfile bevat nu ook de snapshotgenerator en gedeelde helpers die de NAS-publicatie gebruikt.
- De actuele volledige pytest-suite slaagt (`52 passed`); de gerichte statische-snapshottest slaagde eerder ook (`12 passed`) en de legacy-startuphelper heeft drie gerichte tests. De build uit de bestaande publieke snapshot bevat 20 bestanden: `index.html`, `styles.css`, twee JavaScript-bestanden en 16 JSON-bestanden, zonder CSV's.
- Previewstatus: de repository `NubroDR/manillen-preview` is publiek en de bestaande openbare Shinylive-export is in commit `5f55946` bewaard als worker-testbasis. De statische preview is hersteld in commit `e89ec4c` (Pages-run `40214498388`). Na rollback bevatte de eerste helperiteratie een `navigator.serviceWorker.ready`-timeout; de daaropvolgende browserproef vond een top-level `return`-syntaxfout. De definitieve helper is in Pages-run `40214417333` gevalideerd: na verwijdering van alleen de previewregistratie registreerde de eerste load de worker, wachtte op activatie en herlaadde eenmaal; daarna was de Shinylive-viewer gemount en waren controller, registratie en foutloze console bevestigd. Na herstel van de statische preview verdween `/manillen-preview/`, bleef `/Manillen/` actief en was de cachelijst leeg. F1-44 is hiermee op preview geslaagd.
- Browseracceptatie preview: zes routes laden inhoud op HTTPS zonder console- of HTTP-fouten; 30 route-/viewportcombinaties (360, 375, 390, 768 en 1280 px) hadden geen overflow. Op 360 px waren alle zichtbare links/knoppen/inputs/selects minimaal 44×44 px, invoervelden minstens 16 px; het hamburgermenu opende en sloot met Escape. De bestaande productie-URL bleef de Shinylive-site tonen.
- Previewfeedback voor Fase 1: expliciete licht/donker-toggle toegevoegd met licht als standaard en themaopslag in de browser; oude OS-voorkeur voor donker overschrijft de lichtere weergave niet meer. Medaille-emoji's, rode lantaarn en de zachte goud/zilver/brons/lantaarn-achtergronden voor klassementen en awardkolommen zijn teruggebracht. Ook is assetfingerprinting toegevoegd zodat CSS/JS-wijzigingen zichtbaar worden bij een ongewijzigde JSON-snapshot. Lokale browsercontrole: alle zes routes op 360, 375, 390, 768 en 1280 px zonder overflow; toggle bleef op 360 px 44×44, keuze en gekleurde rijen bleven na refresh behouden. Previewcommit `7b124ba` / Pages-run `40217686913` slaagde; op de live preview zijn licht als standaard, persistente toggle, medaille-rijen, gekleurde Hall-of-Fame-kolommen en geen overflow op 360 px bevestigd. Productie blijft onaangeroerd.
- Speeldagen kreeg een desktop-only compacte grid vanaf 901 px: tafelkaarten vullen automatisch één tot vier kolommen afhankelijk van de beschikbare breedte; mobiel blijft onder elkaar. Previewcommit `30d631f` / Pages-run `40219277473` slaagde. Op de live preview zijn 4 kolommen op 1440 px, 3 op 1024 px en gestapelde kaarten op 900 px en mobiel bevestigd, telkens zonder horizontale overflow. Productie is niet aangepast.
- Nog open: gecontroleerde Lighthouse-/Slow-4G-meting en prestatiebudget; handmatige echte-telefooncontrole; F1-15 op de uiteindelijke productie-`docs/`; en expliciete cutovergoedkeuring (F1-46). De NAS-publicatieworkflow en de hoofdrepo-Pages-workflow zijn nog niet uitgevoerd; alleen de previewworkflow is gevalideerd. `actionlint` is niet beschikbaar. De productie-URL en `docs/` zijn niet aangepast.

## 0. Wijzigingen ten opzichte van v1

| # | Wijziging | Reden |
|---|---|---|
| 1 | De mirror wordt **herbouwd als statische site** (Python genereert JSON bij publicatie, vanilla JS toont het). Dit komt vóór de ID-migratie. | De huidige Shinylive-pagina laadt al traag (Pyodide in elke browser). Dit is het grootste mobiele probleem en lost zich niet op met CSS. |
| 2 | Berekeningen verhuizen naar een **gedeelde Python-kern** die hoofdapp en generator beide gebruiken. | Geen dubbele rekenlogica; de hoofdapp importeert nu al uit `mirror_app/`, wat de herbouw anders blokkeert. |
| 3 | Deep links worden **hash-routes** (`#/speler/<PlayerID>`) in plaats van query string + `pushState`. | Geen Shinylive-iframe meer; back/forward, refresh en delen werken zonder server-side routeconfiguratie. |
| 4 | Fase 0 bevat een **meting van de huidige laadtijd** en een beslismoment. | Geeft een objectieve baseline voor de acceptatiecriteria. |
| 5 | Speeldagen-rangschikking staat **vóór** de ID-migratie. | Heeft geen ID's nodig en levert eerder zichtbare waarde op. |
| 6 | Het **ID-model wordt slanker** (besloten). | `playdays.csv`/`playday_players.csv` dupliceren bestaande data; compatibele exports zijn een tweede schrijfroute. |
| 7 | **Migratie-atomiciteit** gebruikt versioned staging en één atomische activatieschakel; de container staat tijdens apply stil. | Per-bestand vervangen of alleen een eindmarker schrijven maakt een set bestanden niet atomair. |
| 8 | Regels gecorrigeerd: **plaats vs. naam**, tonen van saldo, behandeling van bestaande gelijke-score-rijen, `pairings.csv`-drift, `PoolMember=0` in Tussenstand. | Interne tegenstrijdigheden en ontbrekende definities in v1. |
| 9 | Privacy: `noindex`, alleen **afgeleide** data publiceren, vriendelijke toon van partner-/tegenstanderstatistieken. | Publieke site met familienamen. |
| 10 | Mobiele review is nu een **ontwerpeisenlijst** voor de nieuwe mirror, aangevuld met donkere modus, laadindicator, automatische overflow-test en testen op echte telefoon zonder HTTPS-gedoe. | De oude CSS-fixes aan Shiny/Bootstrap vervallen grotendeels. |
| 11 | **Rollback is begrensd** tot vóór nieuwe invoer; het versioned datamodel bevat alleen de gemigreerde CSV's; verouderde root-bestanden en publicatiepaden worden bewaakt. | Na activatie schrijft de app in de nieuwe versie; terugschakelen zou latere invoer anders stil weggooien of verouderde data publiceren. |
| 12 | **Service worker-opruiming** en een preview-locatie bij de cutover. | De oude Shinylive-worker kan in browsers van terugkerende bezoekers de oude pagina's blijven serveren. |
| 13 | Reserve-token wordt **`RESERVE:n`** (niet vast 1–3); ID-ruimte-analyse teruggebracht tot een collisiecheck; resterende verwijzingen opgeschoond. | Meer dan drie tafels moet kunnen; tientallen spelers vragen geen ruimteanalyse. |
| 14 | **Schattingen herzien**: Fase 1 5–7 dagen, Fase 3 5–8 dagen, totaal ca. 19–31 dagen. | Het versioned datamodel maakt Fase 3 aanzienlijk zwaarder. |
| 15 | **Definities vastgelegd:** dubbele spelrij, toekomstige speeldag, reserves in de tafelrangschikking en winstpercentage bij 0 spellen; winstreeksen vallen af. | Tests moeten tegen eenduidig gedrag kunnen worden geschreven. |

## 1. Repositorybevindingen

### Apps en gegevensstromen

- `app.py` is de schrijfbare NAS-app. Indelings- en Excel-logica staat in `manillen_functions.py`, score-opslag en scoreberekening in `score_functions.py`, reserve-opslag in `reserve_assignments.py`.
- `mirror_app/` is nu een afzonderlijke read-only Shiny-app die snapshots uit `mirror_app/data/` leest. Pure helpers staan in `mirror_app/data_helpers.py`, `score_helpers.py` en `season_helpers.py`. **De NAS-app importeert al helpers uit `mirror_app/`**: die koppeling moet worden losgemaakt voordat `mirror_app/` kan verdwijnen (Fase 1).
- `data_paths.py` gebruikt `Path(__file__).resolve().parent` met `MANILLEN_DATA_DIR` als optionele override.
- `github_publish.py` genereert en uploadt een JSON-only archief vanaf de NAS en start `publish-mirror.yml`; `publish_mirror.py` assembleert dat archief in de workflow-checkout naar `docs/`. De live Pages-site is nog de bestaande Shinylive-export. GitHub Pages wordt gedeployed via `.github/workflows/deploy-pages.yml`; de publieke URL is `https://nubrodr.github.io/Manillen/` en moet **stabiel blijven**.
- `docker-entrypoint.sh` kopieert alleen ontbrekende seedbestanden naar `/app/data`; bestaande bestanden worden niet overschreven.
- Er bestaat een pytest-suite onder `tests/`; `tests/conftest.py` isoleert testdata met `MANILLEN_DATA_DIR`.

### Huidige bronnen met namen en herhaalde waarden

| Bestand of bron | Huidige inhoud |
|---|---|
| `data/AllPlayers.csv` | Poolnamen, één naam per regel, geen header. |
| `data/pairings.csv` | `Player1`, `Player2`, `Count`; ongesorteerde namenparen met actuele telling. |
| `data/pairings_history.csv` | `Date`, `Table`, `Players`, `Season`, `Location`; vier namen in één veld. |
| `data/scores_history.csv` | `Date`, `Table`, `Game`, `Team1Players`, `Team2Players`, `Team1Score`, `Team2Score`; vrije tekst. |
| `data/reserve_assignments.csv` | `Date`, `Slot`, `Name`. |
| `data/seasons.csv` | `Season`, `SeasonNumber`, `SeasonStartYear`, `Status`. |
| `data/seasons_history.csv` | Legacy-awardkolommen met spelersnamen. |
| `data/seasons_playdays_legacy.csv` | Legacy-seizoen, datum, locatie, aantal aanwezigen; geen namenlijst per speeldag. |
| `data/Scorebladen.xlsx`, `data/Scorebladen/` | Template en gegenereerde Excelbestanden met namen. |

Tafels, spellen en reserve-slots zijn posities binnen een speeldag, geen eigen entiteiten. Seizoenen behouden hun labels en nummers; er komt geen apart SeasonID.

### Mirror-oppervlakken met spelersnamen (alle worden profiel-links in Fase 5)

Deelnemerskaarten Speeldagen, teams in Scores, spelersrijen Tussenstand, Parenhistoriek, awards in Seizoenen, Hall of Fame, en spelerkeuzes in filters (Scores, Parenhistoriek). Resultaten en tabellen krijgen echte links; filterkeuzes blijven filters met een aparte actie **Open profiel**.

### Historische datadekking

Legacyseizoenen bevatten prijzen en speeldagmetadata, maar geen scorehistorie of deelnemerslijsten per speeldag. Eindposities, rankingverloop, aanwezigheid en head-to-head worden daarom alleen getoond waar individuele score- en deelnemersdata bestaat; anders staat er "niet beschikbaar", nooit een afleiding.

## 2. Architectuur van de nieuwe mirror

```
NAS-app → github_publish.py → generate_static_snapshot.py (actieve data via data_paths.py)
             ├─ gedeelde Python-kern (manillen_core/)
             └─ genereert een gevalideerde, buildId-gemarkeerde publieke JSON-snapshot
github_publish.py uploadt alleen die JSON in één static_snapshot.zip → workflow_dispatch
GitHub Actions gebruikt publish_mirror.py om de site naar docs/ te assembleren; leest geen bron-CSV's
Browser: laadt index.html + css + js (klein), haalt per tab/seizoen alleen de benodigde JSON op.
```

**Principes**
- **Eén berekening, in Python.** De browser doet alleen weergave en filteren. Geen kopie van klassement- of profiellogica in JavaScript.
- **Scheiding tussen genereren en deployen.** `publish_mirror.py` draait op de NAS en leest de actieve versie via `data_paths.py`. `github_publish.py` uploadt uitsluitend de daaruit gegenereerde publieke JSON-snapshot. De GitHub Actions-workflow assembleert/deployt de statische site en voert geen generator uit op ruwe CSV's of de NAS-datastore.
- **Consistente snapshotpublicatie.** De JSON-bestanden en manifest gaan in één `static_snapshot.zip` met `buildId`. De GitHub Contents API vervangt één bestand, zodat een mislukte upload de vorige archiefversie laat staan; de dispatch volgt pas na geslaagde upload. GitHub Actions controleert de manifesthash vóór assemblage.
- **Alleen afgeleide data publiceren.** Geen ruwe CSV's meer in `docs/`; alleen de JSON die de pagina's nodig hebben (kleinere payload en smallere publicatie-oppervlakte, maar nog steeds publiek opvraagbaar).
- **Publiek betekent opvraagbaar.** Alle JSON onder GitHub Pages is rechtstreeks toegankelijk voor iedereen; `noindex` is alleen een indexeringsverzoek en geen privacy- of toegangsbeveiliging.
- **Geen framework en geen build-stap.** Vanilla ES-modules, native `<select>`, echte `<a>`-links, `<table>` met semantische headers. Alle namen en teksten uit data worden als tekst ingevoegd (`textContent`), nooit als ruwe HTML.
- **Hash-routing:** `#/tussenstand?seizoen=…`, `#/speeldagen`, `#/speler/<PlayerID>`. Werkt op GitHub Pages zonder 404-trucs; back/forward en delen werken vanzelf.
- **Voorgestelde JSON-indeling** (definitief vast te leggen in Fase 1): `manifest.json` (buildId, gegenereerd op, actief seizoen, seizoenslijst), `players.json` (alleen publieke velden), `seasons/<seizoen>.json` (klassement, speeldagen met tafels en W-L, scores), `pairings.json`, `hall-of-fame.json`, `players/<key>.json` (profielen, vanaf Fase 5).
- **Cachebusting:** assets en data met versie uit `buildId`, omdat GitHub Pages korte HTTP-cache hanteert.
- **Spelersleutel:** tot de ID-laag bestaat is de sleutel in de JSON de (genormaliseerde) naam; na Fase 3 wordt het de `PlayerID`. De generator leest namen en ID's uitsluitend via één adapter, zodat die overgang klein blijft.
- **Datum "vandaag":** de browser bepaalt "gepasseerd" met `Intl.DateTimeFormat` in `Europe/Amsterdam`; de generator publiceert enkel feiten (datum, volledigheid, W-L).
- **Prestatiebudget (voorstel, definitief na de meting in Fase 0):** eerste bezoek op mobiel met Slow 4G throttling: inhoud zichtbaar binnen ca. 2 s; eerste transfer (HTML, CSS, JS, manifest en eerste data) ca. 150 KB gecomprimeerd; geen externe domeinen (systeemfonts of lokaal gehoste subset); Lighthouse mobiel ≥ 90 performance en ≥ 95 accessibility.
- **Indexering:** gebruik `<meta name="robots" content="noindex">` als verzoek om pagina's niet te indexeren. `robots.txt` is geen toegangsbeveiliging en `Disallow: /` kan verhinderen dat crawlers de `noindex`-meta zien; voeg die regel daarom niet standaard toe. Alle gepubliceerde HTML en JSON blijft publiek opvraagbaar.

## 3. Afgestemde keuzes en resterende technische aannames

### Afgestemd in v1 (blijft gelden, tenzij hieronder gewijzigd)

1. Profielen komen eerst alleen in de publieke read-only mirror.
2. De oorspronkelijke profielwensen zijn geïnventariseerd; de MoSCoW-indeling in Fase 5 bepaalt welke onderdelen in de eerste release komen. Legacydata zonder individuele uitslagen of deelnemerslijsten levert geen gereconstrueerde profielstatistieken op.
3. Reserve-optredens mogen publiek verschijnen nadat een reservepersoon expliciet aan een PlayerID is gekoppeld.
4. ~~Deep links met queryparameter en `pushState`~~ → **gewijzigd:** hash-routes op de statische site (zie §2).
5. Speeldagentafels tonen enkel gewonnen-verloren (W-L), zonder saldo. **Besloten:** de *plaats* wordt bepaald door (gewonnen, gespeeld); gelijke waarden delen een plaats (bv. drie spelers met 1-2 staan allemaal op plaats 2). De naam bepaalt alleen de weergavevolgorde binnen een gedeelde plaats. Dit wijkt bewust af van de Tussenstand, die wel op saldo sorteert.
6. "Gepasseerd" = datum vóór vandaag in `Europe/Amsterdam`; vandaag blijft actueel. Een toekomstige speeldag is niet gepasseerd en toont geen rangschikking.
7. Onvolledige dagen blijven zichtbaar met een onvolledig-label en gebruiken enkel beschikbare geldige scores. Een **dubbele spelrij** (dezelfde datum, tafel en spelnummer meerdere keren) wordt niet meegeteld en markeert de tafel als onvolledig met een zichtbare waarschuwing; het bronbestand wordt niet aangepast. In de tafelrangschikking tonen gekoppelde reserves hun naam; niet-gekoppelde reserves verschijnen als placeholdertekst zonder link.
8. Stabiele IDs voor spelers en locaties; seizoenen behouden labels en nummers.
9. ID-canonieke bestanden zijn de bron van waarheid. **Besloten (beslissing 5):** de naamgebaseerde CSV's worden niet als compatibele export behouden; ID-verwijzingen volstaan voor back-end gebruik. Namen worden alleen via de adapterlaag opgelost.
10. Een reservepersoon kan een eigen PlayerID krijgen maar is geen lid van de standaardpool tenzij expliciet gewijzigd; `Reserve 1` blijft een placeholder zonder ID.
11. Historische naamvarianten via expliciete aliastabel en handmatige review; geen fuzzy samenvoeging.
12. Namen en locaties worden beheerd met een offline commando (dry-run, backup, verificatie); geen editor in de mirror, geen onbeveiligde beheer-UI in de NAS-app.
13. Bestaande Excelbestanden blijven onveranderde snapshots; nieuwe scorebladen gebruiken actuele namen.
14. ID's veranderen nooit na een naamwijziging. **Besloten (beslissing 6):** kort en leesbaar formaat zonder verwarrende tekens, zie §4.
15. Gelijke scores zijn volgens de spelregels niet mogelijk en worden in nieuwe invoer geweigerd. **Aanvulling:** bestaande rijen met gelijke score worden gerapporteerd, niet aangepast, en in W-L-berekeningen als "ongeldig" gemarkeerd (telt niet als gewonnen of gespeeld).

### Besluiten voor deze planversie

| # | Beslissing | Vastgelegde keuze |
|---|---|---|
| 1 | Herbouw als statische mirror | Besloten: ja; Fase 0 meet de baseline. |
| 2 | Naam van de gedeelde kernmodule | `manillen_core/`; tijdelijke re-export-shims totdat NAS-app en tests zijn overgezet. |
| 3 | Uitvoermap | Besloten: `docs/` blijft de GitHub Pages-bron; gegenereerde site wordt gecommit en rollback gebeurt via git revert. |
| 4 | Publieke export | Alleen afgeleide JSON, geen ruwe CSV's. Alle geplande JSON-data is publiek opvraagbaar; `noindex` beperkt dit niet. |
| 5 | Naamgebaseerde CSV's na ID-migratie | Besloten: geen compatibele naamexports. ID-waarden vervangen namen in actieve bestanden; uitzonderingen en reservecodering staan in §4. |
| 6 | ID-formaat | Besloten: korte willekeurige ID's met typeprefix; levenscyclus en collisiecontrole staan in §4. |
| 7 | Tafelrangschikking | Besloten: W-L tonen; plaats bepalen op (gewonnen, gespeeld), zonder saldo; naam alleen als weergavevolgorde. |
| 8 | Donkere modus | Opnemen via `prefers-color-scheme`; animaties respecteren `prefers-reduced-motion`. |
| 9 | Toon van profielstatistieken | Positieve formulering; geen stigmatiserende labels zoals "nemesis" of "slechtste partner" in de eerste release. |
| 10 | Benoemde reserves (`PoolMember=0`) in Tussenstand | Huidig gedrag blijft; gedrag wordt in de Fase 0-baseline vastgelegd. |
| 11 | Onderbroken ID-migratie | Besloten: versioned staging en atomische activatie; de vorige dataset blijft actief en rollbackbaar. |
| 12 | Profiel-MoSCoW | De MoSCoW-indeling in Fase 5 bepaalt de eerste release: Must en Should inbegrepen; Could buiten de eerste release tenzij later apart goedgekeurd. |
| 13 | Testtools | Playwright en Lighthouse zijn optionele lokale/dev-tools, geen runtime-dependencies; CI-installatie is niet vereist voor de eerste implementatie. |

### Aannames die tijdens implementatie nog bevestigd of geverifieerd moeten worden

- Huidige laadtijd en bundelgrootte worden in Fase 0 gemeten; de statische herbouw is besloten, de meting bepaalt de prestatiebaseline en helpt het budget te valideren.
- De scorevalidator mag gelijke scores weigeren zonder bestaand legitiem gebruik te breken; bestaande rijen worden eerst gerapporteerd en niet aangepast.
- Score- en deelnemersdata zijn via datum, tafel en spel eenduidig aan ID's te koppelen; afwijkende rijen blijven in het migratierapport.
- `pairings.csv` komt overeen met de uit `pairings_history.csv` afgeleide tellingen (Fase 0 controleert dit; bestaande drift moet bekend zijn vóór "vóór/na identiek" iets bewijst).
- Het previewproject `Manillen-preview` is publiek (Pages op een privé-repo vraagt een betaald plan) en bevat dezelfde afgeleide publieke JSON als productie; het bestaan en de naam worden in Fase 0 bevestigd.
- De vijftekensleutel is ruim voldoende voor tientallen spelers en locaties; de collisiecheck bij uitgifte vangt de rest op.

## 4. Datamodel voor ID's (slanke variant, besloten)

- `PlayerID` is stabiel en verandert niet na een naamwijziging; `LocationID` idem. GUI, Excel en publieke data tonen namen, geen ID's (uitzondering: ID's in profiel-URL's).
- **ID-formaat (besloten: kort en leesbaar, zonder verwarring):**
  - Prefix per type: `plr_` voor spelers en `loc_` voor locaties, zodat ze nooit door elkaar worden gehaald.
  - Daarna 5 willekeurige tekens uit een alfabet zonder lookalikes (geen `0`, `o`, `1`, `l`, `i`): `abcdefghjkmnpqrstuvwxyz23456789` (31⁵ = 28.629.151 mogelijke suffixen per type). Voorbeeld: `plr_k7x2m`.
  - Willekeurig, dus geen initialen of afgeleide van de naam (een ID mag nooit voor een naam doorgaan); alleen kleine letters. Gebruik een cryptografisch sterke generator uit de Python-standaardbibliotheek, controleer iedere nieuwe ID op botsingen en herhaal de trekking bij een botsing.
  - Leg uitgegeven én ingetrokken IDs blijvend vast, ook na verwijderen of samenvoegen van een speler. Een ID wordt nooit opnieuw uitgegeven. Bij uitgifte controleert het migratiecommando elke nieuwe ID tegen het register van uitgegeven en ingetrokken ID's; bij het huidige aantal spelers en locaties is dat ruim voldoende.
  - Een paar-sleutel is de twee ID's gesorteerd, bv. `plr_b17cd|plr_k7x2m`.
- Poollidmaatschap staat los van persoonsidentiteit (`PoolMember`).
- Reserve-placeholders zijn geen personen; een datumgebonden assignment kan een reserve-slot aan een PlayerID koppelen.
- Een paar is de gesorteerde combinatie van twee PlayerID's, zodat `(a,b)` gelijk is aan `(b,a)`.

**Nieuwe bestanden (minimaal):**

`players.csv`:
```csv
PlayerID,Name,PoolMember,Active
plr_k7x2m,"Voorbeeldspeler",1,1
plr_b17cd,"Voorbeeldreserve",0,1
```
`player_aliases.csv` (`Alias,PlayerID,Source`; genormaliseerde aliassleutel zonder hoofdletter- en spatieverschil), `locations.csv` (`LocationID,Name,Active`) en `location_aliases.csv` (`Alias,LocationID,Source`) voor expliciete historische locatienamen. Verwijderde of samengevoegde spelers/locaties blijven als inactieve tombstones geregistreerd; records en IDs worden niet fysiek verwijderd of hergebruikt.

**Actieve bestanden na migratie:** bestaande naamgebaseerde bestanden worden vervangen door ID-gebaseerde waarden; er zijn geen parallelle naam-exportroutes. `AllPlayers.csv` wordt vervangen door de poolstatus in `players.csv`. Geen aparte `playdays.csv` of `playday_players.csv`; de nieuwe speeldag- en deelnemersinformatie blijft in de bestaande geschiedenisstructuur.

**Vastgelegde ID- en reserveschema's:**

- `pairings.csv`: behoud kolommen `Player1`, `Player2`, `Count`, maar `Player1` en `Player2` bevatten PlayerID's. Alleen echte persoonsparen tellen mee; reserve-placeholders worden niet als persoonspaar geteld.
- `pairings_history.csv`: behoud `Date`, `Table`, `Players`, `Season`, `Location`; `Players` bevat vier tokens in bestaande ` | `-notatie. Een token is een PlayerID of een expliciet reserveslot-token `RESERVE:n` (n ≥ 1 en niet groter dan het aantal tafels van die speeldag; maximaal één reserve per tafel; de validatie meldt afwijkingen); `Location` bevat een LocationID of leeg.
- `scores_history.csv`: behoud de bestaande kolommen. `Team1Players` en `Team2Players` bevatten twee tokens gescheiden door ` | `; iedere token is een PlayerID of `RESERVE:n`. Een ingevulde reservepersoon wordt niet in deze historische uitslag gekopieerd: de datumgebonden assignment bepaalt welke PlayerID bij het slot hoort. Zo blijft de opgeslagen score aan de oorspronkelijke stoel gekoppeld.
- `reserve_assignments.csv`: vervang `Name` door `PlayerID`; kolommen worden `Date`, `Slot`, `PlayerID`. Alleen een expliciet gekoppelde reservepersoon met een bestaande PlayerID is geldig. Onbekende vrije tekst wordt tijdens dry-run gerapporteerd en vraagt handmatige mapping.
- `locations.csv`: bevat `LocationID`, `Name`, `Active`. Nieuwe `Location`-waarden in pairing history zijn LocationID's; legacy-locatienamen blijven in hun read-only bron.
- `seasons_history.csv` en `seasons_playdays_legacy.csv` blijven read-only legacybronnen in hun bestaande vorm. Hun historische awardnamen en locaties worden via goedgekeurde aliases/naamkoppelingen gelezen en naar publieke afgeleide JSON vertaald; ze zijn geen actieve schrijfbestanden en worden niet alleen als migratiebackup behandeld. De gedeelde bronzen plaats van Gilbert en Matthias in 2024–2025 blijft voor beide spelers behouden en wordt als expliciete regressiecase getest.
- Backups van gemigreerde actieve bestanden blijven buiten de actieve datamap en worden nooit gepubliceerd. De actieve en vorige versioned datamappen blijven afzonderlijk herstelbaar.

**Namenopzoeking:** één module (bv. `name_of(id)` / `id_of(name)`) is de enige plek waar namen worden opgelost. Een test dwingt af dat buiten de adapterlaag geen legacy-CSV's meer direct worden gelezen of geschreven.

## 5. Migratie, verificatie en rollback

1. **Dry-run:** inventariseer schemas, aantallen, onbekende en dubbele namen, hoofdletter-/spatieverschillen, aliasconflicten, ongeldige verwijzingen, bestaande gelijke scores en **drift tussen `pairings.csv` en `pairings_history.csv`**. Valideer ook het reserve-slotformaat (`RESERVE:n`). Wijzigt niets.
2. **Mappingreview:** stel PlayerID's, LocationID's en aliaskoppelingen voor. Ambigue matches blokkeren *apply* tot ze handmatig zijn opgelost (bv. verkorte versus volledige voornaam: zelfde persoon of niet?). Plan hiervoor tijd in, buiten de schatting.
3. **Container stoppen:** tijdens apply is de NAS-app gestopt en wordt niet gepubliceerd; voorkom gelijktijdige schrijvers naar de datastore.
4. **Backup en initiële versie:** maak een unieke, volledige backup van de huidige actieve data vóór iedere migratiewijziging. Bestaande backups worden nooit overschreven; een backupfout blokkeert schrijven. Bij de eerste overgang worden de te migreren CSV's gekopieerd naar een versioned `versions/<version-id>/`-directory; de oorspronkelijke bestanden blijven staan en worden niet verplaatst of verwijderd. **Wat wordt geversioneerd:** alleen CSV's waar de app naar schrijft of die ID's gaan bevatten (exacte lijst uit de Fase 0-inventaris van schrijfroutes). **Niet geversioneerd en niet gekopieerd:** `Scorebladen.xlsx` en `Scorebladen/` (blijven in de datastore-root en worden door migraties niet aangeraakt) en de read-only legacybronnen. Controleer vooraf of er voldoende opslagruimte is.
5. **Versioned staging:** maak naast de actieve versie een nieuwe, unieke dataversie. Schrijf alle gemigreerde bestanden uitsluitend naar staging; valideer schemas, referentiële integriteit, rijaantallen en score-/partnerbaselines. De oude actieve map blijft ongewijzigd.
6. **Atomische activatie:** de datastore-root bevat `versions/` en `active-version.json`. Nadat staging volledig is geschreven en gevalideerd, schrijf een nieuw active-version-manifest naar een tijdelijk bestand in dezelfde root en vervang het bestaande manifest met één atomische rename op hetzelfde bestandssysteem. `data_paths.py` leest alleen de versie waarnaar het actieve manifest wijst. Als het proces vóór die rename stopt, blijft de oude versie actief; rollback schrijft atomisch het vorige versienummer terug.
7. **Opstartcontrole:** de app controleert bij start dat de actieve versie bestaat, het verwachte schema heeft en alle verwijzingen geldig zijn. Bij een ontbrekende of inconsistente actieve versie start de app niet met een gemengde dataset; de fout wordt expliciet gemeld. **Bewaking tegen verouderde bestanden:** na activatie zijn de oorspronkelijke root-bestanden een ongebruikte kopie. `data_paths.py` is de enige bron voor paden van geversioneerde bestanden in de NAS-app en de NAS-generator; een markerbestand `LEGACY-NOT-ACTIVE.txt` in de root benoemt dat; de opstartcontrole waarschuwt als geversioneerde bestandsnamen in de root na de activatie nog zijn gewijzigd (teken van een vergeten schrijfroute). GitHub Actions ontvangt alleen de gegenereerde publieke JSON en heeft geen actieve-datastorepad.
8. **Voor/na-verificatie:** klassementen per gemapte speler en genormaliseerde partnercounts zijn identiek, behalve waar een expliciete mappingbeslissing het verschil verklaart. Elke oude rij is terug te vinden via de nieuwe IDs of de read-only legacybron.
9. **Rollback:** stop de app en schakel het active-version-manifest atomisch terug naar de vorige intacte versie. **Rollback is alleen verliesvrij zolang er na activatie geen nieuwe data is ingevoerd.** Het commando vergelijkt de actieve versie met de versie bij activatie, meldt welke rijen (scores, speeldagen, reserve-toewijzingen) later zijn toegevoegd en weigert zonder expliciete bevestiging. Plan de migratie daarom zo dat er een verificatiemoment is vóór de eerstvolgende invoer; na gebruik is herstel een voorwaartse fix of een handmatige herstelactie uit backup, geen automatische terugschakeling. Verwijder geen versie automatisch; opschoning is een afzonderlijke expliciete beheeractie.
10. **Publieke data:** backups, rapporten en migratiestatus komen nooit in `docs/`. Alleen de goedgekeurde afgeleide JSON wordt gepubliceerd; die JSON is publiek opvraagbaar.

## 6. Gefaseerd implementatieplan

Elke fase is afzonderlijk te testen en te mergen. **Na Fase 2 is er een natuurlijk stopmoment:** de laadtijd is dan opgelost en Speeldagen heeft de nieuwe rangschikking; de ID-laag en profielen kunnen daarna rustig volgen.

### Fase 0: Baseline, meting en beslismoment (S)

- **Doel:** objectieve baseline vastleggen vóór de herbouw.
- **Werk:** Lighthouse mobiel (Slow 4G, koud en warm), tijd tot eerste inhoud en totale `docs/`-grootte van de huidige export; dataprofilering uit §5 (naamvarianten, gelijke scores, `pairings`-drift, `PoolMember` in Tussenstand); inventaris van alle imports uit `mirror_app/` door `app.py` en tests; inventaris van alle CSV's waar de app naar schrijft of die ID's gaan bevatten (bepaalt de lijst voor het versioned datamodel); vaststellen welke service worker de huidige Shinylive-export registreert (bestand en scope, via `navigator.serviceWorker.getRegistrations()` op de live site) en bevestigen dat het pad van het previewproject (`/manillen-preview/`) buiten die scope valt; baselineklassementen en partnercounts als testfixtures.
- **Acceptatie:** meetrapport, profileringsrapport, vastgelegd gedrag voor beslissing 10 (benoemde reserves in de Tussenstand), vastgestelde lijst van te versioneren CSV's, geen datamutaties.

### Fase 1: Gedeelde kern en statische mirror op pariteit (M–L)

- **Doel:** zelfde functionaliteit als nu, veel sneller en mobile-first, nog op namen.
- **Bestanden:** nieuwe `manillen_core/` (pure helpers uit `mirror_app/*_helpers.py`, met shims zodat `app.py` en tests blijven werken), `generate_static_snapshot.py` (NAS-generator van gevalideerde JSON), `publish_mirror.py`/`build_static_site.py` (statische assemblage), `site/` (index.html, styles.css, app.js), `github_publish.py` (uploadt uitsluitend het JSON-archief), `.github/workflows/publish-mirror.yml` (assembleert site en snapshot, zonder Shinylive-installatie of bron-CSV's), `tests/`.
- **Werk:** zes tabs (Seizoenen, Hall of Fame, Tussenstand, Speeldagen, Scores, Parenhistoriek) met dezelfde filters (actief seizoen als startwaarde; Tussenstand ook per speeldag; spelerzoekfilter in Parenhistoriek met all-time teller); tabellen met kaartweergave op smal scherm (CSS-only met `data-label`) en sticky eerste kolom waar tabel blijft; laadindicator; noindex; mobile-first eisen uit §8.
- **Cutover:** tijdens de ontwikkeling staat de nieuwe site in een apart GitHub-project `manillen-preview` met eigen Pages (`https://nubrodr.github.io/manillen-preview/`, een pad buiten de scope van `/Manillen/`), aangevuld met lokaal `python -m http.server` voor dagelijks werk; de oude Shinylive-export blijft ondertussen live. De site gebruikt uitsluitend relatieve URL's, zodat dezelfde build onder `/`, `/Manillen/` en `/manillen-preview/` werkt. **Repetitie van de cutover:** zet eerst de huidige Shinylive-export in het previewproject, bezoek die met een testbrowserprofiel, vervang hem door de nieuwe site met het opruimscript en controleer dat het profiel na één bezoek de nieuwe site toont; pas daarna de echte cutover. Bij de cutover vervangt de nieuwe site de root van `docs/` op dezelfde URL. Op het pad van de oude service worker blijft een opruimscript staan dat die worker en zijn caches uitschrijft (enkele maanden, daarna verwijderen). **Rollback:** vorige `docs/`-commit terugzetten.
- **Risico:** pariteitsfouten in klassement of filters. Beperk met automatische vergelijking van de JSON tegen de bestaande berekening op dezelfde snapshot.
- **Acceptatie:** klassementen, scores, parenhistoriek en Hall of Fame gelijk aan de oude mirror (geautomatiseerd, per seizoen); prestatiebudget gehaald; geen horizontale paginaoverflow op 360 px; ruwe CSV's niet meer in `docs/`; hoofdapp en bestaande tests slagen zonder wijziging; workflowduur korter dan voorheen; een browserprofiel dat de oude site eerder bezocht krijgt na één bezoek de nieuwe site.

### Fase 2: Speeldagen-tafelrangschikking en scorevalidatie (M)

- **Doel:** bij gepasseerde speeldagen per tafel de spelers met enkel hun gewonnen-verloren (W-L) tonen, bv. één speler per rij met diens `3-0`-resultaat. De gebruiker wil geen losse speluitslagen in Speeldagen; daarvoor is het tabblad Scores.
- **Werk:** pure functie in `manillen_core/`; generator publiceert per tafel `place`, `wins`, `losses`, `games`, `complete`; browser kiest op basis van de Amsterdamse datum tussen "actueel" en "gepasseerd"; plaatsregels zoals in §3 (gewonnen, gespeeld; geen saldo; naam enkel voor weergavevolgorde); onvolledig-label; ongeldige (gelijke-score) rijen en dubbele spelrijen gemarkeerd; `score_functions.py` weigert gelijke scores bij nieuwe invoer. In Speeldagen staan de vier namen verticaal met W-L per speler naast de naam; verwijder daar de volledige matchup-/score-rijen. Houd de complete uitslagen in Scores. Desktop gebruikt de bestaande auto-grid per speeldag, mobiel stapelt de tafels.
- **Acceptatie:** geen tweede rekenroute; fixtures voor volledige dag, ontbrekend spel, dubbele spelrij, verkeerd aantal spelers, gedeelde plaatsen, gelijke-score-rij; datumgedrag rond middernacht en bij verschillende browsertijdzones; per tafel vier verticale spelersrijen met bijbehorende W-L; geen ruwe speluitslagen in Speeldagen; Scores blijft volledige matchups en scores tonen; W-L zichtbaar zonder alleen kleur.

### Fase 3: ID-registry en migratiecommando (L)

- **Doel:** `players.csv`, speler- en locatiealiassen, `locations.csv` en ID-vervangen bestanden volgens §4 en §5.
- **Bestanden:** nieuw migratie-/beheercommando, `data_paths.py`, referentieadapter, `github_publish.py` en `publish_mirror.py` (paden uitsluitend via `data_paths.py`), tests en Docker-seed-/volumeconfiguratie waar nodig voor het versioned datamodel.
- **Afhankelijkheden:** Fase 0 (profilering). Beslissingen 5 en 6 zijn genomen (geen naamexports, kort ID-formaat).
- **Risico:** hoogste datarisico; geen *apply* zonder gecontroleerde dry-run, aliasbesluiten, backup en vergelijking van klassement en partnercounts.
- **ID-toewijzing:** dry-run maakt een voorstelbestand met willekeurig gegenereerde, botsingsgecontroleerde IDs en mappings; het voorstel wordt buiten de actieve datastore opgeslagen en door de beheerder expliciet goedgekeurd. Apply gebruikt exact dat goedgekeurde bestand. Herhaalde dry-run/apply op hetzelfde goedgekeurde voorstel levert dezelfde IDs op; een nieuwe voorstelrun mag nieuwe, nog niet uitgegeven IDs bevatten.
- **Acceptatie:** ambigue matches worden niet samengevoegd; onbekende ID's en dubbele canonieke namen worden gerapporteerd; klassement en partnercounts identiek; staging en active-version-switch getest, inclusief procesonderbreking vóór activatie en rollback erna (met de begrenzing uit §5 stap 9); na activatie genereert de NAS-knop via `publish_mirror.py` uit de actieve versie een snapshot, uploadt `github_publish.py` alleen die JSON en deployt GitHub Actions die snapshot.

### Fase 4: Hoofdapp, scoreopslag en Excel op ID's (L)

- **Doel:** nieuwe wijzigingen intern op ID's opslaan; GUI, Excel en publieke data tonen namen.
- **Bestanden:** `app.py`, `manillen_functions.py`, `score_functions.py`, `reserve_assignments.py`, referentiehelpers, gerichte tests; de generator schakelt zijn adapter over van naam naar ID.
- **Let op:** naamgebaseerde bestanden worden na de overstap niet meer geschreven; `legacy/`-scripts en notebooks draaien niet meer tegen live data.
- **Risico:** één resterende vrije-tekstschrijfroute kan identiteit splitsen of partnercounts veranderen. De adaptertest uit §4 moet slagen.
- **Acceptatie:** nieuwe data is ID-gebonden; namen blijven overal zichtbaar; `Reserve 1` heeft geen persoons-ID; een reservepersoon wordt alleen via expliciete koppeling herkend; bestaande Excelbestanden blijven ongewijzigd; publieke JSON is na een naamwijziging in één stap bijgewerkt.

### Fase 5: Spelersprofielen en links in de mirror (M)

- **Doel:** profielpagina's en doorklikbare namen overal.
- **Werk:** generator maakt `players/<PlayerID>.json`; route `#/speler/<PlayerID>`; elke naam in tabellen en kaarten is een `<a>` met ruim touch-doel; filters behouden aparte **Open profiel**-knop; onbekende of ongeldige ID geeft een vriendelijke melding; spelers zonder data een duidelijke lege status; reserves zonder koppeling hebben geen profiel.
- **Inhoud (alleen waar data het toelaat; de afgesproken MoSCoW-scope geldt voor de eerste release):**
  - *Must:* samenvatting (speeldagen, spellen gewonnen/verloren, winstpercentage, saldo; bij 0 gespeelde spellen toont het winstpercentage "niet beschikbaar"), seizoensposities, Hall-of-Fame-vermeldingen.
  - *Should:* rankingverloop (inline SVG met tabelalternatief), recente vorm (W-L per speeldag over de laatste vijf speeldagen), aantal 3-0-tafels, partneroverzicht. Winstreeksen vallen buiten scope.
  - *Could (buiten eerste release):* head-to-head, aanwezigheid, beste/slechtste speeldag, fun facts, reserve-optredens (na expliciete koppeling). Alleen na afzonderlijke scopegoedkeuring toevoegen.
- **Acceptatie:** statistieken kloppen met handberekende fixtures; seizoensranking en evolutie alleen bij individuele score- en deelnemersdata; legacy-aliassen tellen alleen via goedgekeurde mapping; deep link werkt na direct openen, refresh, delen en back/forward; profielen zijn mobile-first (kaarten, geen horizontaal scrollen).

### Fase 6: Opruimen, publicatie en documentatie (S–M)

- **Werk:** `docker-entrypoint.sh` en seeds aanpassen voor de nieuwe ID-bestanden (bestaande bestanden blijven onaangeroerd); Shinylive en `mirror_app/` verwijderen of naar `legacy/` verplaatsen; allowlists, `Dockerfile`, `docker-entrypoint.sh` en workflows aanpassen; `README.md` bijwerken (backup, dry-run, verificatie, rollback, lokaal testen); controle dat seedlogica nooit bestaande data overschrijft en dat alleen afgeleide publieke JSON wordt gepubliceerd.
- **Acceptatie:** end-to-end publicatie vanuit de NAS-knop tot live site slaagt; geen interne bestanden in `docs/`; documentatie beschrijft het volledige beheerproces.

## 7. Testplan

### Pariteit en generator (Fase 1)
- Per seizoen: klassement, scores en parenhistoriek uit de JSON gelijk aan de bestaande helpers op dezelfde snapshot.
- Hall-of-Fame-pariteit omvat expliciet alle gedeelde awardplaatsen, waaronder Gilbert en Matthias als gedeeld brons in seizoen 2024–2025.
- Generator gebruikt alleen stdlib en tijdelijke testdata; echte `data/` blijft ongewijzigd.
- Inhoudscontrole van `docs/`: alleen toegestane afgeleide bestanden, geen ruwe CSV's, backups of rapporten; `noindex`-meta aanwezig als indexeringsverzoek. Test niet dat `robots.txt` toegang afschermt.

### Speeldagen en scores (Fase 2)
- Geldige tafel met vier spelers en de drie unieke matchups.
- Complete dag, ontbrekend spel, ontbrekende score, dubbele spelrij, fout aantal deelnemers.
- Plaatsen: gedeelde plaats bij gelijke (gewonnen, gespeeld); naam alleen voor volgorde.
- Gepasseerd-logica: browserdatum in `Europe/Amsterdam`, rond middernacht en bij andere tijdzone.
- Gelijke scores geweigerd bij invoer en opslag; bestaande rijen gerapporteerd, niet aangepast, als ongeldig meegenomen in W-L.

### ID-migratie (Fasen 3–4)
- Dry-run wijzigt niets; backup vóór wijziging; backupfout blokkeert; herhaling geeft dezelfde ID's en inhoud.
- Apply gebruikt uitsluitend het goedgekeurde ID-mappingvoorstel; ingetrokken IDs blijven tombstones en worden nooit hergebruikt.
- Onderbroken migratie vóór activatie laat de oude actieve versie intact; incomplete staging wordt niet actief. Een rollback na activatie schakelt terug naar de vorige versie zolang er geen nieuwe data is ingevoerd; anders meldt het commando de latere rijen en weigert het zonder bevestiging.
- De oorspronkelijke `/app/data`-bestanden blijven bij de eerste overgang staan; staging, manifest-switch en `data_paths.py`-resolutie worden op een tijdelijke datastore getest.
- Aliasmapping werkt; ambigue varianten worden gerapporteerd; onbekende ID's en ongeldige verwijzingen gedetecteerd.
- Klassementen per gemapte speler en genormaliseerde partnercounts vóór/na identiek.
- Adaptertest: geen directe legacy-CSV-toegang buiten de adapterlaag; `github_publish.py` en `publish_mirror.py` krijgen hun paden uitsluitend via `data_paths.py`.

### Profielen (Fase 5)
- Must-/Should-profielstatistieken tegen handberekende fixtures. Head-to-headtests horen bij de Could-scope en worden pas toegevoegd na afzonderlijke goedkeuring.
- Speler zonder data, reservepersoon, onbekende naam, onbekende ID en hernoemde speler.
- Deep link na direct openen, refresh, delen en back/forward.

### Mobiel en prestaties (vanaf Fase 1)
- **Playwright**: voor elke route op 360, 375, 390 en 768 px controleren dat `document.scrollWidth <= innerWidth`, schermafbeeldingen maken en navigatie met toetsenbord testen.
- **Lighthouse mobiel** in CI of lokaal, met het budget uit §2.
- **Echte telefoon:** omdat er geen service worker meer is, volstaat `python -m http.server --bind 0.0.0.0` in `docs/` en openen via het lokale netwerk; geen HTTPS-tunnel meer nodig. Gebruik een betrouwbare lokale netwerkverbinding; de browser krijgt geen HTTPS-beveiligingscontext.
- Matrix: 360 px Android, 375 px iPhone SE-breedte, 390 px iPhone, 768 px tablet; Chrome Android en Safari iOS; portrait en landscape; notch/safe area; filters; menu; tabellen; profiel-links; grafieken; browser back.

## 8. Mobile-first eisen voor de nieuwe mirror

Dit is een ontwerpchecklist op basis van de statische review van v1 (er is geen browser- of echte-telefoonmeting uitgevoerd). Er is geen huidige blocker vastgesteld; de hoogste prioriteit is de laadtijd.

| Prioriteit | Onderwerp | Eis in de nieuwe mirror | Moeite |
|---|---|---|---|
| **Major** | Laadtijd (Pyodide-start) | Opgelost door statische site; budget uit §2; laadindicator; Lighthouse-controle. | in Fase 1 |
| **Major** | Brede tabellen (min. 560 px) | Kaartweergave onder een breakpoint (CSS-only, `data-label`); waar een tabel blijft: scrollhint, sticky eerste kolom, kolomprioriteit. | M |
| **Major** | Externe fonts | Systeemfonts of lokaal gehoste subset; geen Google Fonts. | S |
| **Major** | Navigatie | Echte `<nav>` met links; hamburger met maximale hoogte en scroll; Escape en buitenklik sluiten; focus terug naar menuknop; `aria-current`. | S–M |
| **Minor** | Formuliervelden | Native `<select>` en inputs op ≥ 16 px (geen iOS-zoom); filters duimvriendelijk. | S |
| **Minor** | Touch targets | Alle links en knoppen ≥ 44×44 px, ook spelerlinks en kaarten. | S |
| **Minor** | Toegankelijkheid | Contrast AA gemeten; winst/verlies ook als tekst of icoon, niet alleen kleur; `th scope`; zichtbare focus; semantische koppen. | S |
| **Minor** | Safe areas | `viewport-fit=cover` en `env(safe-area-inset-*)`; landscape testen. | S |
| **Minor** | Thema en beweging | Expliciete licht/donker-toggle met onthouden keuze, lichte standaard; `prefers-reduced-motion`. | S |
| **Minor** | Grafieken (profiel) | Inline SVG, responsive; tik- en toetsenbordfocus in plaats van hover; verplicht tabel/lijst-alternatief. | M |

**Ontwerpregels:** statistieken en tafelrangschikkingen beginnen als stapelbare kaarten (desktop mag grid); spelernamen zijn ruime, duidelijke links; grafieken zijn aanvullend, nooit de enige bron; navigatie werkt met touch, toetsenbord en schermlezer.

## 9. Volgorde en tijdsinschatting

| Fase | Grootte | Richtinschatting |
|---|---:|---:|
| 0. Baseline, meting en beslismoment | S | 0,5–1 dag |
| 1. Gedeelde kern en statische mirror op pariteit | M–L | 5–7 dagen |
| 2. Speeldagen-rangschikking en scorevalidatie | M | 1–3 dagen |
| *Stopmoment: laadtijd opgelost, Speeldagen klaar* | | |
| 3. ID-registry en migratiecommando (versioned datamodel) | L | 5–8 dagen |
| 4. Hoofdapp, scoreopslag en Excel op ID's | L | 3–5 dagen |
| 5. Spelersprofielen en links | M | 3–5 dagen |
| 6. Opruimen, publicatie en documentatie | S–M | 1–2 dagen |

**Volgorde:** Fase 0 → 1 → 2 → 3 → 4 → 5 → 6. Fase 3 kan deels parallel worden voorbereid (dry-run en profilering) tijdens Fase 1–2.

**Totaal:** circa 19–31 werkdagen, exclusief handmatige aliasbesluiten, NAS-backupplanning en extra herstelwerk dat de eerste dry-run kan blootleggen. De totale omvang is iets groter dan in v1 (17–28 dagen), vooral door het versioned datamodel in Fase 3, maar de **zichtbare winst (snelle site en nieuwe Speeldagen) komt na ca. 7–11 dagen** in plaats van pas helemaal aan het eind. De grootste onzekerheden blijven het aantal historische naamvarianten en eventuele pariteitsverschillen bij de herbouw.
