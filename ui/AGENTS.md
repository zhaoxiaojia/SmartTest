<INSTRUCTIONS>
# SmartTest `ui/` Layer Rules

Scope: everything under `ui/`.

## FluentUI first

- Prefer existing FluentUI QML controls/patterns in this repo.
- Avoid introducing alternative UI libraries without explicit approval.
- Before implementing any new frontend/UI requirement, first inspect the available FluentUI controls/patterns in this repo and propose the best matching control(s) for the requirement.
- Pause for user confirmation on the chosen FluentUI control/pattern before modifying UI code.
- Only proceed to implementation after the user confirms the control choice.

## Localization Is Mandatory

- Every newly added or modified UI text must ship with both `en_US` and `zh_CN` translations in the same change.
- This applies to all user-visible text, including:
  - QML `qsTr(...)` strings
  - Python bridge/controller text produced with `tr(...)` / `QCoreApplication.translate(...)`
  - placeholder text, button labels, tooltips, empty states, error text, status text, and summary text
- Do not leave new or changed UI text as `unfinished` in the translation sources for either language.
- Do not hand off UI work until the translation sources are updated, `.qm` files are regenerated, the generated `.qm` files are copied into the QRC-backed `ui/example/imports/example/i18n/` folder, and the QRC resource has been rebuilt when applicable.
- Do not land hard-coded display strings that bypass the translation system.

## Layering

- Keep UI logic in QML/FluentUI and thin Python bridges (signals/slots).
- Do not import `testing/` from QML. Use bridges registered from Python.

## Bridges

- Bridges live in `ui/example/bridge/`.
- Bridges are registered as QML context properties in `ui/example/main.py`.
- Bridges/controllers own business-facing view models for QML.
- QML must not reconstruct business relationships from raw bridge payloads when the relationship can be produced in Python.
- For the Test page, tree structure, selected rows, selected-parameter rows, and selected case-type rows must come from bridge/controller logic.
- QML may keep only presentational state such as filter text, expand/collapse flags, focus, and drag visuals.

Current bridge (Auth):

- `AuthBridge` provides:
  - LDAP sign-in
  - persisted authenticated username/state
  - login gating for the Test page

Current bridge (Test page):

- `TestPageBridge` provides:
  - pytest discovery results (cases list)
  - ordered selection + reorder API
  - global context (DUT/env/report info) persisted locally
  - per-case-type “special params” persisted locally
</INSTRUCTIONS>
