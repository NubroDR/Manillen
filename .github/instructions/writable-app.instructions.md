---
description: "Use when changing the writable Shiny NAS app, its player/table allocation, scoring, reserve assignments, or persistent CSV/Excel data handling."
name: "Writable Shiny App"
applyTo:
  - "app.py"
  - "manillen_functions.py"
  - "score_functions.py"
  - "reserve_assignments.py"
  - "github_publish.py"
---

# Writable app guidance

- `app.py` is the writable NAS application. Keep UI/session behavior there and reuse the focused helper modules for pairing, score, reserve-assignment, and GitHub workflow-dispatch logic.
- Resolve project and data paths from the source file location, not the process working directory.
- Keep persistent records in the existing CSV formats under `data/`; preserve unrelated dates/rows when updating date-specific data.
- The public mirror is read-only. Do not add user-data writes to `mirror_app/` or treat the mirror snapshot as the authoritative store.
- Keep user-provided names safe when rendering HTML, and never display or log the GitHub token.
- When changing score, pairing, or reserve behavior, check its effect on the history views, generated scorebladen, standings, and public mirror.
