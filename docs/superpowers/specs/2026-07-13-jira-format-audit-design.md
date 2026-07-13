# Jira Format Audit Design

## Goal

Provide a portable root-level `jira_handler.py` and integrate its audit capability into the SmartTest Jira page for managers, initially `chao.li`.

## Boundaries

- `jira_handler.py` is a standalone library/CLI. It must not import SmartTest UI, bridge, testing, or project logging modules.
- The standalone script embeds the current distilled Jira rules and runs without `jira规范.md`.
- When SmartTest calls the handler, it passes the repository `jira规范.md`. The handler reads its section text, module table, and label tables so replacing the Markdown updates report citations and table-driven values.
- Stable program checks validate Summary, Component, Description sections, Labels, Regression evidence, and attachment size. A new unsupported Markdown rule category is reported instead of silently accepted.
- Existing `jira_tool` remains the Jira query/auth owner. SmartTest passes fetched issue dictionaries into the handler; no second UI query or credential flow is added.

## Public Interfaces

`jira_handler.py` exposes issue normalization, `validate_issue`, `validate_issues`, Markdown rule loading, manager-name normalization/checking, and XLSX export. The CLI accepts Jira connection/JQL or local JSON input and writes an XLSX report without storing credentials.

Validation results contain issue key/URL, overall result, rule id, specification section/text, Jira field/value, failure reason, and correction guidance.

## SmartTest Flow

`AuthBridge username -> JiraBridge manager check -> current issue rows/raw issues -> jira_handler validation -> bridge-owned audit view model -> T_Jira display/export`.

Only managers see or use the audit controls. The initial manager set is `chao.li`; normalization supports case differences, `DOMAIN\\user`, and `user@domain`.

## Report

Export `.xlsx` with `Summary` and `Details` sheets. Summary contains totals, pass rate, JQL/time, and violation counts. Details contains one row per issue/rule violation for filtering and review.

## Acceptance

- The standalone script validates fixtures and exports a readable workbook without the Markdown file.
- SmartTest loads `jira规范.md`, restricts the feature to `chao.li`, reuses current Jira results, and exposes translated UI text.
- Focused tests, translation audit, QRC rebuild, source startup validation, scoped diff review, functional acceptance, and code-quality acceptance pass.
