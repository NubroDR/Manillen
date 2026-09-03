# Manillen

Een Shiny for Python-app om 2v2-manillen-tafels te organiseren voor een familie-speeldag. De app zoekt een eerlijke spelersverdeling, bewaart de speeldag, genereert scorebladen en houdt scores en klassementen bij.

## Functies

- Spelers selecteren met een typeahead-selector.
- Automatisch tafels van vier spelers indelen met zo weinig mogelijk herhaalde partners.
- Indelingen bewaren en eerdere speeldagen bekijken of verwijderen.
- Excel-scorebladen genereren vanuit een opgeslagen speeldag, met alleen het benodigde aantal reservevelden.
- Reservenamen per speeldag opslaan en automatisch opnieuw laden; reserves krijgen een afwijkende Excel-stijl.
- Scores voor de drie 2v2-spellen per tafel invoeren.
- Een tussenstand bekijken voor alle speeldagen of één specifieke speeldag.
- Een publieke, read-only Shinylive-mirror publiceren naar GitHub Pages.

## Projectstructuur

```text
.
├── app.py                    # Volledige schrijfbare NAS-app.
├── manillen_functions.py     # Indeling, paringen en scorebladlogica.
├── score_functions.py        # Schrijfbare scoreworkflow met gedeelde scoreberekening.
├── reserve_assignments.py    # Datumgebonden CRUD voor ingevulde reservenamen.
├── requirements.txt          # Dependencies voor de volledige app.
├── Dockerfile                # Image voor de volledige NAS-app.
├── docker-compose.yml        # Portainer Stack-configuratie.
├── docker-entrypoint.sh      # Seedt een leeg /app/data-volume.
├── .dockerignore             # Beperkt de Docker build context.
├── publish_mirror.py         # Snapshot kopiëren en Shinylive-export starten.
├── data/
│   ├── AllPlayers.csv        # Beschikbare spelers, één naam per regel.
│   ├── pairings.csv          # Partnerhistoriek met Player1, Player2, Count.
│   ├── pairings_history.csv  # Opgeslagen tafels per Date, Table en Players.
│   ├── scores_history.csv    # Scores per Date, Table en Game.
│   ├── reserve_assignments.csv # Ingevulde reservenamen per Date en Slot.
│   ├── Scorebladen.xlsx      # Leeg Excel-template.
│   └── Scorebladen/          # Gegenereerde scorebladen; lokaal genegeerd door git.
├── mirror_app/
│   ├── app.py                # Alleen-lezen Shiny-app voor publicatie.
│   ├── data/                 # Publieke snapshot van de CSV-data.
│   ├── data_helpers.py       # Pure geschiedenis- en paringreaders.
│   ├── score_helpers.py      # Pure score- en klassementberekening.
│   ├── requirements.txt      # Shinylive-compatibele mirror-dependency.
│   └── README.md             # Korte mirrorhandleiding.
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

## Tafelindeling en scores

De indeling gebruikt een greedy-algoritme. Het algoritme probeert meerdere startvolgordes, vormt telkens de best mogelijke groep van vier en minimaliseert eerst de meest herhaalde paring in de configuratie. Daarna gebruikt het het aantal herhaalde paringen en de totale paringtelling als tie-breakers. Reservespelers worden toegevoegd wanneer het aantal aanwezigen geen veelvoud van vier is; twee reservespelers komen niet samen aan één tafel.

Elke tafel speelt drie unieke 2v2-combinaties. Een spel loopt tot en met 101 punten. In de tussenstand worden spelers eerst gesorteerd op gewonnen spellen, daarna op aantal gespeelde spellen en vervolgens op puntensaldo. Het puntensaldo is punten voor min punten tegen.

## NAS-hosting

De schrijfbare app draait via de root-level `Dockerfile`. Shiny luistert in de container op `0.0.0.0:8000`; omdat poort 8000 op de NAS al bezet is, publiceert de compose-configuratie de app op NAS-poort `8080` via `8080:8000`.

Lokaal bouwen en starten:

```powershell
docker build -t manillen:latest .
docker run --rm -p 8080:8000 -v manillen_data:/app/data manillen:latest
```

Open de app lokaal of via Tailscale op `http://<nas-hostnaam>:8080`.

