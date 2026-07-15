# Jira Integration Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the current `jira_tool` into reusable `support/jira_integration` infrastructure and a root `jira` package owned only by the Jira page.

**Architecture:** Move REST, authentication, fields, stable models, caches, issue access, and sync into the global support package. Move workspace, browse, analysis, presentation, request/payload, query, and composition services into the Jira page package; the page package depends inward on the global integration.

**Tech Stack:** Python 3, Jira Server/Data Center REST, pytest, PySide6 bridge.

## Global Constraints

- The existing Jira page behavior and persisted data remain compatible.
- No `jira_tool` compatibility facade remains.
- The global package is named exactly `support.jira_integration`, not `jira` and not `jira_automation`.
- Create Issue is not implemented in this phase.

---

### Task 1: Establish the global Jira integration package

**Files:**
- Move: `jira_tool/auth`, `cache`, `core`, `fields`, and `transport` to `support/jira_integration/`
- Move: `jira_tool/services/issue_service.py` and `sync_service.py` to `support/jira_integration/services/`
- Create/modify: package exports and global integration README
- Test: Jira transport, field, cache, issue, and sync tests

**Interfaces:**
- Consumes: current stable Jira client/model/service contracts.
- Produces: the same public symbols below `support.jira_integration` with no Qt or page dependency.

- [ ] **Step 1: Change global-owner tests to import the target package**

Replace `jira_tool` imports in transport, cache, fields, issue-service, and sync-service tests with `support.jira_integration` imports. Add a boundary assertion that the package source does not import `jira`, `ui`, or Qt.

- [ ] **Step 2: Verify target imports fail**

Run the focused Jira global-owner tests.

Expected: collection fails because `support.jira_integration` is absent.

- [ ] **Step 3: Move global owners and update internal imports**

Preserve class and function signatures while changing absolute imports to `support.jira_integration...`. Do not copy files, retain duplicate registries, or add forwarding modules.

- [ ] **Step 4: Verify the global layer**

Run focused global-owner tests and:

```powershell
.\.venv\Scripts\python.exe -m compileall support\jira_integration
rg -n "from jira_tool|import jira_tool" support\jira_integration
```

Expected: tests pass; compileall exits `0`; `rg` returns no matches.

### Task 2: Establish the Jira page package

**Files:**
- Move: remaining `jira_tool/services/*.py` to `jira/`
- Move/split: `jira_tool/README.md` into the two owners
- Modify: `ui/example/bridge/JiraBridge.py` and package composition imports
- Test: existing Jira page, service-boundary, and bridge tests

**Interfaces:**
- Consumes: `support.jira_integration` client, models, fields, caches, issue service, and sync service.
- Produces: Jira page workspace/browse/analysis/presentation services under root `jira`.

- [ ] **Step 1: Update page-owner tests to the target imports**

Change imports for workspace, browse, analysis, presenter, query builder, payloads, requests, specs, and factory to root `jira`. Assert `tool` and future Redmine code do not import root `jira` for Jira API access.

- [ ] **Step 2: Verify target imports fail**

Run the current Jira service and bridge boundary tests.

Expected: collection fails because root `jira` is absent.

- [ ] **Step 3: Move page owners and compose dependencies**

Move the page-specific modules without compatibility wrappers. `jira/factory.py` must construct page services from `support.jira_integration` dependencies. Update `JiraBridge` to depend on the root Jira page facade and keep REST/field/cache logic out of the bridge.

- [ ] **Step 4: Run Jira acceptance**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest testing\self_tests\jira_tool testing\self_tests\ui\test_jira_bridge_service_boundary.py -q
.\.venv\Scripts\python.exe -m compileall support\jira_integration jira ui\example\bridge\JiraBridge.py
rg -n "from jira_tool|import jira_tool" --glob "*.py" .
git diff --check
```

Expected: tests pass; compilation succeeds; no Python imports reference `jira_tool`; diff check exits `0`.

- [ ] **Step 5: Commit the split**

```powershell
git add support\jira_integration jira ui\example\bridge\JiraBridge.py testing
git commit -m "refactor: separate Jira integration from page logic"
```

