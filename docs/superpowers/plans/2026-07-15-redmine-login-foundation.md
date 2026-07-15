# Redmine Login Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reusable Playwright infrastructure and a SmartHome Redmine login workflow that defaults to the current SmartTest LDAP credentials and distinguishes credential errors from mobile verification.

**Architecture:** A lazy global browser runtime owns one Playwright browser process and isolated contexts keyed by system and account. A Redmine-specific state machine owns page selectors and authentication classification; a narrow Qt bridge supplies transient credentials and exposes only native SmartTest dialogs/status to QML.

**Tech Stack:** Python 3, Playwright Chromium, PySide6/QML, pytest.

## Global Constraints

- SmartTest does not embed the Redmine web UI.
- Passwords, OTPs, tokens, cookies, and protected HTML are never logged or persisted by SmartTest.
- Fallback credentials are requested only after explicit credential-error evidence.
- Verification input is requested only after explicit verification-state evidence.
- Browser contexts are isolated by `(system_id, account_id)` and remain in memory for version 1.
- Redmine query, parsing, mapping, layout, and Clone are out of scope.

---

### Task 1: Add reusable browser automation

**Files:**
- Create: `support/browser_automation/__init__.py`
- Create: `support/browser_automation/runtime.py`
- Create: `support/browser_automation/session.py`
- Create: `support/browser_automation/models.py`
- Create: `support/browser_automation/errors.py`
- Modify: `support/scripts/script-init-venv.py`
- Test: `testing/self_tests/support/test_browser_automation.py`

**Interfaces:**
- Produces: `BrowserRuntime(headless: bool = True, browser_type: str = "chromium")`, async `start()`, async `context(system_id: str, account_id: str) -> BrowserSession`, async `close_context(...)`, and async `close()`.
- Produces: `BrowserSession.new_page()` and async `close()`; raw context access remains internal to adapters.

- [ ] **Step 1: Write fake-driver lifecycle and isolation tests**

Cover one browser launch, reuse for the same `(system_id, account_id)`, distinct contexts for different keys, deterministic context close, and global close. Add an optional real-browser smoke test that skips only when Chromium is unavailable; fake-driver tests must never skip.

- [ ] **Step 2: Verify tests fail**

Run: `.\.venv\Scripts\python.exe -m pytest testing\self_tests\support\test_browser_automation.py -q`

Expected: collection fails because `support.browser_automation` does not exist.

- [ ] **Step 3: Implement the minimum async runtime**

Use dependency injection for the Playwright launcher in tests. Guard mutable runtime/context state with one async lock, lazily launch once, and remove closed sessions from the key map. Wrap external launch/navigation failures in typed errors without including secrets.

- [ ] **Step 4: Add Playwright installation support**

Update the environment initialization script to install the pinned Python dependency and Chromium through the repository's existing subprocess/error-reporting pattern. Do not download a browser at application import time.

- [ ] **Step 5: Verify browser infrastructure**

Run the focused tests and `python -m compileall support/browser_automation`; expected result is PASS and exit `0`.

### Task 2: Implement the Redmine authentication state machine

**Files:**
- Create: `tool/__init__.py`, `tool/SmartHome/__init__.py`, and `tool/SmartHome/redmine/__init__.py`
- Create: `tool/SmartHome/redmine/models.py`
- Create: `tool/SmartHome/redmine/selectors.py`
- Create: `tool/SmartHome/redmine/auth.py`
- Test: `testing/self_tests/tool/smarthome/redmine/test_auth.py`

**Interfaces:**
- Produces immutable `Credential(username: str, password: str)`.
- Produces `AuthState`: `IDLE`, `SIGNING_IN`, `CREDENTIALS_REQUIRED`, `VERIFICATION_REQUIRED`, `AUTHENTICATED`, `FAILED`.
- Produces immutable `AuthResult(state: AuthState, message: str = "", username: str = "")`.
- Produces async `RedmineAuthService.login(credential)`, `submit_verification(code)`, and `close()`.

- [ ] **Step 1: Write classifier and transition tests**

