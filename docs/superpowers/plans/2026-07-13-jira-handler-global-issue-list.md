# Jira Handler Global Issue List Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run `jira_handler.py` from an in-file configuration and expose one reusable global Jira issue list for every business operation.

**Architecture:** Extend the existing standalone module rather than creating another client. Source resolution produces either issue keys or JQL, one loader populates `ISSUE_LIST` in place, and the existing validator/exporter consumes that list.

**Tech Stack:** Python 3 standard library, pytest, Jira REST API v2, XLSX ZIP/XML writer already in `jira_handler.py`.

## Global Constraints

- Do not require command-line business arguments.
- Do not add third-party dependencies.
- Never print or return the configured password.
- Preserve existing embedded-rule, Markdown-rule, validation, and XLSX behavior.
- Preserve unrelated staged and unstaged workspace changes; do not commit or push.

---

### Task 1: Configured Jira Source Resolution

**Files:**
- Modify: `jira_handler.py`
- Test: `testing/self_tests/jira/test_jira_handler.py`

**Interfaces:**
- Consumes: `JIRA_CONFIG: dict[str, Any]` with `jql`, `jira_url`, and `issue_keys`.
- Produces: `resolve_issue_source(config: dict[str, Any]) -> dict[str, Any]` containing either `issue_keys` or `jql`.

- [ ] **Step 1: Write failing tests** for `/browse/TV-123`, encoded `jql`, `filter=12345`, explicit key lists, empty configuration, and unsupported URLs.
- [ ] **Step 2: Run** `.venv\Scripts\python.exe -m pytest testing/self_tests/jira/test_jira_handler.py -q` and confirm the new tests fail because the resolver does not exist.
- [ ] **Step 3: Implement minimal source parsing** with `urllib.parse.urlparse`, `parse_qs`, URL decoding, issue-key validation, and a REST filter resolver using the existing authenticated request boundary.
- [ ] **Step 4: Re-run the focused tests** and confirm all source-resolution tests pass.

### Task 2: One Global Issue List

**Files:**
- Modify: `jira_handler.py`
- Test: `testing/self_tests/jira/test_jira_handler.py`

**Interfaces:**
- Produces: `ISSUE_LIST: list[dict[str, Any]]` and `load_global_issues(config: dict[str, Any] | None = None) -> list[dict[str, Any]]`.
- Consumes: `resolve_issue_source`, existing Jira request logic, and the full audit field set.

- [ ] **Step 1: Write failing tests** proving `ISSUE_LIST` keeps its object identity, is replaced in place, and only one Jira search is performed for all configured business operations.
- [ ] **Step 2: Run the focused tests** and confirm failure because the global loader is absent.
- [ ] **Step 3: Implement the loader** with `ISSUE_LIST.clear()` plus `ISSUE_LIST.extend(...)`; add an issue-key JQL query path and reuse the existing paginated search.
- [ ] **Step 4: Re-run the focused tests** and confirm the global-list tests pass.

### Task 3: Direct Execution And Business Dispatch

**Files:**
- Modify: `jira_handler.py`
- Test: `testing/self_tests/jira/test_jira_handler.py`

**Interfaces:**
- Consumes: `JIRA_CONFIG`, `ISSUE_LIST`, `validate_issues`, and `export_xlsx`.
- Produces: `run_format_audit(issues: list[dict[str, Any]], config: dict[str, Any]) -> Path` and `main() -> int`.

- [ ] **Step 1: Write a failing direct-execution test** that invokes `main()` with patched in-file configuration and request boundaries, supplies no CLI arguments, and verifies the audit receives the exact global list object.
- [ ] **Step 2: Run the test** and confirm the current argument parser prevents direct execution.
- [ ] **Step 3: Replace CLI dispatch with configuration dispatch** while leaving reusable validation/export functions public. Keep `if __name__ == "__main__": sys.exit(main())`.
- [ ] **Step 4: Run** `.venv\Scripts\python.exe -m pytest testing/self_tests/jira -q` and confirm the full standalone suite passes.
- [ ] **Step 5: Run** `.venv\Scripts\python.exe -m compileall -q jira_handler.py testing/self_tests/jira` and `git diff --check`.

## Self-Review

- All design requirements map to Tasks 1-3.
- Function names and data types are consistent across tasks.
- No new file or abstraction is introduced beyond the module-level configuration, source resolver, global loader, and business entrypoint required by the request.
