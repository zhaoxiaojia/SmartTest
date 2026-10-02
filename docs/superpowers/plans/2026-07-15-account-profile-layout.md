# Account Profile Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved account profile card and compact account footer using dynamic personnel data and project-local avatars.

**Architecture:** Extend `AuthBridge` as the single profile view-model boundary: it authenticates, resolves LDAP `displayName` against `config/personnel.json`, computes presentation-ready dynamic fields, and owns avatar import. Extend the existing account footer through its local icon delegate and account window without changing shared FluentUI navigation behavior except for the smallest model/delegate height contract required by the compact account item.

**Tech Stack:** Python 3, PySide6 QObject/Property/Slot, QML/FluentUI, JSON, pytest, Qt resources.

## Global Constraints

- Dynamic personnel values render verbatim and never pass through `tr()` or `qsTr()`.
- Fixed frontend labels remain bilingual in both TS catalogs.
- Store both employee `display_name` and unique LDAP/SmartTest `account`; do not store a redundant full email address.
- Uploaded avatars are stored under `config/avatars/`; server upload is out of scope.
- Preserve all unrelated user-owned workspace changes.
- Follow TDD: each production behavior starts with a focused failing test.

---

### Task 1: Personnel reporting relationships

**Files:**
- Modify: `config/personnel.json`
- Test: `testing/self_tests/ui/test_auth_bridge_profile.py`

**Interfaces:**
- Consumes: existing `employees[].display_name` and `employees[].employment.grade`.
- Produces: `employees[].reports_to: str`.

- [ ] Write a failing test that loads the real personnel file and asserts the five Chen Chen reports, their required grades, and that every M3/M4 employee reports to Xiuyue Zhang.
- [ ] Run `./.venv/Scripts/python.exe -m pytest -q testing/self_tests/ui/test_auth_bridge_profile.py` and confirm the relationship assertions fail because `reports_to` is absent.
- [ ] Add `reports_to` to employee records, set the five named reports to `Chen Chen`, set every current M3/M4 record to `Xiuyue Zhang`, and leave other unknown relationships empty.
- [ ] Re-run the focused test and confirm it passes.

### Task 2: Profile resolution and initials

**Files:**
- Modify: `ui/example/bridge/AuthBridge.py`
- Test: `testing/self_tests/ui/test_auth_bridge_profile.py`

**Interfaces:**
- Consumes: LDAP `displayName`, authenticated username, `config/personnel.json`.
- Produces: bridge properties for display name, initials, grade/title, organization, product lines, and manager, plus a profile-changed signal.

- [ ] Write failing tests proving exact display-name matching, dynamic values returned verbatim, `Xiaojia Zhao -> XZ`, single-word fallback, and unmatched-profile behavior.
- [ ] Run the focused tests and confirm failures are caused by missing profile APIs.
- [ ] Add small pure helpers for personnel loading/matching and initials, then expose presentation-ready bridge properties without translating dynamic values.
- [ ] Extend the existing LDAP lookup to request `displayName` alongside photo attributes and establish the matched profile on successful login/state restoration.
- [ ] Re-run focused tests and the existing auth/Jira boundary test.

### Task 3: Project-local avatar import

**Files:**
- Modify: `ui/example/bridge/AuthBridge.py`
- Test: `testing/self_tests/ui/test_auth_bridge_profile.py`
- Create: `config/avatars/.gitkeep`

**Interfaces:**
- Consumes: local file URL/path selected by QML and current display name.
- Produces: `AuthBridge.importAvatar(source) -> dict`, persisted avatar URL, and profile change notification.

- [ ] Write failing tests for accepted PNG/JPEG input, unsupported/nonexistent input rejection, deterministic destination confinement under `config/avatars`, and uploaded-avatar precedence over LDAP cache.
- [ ] Run the focused tests and confirm expected failures.
- [ ] Implement image validation and non-destructive copy using resolved-path confinement and a deterministic safe filename.
- [ ] Re-run focused tests and confirm all avatar cases pass.

### Task 4: Account card and compact navigation footer

**Files:**
- Modify: `ui/example/imports/example/qml/global/ItemsFooter.qml`
- Modify: `ui/example/imports/example/qml/window/LoginWindow.qml`
- Modify only if required: `ui/FluentUI/imports/FluentUI/Controls/FluNavigationView.qml`
- Modify: `ui/example/example_en_US.ts`
- Modify: `ui/example/example_zh_CN.ts`
- Modify: `ui/example/imports/resource.qrc`
- Regenerate: `ui/example/imports/resource_rc.py`
- Test: `testing/self_tests/ui/test_auth_bridge_profile.py`

**Interfaces:**
- Consumes: AuthBridge profile/avatar properties and `importAvatar` slot; navigation Compact/Open state.
- Produces: A-style signed-in card, clickable avatar picker, expanded footer identity, and compact 32 px avatar/name stack.

- [ ] Add source-structure tests asserting dynamic bridge properties are not wrapped in translation and the account QML contains the required compact/avatar-upload bindings.
- [ ] Run the focused tests and confirm the QML assertions fail.
- [ ] Implement the expanded account footer and A-style account window with a `FileDialog`; keep fixed labels translated and dynamic values raw.
- [ ] Implement the account-only compact height/delegate behavior while preserving standard 38 px rows and 15 px icons.
- [ ] Update both translation catalogs for fixed labels only, rebuild `resource_rc.py`, and re-run focused profile and owned-translation tests.

### Task 5: Integrated verification and cleanup

**Files:**
- Verify all scoped files above.

**Interfaces:**
- Consumes: completed profile bridge, personnel relations, and QML presentation.
- Produces: source-validated account experience with concise evidence.

- [ ] Run `./.venv/Scripts/python.exe -m pytest -q testing/self_tests/ui/test_auth_bridge_profile.py testing/self_tests/ui/test_owned_ui_translations.py testing/self_tests/ui/test_jira_bridge_service_boundary.py`.
- [ ] Run the required QRC rebuild command and confirm generated resources are newer than changed QML.
- [ ] Run a bounded source startup from the repository root and record the outcome as source validation.
- [ ] Run `git diff --check`, inspect scoped `git diff`, and remove temporary diagnostics or unrelated changes.
