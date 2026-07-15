---
name: smarttest-ui-workflow
description: Use when changing SmartTest ui/, QML/FluentUI pages, Python bridge view models, frontend text, UI persistence, QRC resources, Test/Run/Report presentation, or diagnosing source/package UI behavior.
---

# SmartTest UI Workflow

## Ownership

- QML under `ui/example/imports/example/qml/` owns layout, interaction, and presentational state only.
- Bridges under `ui/example/bridge/`, registered from `ui/example/main.py`, own narrow signals/slots and business-facing view models: ordering, grouping, selection mappings, parameter applicability, and Test-page relationships.
- QML never imports `testing/`; bridges are the boundary. Do not move pytest/runner logic into bridges.
- Prefer existing FluentUI controls, styles, effects, and nearby patterns. Inspect them before introducing a visible pattern; alternative UI libraries require Coco's approval.

## State And Dynamic Options

- Persist user-visible selections unless explicitly transient. Use `SettingsHelper` for local ini-backed UI preferences and `testing/state/local_store.py` for bridge-owned JSON preferences.
- User-configured test parameters have one source of truth: `%LOCALAPPDATA%\Amlogic\SmartTest\test_page_state.json` through `ui/jsonTool.py`. Bridges may keep short render/edit mirrors; cross-layer calls pass identities such as nodeid/source/DUT, not parameter values.
- Render cached selectable data first, then refresh external data asynchronously.
- DUT refresh uses contracts in `testing/params/contracts.py` and `testing/tool/dut_tool/parameter_helper.py`. The bridge derives needed parameter/env sources from selected cases; do not hard-code case/field refresh paths.
- Declare dependencies between dynamic sources in schema. Refresh a dependent source for its nodeid only after upstream state is persisted; include nodeid in parameter-dependent cache identity.
- Refreshed scalar/path facts may replace stale persisted values. Multi-select refresh updates candidates only; user selection owns the persisted run value.
- Render normal numeric/equipment inputs as text boxes unless incremental controls are requested. Use compact bounded inputs for short values and full width for paths/long/multiline values.

## Text, Theme, And Resources

- Fixed frontend text lives only in `ui/example/example_en_US.ts` and `ui/example/example_zh_CN.ts`; both languages change together. QML uses `qsTr(...)`; QObject bridges use `self.tr(...)`.
- `testing/` exposes machine keys/types/defaults/scopes/options/results, never frontend labels, descriptions, hints, titles, locale strings, bilingual dictionaries, or fallback maps.
- Bridge display fields mark sources explicitly (`label_source`, `description_source`, `title_source`, `value_source`, or `enum_values_source`) as fixed or dynamic. QML renders bridge text as already localized.
- Keep external/system/user text raw: pytest/adb logs, paths, serials, Jira content, package/case ids, versions, user input, and fetched option values.
- Fixed text has no fallback. Treat missing entries, `unfinished`, mojibake, `?`, `??`, and `???` as failures; do not assemble sentences from translated fragments.
- Prefer `FluTheme` semantic colors. Every custom theme-sensitive color must define and select explicit light/dark values.
- Rebuild the applicable `resource_rc.py` after QRC-backed changes and validate the runtime resource/translation chain.

```powershell
.\.venv\Scripts\pyside6-rcc.exe ui\example\imports\resource.qrc -o ui\example\imports\resource_rc.py
```

Rebuild the FluentUI QRC too when `ui/FluentUI/imports/resource.qrc` changes.

## Test, Run, And Report Presentation

- Test tree, selected rows, selected parameters, and case-type rows come from bridge/controller models. QML retains only filter, expansion, focus, and drag visuals.
- Run and Report consume one bridge-owned `list[dict]` step model. QML renders rows/status only; runtime updates update declared rows and never remove planned rows or create APK-derived replacements.
- Repeated cases show one visible cycle window. At a new cycle, refresh the entire group title to current `x/x` immediately while preserving per-row `planned/running/passed` state.
- `ReportBridge.py` owns report rows, URLs, folder opening, and PDF export. QML never parses report JSON, infers case/step relations, rebuilds summaries, scrapes HTML/PDF, or creates report-only step/log models.
- Run Logs, Report Logs, and step logs reuse one log-list component. Rows use text color plus a narrow left accent; default row background stays transparent.

## Validation

1. Run focused bridge/QML/translation tests; for owned text use `testing/self_tests/ui/test_owned_ui_translations.py`.
2. Confirm generated resources are newer than changed QML/resources.
3. Validate source startup from repository root with `.\.venv\Scripts\python.exe main.py` or a bounded startup/log check.
4. State whether validation used source or package. Never imply `SmartTest.exe` contains source edits without rebuilding it.

Source validation is normal during development. Rebuild desktop packages only when requested, preparing a release, or targeting packaged-runtime behavior; packaged behavior remains the product target.

Every desktop package/installer build must increment the final `MAJOR.MINOR.PATCH` segment through `support/scripts/script-build-manifest.py`. Keep `support/packaging/version.json`, `build/generated/build_manifest.json`, and `build/generated/installer_version.iss` consistent through that manifest/include chain; never bypass it.

## Quality Check

Move grouping/sorting/business relationships out of QML; move pytest details out of bridges; replace page-local stores with existing owners; replace blocking external page-load calls with cache-first async refresh; reject duplicate step/log models.
