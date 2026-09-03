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

De schrijfbare app kan in Docker op de NAS draaien. Bouw een image met Python 3.11+, installeer `requirements.txt` en start de app op `0.0.0.0:8000`, bijvoorbeeld met `shiny run --host 0.0.0.0 --port 8000 app.py`. Koppel in Portainer een persistent volume aan `/app/data`, zodat CSV’s en gegenereerde scorebladen behouden blijven wanneer de container opnieuw wordt aangemaakt.

Maak in Portainer een stack met dezelfde image, poortmapping `8000:8000` en een bind mount van een NAS-map naar `/app/data`. Beperk de toegang tot het lokale netwerk of gebruik Tailscale om de NAS-app privé te bereiken. De app gebruikt absolute paden vanuit `app.py` en blijft daardoor onafhankelijk van de working directory.

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

Het script kopieert `data/pairings.csv`, `data/pairings_history.csv` en, indien aanwezig, `data/scores_history.csv` naar `mirror_app/data/`, en voert `shinylive export mirror_app docs` uit. Git-commando’s blijven bewust handmatig.

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
