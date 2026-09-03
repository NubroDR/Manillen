# Publieke Manillen-mirror

Deze map bevat een read-only Shiny for Python-app voor GitHub Pages. De CSV-bestanden in `data/` zijn een snapshot; de app schrijft nooit naar deze bestanden.

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

Stel in GitHub in via **Settings > Pages > Build and deployment**: kies **Deploy from a branch**, selecteer de publicatiebranch en als map **`/docs`**.