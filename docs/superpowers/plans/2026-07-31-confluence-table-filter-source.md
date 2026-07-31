# Confluence Table Filter Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans`. SmartTest only permits the existing Mason worker.

**Goal:** Replace multi-space project-root crawling with two Project Space summary-table reads and remove History end to end.

**Architecture:** Parse the DOPL and SDPL Table Filter source tables into a compact catalog, derive the three filter option sets from catalog columns, and filter the catalog locally. Keep project-detail discovery only at audit execution.

**Tech Stack:** Python 3.10, existing Confluence REST client, HTML table parser, PySide/QML, pytest.

## Global Constraints

- Only Year, Support Mode, and Project Status affect candidates.
- Year comes from Date of Commercial approval.
- No Table Filter browser session/private JS API dependency.
- No candidate-time project-detail requests.
- Delete the old crawl and History mechanisms; no parallel compatibility flow.
- No commit, push, package build, or Confluence writes.

---

### Task 1: Summary-Table Catalog Parser

**Files:**
- Modify: `support/confluence_audit/discovery.py`
- Modify if needed: `support/confluence_audit/models.py`
- Test: `testing/self_tests/support/test_confluence_project_discovery.py`

- [ ] Add RED tests with DOPL/SDPL rendered tables proving one page read per space, required-column recognition, date-year parsing, cross-space identity, partial-space failure, and zero project-detail calls.
- [ ] Run focused tests and confirm failures are caused by the existing child/root crawl.
- [ ] Implement one summary-table parser using existing `html_tables`, `links`, and `text` helpers. Select tables by required headers, merge split/repeated header tables without duplicating rows, and emit compact catalog rows.
- [ ] Delete `get_page_children` candidate crawling, project-root Project Target reads, year-directory traversal, and their diagnostics/helpers.
- [ ] Run focused tests and require exit 0.

### Task 2: Filter Options and Candidate Projection

**Files:**
- Modify: `support/confluence_audit/project_collection.py`
- Modify: `ui/example/bridge/ConfluenceAuditBridge.py`
- Test: `testing/self_tests/support/test_confluence_project_collection.py`
- Test: `testing/self_tests/ui/test_confluence_audit_bridge.py`

- [ ] Add RED tests proving available years/modes/statuses derive from catalog fields, empty selection means all, and repeated refresh while busy submits only one job.
- [ ] Add a RED bridge test proving stale available values/candidates are cleared when refresh starts.
- [ ] Implement the single local filter owner and one in-flight refresh guard. Manual refresh bypasses cache; ordinary initialization may reuse account-scoped cache.
- [ ] Remove obsolete source/year-directory projection and root/readable/matched diagnostics.
- [ ] Run focused tests and require exit 0.

### Task 3: Remove History End to End

**Files:**
- Modify: `ui/example/imports/example/qml/component/confluenceaudit/ConfluenceAuditWorkspace.qml`
- Modify: `ui/example/bridge/ConfluenceAuditBridge.py`
- Modify/delete as ownership proves: `support/confluence_audit/store.py`
- Modify: `support/confluence_audit/service.py`
- Modify: translations only through the repository translation workflow if fixed text changes
- Update/delete corresponding support/UI tests

- [ ] Add/adjust contract tests so History controls, state keys, slots, and historical selection are absent while current result/export remain.
- [ ] Remove QML History UI and bridge history projection/selection/loading.
- [ ] Trace store consumers and delete only History-owned APIs; retain the minimal current-batch persistence needed by scheduler/export, or delete store if no remaining consumer exists.
- [ ] Remove obsolete History tests and regenerate translations if required.
- [ ] Run bridge, service, store, tool-page, translation, and persistence tests.

### Task 4: Cleanup and Verification

- [ ] Search for `PROJECT_SPACES`, year-root crawl helpers, `get_page_children` candidate use, root/readable/matched diagnostics, `history`, and `selectHistory`; remove obsolete matches and tests.
- [ ] Review net production-code change and ensure no new Table Filter plugin transport or browser automation exists.
- [ ] Run all `testing/self_tests/support`, scoped UI tests, compileall, and `git diff --check`.
- [ ] Report RED/GREEN evidence, changed/deleted files, remaining store ownership, performance request count, limitations, and task identity.
