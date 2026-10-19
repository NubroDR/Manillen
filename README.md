# Manillen

Een Shiny for Python-app om 2v2-manillen-tafels te organiseren voor een familie-speeldag. De app zoekt een eerlijke spelersverdeling, bewaart de speeldag, genereert scorebladen en houdt scores en klassementen bij.

## Projectstatus

Deze repository is de actuele, werkende basis voor de volledige NAS-applicatie en de read-only GitHub Pages-app. De hoofdapplicatie is de schrijfbare Shiny-app in `app.py`; de app in `mirror_app/` is een momentopname voor GitHub Pages. De meest recente workflow is: data wordt lokaal ingevoerd, de app bewaart en berekent de stand, en de GitHub Pages-weergave kan handmatig via GitHub Actions worden bijgewerkt.

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
- Excel-scorebladen genereren vanuit een opgeslagen speeldag, met alleen het benodigde aantal reservevelden.
- Reservenamen per speeldag opslaan en automatisch opnieuw laden; reserves krijgen een afwijkende Excel-stijl.
- Scores voor de drie 2v2-spellen per tafel invoeren.
- Alle ingevulde scores voor een speeldag met één knop opslaan; onvolledige spellen worden overgeslagen met een melding.
- Een tussenstand en speeldaggeschiedenis bekijken met een seizoensfilter.
- Historische seizoenen en de Hall of Fame bekijken.
- Een alleen-lezen Shinylive-app publiceren naar GitHub Pages.

## Projectstructuur

```text
.
├── app.py                    # Volledige schrijfbare NAS-app.
├── data_paths.py             # Data-directory, configureerbaar via MANILLEN_DATA_DIR.
├── manillen_functions.py     # Indeling, paringen en scorebladlogica.
├── score_functions.py        # Schrijfbare scoreworkflow met gedeelde scoreberekening.
├── reserve_assignments.py    # Datumgebonden CRUD voor ingevulde reservenamen.
├── github_publish.py         # Veilige GitHub Actions workflow-dispatch.
├── requirements.txt          # Dependencies voor de volledige app.
├── requirements-dev.txt      # pytest en de runtime-dependencies voor tests.
├── Dockerfile                # Image voor de volledige NAS-app.
├── docker-compose.yml        # Portainer Stack-configuratie.
├── docker-entrypoint.sh      # Seedt een leeg /app/data-volume.
├── .dockerignore             # Beperkt de Docker build context.
├── publish_mirror.py         # Snapshot kopiëren en Shinylive-export starten.
├── data/
│   ├── AllPlayers.csv        # Beschikbare spelers, één naam per regel.
│   ├── pairings.csv          # Partnerhistoriek met Player1, Player2, Count.
│   ├── pairings_history.csv  # Opgeslagen tafels per Date, Table, Players, Season en Location.
│   ├── scores_history.csv    # Scores per Date, Table en Game.
│   ├── reserve_assignments.csv # Ingevulde reservenamen per Date en Slot.
│   ├── Scorebladen.xlsx      # Leeg Excel-template.
│   └── Scorebladen/          # Gegenereerde scorebladen; lokaal genegeerd door git.
├── mirror_app/
│   ├── app.py                # Alleen-lezen Shiny-app voor publicatie.
│   ├── data/                 # Publieke snapshot van de CSV-data.
│   ├── data_helpers.py       # Pure geschiedenis- en paringreaders.
│   ├── season_helpers.py     # Seizoensmigratie, awards en Hall of Fame-berekening.
│   ├── score_helpers.py      # Pure score- en klassementberekening.
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

### NAS -> GitHub Pages publiceren

In de NAS-app staat in het tabblad Geschiedenis de knop **Publiceer data**. Deze knop start de GitHub Actions-workflow via GitHub’s `workflow_dispatch` API. De workflow voert daarna zelf `publish_mirror.py` uit, commit de nieuwe momentopname en werkt GitHub Pages bij. Een succesmelding betekent dus alleen dat de workflow is gestart; GitHub Pages kan daarna nog enige tijd nodig hebben.

De publieke projectsite staat op `https://nubrodr.github.io/Manillen/`. De URL `https://nubrodr.github.io/` is alleen de gebruikerssite van GitHub en verwijst niet automatisch naar deze repository.

Stel in Portainer de volgende environment variables in voor de container:

- `GITHUB_TOKEN`: verplicht; een token met voldoende rechten om de geconfigureerde workflow te dispatchen.
- `GITHUB_REPOSITORY`: verplicht, in de vorm `owner/repository`.
- `GITHUB_WORKFLOW`: verplicht; voor de meegeleverde workflow is dit `publish-mirror.yml`.
- `GITHUB_REF`: optioneel; de ref waarop de workflow dispatcht, standaard `main`.

De meegeleverde workflow staat in `.github/workflows/publish-mirror.yml` en kan handmatig of via de NAS-knop worden gestart. De token wordt uitsluitend uit de environment gelezen en wordt nooit in de UI, logs of foutmeldingen getoond. De NAS-app voert zelf geen `publish_mirror.py` uit en maakt geen Git-commit. De volledige flow is:

```text
NAS-knop -> GitHub API -> workflow_dispatch -> publish_mirror.py -> GitHub commit -> GitHub Pages
```

`data/seasons_history.csv`, `data/seasons_playdays_legacy.csv` en `data/hall_of_fame_check.csv` zijn opgenomen in Git en worden niet genegeerd, zodat ze beschikbaar zijn in de Portainer Stack-from-Git-build. De Hall-of-Fame-check is alleen voor tests; hij wordt niet naar GitHub Pages geüpload.

## Read-only GitHub Pages-app

`mirror_app/` toont Geschiedenis, Tussenstand, Parenhistoriek, Seizoenen en Hall of Fame. Er zijn geen formulieren, score-invoer, indelingsknoppen of verwijderacties. De CSV’s in `mirror_app/data/` zijn een momentopname en worden niet live van de NAS gelezen. Op mobiel staat de navigatie sticky bovenaan met een hamburgerknop; de tabbladen klappen verticaal uit.

Werk de snapshot en GitHub Pages-export bij vanuit de repository-root:

```powershell
pip install -r mirror_app/requirements.txt
python publish_mirror.py
git add .
git commit -m "Update Manillen Pages-app"
git push
```

Het script kopieert `AllPlayers.csv`, pairing-, score- en reservegegevens, `seasons.csv`, `seasons_history.csv` en `seasons_playdays_legacy.csv` indien aanwezig naar `mirror_app/data/`, en voert `shinylive export mirror_app docs` uit. De Pages-app gebruikt deze snapshot voor seizoensfilters, historische tabbladen en reserveweergave. `hall_of_fame_check.csv` wordt niet gepubliceerd. Git-commando’s blijven bewust handmatig.

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
