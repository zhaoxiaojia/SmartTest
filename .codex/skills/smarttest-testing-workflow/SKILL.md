---
name: smarttest-testing-workflow
description: SmartTest testing workflow for pytest discovery, runner execution, run config, parameter contracts, DUT serial handling, lab equipment, runtime events, steps, reports, and Android mirrored cases. Use when working in testing/, pytest cases, testing/runner/, testing/runtime/, testing/params/, testing/steps/, testing/tool/, or UI-to-pytest execution issues.
---

# SmartTest Testing Workflow

## Overview

Use this skill to keep SmartTest pytest execution, DUT/lab equipment access, parameter contracts, step planning, and reports on one coherent path.

## Ownership Chain

Keep each layer narrow:

- `testing/tests/`: case flow, markers, and parameter consumption only
- `testing/steps/definitions.py`: reusable step definitions, planning decisions, and check executors
- `testing/runner/android_client.py`: Android client trigger helpers and Android client case plan composition
- `testing/tool/dut_tool/`: concrete DUT capabilities and transports
- `testing/tool/dut_tool/features/`: reusable DUT business features
- `testing/tool/equipment.py`: lab equipment composition root
- `testing/runner/`: pytest subprocess, Android client transport, cancellation
- `testing/runtime/`: pytest-time config, params, steps, events, equipment singleton
- `testing/reporting/`: report assembly and storage

Do not add pass-through wrappers or package-level re-export facades in `testing/`. Import from the module that owns the behavior unless an external/stable API boundary is explicitly required.

Treat framework slimming as a standing requirement, not a separate cleanup phase:

- When a module only forwards arguments, renames a call, or wraps a single existing implementation without adding business value, delete that layer and call the owner directly.
- Prefer removing code over moving code. Splitting one large redundant path into several smaller redundant files is not an optimization.
- Before adding a helper, search whether the same behavior already exists in `testing/`, especially under `testing/params/`, `testing/runtime/`, `testing/steps/`, `testing/tool/`, and existing DUT features.
- If two modules implement the same business action with slightly different local helpers, consolidate them into one owner instead of keeping parallel versions.
- Large refactors should reduce net code size unless there is a clear product requirement that justifies growth.

Do not import UI modules from `testing/`, except `ui/jsonTool.py` when business code needs persisted frontend configuration and `ui/yamlTool.py` when code needs shared YAML loading. UI may call `testing/` through Python bridges, but QML must not import `testing/` directly.

Frontend user configuration and parameter values are persisted as JSON under `%LOCALAPPDATA%\Amlogic\SmartTest` through `ui/jsonTool.py`. When pytest cases, step planning, reports, AI, debug, or other business code need frontend test parameters, read them through `testing/params/runtime.py`. Do not introduce alternate config stores, environment-variable parameter transport, or business-specific helpers that hide the JSON source.

## Discovery And Metadata

1. Use `testing/cases/discovery.py` for UI-facing pytest collection.
2. Keep collection isolated in a subprocess with `--collect-only`.
3. Export metadata from `testing/conftest.py` only when `SMARTTEST_PYTEST_COLLECT_OUT` is set.
4. Default discovery scans `testing/tests/`, not `testing/self_tests/`.
5. Prefer `@pytest.mark.case_type("...")`; fallback marker-as-type only when no `case_type` marker exists.

## Parameter Contracts

1. Define parameter schemas in `testing/params/schema.py` and `testing/params/registry.py`.
2. Keep parameter schemas UI-neutral. `testing/` defines machine contracts only: keys, value types, defaults, scopes, option sources, groups, and runtime values. It must not provide frontend labels, descriptions, hints, titles, locale strings, or bilingual display text.
3. Use `testing/params/contracts.py` to centrally define case parameter exposure, `required_at_start`, env requirements, and dynamic option sources. `requires_params` means "show these parameters for the case"; it does not make every parameter mandatory.
4. Validate required parameters through `testing/params/validation.py` before starting a run. Missing required values must block execution before pytest starts.
5. DUT-backed dynamic option loading and env refresh must go through `testing/tool/dut_tool/parameter_helper.py` using the contracts declared in `testing/params/contracts.py`. Do not call DUT feature option providers directly from UI bridge getter methods or QML bindings.
6. Parameter type conversion is globally owned by `tools/param_conversion.py`. Runtime frontend parameter access is owned by `testing/params/runtime.py`. Do not add private `_int_param`, `_float_param`, `int(float(...))`, or equivalent parameter-conversion helpers in runner, pytest cases, feature modules, step planners, or UI bridges.
7. Bind case requirements close to the pytest case with markers:

