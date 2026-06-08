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

Do not import UI modules from `testing/`, except `ui/jsonTool.py` when business code needs persisted frontend configuration and `ui/yamlTool.py` when code needs shared YAML loading. UI may call `testing/` through Python bridges, but QML must not import `testing/` directly.

Frontend user configuration and parameter values are persisted as JSON under `%LOCALAPPDATA%\Amlogic\SmartTest` through `ui/jsonTool.py`. When pytest cases, step planning, reports, AI, debug, or other business code need frontend configuration, load the relevant JSON through `jsonTool` directly. Do not introduce alternate config stores, environment-variable parameter transport, or business-specific helpers that hide the JSON source.

## Discovery And Metadata

1. Use `testing/cases/discovery.py` for UI-facing pytest collection.
2. Keep collection isolated in a subprocess with `--collect-only`.
3. Export metadata from `testing/conftest.py` only when `SMARTTEST_PYTEST_COLLECT_OUT` is set.
4. Default discovery scans `testing/tests/`, not `testing/self_tests/`.
5. Prefer `@pytest.mark.case_type("...")`; fallback marker-as-type only when no `case_type` marker exists.

## Parameter Contracts

1. Define parameter schemas in `testing/params/schema.py` and `testing/params/registry.py`.
2. Keep parameter schemas UI-neutral. `testing/` defines machine contracts only: keys, value types, defaults, scopes, option sources, groups, and runtime values. It must not provide frontend labels, descriptions, hints, titles, locale strings, or bilingual display text.
3. Use `testing/params/required_params.yaml` to centrally define run-blocking required case inputs. `requires_params` means "show these parameters for the case"; it does not make every parameter mandatory.
4. Validate required parameters through `testing/params/validation.py` before starting a run. Missing required values must block execution before pytest starts.
5. DUT-backed dynamic option loading must go through `testing/tool/dut_tool/parameter_adapter.py`. Do not call DUT feature option providers directly from UI bridge getter methods or QML bindings.
6. Bind case requirements close to the pytest case with markers:

```python
@pytest.mark.requires_params("operator", "duration_s")
@pytest.mark.requires_param_groups("stress_runtime")
```

7. Let `testing/conftest.py` expand groups and export `required_params` / `required_param_groups`.
8. Keep scope explicit: `global_context`, `case_type_shared`, or `case`.
9. Cases with no mapping must export an empty list, not placeholder fields.
10. For Android mirrored cases, keep the Android catalog contract aligned with `android_client/app/src/main/java/com/smarttest/mobile/runner/SmartTestCatalog.kt` and use case-scoped keys such as `emmc_rw:loop_count`.

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

Do not pass frontend parameter values through run-config fields or environment variables. Business code that needs frontend configuration must read the persisted JSON through `ui/jsonTool.py`.

## DUT And Lab Equipment

1. Resolve the DUT serial once at the run boundary and carry it through `RunConfig`.
2. Low-level adb helpers should consume the selected serial through the shared adb command policy; they should not rediscover or choose devices.
3. Access lab equipment through `testing.runtime.test_equipment()` or `testing.tool.equipment.TestEquipment`.
4. Extend `TestEquipment` for shared relay, attenuator, router, or future lab devices instead of adding case-local construction.
5. Keep `testing/tool/` hardware wrappers free of UI cache, QML, and report presentation logic.
6. `testing/tool/dut_tool/duts/` owns DUT transport/session interaction; `testing/tool/dut_tool/features/` owns concrete DUT commands. UI-triggered DUT discovery and DUT-backed CaseParameters option refresh are owned by `testing/tool/dut_tool/parameter_adapter.py`.

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

## Steps And Reports

1. Declare visible steps in pytest entry files; do not let the APK synthesize frontend step rows.
2. Build the initial Run page steps model before execution begins.
3. Runtime events may update existing declared rows; they must not delete planned rows or create replacement rows from APK data.
4. Keep unmatched runtime updates diagnostic-rich: nodeid, step id, definition id, status/event type, and parameters.
5. Failed cases must be recorded and the run must continue unless stop-on-failure is explicitly enabled.

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
2. If logs are insufficient, add temporary boundary prints around UI -> runner -> pytest -> DUT/equipment -> reporting.
3. Include stable business identity in prints: nodeid, Android case id, request id, step id, definition id, status, selected DUT, and parameter set.
4. Fix the existing state transition, condition, ordering, or mapping after evidence shows the mismatch.
5. Remove temporary prints after the user confirms the behavior.

## Validation

Run focused self-tests for the changed surface. Common targets:

```powershell
.\.venv\Scripts\python.exe -m pytest testing\self_tests\runner testing\self_tests\runtime testing\self_tests\params -q
.\.venv\Scripts\python.exe -m pytest testing\self_tests\ui\test_run_bridge.py -q
.\.venv\Scripts\python.exe -m compileall testing\runner testing\runtime testing\steps testing\tool
```

For hardware-dependent tests, prefer unit tests with injected device listers, transports, equipment factories, and subprocess runners.

## Redundancy Checks

- If DUT serial selection appears in more than one layer, keep it only at the run boundary and pass the selected serial down.
- If dynamic CaseParameters options are fetched from a DUT outside `DutParameterAdapter`, move that code into the adapter instead of adding another refresh path.
- If pytest cases call low-level DUT/APK APIs directly while a shared step definition, runner helper, or DUT feature exists, route through that shared mechanism.
- If bridge code understands pytest internals beyond run config and result events, move that detail into `testing/runner/` or `testing/runtime/`.
- If Android mirrored cases define a second parameter catalog, align them back to the Android catalog and pytest markers.
- If equipment construction appears in individual cases, move it into `TestEquipment` or a tool adapter used by `TestEquipment`.
