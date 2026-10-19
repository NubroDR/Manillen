# Manillen voor GitHub Pages

Deze map bevat een alleen-lezen Shiny for Python-app voor GitHub Pages. De CSV-bestanden in `data/` zijn een momentopname; de app schrijft nooit naar deze bestanden. De momentopname bevat ook `AllPlayers.csv`, de seizoensregistratie en de twee historische seizoensbronnen. Zo kunnen Seizoenen, Hall of Fame, seizoensfilters en de per speeldag ingevulde reservenamen worden getoond. `hall_of_fame_check.csv` is uitsluitend testdata en wordt niet gepubliceerd.

Tussenstand en Speeldagen starten met het actieve seizoen als filter. De tussenstand kan daarnaast op één speeldag worden gefilterd. Parenhistoriek behoudt zijn bestaande spelerzoekfilter en gebruikt de all-time paringteller.

## Lokaal testen

Installeer de dependencies uit `mirror_app/requirements.txt` en start:

```text
shiny run mirror_app/app.py
```

## Publiceren

Voer vanuit de repository-root uit:

```text
python publish_mirror.py
```

Het script kopieert de actuele snapshots, voert `shinylive export mirror_app docs` uit en toont het exportpad. Publiceer daarna bewust zelf met `git add`, `git commit` en `git push`.

De GitHub Pages-deployment wordt uitgevoerd door `.github/workflows/deploy-pages.yml`. De publieke projectsite staat op `https://nubrodr.github.io/Manillen/`.