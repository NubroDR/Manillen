# Manillen

Een Shiny for Python-app om 2v2-manillen-tafels te organiseren voor een familie-speeldag. De app zoekt een eerlijke spelersverdeling, bewaart de speeldag, genereert scorebladen en houdt scores en klassementen bij.

## Projectstatus

Deze repository is de actuele basis voor de volledige NAS-applicatie en de read-only GitHub Pages-app. De schrijfbare hoofdapp staat in `app.py`; de productie-URL <https://nubrodr.github.io/Manillen/> gebruikt nog de bestaande Shinylive-app uit `mirror_app/`. De nieuwe statische mirror staat alleen op de aparte preview <https://nubrodr.github.io/manillen-preview/>; afgeronde mirrorwijzigingen worden daar na lokale validatie uitgerold zodat ze kunnen worden nagekeken. De laatste previewdeploy is commit `584f5cc` (Pages-run `41836029669`): spelerprofielen tonen compacte statistieken, uitgelijnde seizoensresultaten en geregistreerde speeldagen met locaties. Speeldagen toont W-L-resultaten pas na afloop volgens `Europe/Amsterdam`, plant een verversing op de volgende Amsterdamse middernacht en toont tot die tijd alleen de spelerslijst; ingevulde reservespelers hebben een `*`, net als Scores en Tussenstand. De preview heeft een eigen SVG-favicon; de bestaande productiepagina serveert al `favicon.ico`. Gelijke scores worden als ongeldig aangeduid en tellen niet mee in klassementen. Mobiele tabellen blijven horizontaal verschuifbaar. De oude Shinylive-worker is op het previewpad opgeruimd en de rollback/startup is in de preview gerepeteerd en gevalideerd (F1-44). Productie-`docs/` is niet aangepast en er is geen productiecutover uitgevoerd. Zie [het implementatieplan](./plans/IMPLEMENTATIEPLAN_PROFIELEN_IDS_MOBIEL_v3.md) en [het testplan](./plans/TESTPLAN_ACCEPTATIE_v3.md) voor de overdracht, open acceptatie en eerstvolgende taak.

## LLM-context en wijzigingsbasis

Dit README is de canonieke projectcontext voor nieuwe feature-verzoeken, bugs, refactors en AI/LLM-hulp. Gebruik dit bestand als eerste input bij een nieuw wijzigingsverzoek: het beschrijft het actuele doel van het project, de huidige architectuur, deploy-omgeving, relevante bestanden, dataflow en onderhoudsregels.

Belangrijk: als een wijziging groot genoeg is om de app, de dataflow, de deploy, de interfaces of de projectstructuur te beïnvloeden, dan moet ook dit README direct worden bijgewerkt. Een verouderd README is een projectprobleem, niet alleen een documentatieprobleem.

## README-onderhoudsregel

Wanneer een wijziging een van deze punten raakt, werk dan dit bestand direct bij in dezelfde change:

- nieuwe of gewijzigde app-functionaliteit
- nieuwe datafiles of gewijzigde CSV/Excel-structuur
- gewijzigde deployment of Docker/NAS-opzet
- nieuwe GitHub Actions- of publish-workflows
- architectural changes in `app.py`, `mirror_app/` of workflow
- nieuwe env-vars, startup-commando's of lokale/ publieke deploy-flow
- wijziging in spelregels, scorelogica of onderliggende berekeningen

Kortom: als een wijziging "groot" is, dan is een README-update verplicht. Als een wijziging klein is maar de gebruikersworkflow of projectcontext beïnvloedt, ook dan upgraden.

## Functies

