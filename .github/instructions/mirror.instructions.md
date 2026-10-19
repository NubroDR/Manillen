---
description: "Use when changing the public read-only mirror, its snapshot data, Shinylive compatibility, or the GitHub Pages export."
name: "Public Mirror"
applyTo:
  - "mirror_app/**"
  - "publish_mirror.py"
  - "docs/**/*.md"
---

# Public mirror guidance

- `mirror_app/` is a read-only public view; it must not modify its snapshot CSVs or provide write actions.
- The mirror consumes the checked-in snapshot in `mirror_app/data/`, not live NAS data. Update snapshots from the repository-root `data/` through `publish_mirror.py`.
- `publish_mirror.py` creates the Shinylive export in `docs/`. Change the source app or export script, then regenerate; do not hand-edit generated runtime files in `docs/`.
- Keep mirror code and dependencies compatible with the Shinylive/Pyodide export. Prefer the existing pure helper modules and avoid adding dependencies without verifying export support.
- The Pages deployment and mirror publication are separate workflows. Preserve their existing trigger and permission boundaries when changing either flow.