```python
@pytest.mark.requires_params("operator", "duration_s")
@pytest.mark.requires_param_groups("stress_runtime")
```

8. Let `testing/conftest.py` expand groups and export `required_params` / `required_param_groups`.
9. Keep scope explicit: `global_context`, `case_type_shared`, or `case`.
10. Cases with no mapping must export an empty list, not placeholder fields.
11. For Android mirrored cases, keep the Android catalog contract aligned with `android_client/app/src/main/java/com/smarttest/mobile/runner/SmartTestCatalog.kt` and use case-scoped keys such as `emmc_rw:loop_count`.

Parameter transport must stay minimal:

- The canonical flow is `ui -> persisted JSON state -> testing/params/runtime.py -> pytest case / step planner / runner consumers`.
- Do not carry frontend parameter values through extra bridge fields, run-config fields, environment variables, feature constructors, or duplicated case-local caches.
- Pass stable identity across layers, such as `nodeid`, selected DUT serial, source key, request id, or equipment name; resolve parameter values at the point of business use through shared runtime/schema helpers.
- Remove stale intermediate assignments and "keep for later" parameter copies when the value can be read once from the shared runtime contract.
- `requires_params` means "this case exposes these inputs"; required-at-start validation belongs only to `testing/params/contracts.py` and `testing/params/validation.py`.
- For APK-backed checkpoint parameters, frontend-selected `None` means "skip this checkpoint". Do not include those values in the APK request payload. Android-side parameter readers must also treat `"None"` / `"none"` as not configured so future checkpoint additions follow the same rule automatically.

## Run Flow

The preferred execution path is:

```text
UI/TestPage state
  -> ui/example/bridge/RunBridge.py
  -> testing.runner.config.RunConfig
  -> testing.runner.execution.start_pytest_run
  -> SMARTTEST_RUN_CONFIG_JSON
  -> testing.runtime.config / equipment
  -> pytest case/action/tool execution
  -> runtime events and report store
```

Do not pass frontend parameter values through run-config fields or environment variables. Business code that needs frontend test parameters must use `testing/params/runtime.py`, which reads the persisted JSON and applies schema-backed conversion.

For step updates, `testing/` is a producer, not the frontend model owner:

- `testing/` may emit runtime step events and APK snapshot-derived step updates.
- `testing/` must not maintain a second UI-facing step list or report-only step structure.
- APK snapshot translation should emit enough identity for the UI bridge owner to update the single visible step model, but it should not own frontend row coloring, ordering, or a duplicate visible list.

## DUT And Lab Equipment

1. Resolve the DUT serial once at the run boundary and carry it through `RunConfig`.
2. Low-level adb helpers should consume the selected serial through the shared adb command policy; they should not rediscover or choose devices.
3. Access lab equipment through `testing.runtime.test_equipment()` or `testing.tool.equipment.TestEquipment`.
4. Extend `TestEquipment` for shared relay, attenuator, router, or future lab devices instead of adding case-local construction.
5. Keep `testing/tool/` hardware wrappers free of UI cache, QML, and report presentation logic.
6. `testing/tool/dut_tool/duts/` owns DUT transport/session interaction; `testing/tool/dut_tool/features/` owns concrete DUT commands. UI-triggered DUT discovery, dynamic CaseParameters option refresh, and env dynamic refresh are owned by `testing/tool/dut_tool/parameter_helper.py`.

DUT structure rules:

- Keep `BaseDut` narrow. Only place truly cross-platform device capabilities there.
- Keep Android-only logic in `duts/android.py` and Linux-only logic in `duts/linux.py`; do not force platform-specific behavior into `BaseDut` for symmetry.
- Prefer pure feature functions that accept `dut` as an argument over mounted feature facade objects attached to the DUT instance.
- If a helper like `_android_dut(...)` returns an `android` object, use that object directly. Do not expect stale wrapper fields such as `.dut`.
- When slimming DUT code, remove compatibility leftovers at call sites in the same change. Do not leave old wrapper-style access patterns behind after deleting the wrapper.

## ADB Command Serial Policy

Default to explicit serial commands:

```text
adb -s <serial> shell ...
adb -s <serial> install ...
```

If the selected DUT serial contains mojibake, non-ASCII suffixes, or any character that is not safe for `adb -s`, use the shared serial resolver and run every adb command in the full run lifecycle without `-s`, including ready checks, shell commands, install/uninstall, force-stop, am start, status polling, snapshots, root/remount, push, reboot, and file hash probes:

```text
adb shell ...
adb install ...
```

