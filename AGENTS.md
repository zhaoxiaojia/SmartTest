# SmartTest Agent Rules (Codex)

This file defines how Codex should work in this repository.

## 0. Default Priorities

1. Prefer existing FluentUI components/styles/effects from the codebase.
2. Preserve known-good behavior: if the user says "this used to work", treat it as a regression and fix root cause.
3. Keep architecture layered: UI (FluentUI/QML) + test runner (pytest) + reserved integrations (debug/Jira).
4. Make changes intentionally: discuss large modules and design first, then implement.

## 1. Frontend Rules (FluentUI First)

- For any UI requirement, first search and reuse existing FluentUI QML controls and patterns already present in this repo (example gallery, controls, styles, animations).
- If a requirement cannot be met cleanly with existing FluentUI controls, stop and discuss tradeoffs before introducing new UI code or alternative libraries.
- Do not replace FluentUI controls with Qt Quick Controls equivalents "for simplicity" without explicit user approval.

### QRC Resource Rebuild

- `ui/example/main.py` loads QML from `qrc:/...`, not directly from source files.
- After any change to files covered by `ui/example/imports/resource.qrc`, you must rebuild `ui/example/imports/resource_rc.py` before handing off or asking the user to run the app.
- Use this command from repo root:
  - `.\.venv\Scripts\pyside6-rcc.exe ui\example\imports\resource.qrc -o ui\example\imports\resource_rc.py`
- If FluentUI resource files under `ui/FluentUI/imports/resource.qrc` are changed, rebuild that resource file too before finishing.

### UI Verification After Rebuild

- Rebuilding `resource_rc.py` is required but not sufficient. After rebuilding, verify that the updated resource is actually loadable before handoff.
- Minimum verification for `ui/example/imports/resource.qrc` changes:
  - confirm `ui/example/imports/resource_rc.py` has been regenerated after the edited QML file
  - run the app from the source entrypoint at repo root: `.\.venv\Scripts\python.exe main.py`
  - if a full interactive run is not practical, perform a short startup validation and inspect startup logs/errors
- If the user reports a QML runtime error after a UI change, do not assume rebuild already took effect. Rebuild again, then reproduce from the source entrypoint before answering.
- Do not rely on static inspection alone for QRC-backed UI changes when a runtime validation is feasible.

### Source vs Packaged App

- Distinguish clearly between the source-run app and packaged binaries.
- Source validation must use repo root `main.py`, which ensures the in-repo `ui/` packages are imported first.
- Do not assume `SmartTest.exe` reflects current source edits. A previously built exe may contain stale QML/resources.
- Before telling the user to test with `SmartTest.exe`, confirm whether a packaging/build step is also required and say so explicitly.
- In handoff notes for UI work, state which entrypoint was verified:
  - source: `.\.venv\Scripts\python.exe main.py`
  - packaged: `SmartTest.exe` or other built artifact

## 2. Backend/Framework Layering

Target architecture:

- `ui/`: QML/FluentUI app code and UI assets (run from source).
- `testing/`: pytest invocation, collection, reporting, cancellation, and tests.
- `debug/`: reserved for debugging utilities, log viewers, tooling.
- `jira/`: reserved for Jira integration (API client, auth, mappings).

Guidelines:

- Keep UI logic in QML/FluentUI and thin Python bridges (signals/slots).
- Keep pytest logic isolated: no UI imports inside runner code.
- When adding new modules, put them into the appropriate layer folder even if the feature is not finished yet.

## 2.1 Strict Ownership / Decoupling

- All business code must belong to exactly one layer. Do not place "shared" logic into a random folder.
- If ownership is ambiguous, stop and ask the user before writing code.
- UI work must stay in the UI layer (FluentUI/QML usage). Test execution logic must stay in the pytest layer.
- Keep layers strictly decoupled to keep issues easy to localize and fix.

## 3. Bug Fix Policy (No Workarounds)

When the user says a feature "was working before":

- Do not bypass it with a new implementation.
- Do not "paper over" with a different code path.
- Find the root cause and fix it where it belongs (correct module, correct abstraction).
- Keep the fix scoped to the bug; do not refactor unrelated areas.

If the root cause is unclear:

- Ask clarifying questions before changing code.
- Provide a short hypothesis list and a minimal plan to validate it.

## 4. Minimal-Defense Coding Style

Goal: avoid "try/except everywhere" and "if everywhere" that hides bugs.

- Do not add broad `try/except` blocks to suppress errors.
- Do not add speculative guard checks that merely avoid crashes without addressing the cause.
- Use concise value normalization where appropriate (e.g., ternary expressions for empty-string defaults).

Allowed exceptions (must be explicit and minimal):

- External I/O boundaries (network, filesystem, subprocess): handle errors to produce a clear, actionable message.
- User-provided inputs: validate at the boundary (not deep inside unrelated functions).

## 5. Collaboration Workflow for Large Modules

For any "large business module" request (new subsystem, cross-layer changes, new data model, new UI navigation concept):

- Stop and discuss first:
  - proposed module boundaries
  - folder layout
  - public interfaces (signals/slots, Python APIs)
  - expected flows (UI -> controller -> runner -> results)
- Only implement after the user confirms the approach.

## 6. External Links / Upstream Coupling

- Do not add hard-coded links to upstream author repos or services.
- OTA/update mechanisms must be configurable (endpoints provided by SmartTest), disabled by default.
