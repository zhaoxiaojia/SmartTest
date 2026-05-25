---
name: smarttest-testing-workflow
description: SmartTest testing workflow for pytest discovery, runner execution, run config, parameter contracts, DUT serial handling, lab equipment, runtime events, steps, reports, and Android mirrored cases. Use when working in testing/, pytest cases, testing/runner/, testing/runtime/, testing/params/, testing/actions/, testing/tool/, or UI-to-pytest execution issues.
---

# SmartTest Testing Workflow

## Overview

Use this skill to keep SmartTest pytest execution, DUT/lab equipment access, parameter contracts, step planning, and reports on one coherent path.

## Ownership Chain

Keep each layer narrow:

- `testing/tests/`: case flow, markers, and parameter consumption only
- `testing/actions/`: reusable business actions and result normalization
- `testing/tool/dut_tool/`: concrete DUT capabilities and transports
- `testing/tool/equipment.py`: lab equipment composition root
- `testing/runner/`: pytest subprocess, Android client transport, cancellation
- `testing/runtime/`: pytest-time config, params, steps, events, equipment singleton
- `testing/reporting/`: report assembly and storage

Do not import UI modules from `testing/`. UI may call `testing/` through Python bridges, but QML must not import `testing/` directly.

## Discovery And Metadata

1. Use `testing/cases/discovery.py` for UI-facing pytest collection.
2. Keep collection isolated in a subprocess with `--collect-only`.
3. Export metadata from `testing/conftest.py` only when `SMARTTEST_PYTEST_COLLECT_OUT` is set.
4. Default discovery scans `testing/tests/`, not `testing/self_tests/`.
5. Prefer `@pytest.mark.case_type("...")`; fallback marker-as-type only when no `case_type` marker exists.

## Parameter Contracts

1. Define parameter schemas in `testing/params/schema.py` and `testing/params/registry.py`.
2. Keep parameter schemas UI-neutral. `testing/` defines machine contracts only: keys, value types, defaults, scopes, option sources, groups, and runtime values. It must not provide frontend labels, descriptions, hints, titles, locale strings, or bilingual display text.
3. Bind case requirements close to the pytest case with markers:

```python
@pytest.mark.requires_params("operator", "duration_s")
@pytest.mark.requires_param_groups("stress_runtime")
```

4. Let `testing/conftest.py` expand groups and export `required_params` / `required_param_groups`.
5. Keep scope explicit: `global_context`, `case_type_shared`, or `case`.
6. Cases with no mapping must export an empty list, not placeholder fields.
7. For Android mirrored cases, keep the Android catalog contract aligned with `android_client/app/src/main/java/com/smarttest/mobile/runner/SmartTestCatalog.kt` and use case-scoped keys such as `emmc_rw:loop_count`.

## Run Flow

The preferred execution path is:

```text
UI/TestPage state
  -> ui/example/bridge/RunBridge.py
  -> testing.runner.config.RunConfig
  -> testing.runner.execution.start_pytest_run
  -> SMARTTEST_RUN_CONFIG_JSON
  -> testing.runtime.config / params / equipment
  -> pytest case/action/tool execution
  -> runtime events and report store
```

Use legacy env vars such as `SMARTTEST_ADB_SERIAL` and `SMARTTEST_CASE_CONFIGS_JSON` only for compatibility while the unified run config remains the source of truth.

## DUT And Lab Equipment

1. Resolve the DUT serial once at the run boundary and carry it through `RunConfig`.
2. Low-level adb helpers should consume the selected serial through the shared adb command policy; they should not rediscover or choose devices.
3. Access lab equipment through `testing.runtime.test_equipment()` or `testing.tool.equipment.TestEquipment`.
4. Extend `TestEquipment` for shared relay, attenuator, router, or future lab devices instead of adding case-local construction.
5. Keep `testing/tool/` hardware wrappers free of UI cache, QML, and report presentation logic.

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
.\.venv\Scripts\python.exe -m compileall testing\runner testing\runtime testing\actions testing\tool
```

For hardware-dependent tests, prefer unit tests with injected device listers, transports, equipment factories, and subprocess runners.

## Redundancy Checks

- If DUT serial selection appears in more than one layer, keep it only at the run boundary and pass the selected serial down.
- If pytest cases call low-level DUT/APK APIs directly while a shared action exists, route through `testing/actions/`.
- If bridge code understands pytest internals beyond run config and result events, move that detail into `testing/runner/` or `testing/runtime/`.
- If Android mirrored cases define a second parameter catalog, align them back to the Android catalog and pytest markers.
- If equipment construction appears in individual cases, move it into `TestEquipment` or a tool adapter used by `TestEquipment`.