- Spelers selecteren met een typeahead-selector.
- Automatisch tafels van vier spelers indelen met zo weinig mogelijk herhaalde partners.
- Indelingen bewaren en eerdere speeldagen bekijken of verwijderen.
- Speeldagen tonen spelers per tafel, gerangschikt op W-L; de volledige matchups en scores staan apart in Scores.
- Excel-scorebladen genereren vanuit een opgeslagen speeldag, met alleen het benodigde aantal reservevelden.
- Reservenamen per speeldag opslaan en automatisch opnieuw laden; reserves krijgen een afwijkende Excel-stijl.
- Scores voor de drie 2v2-spellen per tafel invoeren.
- Gelijke scores worden geweigerd; bestaande gelijke uitslagen blijven ongewijzigd, tellen niet mee in klassementen en worden als ongeldig aangeduid.
- Alle ingevulde scores voor een speeldag met één knop opslaan; onvolledige spellen worden overgeslagen met een melding.
- Een tussenstand en speeldaggeschiedenis bekijken met een seizoensfilter.
- Historische seizoenen en de Hall of Fame bekijken.
- Doorklikbare spelersnavigatie in de statische mirror met compacte profielpagina's, seizoensresultaten en geregistreerde speeldagen met locaties.
- Een alleen-lezen mirror publiceren naar GitHub Pages (de productie gebruikt nog Shinylive; de statische versie staat op de aparte preview).

## Projectstructuur

```text
.
├── app.py                    # Volledige schrijfbare NAS-app.
├── data_paths.py             # Datastore-root en fail-closed resolutie via active-version.json.
├── manillen_core/            # Gedeelde CSV-, seizoen-, score- en referentiehelpers.
├── manillen_functions.py     # Indeling, paringen en scorebladlogica.
├── score_functions.py        # Schrijfbare scoreworkflow met gedeelde scoreberekening.
├── reserve_assignments.py    # Datumgebonden CRUD voor ingevulde reservenamen.
├── github_publish.py         # Uploadt alleen afgeleide JSON en dispatcht de Pages-workflow.
├── profile_data.py           # Read-only nulmeting voor datamigratie.
├── requirements.txt          # Dependencies voor de volledige app.
├── requirements-dev.txt      # pytest en de runtime-dependencies voor tests.
├── Dockerfile                # Image voor de volledige NAS-app.
├── docker-compose.yml        # Portainer Stack-configuratie.
├── docker-entrypoint.sh      # Seedt een leeg /app/data-volume.
├── .dockerignore             # Beperkt de Docker build context.
├── publish_mirror.py         # Bouwt de statische mirror uit CSV-data of een JSON-archief.
├── generate_static_snapshot.py # Afgeleide JSON voor de nieuwe statische mirror.
├── build_static_site.py      # Bouwt een statische preview in een lege outputmap.
├── migrate_ids.py            # Maakt een privé, alleen-lezen ID-migratievoorstel.
├── stage_ids.py              # Bouwt een gevalideerde, inactieve ID-stagingversie.
├── versioned_data.py         # Schema- en referentievalidatie voor ID-datasets.
├── data_versions.py          # Full backup, atomische activering en rollback.
├── site/                     # Bronbestanden van de nieuwe vanilla-JS preview.
├── static_snapshot.zip       # JSON-only invoerarchief voor de handmatige Pages-workflow.
├── data/
│   ├── AllPlayers.csv        # Beschikbare spelers, één naam per regel.
│   ├── pairings.csv          # Partnerhistoriek met Player1, Player2, Count.
│   ├── pairings_history.csv  # Opgeslagen tafels per Date, Table, Players, Season en Location.
│   ├── scores_history.csv    # Scores per Date, Table en Game.
│   ├── reserve_assignments.csv # Ingevulde reservenamen per Date en Slot.
│   ├── Scorebladen.xlsx      # Leeg Excel-template.
│   └── Scorebladen/          # Gegenereerde scorebladen; lokaal genegeerd door git.
├── mirror_app/
│   ├── app.py                # Huidige alleen-lezen Shiny-app voor publicatie.
│   ├── data/                 # Publieke snapshot van de CSV-data.
│   ├── *_helpers.py          # Compatibiliteitsre-exports uit manillen_core/.
│   ├── requirements.txt      # Shinylive-compatibele dependency.
│   └── README.md             # Korte handleiding voor de GitHub Pages-app.
├── tests/                    # Geïsoleerde pytest-suite en tijdelijke fixtures.
├── legacy/
│   ├── ManillenGUI.py        # Oude Tkinter/ipywidgets-interface.
│   └── Manillen.ipynb        # Oude notebook-workflow.
└── docs/                     # Gegenereerde Shinylive-site voor GitHub Pages.
```

De gegenereerde bestanden onder `data/Scorebladen/` worden niet getrackt; het lege `data/Scorebladen.xlsx`-template blijft wel behouden.

