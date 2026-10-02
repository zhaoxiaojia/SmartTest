# Confluence Multi-Space Project Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. SmartTest only permits the existing Mason worker; do not dispatch additional agents.

**Goal:** Replace year-table-driven discovery with direct project-root traversal across DOPL and SDPL, while keeping Year, Support Mode, and Project Status as the only eligibility filters.

**Architecture:** Treat each configured Project Space as a source, each `YYYY Projects` page as a year owner, and each direct child of a year page as a project root. Read only the project root's Project Target fields needed for filtering and identity, merge both spaces using a space-qualified identity, then reuse the existing child-page audit flow.

**Tech Stack:** Python 3.10, existing Confluence REST client, dataclasses, `smart_log`, pytest, PySide/QML bridge.

## Global Constraints

- Sources are fixed to DOPL and SDPL; the UI does not expose a Project Space filter.
- Candidate eligibility uses only Year, Support Mode, and Project Status.
- `Current Stage`, Project Owner, ODM, OEM/Operator, OS, dates, and other fields never exclude a project.
- Project names and URLs always refer to direct children of a `YYYY Projects` page.
- Cross-space identity is `space_key + project_root_page_id`.
- A failed space/year/project does not block readable sources; partial results must be explicit.
- Delete the old year table, Project Link, parent-chain inference, distance selection, and compatibility mechanisms.
- Preserve all user-owned workspace changes; do not commit, push, build packages, or write to Confluence.

---

### Task 1: Establish the Multi-Space Collection Contract

**Files:**
- Modify: `support/confluence_audit/models.py`
- Modify: `support/confluence_audit/project_collection.py`
- Test: `testing/self_tests/support/test_confluence_project_collection.py`

**Interfaces:**
- Produces: a project identity that includes `space_key` and project-root `pageId`.
- Produces: collection metadata that can report partial source/year failures without exposing project content.
- Preserves: `ProjectCollectionFilter` eligibility values for years, support modes, project statuses, and selected project identities.

- [ ] **Step 1: Add failing cross-space identity tests**

Add tests proving that two projects with the same title and Project ID but different `space_key`/root page IDs both survive consolidation and selection. Assert that `Current Stage` and all non-filter attributes do not affect inclusion.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest testing\self_tests\support\test_confluence_project_collection.py -q
```

Expected: failures show the current identity collapses cross-space projects or the model lacks `space_key`.

- [ ] **Step 3: Implement the minimal model and filtering changes**

Extend the existing project model with a stable `space_key` and root identity. Keep `filter_projects(...)` limited to:

```python
year_match and support_mode_match and project_status_match
```

Selection must use the space-qualified root identity rather than a potentially duplicated Project ID. Do not create a second filter pipeline.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run the Task 1 command and require exit code `0`.

---

### Task 2: Replace Year-Table Parsing with Direct Root Traversal

**Files:**
- Modify: `support/confluence_audit/discovery.py`
- Modify if required: `support/confluence_integration/client.py`
- Test: `testing/self_tests/support/test_confluence_project_discovery.py`
- Test if client changes: `testing/self_tests/support/test_confluence_client.py`

**Interfaces:**
- Consumes: fixed source definitions for DOPL and SDPL.
- Produces: `discover_project_collection(...)` results whose projects are direct children of a year page.
- Produces: aggregate diagnostics by space/year: root count, readable count, matched count, and error count.

- [ ] **Step 1: Add failing hierarchy-first discovery tests**

Cover these behaviors with real model objects and bounded fake clients:

```text
DOPL Project Space -> 2025 Projects -> direct project roots
SDPL Project Space -> 2026 Projects -> direct project roots
```

Assert that:

- both spaces are merged;
- only requested years are traversed;
- each direct child is fetched and its Project Target table supplies Support Mode and Project Status;
- missing Project ID falls back to the space-qualified root page ID;
- missing Current Stage, Owner, ODM, OS, or dates does not reject a project;
- missing Mode or Status records an unreadable/indeterminate project diagnostic;
- Basic Information and Status Report descendants never become projects;
- failure of one space or one year leaves other results available and marks the collection partial.

- [ ] **Step 2: Run discovery tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest testing\self_tests\support\test_confluence_project_discovery.py testing\self_tests\support\test_confluence_client.py -q
```

Expected: failures show the current dependency on year-page HTML tables and Project Link ownership inference.

- [ ] **Step 3: Implement direct traversal**

Use the existing Confluence client boundary:

```python
get_page_by_url(project_space_url)
get_page_children(project_space_page.id)
get_page_by_url(year_page.url)
get_page_children(year_page.id)
get_page_by_url(project_root.url)
```

For each project root, parse the first Project Target-style two-column table containing `Support Mode` and `Project Status`. Read `Project ID` when present; otherwise use the root page ID as the internal identity component. Store the direct child title/URL as the authoritative project name/home URL.