Use fake pages to cover default credential success, explicit credential error, verification redirect, verification success, incorrect OTP, unsupported page, timeout, and results/logs containing none of the supplied password or OTP.

- [ ] **Step 2: Verify tests fail**

Run the exact Redmine auth test module; expected failure is missing target package.

- [ ] **Step 3: Implement Redmine-owned selectors and transitions**

Use the observed public form contract: `/login`, CSRF input `authenticity_token`, `username`, `password`, and submit `login`. Classify after submission in strict order: authenticated evidence, verification evidence, explicit credential-error evidence, then unexpected failure. Never infer credential failure merely because authentication is incomplete.

- [ ] **Step 4: Verify state-machine tests**

Run the exact auth test module; expected result is PASS.

### Task 3: Connect transient LDAP credentials and native UI dialogs

**Files:**
- Modify: `ui/example/bridge/AuthBridge.py`
- Create: `ui/example/bridge/RedmineBridge.py`
- Modify: `ui/example/bridge/ToolBridge.py`
- Modify: `ui/example/main.py`
- Modify: `ui/example/imports/example/qml/page/T_Tool.qml`
- Modify: `ui/example/example_en_US.ts`
- Modify: `ui/example/example_zh_CN.ts`
- Regenerate: `ui/example/imports/resource_rc.py`
- Test: `testing/self_tests/ui/test_redmine_bridge.py`, `test_tool_page.py`, `test_auth_bridge_profile.py`, and owned translation tests

**Interfaces:**
- Auth owner produces a Python-only transient credential accessor not exposed as a QML Slot.
- `RedmineBridge` exposes properties `state`, `statusText`, `account`, and `loading`; signals `credentialsRequired` and `verificationRequired`; slots `startLogin()`, `submitCredentials(username, password)`, `submitVerification(code)`, and `cancelLogin()`.

- [ ] **Step 1: Write bridge and Tool catalog tests**

Assert `startLogin()` uses the transient SmartTest credential, explicit auth error emits only `credentialsRequired`, verification emits only `verificationRequired`, work does not block the UI thread, and Tool metadata places Redmine under SmartHome.

- [ ] **Step 2: Verify tests fail**

Run the focused UI tests; expected failure is missing Redmine bridge/catalog behavior.

- [ ] **Step 3: Implement the Python-only credential boundary and bridge**

Reuse the existing in-memory authenticated credential owner. Do not add QML-readable password properties or persistent storage. Marshal async worker results back to Qt signals and keep page classification out of the bridge.

- [ ] **Step 4: Implement the native Tool workspace**

Add Redmine status, retry/cancel actions, a fallback username/password dialog, and a verification-code dialog using existing FluentUI patterns. All fixed text uses `qsTr`/`self.tr` and both translation catalogs; no WebView is added.

- [ ] **Step 5: Rebuild resources and run focused acceptance**

Run:

```powershell
.\.venv\Scripts\pyside6-rcc.exe ui\example\imports\resource.qrc -o ui\example\imports\resource_rc.py
.\.venv\Scripts\python.exe -m pytest testing\self_tests\support\test_browser_automation.py testing\self_tests\tool\smarthome\redmine\test_auth.py testing\self_tests\ui\test_redmine_bridge.py testing\self_tests\ui\test_tool_page.py testing\self_tests\ui\test_auth_bridge_profile.py testing\self_tests\ui\test_owned_ui_translations.py -q
.\.venv\Scripts\python.exe -m compileall support\browser_automation tool ui\example\bridge
git diff --check
```

Expected: tests pass, resource generation and compilation exit `0`, and diff check is clean.

- [ ] **Step 6: Perform bounded source startup and live login acceptance**

Start from the repository root in source mode. Confirm the Tool workspace remains responsive; initiate Redmine login with the current LDAP account. Coco supplies any mobile verification code through the SmartTest dialog. Record the resulting state without logging credentials, OTP, cookies, or protected page content.

- [ ] **Step 7: Commit the login foundation**

```powershell
git add support\browser_automation support\scripts\script-init-venv.py tool ui testing\self_tests
git commit -m "feat: add SmartHome Redmine login"
```

