# Jira Format Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans task-by-task. Steps use checkbox syntax.

**Goal:** Deliver a portable Jira format auditor and a manager-only SmartTest Jira audit view.

**Architecture:** `jira_handler.py` owns validation and XLSX export. Existing `jira_tool` owns Jira transport/query. `JiraBridge` adapts current issues for the handler and owns the UI model; QML only renders it.

**Tech Stack:** Python, requests-compatible Jira REST, openpyxl, PySide6/QML/FluentUI, pytest.

## Global Constraints

- Preserve all existing uncommitted changes.
- Do not duplicate Jira authentication, query, issue, or report models.
- Keep credentials out of code, logs, and reports.
- Require both Functional Acceptance and Code Quality PASS.

### Task 1: Standalone handler

**Files:** create `jira_handler.py`; create focused tests under `testing/self_tests/jira/`.

- [ ] Write failing fixture tests for embedded rules, Markdown overrides, manager normalization, violations, and workbook export.
- [ ] Reuse existing `jira_tool` field semantics while keeping the standalone file independent of SmartTest modules.
- [ ] Implement embedded rules, Markdown table/section loading, validation APIs, CLI input/query modes, and XLSX export.
- [ ] Run focused tests, CLI help/smoke, compile, and `git diff --check`.
- [ ] Complete reuse/abstraction/cleanup review; do not commit.

### Task 2: SmartTest integration

**Files:** modify `ui/example/bridge/JiraBridge.py`, `ui/example/imports/example/qml/page/T_Jira.qml`, both translation TS files, QRC output, and focused UI tests.

- [ ] Write failing bridge tests for manager gating, current-result validation, Markdown dependency, result rows, and export.
- [ ] Add narrow bridge APIs using `jira_handler`; keep QML display-only.
- [ ] Add manager-only FluentUI controls and translated text.
- [ ] Rebuild translations/QRC and run focused UI, translation, startup, and export tests.
- [ ] Complete functional and code-quality acceptance; do not commit or push until Atlas approves.