Het externe volume `manillen_data` moet vooraf bestaan. Bij een eerste start kopieert de entrypoint alleen ontbrekende basisbestanden naar `/app/data`, waaronder `Scorebladen.xlsx`. Bestaande CSV’s en scorebladen worden nooit overschreven. Gegenereerde scorebladen blijven samen met de datastore in het volume staan.

Maak in Portainer een Stack from Git repository met deze repository. De stack gebruikt `docker-compose.yml`, bouwt vanuit de repository-root, gebruikt containernaam `manillen`, restartbeleid `unless-stopped` en mount `manillen_data:/app/data`. Het volume is als `external: true` gedeclareerd en moet dus al aangemaakt zijn. Er wordt geen volledige repository in de container gemount.

Beperk de toegang tot het lokale netwerk of gebruik Tailscale om de NAS-app privé te bereiken. De app gebruikt absolute paden vanuit de projectcode en blijft daardoor onafhankelijk van de working directory. Na een nieuwe GitHub-versie kies je in Portainer **Pull and redeploy** of voer je een stack-update/redeploy uit, zodat de image opnieuw wordt gebouwd; `/app/data` blijft behouden.

De volledige NAS-app en de publieke mirror zijn aparte deployments. De Docker-container voert alleen `app.py` uit en draait `mirror_app/` niet als viewer.

## Publieke read-only mirror

`mirror_app/` toont alleen Geschiedenis, Tussenstand en Parenhistoriek. Er zijn geen formulieren, score-invoer, indelingsknoppen of verwijderacties. De CSV’s in `mirror_app/data/` zijn een snapshot en worden niet live van de NAS gelezen. Op mobiel staat de navigatie sticky bovenaan met een hamburgerknop; de drie tabs klappen verticaal uit.

Werk de snapshot en GitHub Pages-export bij vanuit de repository-root:

```powershell
pip install -r mirror_app/requirements.txt
python publish_mirror.py
git add .
git commit -m "Update publieke mirror"
git push
```

Het script kopieert `data/pairings.csv`, `data/pairings_history.csv`, `data/scores_history.csv` en `data/reserve_assignments.csv` indien aanwezig naar `mirror_app/data/`, en voert `shinylive export mirror_app docs` uit. De mirror gebruikt de reserve-snapshot om ingevulde reservenamen in de geschiedenis te tonen. Git-commando’s blijven bewust handmatig.

Stel GitHub Pages in via **Settings > Pages > Build and deployment**. Kies **Deploy from a branch**, selecteer de publicatiebranch en kies als map **`/docs`**.

Lokaal testen kan met:

```powershell
shiny run mirror_app/app.py
```

## Databestanden

- `AllPlayers.csv`: CSV zonder header, met één spelersnaam per regel.
- `pairings.csv`: CSV met de kolommen `Player1`, `Player2` en `Count`; elke rij is een ongesorteerd partnerpaar met de actuele telling.
- `pairings_history.csv`: CSV met `Date`, `Table` en `Players`; de vier spelers staan in één veld, gescheiden door ` | `.
- `scores_history.csv`: CSV met `Date`, `Table`, `Game`, `Team1Players`, `Team2Players`, `Team1Score` en `Team2Score`.
- `reserve_assignments.csv`: CSV met `Date`, `Slot` en `Name`; bewaart ingevulde reservenamen per speeldag.
- `Scorebladen.xlsx`: leeg Excel-template voor maximaal vier tafels.
- `Scorebladen/`: automatisch gemaakte Excel-bestanden per speeldatum; dit zijn uitvoerbestanden en worden niet getrackt.

## Licentie en auteur

Persoonlijk familieproject. Geen aparte open-sourcelicentie voorzien.
