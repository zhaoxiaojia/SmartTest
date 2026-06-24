---
name: smarttest-ui-workflow
description: SmartTest UI workflow for QML/FluentUI frontend changes, Python bridge view models, translations, SettingsHelper persistence, QRC resource rebuilds, and source/package runtime validation. Use when working in ui/, ui/example/bridge/, QML pages, frontend-owned text, UI state persistence, Test page models, or UI runtime errors.
---

# SmartTest UI Workflow

## Overview

Use this skill to make SmartTest UI changes without breaking the QML resource pipeline, translation chain, bridge-owned data contracts, or packaged-runtime expectations.

## Entry Points

- QML pages and controls: `ui/example/imports/example/qml/`
- Python bridges: `ui/example/bridge/`
- Bridge registration: `ui/example/main.py`
- Shared UI text renderer: `ui/example/helper/UiText.py`
- Settings helper: `ui/example/helper/SettingsHelper.py`
- Example QRC: `ui/example/imports/resource.qrc`
- FluentUI QRC: `ui/FluentUI/imports/resource.qrc`
- Translation tooling: `tools/scripts/script-update-translations.py`

## Before Editing

1. Inspect the existing FluentUI controls, styles, and nearby QML patterns before adding UI code.
2. Keep QML display-oriented. Put business-facing view models, ordering, grouping, parameter applicability, and Test page relationships in bridge/controller Python.
3. Treat `TestTree -> Selected`, `Selected -> Parameter`, and `TestTree -> Selected -> CaseType` as bridge-owned relationships.
4. Use `SettingsHelper` for local ini-backed UI selections and `testing/state/local_store.py` for bridge-owned JSON preferences. User-configured test parameters must use `%LOCALAPPDATA%\Amlogic\SmartTest\test_page_state.json` as the single source of truth: bridge may keep a short-lived `_state` mirror, but cross-layer flows pass only identity such as nodeid/source/DUT and read parameter values back from JSON.
5. Render cached selectable data first, then refresh external data asynchronously after page load or explicit user action.
6. DUT refresh or DUT selection changes are a generic trigger only. The bridge must inspect the currently selected cases, collect their DUT-backed parameter and env `options_source` contracts, and refresh those sources through `testing/tool/dut_tool/parameter_helper.py`; do not hard-code a case-specific DUT refresh path in QML or a page bridge.
7. When a user-edited or adapter-refreshed parameter affects another DUT-backed dynamic option source, declare that dependency in the parameter schema and have the bridge refresh the dependent source for the relevant nodeid only after the upstream adapter result has been written to state. Dynamic option caches that depend on persisted case parameters must include nodeid in the cache identity.
8. Adapter refresh results are current DUT facts for available values. After a successful refresh, scalar/path parameters such as `media_dir` may be compared with the corresponding value in `test_page_state.json` and overwritten when different. Multi-select parameters such as `media_files` must not be overwritten by the full refreshed option list; refresh updates the candidate list, and user checkbox selection writes the run value to `test_page_state.json`. For dependent values, use chained adapter sources such as `media_dir` first and `media_files` second rather than deriving one parameter from another.
9. Render numeric input fields as text boxes by default. Do not use stepper/spinbox controls for normal test parameters or equipment fields unless the user explicitly asks for incremental +/- interaction.
10. Use compact row layout for short single-line text inputs: label/description on the left and a bounded-width text box on the right. Reserve full-width inputs for paths, long strings, and multiline content.
11. Custom UI drawing colors must be theme-paired: whenever QML/UI code uses a custom color instead of an existing `FluTheme`/FluentUI semantic color, provide explicit light-theme and dark-theme values and select between them through the current theme state. Do not add single-value hard-coded colors for theme-sensitive UI.
12. Frontend fixed text has exactly one translation resource entrypoint: `ui/example/example_en_US.ts` and `ui/example/example_zh_CN.ts`. QML uses `qsTr(...)`; Python QObject bridges use `self.tr(...)`; both must resolve through those `.ts` files and compiled `.qm` files.
13. The testing layer must not own UI wording. `testing/` may expose machine-readable keys, types, defaults, scopes, option sources, and runtime results, but it must not provide labels, descriptions, hints, titles, or bilingual display text for the frontend. The frontend maps those keys to fixed display text through the translation files.
14. Bridge view models that expose display text must identify every displayed text value as `fixed` or `dynamic` with an explicit source marker such as `label_source`, `description_source`, `title_source`, `value_source`, or `enum_values_source`.
15. The Run/Report steps view must read from one bridge-owned step model only. `ui/example/bridge/` owns the visible `list[dict]` rows, row ordering, row status/color mapping, and repeated-cycle title refresh behavior. QML should only render what the bridge model provides.
16. For repeated step groups, entering a new loop/cycle must refresh the whole visible group to the new `x/x` title immediately. Do not wait for later rows to individually start before their displayed loop/cycle count updates. Later rows may still remain `planned` while already showing the current loop title.
17. The Report page bridge owns only the report list view model and narrow actions such as report URL lookup, folder opening, and PDF export. QML must not parse report JSON, infer case/step business relationships, or rebuild report summaries that belong in Python.
18. Report HTML/PDF are display/export surfaces. UI code must not scrape generated HTML as a data source, and Report-specific UI must not create a second Run-page step/log model.

