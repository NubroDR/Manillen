# Publieke Manillen-mirror

Deze map bevat een read-only Shiny for Python-app voor GitHub Pages. De CSV-bestanden in `data/` zijn een snapshot; de app schrijft nooit naar deze bestanden. Naast de indelings- en scoredata bevat de snapshot ook `reserve_assignments.csv`, zodat ingevulde reservenamen in Geschiedenis zichtbaar blijven.

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