## Aan de slag

Gebruik Python 3.11 of nieuwer. Maak bij voorkeur een virtuele omgeving aan en installeer de dependencies vanuit de repository-root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
shiny run app.py
```

Open daarna de URL die Shiny toont, normaal `http://127.0.0.1:8000`.

Voor geïsoleerde lokale tests wordt `MANILLEN_DATA_DIR` gebruikt. Zonder deze variabele blijft de projectmap `data/` de standaard. Installeer de testafhankelijkheden en voer pytest uit:

```powershell
pip install -r requirements-dev.txt
pytest
```

De tests zetten `MANILLEN_DATA_DIR` naar een tijdelijke map. `tests/`, `requirements-dev.txt` en `data/hall_of_fame_check.csv` worden niet in het Docker-image opgenomen.

## Datamigratie nulmeting

`profile_data.py` maakt een read-only JSON-rapport met CSV-schema's en aantallen, naamvarianten en onbekende verwijzingen, conflicterende aliassen, ongeldige of gelijke scores, drift tussen partnercounts en pairing history, en de huidige imports en CSV-routes. Het leest standaard de geconfigureerde `MANILLEN_DATA_DIR` (of `data/`) en schrijft niets naar de datastore:

```powershell
python profile_data.py
```

Namen zijn standaard weggelaten uit het rapport. Voeg `--include-names` alleen toe voor een lokale, private mappingreview; deel of publiceer die uitvoer niet. Een alternatieve datastore kan met `--data-dir <pad>` worden gecontroleerd.

`migrate_ids.py` maakt de eerste alleen-lezen stap van Fase 3: een JSON-voorstel met willekeurige PlayerID's/LocationID's, aliassen, bronhashes en de datakwaliteitsbevindingen. Geef altijd een nieuwe outputlocatie buiten de datastore op:

```powershell
python migrate_ids.py --data-dir "<datastore>" --proposal-output "<private reviewmap>\manillen-id-proposal.json"
```

Het voorstel bevat namen en is dus privé. Het commando weigert de actieve datastore als uitvoerlocatie, overschrijft geen bestaand voorstel en verandert geen bronbestanden. Het voorstel blijft `pending`; niet-poolspelers en locaties krijgen geen automatische actieve status.

Na een private mappingreview kan een stagingversie worden gebouwd. De reviewer moet in het voorstel alle `Active`- en `PoolMember`-statussen invullen en een aparte approval-JSON maken die exact de hash van dat voorstel noemt:

```json
{
  "status": "approved",
  "proposal_sha256": "<proposal_sha256 uit het reviewed voorstel>",
  "approved_by": "<reviewer>",
  "approved_at": "2026-11-04T12:00:00+01:00"
}
```

De hash in het voorstel moet overeenkomen met de inhoud; iedere wijziging aan het voorstel maakt de bestaande hash ongeldig. Bewaar het reviewed voorstel als een nieuwe privé-kopie en bereken daarna de hash opnieuw:

```powershell
python -c "import json; from pathlib import Path; from migrate_ids import calculate_proposal_hash; s=Path(r'<original proposal.json>'); p=Path(r'<new reviewed proposal.json>'); d=json.loads(s.read_text(encoding='utf-8')); d['proposal_sha256']=calculate_proposal_hash(d); p.open('x', encoding='utf-8').write(json.dumps(d, ensure_ascii=False, indent=2)+'\n')"
```

Maak vervolgens de approval-JSON met deze nieuwe hash. Bewaar voorstel, approval en staging buiten de repository en de datastore. De stagingopdracht weigert een pending, gewijzigd of verouderd voorstel, overschrijft geen bestaande uitvoermap en activeert de data niet:

```powershell
python stage_ids.py --data-dir "<tijdelijke datastore>" `
  --proposal "<private reviewmap>\proposal.json" `
  --approval "<private reviewmap>\approval.json" `
  --staging-output "<private stagingmap>"