## Frontend Text

1. All frontend-owned fixed text must have both `en_US` and `zh_CN` values in `ui/example/example_en_US.ts` and `ui/example/example_zh_CN.ts` in the same change. This includes layout labels, use-case descriptions, parameter labels/descriptions, and equipment labels/descriptions.
2. Keep external/dynamic data raw: pytest logs, adb output, user input, file paths, device serials, Jira text, package names, case ids, versions, and option values fetched from external systems.
3. For QML-owned static layout text, use `qsTr()` and update both `.ts` files.
4. For Python bridge-generated fixed text, use `self.tr()` and update both `.ts` files. If the display text is derived from testing metadata, translate a frontend-owned stable text key such as `test.param.<param-id>.label`; do not read labels, descriptions, hints, or titles from `testing/`. Do not store bilingual dictionaries, `FixedText` pairs, locale-specific strings, or translation fallback maps in `testing/`, bridge code, QML, JSON, or helper modules.
5. QML should render bridge text as already-localized display text; do not make QML decide whether a bridge string needs translation.
6. Fixed text must not have fallback translation behavior. If a fixed text is missing a translation, let the translation audit fail and add the missing `.ts` entry.
7. Dynamic text must not be translated or normalized to hide missing fixed text. If text comes from files, devices, user input, pytest, adb, network services, or external option providers, mark it as `dynamic` and render it raw.
8. Avoid sentence assembly from translated fragments. Use one complete value/template per language.
9. Treat `?`, `??`, `???`, mojibake, and `unfinished` translations as failures.

## QRC And Translation Pipeline

After changing files covered by `ui/example/imports/resource.qrc`, rebuild:

```powershell
.\.venv\Scripts\pyside6-rcc.exe ui\example\imports\resource.qrc -o ui\example\imports\resource_rc.py
```

After changing files covered by `ui/FluentUI/imports/resource.qrc`, rebuild the FluentUI resource file too.

For translation changes, verify the full runtime chain:

```text
source text -> .ts -> .qm -> QRC-backed i18n folder -> QRC rebuild -> QTranslator
```

Do not fix translation corruption in QML. Find the broken step in the chain and fix that step.

## Validation

1. For QRC-backed UI changes, confirm `resource_rc.py` is newer than the edited QML/resource file.
2. Run the source entrypoint from the repo root:

```powershell
.\.venv\Scripts\python.exe main.py
```

3. If a full interactive run is not practical, perform a short startup validation and inspect logs.
4. For translation work, run or update `testing/self_tests/ui/test_owned_ui_translations.py` when SmartTest-owned files change.
5. State in the handoff whether validation used source `main.py` or a packaged artifact.

## Source Vs Packaged Runtime

Use source validation for development, but reason about the packaged app as the product target. Do not assume `SmartTest.exe` contains current source changes. Rebuild packaged artifacts only when the user asks, when preparing a release handoff, or when the change targets packaged-runtime behavior.

## Redundancy Checks

- If QML is grouping, sorting, binding parameters to cases, or inferring business relationships from raw snapshots, move that logic to a bridge/controller.
- If page load blocks on adb, network, pytest discovery, or another external command, introduce cache-first rendering and async refresh.
- If a new preference store appears under a page/bridge, prefer `SettingsHelper` or `testing/state/local_store.py`.
- If a UI bridge starts owning pytest execution details, move the runner-specific logic to `testing/` and expose a narrow bridge call.
