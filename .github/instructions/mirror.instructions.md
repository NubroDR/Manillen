---
description: "Use when changing the public read-only mirror, its snapshot data, Shinylive compatibility, or the GitHub Pages export."
name: "Public Mirror"
applyTo:
  - "mirror_app/**"
  - "publish_mirror.py"
  - "docs/**/*.md"
---

# Public mirror guidance

- `mirror_app/` remains the current read-only Shinylive site until the static replacement passes preview, service-worker, rollback, and cutover acceptance. It must not modify its snapshot CSVs or provide write actions.
- The new public mirror uses `site/`, `manillen_core/`, and derived JSON generated from a datastore. `github_publish.py` uploads one JSON-only `static_snapshot.zip`; never upload source CSVs, backups, or private reports through this path.
- `publish_mirror.py` assembles either a local datastore snapshot or the uploaded archive into a new, empty output directory. The Pages workflow uses the archive and writes only generated site assets and JSON to `docs/`.
- `docs/` is generated output. Change the source or build scripts, then regenerate through the workflow; do not hand-edit generated runtime files in `docs/`.
- Keep the Pages deployment and mirror publication as separate workflows. Preserve their existing target URL and permission boundaries; do not run a live publish or cutover without explicit approval.
