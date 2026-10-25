---
name: manillen-testing
description: "Plan, add, run, or troubleshoot tests for the Manillen Python/Shiny repository. Use when validating code changes, fixing bugs, adding pytest coverage, investigating test failures, or selecting a safe regression and smoke-test strategy for the writable app, data helpers, publishing, or read-only mirror."
---

# Manillen Testing

## Purpose

Validate Manillen changes with focused, meaningful tests while protecting persistent user data. Prefer existing pytest patterns and the smallest test command that directly covers the change; expand to broader suites when risk or results justify it.

## Workflow

1. **Understand the change and test setup**
   - Read `README.md`, `.github/copilot-instructions.md`, and any matching scoped instructions before changing code or test files.
   - Inspect the affected implementation, neighboring tests, and project test configuration. Reuse existing fixtures and helpers rather than inventing parallel conventions.
   - Determine whether the change concerns pure logic, CSV/file behavior, Shiny startup, publishing, or browser UI, and select tests that exercise the actual behavior.

2. **Protect persistent data**
   - Treat `data/` and NAS-mounted data as user data. Never use them as writable test fixtures or reset/delete their contents.
   - The existing `tests/conftest.py` sets `MANILLEN_DATA_DIR` to an isolated temporary directory for pytest. Preserve this isolation; ensure subprocess tests inherit the temporary environment and tests that write files use `tmp_path` or equivalent temporary locations.
   - If a proposed check could access or modify real data, stop and adapt it to temporary fixtures before running.

3. **Write tests at the right level**
   - Add pure unit tests for deterministic calculations and validation, with explicit edge cases and expected outputs.
   - Add integration tests for CSV schemas, path resolution, backups, atomic writes, migration behavior, and publishing boundaries. Assert both intended results and preservation of unrelated data.
   - For Shiny or mirror changes, test startup/rendering and relevant user interactions when the project’s available tooling supports it. Keep the writable app and public read-only mirror boundaries explicit; the mirror must never write.
   - For data migrations, verify dry-run immutability, idempotence, backup behavior, referential integrity, and before/after invariants using disposable copies. Never run apply against the repository's real `data/` during tests.
   - Prefer regression tests that fail on the original bug and pass after the fix. Avoid tests that merely mirror implementation details.

4. **Run focused validation**
   - Start with the specific test file or test node for the changed behavior, using the repository environment (normally `.venv`).
   - Run the complete suite with `pytest` when changes cross module boundaries, alter shared behavior, or when focused tests reveal broader risk.
   - Run an app-start or publishing smoke test only when it is relevant and can be isolated from persistent data and live publication.
   - Do not install dependencies or add test tooling solely for a task without user approval. If a check cannot run because tooling is unavailable, report the limitation and a safe alternative rather than claiming success.

5. **Report accurately**
   - State the exact commands/checks run and their outcomes.
   - Report failures with the relevant test name and concise cause; distinguish code failures from environment/tooling failures.
   - State which important paths or behaviors were not exercised. Never claim a smoke, browser, migration, or full-suite test passed unless it actually ran.

## Guardrails

- Do not alter production data to make a test pass.
- Do not silently skip failed assertions or weaken existing regression coverage to accommodate a change.
- Do not run publishing workflows, mutate live GitHub Pages, or use credentials as part of routine tests.
- Keep tests deterministic, isolated, and aligned with Python 3.11+ and the dependencies already declared by the project.