```

`data_paths.py` ondersteunt `active-version.json`: zonder manifest blijft de huidige datastore-root actief; met manifest worden de negen ID-CSV's uit `versions/<active_version>/` gecontroleerd op schema's en verwijzingen. De schrijfbare Shiny-app leest en schrijft in die actieve versie en toont namen in de UI en Excel-uitvoer; legacyseizoensbronnen en scorebladbestanden blijven in de datastore-root. De snapshotgenerator en archiefopbouw lezen de actieve ID-versie en exporteren alleen namen en afgeleide JSON; deze ID-route is op tijdelijke fixtures getest. `data_versions.py` biedt full-backup en manifest-activering/rollback:

```powershell
python data_versions.py activate --data-dir "<testdatastore>" `
  --staging "<private stagingmap>" `
  --backup-output "<nieuwe externe backupmap>" --confirm
python data_versions.py rollback --data-dir "<testdatastore>" `
  --backup-output "<nieuwe externe rollback-backupmap>"
```

De backup is een unieke, geverifieerde kopie van de volledige datastore. Activering kopieert een gevalideerde stagingversie naar `versions/` en wijzigt daarna alleen `active-version.json` via een tijdelijke file en atomische replace; vóór die replace blijft de vorige versie actief. Rollback weigert standaard als bestanden sinds activering zijn veranderd en rapporteert de rij-aantallen; `--confirm-data-loss` is vereist om die wijzigingen bewust te laten vallen. Oude versies worden nooit verwijderd.

**Niet op de echte NAS-datastore toepassen.** De hoofdapp, scorebladexport en snapshot-/archiefopbouw zijn op tijdelijke fixtures met een actieve ID-versie getest, maar de volledige Fase 4-acceptatie en productievalidatie zijn nog open. Productieactivatie blijft geblokkeerd totdat de volledige regressie- en acceptatiesuite, deployment-/rollbackcontrole en aparte migratiegoedkeuring gereed zijn. Gebruik deze commando's nu alleen met tijdelijke testdata.

## Statische mirror-preview (preview live; productiecutover open)

De berekeningen voor de NAS-app en generator staan nu in `manillen_core/`; de oude `mirror_app/*_helpers.py`-imports blijven als compatibiliteitsshims bestaan. `generate_static_snapshot.py` maakt alleen afgeleide JSON en `build_static_site.py` assembleert die met de statische bronbestanden uit `site/`. Beide schrijven uitsluitend naar een expliciet opgegeven, lege outputmap. Gebruik voor tests een tijdelijke datastore:

```powershell
$env:MANILLEN_DATA_DIR = "<tijdelijke fixturemap>"
python build_static_site.py --output "<nieuwe lege previewmap>"
python -m http.server --directory "<previewmap>" 8000
```

`github_publish.py` genereert op de NAS een afgeleide JSON-snapshot en uploadt die als één `static_snapshot.zip`; de bron-CSV's worden niet door deze nieuwe knopstroom geüpload. De handmatige `publish-mirror.yml`-workflow assembleert het archief met `publish_mirror.py` naar `docs/`, zonder Shinylive-installatie. Deze hoofdrepo-workflow is voorbereid maar nog niet uitgevoerd. Preview-, service-worker- en rollbackacceptatie zijn op de aparte preview afgerond; de productie blijft de huidige Shinylive-export tot de resterende productieacceptatie en cutover expliciet zijn goedgekeurd.

In De statische mirror toont W-L-resultaten op Speeldagen pas na afloop van de speeldag in de tijdzone `Europe/Amsterdam`; de pagina ververst de status bij een datumwissel. Tot die tijd toont de tafel de spelerslijst zonder uitslagen. Na afloop staan de spelers verticaal gerangschikt op W-L; ingevulde reservespelers krijgen, net als in Scores en de Tussenstand, een `*` achter hun naam. Tussenstand en Scores filteren per seizoen (zonder optie voor alle seizoenen); Seizoenen toont één overzichtsrij per seizoen en linkt naar de speeldagen wanneer die beschikbaar zijn. Mobiele tabellen blijven tabellen en kunnen horizontaal worden verschoven zonder pagina-overflow.

## Tafelindeling en scores

De indeling gebruikt een greedy-algoritme. Het algoritme probeert meerdere startvolgordes, vormt telkens de best mogelijke groep van vier en minimaliseert eerst de meest herhaalde paring in de configuratie. Daarna gebruikt het het aantal herhaalde paringen en de totale paringtelling als tie-breakers. Reservespelers worden toegevoegd wanneer het aantal aanwezigen geen veelvoud van vier is; twee reservespelers komen niet samen aan één tafel.

