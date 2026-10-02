# Confluence Audit Period And Grouped Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct manual/scheduled audit windows and produce a grouped Excel report with traceable invalid-format diagnostics.

**Architecture:** Extend the existing period, audit-result, service, store, and XLSX report owners. Do not add a second audit or export path. Persist compact sanitized diagnostics beside matrix states so history and reports share one source.

**Tech Stack:** Python dataclasses, PySide6 bridge, openpyxl-backed `support.report`, pytest.

## Global Constraints

- Manual window is Monday 00:00 through the trigger timestamp.
- Scheduled window is Monday 00:00 through Friday 00:00.
- Only `updated`, `not_updated`, and `invalid_format` remain valid matrix states.
- Status items 1 and 2 remain excluded; content semantic review, PDF, and screenshots remain inactive.
- Preserve all unrelated user-owned changes and do not expose credentials.

---

### Task 1: Trigger-aware audit periods

**Files:**
- Modify: `support/confluence_audit/period.py`
- Modify: `ui/example/bridge/ConfluenceAuditBridge.py`
- Modify: `support/confluence_audit/command.py`
- Test: `testing/self_tests/support/test_confluence_audit_scheduler.py`
- Test: `testing/self_tests/ui/test_confluence_audit_bridge.py`

**Interfaces:**
- Produces: one manual-period function and one scheduled-period function returning `AuditPeriod`.
- Consumes: `AuditExecutionContext.trigger`.

- [ ] Add failing tests for manual Monday-to-trigger and scheduled Monday-to-Friday windows.
- [ ] Run the focused tests and confirm the existing shared period behavior fails them.
- [ ] Route manual UI and scheduled command callers to the correct period function.
- [ ] Run the focused tests and confirm both boundary contracts pass.

### Task 2: Persist invalid-format diagnostics

**Files:**
- Modify: `support/confluence_audit/models.py`
- Modify: `support/confluence_audit/service.py`
- Modify: `support/confluence_audit/store.py`
- Test: `testing/self_tests/support/test_confluence_audit_service.py`

**Interfaces:**
- Produces: compact diagnostic fields attached to each `AttentionResult`.
- Consumes: page discovery/read exceptions and unexpected candidate responses.

- [ ] Add failing tests for missing, foreign, ambiguous, permission, and unreadable responses.
- [ ] Run focused tests and confirm the diagnostic data is currently lost.
- [ ] Add a sanitized diagnostic payload and map each invalid page kind to affected attention points.
- [ ] Round-trip the payload through history JSON and verify secrets/raw HTML are absent.

### Task 3: Grouped Excel report

**Files:**
- Modify: `support/confluence_audit/report.py`
- Extend only if needed: `support/report/xlsx.py`
- Test: `testing/self_tests/support/test_confluence_audit_pdf.py`
- Test: `testing/self_tests/support/test_report.py`

**Interfaces:**
- Consumes: `AuditBatch`, matrix states, persisted diagnostics.
- Produces: grouped XLSX sections keyed by `(support_mode, project_status)`.

- [ ] Add a failing workbook test covering multiple groups, cross-year projects, PS merging, and hyperlinks.
- [ ] Run the test and confirm repeated common columns and missing PS fail expectations.
- [ ] Emit one group row with mode, status, and period; emit project rows with year, name, link, 12 states, and PS.
- [ ] Merge repeated diagnostics by actual response and list all affected attention keys.
- [ ] Validate workbook values, layout, hyperlinks, and exact three-state vocabulary.

### Task 4: Regression and source validation

**Files:**
- Modify only durable tests required by Tasks 1-3.

**Interfaces:**
- Consumes: completed implementation.
- Produces: fresh acceptance evidence.

- [ ] Run all Confluence support and UI tests.
- [ ] Run `compileall` and `git diff --check`.
- [ ] Start source SmartTest with a bounded startup check.
- [ ] Export and visually inspect a representative grouped workbook.
