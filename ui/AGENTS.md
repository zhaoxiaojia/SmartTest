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

- Localization ownership is determined by the source of the text, not by the control that displays it.
- Any text owned by the frontend must ship with both `en_US` and `zh_CN` translations in the same change.
- Frontend-owned text includes:
  - QML `qsTr(...)` strings
  - Python bridge/controller text produced with `tr(...)` / `QCoreApplication.translate(...)`
  - placeholder text, button labels, tooltips, empty states, error text, status text, summary text, navigation labels, section titles, enum display names, and frontend mock/placeholder data
- Dynamic content from outside the frontend must remain raw and must not be translated by the frontend. This includes Jira issue text, Confluence page titles/content, MCP/company information payloads, Bing wallpaper title/copyright, pytest/adb/runner logs, user input, file paths, device serials, package names, case ids, and version strings.
- Bridge payloads that mix frontend-owned text with external data must be structured:
  - use translated payloads for frontend-owned templates: `{"kind": "translated", "template": "...", "values": {...}}`
  - use raw payloads for external/system-returned text: `{"kind": "raw", "text": "..."}`
  - render translated payloads through `ui/example/helper/UiText.py`; do not reimplement ad hoc translated/raw renderers in each bridge.
- Do not concatenate full display sentences from smaller translated fragments. Use a single translatable template with placeholders, such as `qsTr("%1 waiting for test").arg(count)` or a bridge translated template with `values`.
- Do not leave new or changed UI text as `unfinished` in the translation sources for either language.
- Do not hand off UI work until the translation sources are updated, `.qm` files are regenerated, the generated `.qm` files are copied into the QRC-backed `ui/example/imports/example/i18n/` folder, and the QRC resource has been rebuilt when applicable.
- Do not land hard-coded display strings that bypass the translation system.
- If a translation changes, verify the runtime translation path, not just the `.ts` file. The effective chain is: source text -> `.ts` -> `.qm` -> QRC -> `QTranslator`.
- Do not mask translation corruption in QML. Find the broken step in the translation resource pipeline and fix that step.
- Treat placeholder-like translations such as `?`, `??`, `???`, or mojibake text as translation failures.
- For SmartTest-owned UI files, `testing/self_tests/ui/test_owned_ui_translations.py` dynamically audits active `.ts` messages by source location. If a new SmartTest-owned QML/bridge file is added, add that file to `OWNED_UI_SOURCE_FILES` in the test and include bridge Python files in `tools/scripts/script-update-translations.py` when they contain translatable text.

## UI State Persistence Is Mandatory

- User-visible UI selections should persist by default unless the state is explicitly transient.
- Persisted UI state must be stored through `SettingsHelper` in the local ini-backed settings file.
- On page initialization, restore persisted values before triggering data loads that depend on them.
- This applies to toggles, combo selections, filter inputs, multi-select state, and similar preference-like controls.
- Do not implement page-specific ad hoc persistence when a generic `SettingsHelper` getter/setter can be reused.

## UI Data Source Caching (for selectable lists)

- For user-selectable data-source lists shown in UI (for example device lists, source lists, selectable scopes), the default flow must be:
  1. load local cached value first
  2. render UI immediately from cache
  3. refresh real data asynchronously after page load or explicit user action
  4. write refreshed result back to local cache
- Do not block first paint or page switching on external commands/network calls.
- External data refresh must be user-triggered or post-load async; never run synchronously in hot UI read paths.
- For bridge-owned UI preferences, use the shared local JSON preference store (`testing/state/local_store.py`) instead of adding one-off per-feature persistence helpers.
- Keep tool capability modules (for example `testing/params/adb_devices.py`) free of UI cache persistence responsibilities.

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