Elke tafel speelt drie unieke 2v2-combinaties. Een spel loopt tot en met 101 punten. In **Scores invoeren** worden met één knop alle volledige spellen van de geselecteerde speeldag opgeslagen; ontbrekende scores blokkeren de volledige spellen niet en worden gemeld. Opslaan vervangt dezelfde spellen op basis van datum, tafel en spelnummer, zodat herhaald opslaan geen dubbele rij maakt. Een volledig spel vereist twee niet-negatieve gehele scores.

In de tussenstand worden spelers eerst gesorteerd op gewonnen spellen, daarna op aantal gespeelde spellen, vervolgens op puntensaldo en ten slotte op naam. Het puntensaldo is punten voor min punten tegen. De reservekolommen in opgeslagen scores blijven herkenbaar als reserve; de tussenstand toont de per speeldag opgeslagen reservenaam met `*` en vermeldt `* = reservespeler`. Een ingevoerde reservenaam die gelijk is aan een poolspeler geeft een waarschuwing.

## Seizoenen en prijzen

`data/seasons.csv` is het register van tool-seizoenen met uitsluitend `Season`, `SeasonNumber`, `SeasonStartYear` en `Status`. Een nieuwe speeldag krijgt standaard het actieve seizoen, maar het seizoen is vóór het bewaren te kiezen. `pairings_history.csv` bewaart `Season` en `Location` per tafelrij; oude bestanden krijgen deze kolommen veilig toegevoegd en een ontbrekend seizoen wordt als `2026-2027` gelezen. De locatie is te kiezen uit eerder gebruikte locaties of als nieuwe locatie in te voeren, en verschijnt op de tabbladen **Speeldagen** en **Seizoenen**.

Bij de eerste migratie wordt vóór wijziging van `pairings_history.csv` verplicht één backup gemaakt als `pairings_history.csv.bak-pre-seasons`; een bestaande backup wordt nooit overschreven. De migratie schrijft eerst naar een tijdelijk bestand en vervangt het origineel alleen na een geslaagde write. De startup kopieert ontbrekende seedbestanden naar `/app/data`, maar vervangt geen bestaande bestanden.

**Maak vóór de eerste redeploy handmatig een volledige kopie van `/volume1/manillen_data` naar een veilige backup-locatie.** De automatische historybackup is aanvullend en vervangt deze NAS-backup niet.

`Tussenstand` en `Speeldagen` starten met een filter op het actieve seizoen en kunnen naar eerdere seizoenen worden geschakeld. Tussenstand behoudt ook de keuze voor één specifieke speeldag. `Nieuw seizoen` toont eerst de eindstand ter controle; na bevestiging sluit het huidige seizoen en maakt het volgende actief. Een afgesloten seizoen kan worden heropend zolang er geen later seizoen actief is.

Tool-seizoenen kennen prijzen alleen toe als ze zijn afgesloten. De berekening gebruikt de getoonde rangschikking en spelers uit `AllPlayers.csv`; minimaal drie gespeelde spellen zijn vereist. Reserves zijn uitgesloten van prijzen en Hall of Fame. Bij minder dan vier eligible spelers kan volgens de gekozen regel een speler zowel een medaille als de rode lantaarn krijgen. De prijzen worden steeds uit scores berekend en niet apart opgeslagen.

De tabbladen **Seizoenen** en **Hall of Fame** bevatten de historische seizoenen uit `seasons_history.csv` en, voor legacy-seizoenen, de speeldagen uit `seasons_playdays_legacy.csv`. Het seizoenenoverzicht toont de seizoenen antichronologisch en aanwezigen per speeldag apart van de poolgrootte; voor tool-seizoenen worden speeldagen en aanwezigen uit `pairings_history.csv` afgeleid. Ties tellen voor iedere betrokken speler. De Hall of Fame toont alle huidige poolspelers, ook met nul prijzen, plus voormalige spelers met historische prijzen; de sortering is aflopend op goud, zilver en brons, daarna oplopend op aantal rode lantaarns. `hall_of_fame_check.csv` wordt uitsluitend als testfixture gebruikt en nooit door de entrypoint, `publish_mirror.py` of `github_publish.py` gekopieerd.