Apply this once at the adb command boundary. Do not add case-local fallbacks, print wrappers, or separate install-only special cases. Install state keys must use the same effective command serial, so malformed serials map to the default single-device adb path consistently.

## Android APK Install/Update

Use this workflow when debugging or changing APK-backed cases:

1. If `com.smarttest.mobile` is missing on the selected DUT, install the resolved APK.
2. If it is installed, print and verify the device package path, versionCode/versionName, local APK hash, recorded install state, and selected DUT serial before deciding to skip.
3. In source runs, rebuild the debug APK when Android source files or manifest are newer than the APK so the next run installs the latest build.
4. If the installed package is not the latest expected APK, uninstall/reinstall or privileged-provision through the shared install mechanism; do not add case-local install logic.
5. For new-DUT failures, first add/inspect boundary prints in `android_client.ensure_test_apk_installed`: requested serial, effective command serial, resolved APK path, build check mtimes, installed probe output, package code path, package version, install state key, recorded hash, current hash, and final decision.
6. `com.smarttest.mobile` may be a system priv-app with `sharedUserId`. Do not default to raw `adb install -r` for that package. Use `android_client.sign_privileged_apk(...)` and `android_client.ensure_test_apk_installed(..., require_privileged=True)` or the equivalent shared priv-app installation script.

## Android APK Packaging

Package Python and Android independently:

1. Desktop packaging produces the SmartTest `.exe`; Android packaging produces the SmartTest mobile `.apk`.
2. Do not treat an `.exe` package build as Android APK validation.
3. APK packaging may use a dedicated script, but the packaged APK artifact must be copied under `dist/`.
4. After modifying source under `android_client/`, build/package the APK once before handoff, at minimum with a Gradle APK task such as:

```powershell
.\android_client\gradlew.bat -p android_client :app:assembleDebug
```

5. Use a stricter Gradle task when the change requires it.

## Steps And Reports

1. Declare visible steps in pytest entry files; do not let the APK synthesize frontend step rows.
2. Build the initial Run page steps model before execution begins.
3. Runtime events may update existing declared rows; they must not delete planned rows or create replacement rows from APK data.
4. Keep unmatched runtime updates diagnostic-rich: nodeid, step id, definition id, status/event type, and parameters.
5. Failed cases must be recorded and the run must continue unless stop-on-failure is explicitly enabled.

Report boundaries:

- `testing/reporting/store.py` owns JSON persistence only: save, load, list, and path resolution.
- `tools/report.py` owns report construction, machine-readable summary/filtering, HTML rendering, PDF export, and report file naming.
- Report storage and generation must stay UI-free. Do not import QML, bridges, FluentUI, or frontend state into report storage/generation code.
- HTML and PDF reports are export views, not data sources. Do not parse generated HTML to drive later business logic.
- Report logs must use structured records from `tools/logging.py`; do not depend on ANSI colors, root-level stdout mirror files, or temporary print output.
- New report fields should preserve stable identities such as `run_id`, `case_nodeid`, `step_id`, `definition_id`, `status`, `duration`, `domain`, `source`, `level`, and structured `extra`.
- When optimizing report code, prefer deleting duplicate summary, filtering, formatting, or path helpers over moving them to a new wrapper module.

Cycle/loop planning is a shared mechanism:

- All repeatable cases should follow the cycle model. Every case is assumed to have `loop_count`/`cycle_count` semantics, with a default of `1` when the case does not override it.
- Step planning should expand cycle rows through shared planner logic, not ad hoc case-specific UI patches.
- Frontend-visible step rows should be stable and predeclared as much as possible. Runtime events are expected to update planned rows, not invent an unrelated second step structure.
- Do not keep one mechanism for explicit `cycle.*` cases and another unrelated mechanism for ordinary looped cases; unify them in shared plan expansion.
- When a case needs repeated execution, prefer a shared `loop_count` case parameter over custom per-case repeat flags.
- For repeated cases whose cycle structure is the same each round, the Run page should show one visible set of cycle rows and refresh that same set for the current cycle. Do not pre-expand every cycle into the visible UI when it only creates duplicated rows.
- When a new loop/cycle begins, testing-side updates must provide enough information for the UI-owned step model to refresh the whole visible repeat group to the new `x/x` title immediately, not only the currently running row.

## Stress Case Step Tolerance

