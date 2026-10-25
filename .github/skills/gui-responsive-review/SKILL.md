---
name: gui-responsive-review
description: "Review and test web-page GUI consistency, responsive behavior, and mobile friendliness in this repository. Use for front-end/UI reviews, visual inconsistencies, accessibility checks, mobile layout audits, or validating webpage changes; inspect the implementation, exercise the UI at representative viewport sizes, and give evidence-based prioritized findings and suggestions."
---

# GUI and Responsive Review

## Purpose

Review the repository's web interfaces as a senior GUI reviewer. Find visual or interaction inconsistencies, test mobile and responsive behavior, and report actionable suggestions supported by source or browser evidence. This is a review-and-test workflow; do not change application code unless the user also asks for implementation.

## Workflow

1. **Establish scope and current behavior**
   - Read the repository `README.md` and relevant project instructions before testing.
   - Identify the target app, routes/tabs, source styles, and existing UI tests. In this repository, distinguish the writable Shiny app from the public read-only mirror.
   - Inspect the relevant source and existing patterns before judging an element inconsistent.
   - Treat `data/` as persistent user data. Use fixture or temporary data for tests; do not write to production data.

2. **Start or locate the app safely**
   - Prefer the repository's existing run/test commands. If the app must be started, use a local development process and verify that it responds before browser review.
   - Do not publish, dispatch workflows, or access private NAS data as part of a review.
   - If browser automation tools are available, search for the browser capabilities first and use the provided browser session for navigation, interaction, screenshots, and viewport changes. If they are unavailable, use existing automated checks and clearly state the manual/browser validation limitation.
   - Do not install new dependencies just for an audit without user approval. Use existing Playwright or browser tools when available.

3. **Review consistency**
   - Compare typography, spacing, colors, borders, control sizes, headings, navigation, active/disabled states, table/card patterns, and terminology across relevant views.
   - Check whether interactive elements look and behave consistently, and whether related data is presented with the same hierarchy and formatting.
   - Separate intentional differences between the writable app and public mirror from accidental inconsistencies.

4. **Exercise responsive layouts**
   - Test at minimum 360 px, 375 px, 390 px, and 768 px viewport widths, plus a desktop width. Include a narrow landscape viewport when relevant.
   - Visit every relevant route/tab and exercise menus, filters, selects, links, dialogs, tables, and any other key interaction.
   - Look for page-level horizontal overflow, clipped or overlapping content, unusable wide tables, hidden actions, cramped navigation, and content that requires hover.
   - For touch/mobile usability, check that important targets are approximately 44×44 px or larger, inputs use at least 16 px text to avoid iOS zoom, spacing supports touch, and controls remain usable with the on-screen keyboard.
   - Check visible focus, keyboard navigation, semantic headings/labels, and contrast where practical. Also consider safe areas, portrait/landscape, dark mode, and reduced motion when the UI supports them.
   - Capture screenshots or test output when the available browser tooling supports it. Findings must describe what was observed, not merely what the source appears likely to do.

5. **Verify and report**
   - Run the smallest relevant existing automated check. For measurable issues, state the viewport, route, interaction, and observed result; do not claim a test passed unless it was actually exercised.
   - Report findings in priority order using **Blocker**, **Major**, **Minor**, and **Nice-to-have**.
   - For each finding include: page/component and source location when identifiable, observed problem and reproduction context, user impact, a concrete suggestion, and effort estimate (S/M/L).
   - Distinguish verified defects from potential risks and note any untested browser/device combinations.
   - End with a concise summary of what was tested, what could not be tested, and the highest-value next improvements.

## Guardrails

- Preserve the existing visual language unless the user requests a redesign.
- Do not infer a defect from a screenshot alone when source or interaction can clarify it.
- Do not modify code, data, screenshots, or generated site output during a review unless requested.
- Avoid exposing credentials, private NAS data, or real user records in reports or screenshots.
