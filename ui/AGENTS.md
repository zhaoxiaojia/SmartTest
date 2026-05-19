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

## Run Page Steps Mechanism

- The Run page steps list is a frontend presentation mechanism owned by the UI bridge/controller layer. QML renders rows and status changes only; it must not infer business step structure from raw runner, APK, or DUT data.
- Every visible test case, whether pure pytest or an APK-driven pytest wrapper, must declare explicit step information in its `test_xxx.py` entry file. The declaration must cover setup steps, test steps, and checks when checks exist.
- The APK must not define, mirror, or synthesize frontend step rows. Android-side status may help update progress, but the row catalog, row order, cycle grouping, and check inclusion come from the pytest-side declarations and user config.
- When the user finishes case configuration and starts a run, the bridge must build the complete initial Run page steps model before execution begins. User config can change loop counts and enable/disable case-specific checks, and those decisions must be reflected before the Run page displays the run.
- Loop/cycle cases show one row for each declared step inside the cycle. If a cycle has five declared steps, all five rows are displayed. When runtime advances to another cycle, every row in that cycle group refreshes its progress label, for example `3/5`.
- Each step row has a visible lifecycle: `planned` -> `running` -> `passed` or `failed`. Runtime events that arrive quickly must still let the Run page show `running`; rows must not jump directly from `planned` to terminal state.
- Runtime updates may only update existing declared rows. They must not delete planned rows, collapse multiple declared cycle rows into one row, or create APK-derived replacement rows. Unmatched runtime steps should be printed as diagnostics with case nodeid, step id, definition id, status/event type, and relevant parameters.
- Debugging this mechanism requires flow-boundary prints for initial plan loading, selected nodeid/config handoff, event ingestion, row matching, cycle progress refresh, and unmatched runtime updates. Keep temporary prints until the user confirms the behavior.

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

## Test Parameter Option Sources

- Test case parameter categories and field contracts are fixed by the `testing/params` schema/registry layer. QML must only render the field view model returned by the bridge.
- Dynamic selectable ranges must be declared by parameter metadata, such as an option source id, not by parameter-key special cases in QML or page code.
- On Test page load, the bridge should refresh DUT identity first, then refresh the dynamic option sources needed by the currently selected cases. Cached options may be shown immediately while refresh runs.
- When the selected DUT or selected cases change, the bridge should refresh only the affected dynamic option sources.
- Do not add per-case or per-parameter refresh methods/signals to `TestPageBridge` for every new parameter. Add or register a provider in the parameter layer, then let the generic bridge refresh path handle it.
- UI getters such as field/model readers must be side-effect free. External commands and DUT interaction should run from page-load, user-refresh, DUT-change, or selection-change refresh flows.
- Dynamic option caches must be keyed by option source and DUT identity when the result depends on the connected DUT.

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