1. Stress cases are identified by `@pytest.mark.case_type("stress")` or `@pytest.mark.stress`.
2. Functional cases remain strict: assertion/check failures inside `testing.runtime.steps.step()` must fail the step and case.
3. Stress cases use step-level soft failure for detection/checkpoint failures only. `AssertionError`, `pytest.fail()`, and `StressCheckFailure` inside a stress step must be logged as `[stress.soft_failure]`, emitted as warning evidence, and allow the case to continue.
4. Do not globally swallow all exceptions. Unexpected code errors such as `TypeError`, `AttributeError`, `NameError`, device setup errors, cancellation, `KeyboardInterrupt`, and `SystemExit` must still stop/fail normally unless a reusable, explicit detection exception is introduced.
5. Keep stress loops split into small `step(...)` blocks around each repeat/action/check. A single large step around an entire loop cannot resume the next loop item after an exception.
6. Use `stress_tolerant=False` for critical stress setup or teardown steps that must remain strict.
7. Do not convert stress failures to hidden success without diagnostics; logs must include step id, definition id, exception type, and message.

## Local Playback Stress Action Safety

1. Local playback stress actions must be scheduled from the current playback time and media duration read from the action-preflight screenshot, not blindly executed from the selected action list.
2. Progress reads must first analyze a screenshot as-is; if playback time or controls are not visible, tap once and analyze a fresh screenshot, repeating only within the shared retry limit.
3. If current playback has five seconds or less remaining, skip `seek_forward`.
4. If current playback is already at or beyond 75% of duration, skip `seek_to_end`.
5. If the action-preflight screenshot cannot provide current time and duration, dump media session state; skip only the current action when the file is still playing, and stop scheduling the remaining actions for the current file when media session is no longer playing that file.
6. Skipped actions must emit diagnostic logs with action, current time, duration, remaining time, and skip reason.
7. Do not add case-specific handling for one file name, format, path, or parameter value; implement reusable scheduling rules.

## Debugging Flow

1. Gather logs/prints from the relevant handoff before changing behavior.
2. When the user reports that something used to work, default to inspecting prints/logs and explaining the suspected root cause first.
3. Do not modify code for that regression until the user approves the analysis logic.
4. If logs are insufficient, propose the minimal temporary boundary prints around UI -> runner -> pytest -> DUT/equipment -> reporting.
5. Include stable business identity in prints: nodeid, Android case id, request id, step id, definition id, status, selected DUT, and parameter set.
6. After approval, fix the existing state transition, condition, ordering, or mapping shown by evidence.
7. Remove temporary prints after the user confirms the behavior.

Temporary validation artifacts must also be removed:

- Self-tests created only to debug a one-off issue must be deleted after they have served their purpose.
- Do not keep "just in case" debug-only tests, scripts, or probes in `testing/self_tests/` or `testing/tool/`.
- Recreate focused debug tests next time they are needed instead of letting the repository accumulate temporary scaffolding.

## Validation

Run focused self-tests for the changed surface. Common targets:

```powershell
.\.venv\Scripts\python.exe -m pytest testing\self_tests\runner testing\self_tests\runtime testing\self_tests\params -q
.\.venv\Scripts\python.exe -m pytest testing\self_tests\ui\test_run_bridge.py -q
.\.venv\Scripts\python.exe -m compileall testing\runner testing\runtime testing\steps testing\tool
```

For hardware-dependent tests, prefer unit tests with injected device listers, transports, equipment factories, and subprocess runners.

Temporary self tests created only for debugging must be removed after validation. Recreate focused self tests next time they are needed; do not keep debug-only tests in the repository.

## Redundancy Checks

- If DUT serial selection appears in more than one layer, keep it only at the run boundary and pass the selected serial down.
- If dynamic CaseParameters options or env options are fetched outside `ParameterHelper`, move that code into `testing/tool/dut_tool/parameter_helper.py` instead of adding another refresh path.
- If pytest cases call low-level DUT/APK APIs directly while a shared step definition, runner helper, or DUT feature exists, route through that shared mechanism.
- If bridge code understands pytest internals beyond run config and result events, move that detail into `testing/runner/` or `testing/runtime/`.
- If Android mirrored cases define a second parameter catalog, align them back to the Android catalog and pytest markers.
- If equipment construction appears in individual cases, move it into `TestEquipment` or a tool adapter used by `TestEquipment`.
- If a `testing/tool/` module contains multiple copies of adb helpers, shell quoting, UI dumping, transport startup, or router/lab device selection, collapse them into one shared owner instead of re-implementing them inside each feature.
- If a DUT feature can be expressed as module functions plus a passed-in DUT object, prefer that over creating another feature facade class.
- If an optimization only changes file layout but leaves the same amount of business branching and argument plumbing, it is incomplete; keep simplifying until coupling and code size both drop.