## NAS-hosting

De schrijfbare app draait via de root-level `Dockerfile`. Shiny luistert in de container op `0.0.0.0:8000`; omdat poort 8000 op de NAS al bezet is, publiceert de compose-configuratie de app op NAS-poort `8080` via `8080:8000`.

Lokaal bouwen en starten:

```powershell
docker build -t manillen:latest .
docker run --rm -p 8080:8000 -v manillen_data:/app/data manillen:latest
```

Open de app lokaal of via Tailscale op `http://<nas-hostnaam>:8080`.

De lokale `docker run`-voorbeeldopdracht gebruikt een Docker-volume met de naam `manillen_data`. De NAS-configuratie in `docker-compose.yml` gebruikt daarentegen een bind mount van `/volume1/manillen_data` naar `/app/data`; zorg dat deze map op de NAS bestaat en schrijfbaar is. Bij een eerste start kopieert de entrypoint alleen ontbrekende basisbestanden naar `/app/data`, waaronder `Scorebladen.xlsx` en de twee historische seizoensbronnen. Bestaande CSV’s en scorebladen worden nooit overschreven. Gegenereerde scorebladen blijven samen met de datastore in de gemounte map staan.

Maak in Portainer een Stack from Git repository met deze repository. De stack gebruikt `docker-compose.yml`, bouwt vanuit de repository-root, gebruikt containernaam `manillen`, restartbeleid `unless-stopped` en mount `/volume1/manillen_data:/app/data`. Er wordt geen volledige repository in de container gemount.

Beperk de toegang tot het lokale netwerk of gebruik Tailscale om de NAS-app privé te bereiken. De app gebruikt absolute paden vanuit de projectcode en blijft daardoor onafhankelijk van de working directory. Na een nieuwe GitHub-versie kies je in Portainer **Pull and redeploy** of voer je een stack-update/redeploy uit, zodat de image opnieuw wordt gebouwd; `/app/data` blijft behouden.

De volledige NAS-app en de read-only GitHub Pages-app zijn aparte deployments. De Docker-container voert alleen `app.py` uit en draait `mirror_app/` niet als viewer.

### NAS -> GitHub Pages-publicatie voorbereiden

In de NAS-app staat in het tabblad Geschiedenis de knop **Publiceer data**. De nieuwe code genereert eerst lokaal een afgeleide JSON-snapshot, verpakt alleen JSON in `static_snapshot.zip`, uploadt dat ene bestand via de GitHub Contents API en start daarna de workflow via `workflow_dispatch`. De workflow assembleert de statische site, vervangt `docs/` in de workflow-checkout en commit alleen de gegenereerde site. Een succesmelding betekent alleen dat de workflow is gestart; GitHub Pages kan daarna nog enige tijd nodig hebben.

De publieke projectsite staat op `https://nubrodr.github.io/Manillen/`. De URL `https://nubrodr.github.io/` is alleen de gebruikerssite van GitHub en verwijst niet automatisch naar deze repository.

Stel in Portainer de volgende environment variables in voor de container:

- `GITHUB_TOKEN`: verplicht; een token met Contents write- en Actions write-rechten op de repository.
- `GITHUB_REPOSITORY`: verplicht, in de vorm `owner/repository`.
- `GITHUB_WORKFLOW`: verplicht; voor de meegeleverde workflow is dit `publish-mirror.yml`.
- `GITHUB_REF`: optioneel; de ref waarop de workflow dispatcht, standaard `main`.

De meegeleverde workflow staat in `.github/workflows/publish-mirror.yml` en kan handmatig of via de NAS-knop worden gestart. De token wordt uitsluitend uit de environment gelezen en wordt nooit in de UI, logs of foutmeldingen getoond. De NAS-app commit niets; de workflow commit alleen de statische uitvoer. De volledige nieuwe flow is:

```text
NAS-knop -> JSON-generator -> static_snapshot.zip -> GitHub API -> workflow_dispatch
         -> statische sitebouw -> docs-commit -> GitHub Pages
```

