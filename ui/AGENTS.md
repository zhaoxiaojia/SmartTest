<INSTRUCTIONS>
# SmartTest `ui/` Layer Rules

Scope: everything under `ui/`.

For detailed UI workflow, use `.codex/skills/smarttest-ui-workflow/SKILL.md`.

## Hard Rules

- Prefer existing FluentUI QML controls, styles, effects, and nearby patterns.
- Do not introduce alternative UI libraries or replace FluentUI controls without explicit user approval.
- Before implementing a new visible UI pattern, inspect available FluentUI controls/patterns and discuss the intended control choice when the change is non-trivial.
- QML must stay display-oriented. Bridge/controller Python owns business-facing view models, ordered models, grouping, selection mappings, parameter applicability, and Test page relationships.
- Do not import `testing/` from QML. Use Python bridges registered from `ui/example/main.py`.
- Bridges live in `ui/example/bridge/` and expose narrow signals/slots or view models to QML.

## Text, State, And Resources

- Frontend-owned text must use the translation system and include both `en_US` and `zh_CN`.
- Dynamic external/system text remains raw: pytest/adb/runner logs, user input, file paths, device serials, package names, case ids, Jira content, and versions.
- Do not land hard-coded display strings that bypass translation.
- Persist user-visible UI selections by default through `SettingsHelper` unless the state is explicitly transient.
- For bridge-owned UI preferences, use `testing/state/local_store.py` instead of feature-local stores.
- QRC-backed changes must rebuild the relevant `resource_rc.py` before handoff.
- Verify runtime translation/QRC behavior, not just source files.

## Run/Test Page UI

- The Run page steps list is a frontend presentation mechanism owned by the bridge/controller layer.
- QML renders rows and status changes only; it must not infer business step structure from runner, APK, DUT, or raw case data.
- Runtime updates may update existing declared rows; they must not delete planned rows or create APK-derived replacement rows.
- The Test page tree, selected rows, selected-parameter rows, and selected case-type rows must come from bridge/controller logic.
- QML may keep only presentational state such as filter text, expand/collapse flags, focus, and drag visuals.
</INSTRUCTIONS>