Continue at space, year, and project boundaries with structured aggregate errors. Never log project titles, IDs, page bodies, people, or credentials.

- [ ] **Step 4: Delete superseded discovery code**

Remove:

```text
_projects_from_year_page
year table required-header validation
Project Link extraction
_project_owner
entry-depth/root-distance selection
fallback discovery from year-table/Base Information assumptions
diagnostics that only describe year-table rows or root dedupe repair
```

Keep one hierarchy-first discovery flow.

- [ ] **Step 5: Run discovery/client tests and verify GREEN**

Run the Task 2 command and require exit code `0`.

---

### Task 3: Update Bridge, Persistence, and Presentation

**Files:**
- Modify: `ui/example/bridge/ConfluenceAuditBridge.py`
- Modify if source text is owned there: `ui/example/imports/example/qml/component/confluenceaudit/ConfluenceAuditWorkspace.qml`
- Modify if fixed text changes: `ui/example/example_en_US.ts`
- Modify if fixed text changes: `ui/example/example_zh_CN.ts`
- Modify: `support/confluence_audit/plans.py`
- Modify: `support/confluence_audit/service.py`
- Test: `testing/self_tests/ui/test_confluence_audit_bridge.py`
- Test: `testing/self_tests/support/test_confluence_audit_plans.py`
- Test: `testing/self_tests/support/test_confluence_audit_service.py`

**Interfaces:**
- Consumes: the unified DOPL+SDPL collection.
- Produces: unchanged user filters for years, support modes, and project statuses.
- Produces: a neutral source label such as `DOPL + SDPL Project Spaces`; no source selector.

- [ ] **Step 1: Add failing bridge and plan tests**

Assert that refresh invokes unified discovery, filter state contains only years/modes/statuses, candidate identities remain unique across spaces, and stored plans do not restore a single-space URL as active product scope. Add a migration assertion for existing stored data containing the legacy `sourceUrl`: it must load safely while product discovery still uses both fixed spaces.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest testing\self_tests\ui\test_confluence_audit_bridge.py testing\self_tests\support\test_confluence_audit_plans.py testing\self_tests\support\test_confluence_audit_service.py -q
```

- [ ] **Step 3: Implement minimal bridge and persistence changes**

Remove the single editable/active source URL from filtering semantics. Preserve backward reading of existing plan JSON only at the serialization boundary; do not keep a legacy discovery branch. Present both spaces as one collection.

- [ ] **Step 4: Regenerate translations if visible fixed text changed**

Use the repository translation script required by `smarttest-ui-workflow`; do not hand-edit generated location metadata.

- [ ] **Step 5: Run tests and verify GREEN**

Run the Task 3 command and require exit code `0`.

---

### Task 4: Cleanup and Full Verification

**Files:**
- Review all files changed in Tasks 1–3.
- Delete obsolete tests that assert year-table, Project Link, parent-chain, or single-source behavior.

**Interfaces:**
- Produces: one multi-space hierarchy-first discovery owner with no compatibility execution path.

- [ ] **Step 1: Search for obsolete mechanisms**

Run:

```powershell
rg -n "_projects_from_year_page|_project_owner|Project Link|required header|root_dedupe_count|entry_depth|sourceUrl" support\confluence_audit ui\example\bridge testing\self_tests\support testing\self_tests\ui
```

Every remaining match must be either an intentional legacy-data migration assertion or unrelated reader-facing text. Remove abandoned helpers, tests, and diagnostic fields.

- [ ] **Step 2: Review production-code growth and ownership**

Confirm discovery reuses the existing Confluence client and filter owner, introduces no parallel collection, and deletes more legacy mechanism than it adds replacement mechanism where practical.

- [ ] **Step 3: Run the complete scoped verification**

```powershell
.\.venv\Scripts\python.exe -m pytest testing\self_tests\support -q
.\.venv\Scripts\python.exe -m pytest testing\self_tests\ui\test_confluence_audit_bridge.py testing\self_tests\ui\test_tool_page.py testing\self_tests\ui\test_owned_ui_translations.py testing\self_tests\ui\test_frontend_persistence_contract.py -q
.\.venv\Scripts\python.exe -m compileall -q support\confluence_audit support\confluence_integration ui\example\bridge\ConfluenceAuditBridge.py
git diff --check
```

All commands must exit `0`.

- [ ] **Step 4: Perform the highest practical read-only environment validation**

Using valid transient LDAP credentials through the existing SmartTest flow, refresh collection options once and verify aggregate logs report both `DOPL` and `SDPL`, selected years, total readable roots, filter exclusions, and final candidates. Do not print page content or credentials and do not write to Confluence.

- [ ] **Step 5: Return the SmartTest delivery report**

Report changed/deleted files, RED/GREEN evidence, full verification commands and exit codes, partial-access limitations, relevant dirty status, reuse decision, net production-code growth, and Mason task identity. Do not commit or push before Coco confirms functional completeness.
