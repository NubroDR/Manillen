---
description: "Use when changing the public read-only mirror, its snapshot data, Shinylive compatibility, or the GitHub Pages export."
name: "Public Mirror"
applyTo:
  - "mirror_app/**"
  - "site/**"
  - "manillen_core/**"
  - "generate_static_snapshot.py"
  - "build_static_site.py"
  - "publish_mirror.py"
  - "github_publish.py"
  - ".github/workflows/publish-mirror.yml"
  - ".github/workflows/deploy-pages.yml"
  - "docs/**/*.md"
---

# Public mirror guidance

- `mirror_app/` remains the current read-only Shinylive site until the static replacement passes preview, service-worker, rollback, and cutover acceptance. It must not modify its snapshot CSVs or provide write actions.
- The new public mirror uses `site/`, `manillen_core/`, and derived JSON generated from a datastore. `github_publish.py` uploads one JSON-only `static_snapshot.zip`; never upload source CSVs, backups, or private reports through this path.
- `publish_mirror.py` assembles either a local datastore snapshot or the uploaded archive into a new, empty output directory. The Pages workflow uses the archive and writes only generated site assets and JSON to `docs/`.
- `docs/` is generated output. Change the source or build scripts, then regenerate through the workflow; do not hand-edit generated runtime files in `docs/`.
- After each completed and locally validated mirror feature that changes the published site, deploy it to the separate preview repository `NubroDR/manillen-preview` at https://nubrodr.github.io/manillen-preview/ so the user can review it. This is standing user authorization; do not ask for per-deploy approval. Confirm the Pages workflow succeeds and check the preview before reporting completion.
- Build preview data only from the already-public `mirror_app/data` snapshot or another explicitly approved public snapshot. Never publish the NAS `data/` directory, source CSVs, backups, private reports, or migration artifacts.
- Keep preview deployment, production mirror publication, and production Pages deployment separate. Preview authorization does not authorize changing the main repository's `docs/`, publishing to production, or performing the production cutover; those still require separate explicit approval.