`data/seasons_history.csv`, `data/seasons_playdays_legacy.csv` en `data/hall_of_fame_check.csv` zijn opgenomen in Git en worden niet genegeerd, zodat ze beschikbaar zijn in de Portainer Stack-from-Git-build. De Hall-of-Fame-check is alleen voor tests; hij komt niet in de JSON-snapshot of Pages-uitvoer.

## Read-only GitHub Pages-mirror

De huidige live site gebruikt nog de read-only Shinylive-app uit `mirror_app/`; de CSV’s in `mirror_app/data/` zijn een momentopname en worden niet live van de NAS gelezen. De nieuwe vanilla-JS mirror heeft zes routes en consumeert alleen afgeleide JSON. De statische site biedt standaard een lichte weergave, met een licht/donker-toggle die de keuze in de browser onthoudt; klassementmedailles en awardkolommen hebben bijpassende emoji's en kleuraccenten. CSS- en JavaScript-URL's gebruiken naast de snapshot-ID een fingerprint van de site-assets, zodat een vormgevingsupdate ook zichtbaar wordt wanneer de openbare JSON-snapshot niet is gewijzigd. De site is als preview gedeployed op <https://nubrodr.github.io/manillen-preview/>. De Pages-workflow past `prepare_legacy_pages.py` alleen toe op het deployment-artifact: statische exports blijven ongewijzigd; een legacy Shinylive-export registreert de service worker, wacht op activatie en herlaadt eenmaal als de pagina nog niet wordt bestuurd. De preview-rollback is in dezelfde browsercontext met een verse eerste load geslaagd zonder JavaScript- of consolefouten. Na herstel van de statische preview is de worker voor `/manillen-preview/` verwijderd en bleef de productie-worker voor `/Manillen/` behouden. Productie is niet gewijzigd en cutover blijft apart.

Maak een lokale preview met een geïsoleerde datastore en een nieuwe, lege uitvoermap:

```powershell
$env:MANILLEN_DATA_DIR = "<tijdelijke fixturemap>"
python build_static_site.py --data-dir $env:MANILLEN_DATA_DIR --output "<nieuwe lege previewmap>"
python -m http.server --directory "<previewmap>" 8000
```

`publish_mirror.py --snapshot-archive static_snapshot.zip --output "<nieuwe lege uitvoermap>"` assembleert hetzelfde JSON-only snapshotarchief als de workflow. Gebruik voor een NAS-datastore geen handmatige publicatie naar Pages als vervanging voor de acceptatie- en cutoverstappen in de plannen.

GitHub Pages wordt gedeployed door `.github/workflows/deploy-pages.yml`. Na een push naar `main` is de publieke projectsite beschikbaar op `https://nubrodr.github.io/Manillen/`.

Lokaal testen kan met:

```powershell
shiny run mirror_app/app.py
```

## Databestanden

- `AllPlayers.csv`: CSV zonder header, met één spelersnaam per regel.
- `pairings.csv`: CSV met de kolommen `Player1`, `Player2` en `Count`; elke rij is een ongesorteerd partnerpaar met de actuele telling.
- `pairings_history.csv`: CSV met `Date`, `Table` en `Players`; de vier spelers staan in één veld, gescheiden door ` | `.
- `pairings_history.csv` bevat daarnaast `Season`; de migratie voegt die kolom veilig toe aan bestaande volumes.
- `scores_history.csv`: CSV met `Date`, `Table`, `Game`, `Team1Players`, `Team2Players`, `Team1Score` en `Team2Score`.
- `reserve_assignments.csv`: CSV met `Date`, `Slot` en `Name`; bewaart ingevulde reservenamen per speeldag.
- `seasons.csv`: tool-seizoenen met `Season`, `SeasonNumber`, `SeasonStartYear` en `Status`.
- `seasons_history.csv` en `seasons_playdays_legacy.csv`: read-only brondata voor vroegere seizoenen en speeldagen.
- `hall_of_fame_check.csv`: testdata; niet voor app-runtime of publicatie.
- `Scorebladen.xlsx`: leeg Excel-template voor maximaal vier tafels.
- `Scorebladen/`: automatisch gemaakte Excel-bestanden per speeldatum; dit zijn uitvoerbestanden en worden niet getrackt.

## Licentie en auteur

Persoonlijk familieproject. Geen aparte open-sourcelicentie voorzien.
