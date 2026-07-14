---
name: smarttest-testing-workflow
description: Use when changing SmartTest testing/, pytest discovery/execution, runtime parameters, steps/events/reports, DUT or serial tools, lab equipment, Android-mirrored cases, or UI-to-pytest behavior.
---

# SmartTest Testing Workflow

## Owners And Dependencies

| Owner | Responsibility |
|---|---|
| `testing/tests/` | discoverable business cases: flow, markers, parameter use |
| `testing/self_tests/` | framework, runner, runtime, parameter, bridge, Jira, and AI tests |
| `testing/steps/definitions.py` | reusable definitions, plans, checks |
| `testing/runner/` | pytest subprocess, Android trigger/plan transport, cancellation |
| `testing/runtime/` | pytest-time config, parameters, steps/events, equipment singleton |
| `testing/tool/dut_tool/duts/` | DUT contracts/transports; Android/Linux behavior stays platform-specific |
| `testing/tool/dut_tool/features/` | reusable DUT business operations |
| `testing/tool/pc_tool/serial_tool.py` | only serial implementation/enumeration/read/write/query boundary |
| `testing/tool/equipment.py` | relay/router/attenuator and other lab composition |
| `testing/reporting/store.py` | report JSON save/load/list/path only |
| `tools/report.py` | report construction, summaries/filters, HTML/PDF, filenames |

`testing/` does not import UI except `ui/jsonTool.py` for persisted frontend state and `ui/yamlTool.py` for shared YAML. QML calls testing only through registered Python bridges. Avoid re-export/pass-through facades; import the business owner directly unless a stable external boundary is required.

Keep new modules in their business layer: `ui/` presentation/bridges, `testing/` pytest/runtime/tools/reporting, `debug/` debugging utilities, and `jira/` Jira integration.

Before adding code, choose `reuse`, `extend owner`, `consolidate duplication`, or `new owner` with a concrete gap. Delete thin forwarding/renaming wrappers and stale compatibility paths. Prefer less coupling and net code over file shuffling; no case/value/file-specific mechanism unless explicitly requested.

Keep defenses minimal: do not suppress defects with broad `try/except` or speculative guards. Handle errors at external-I/O and user-input boundaries with actionable messages; fix the failing transition at its owner. New OTA/update links must use configurable SmartTest-owned endpoints and remain disabled by default; never hard-code upstream author repositories/services.

## Discovery And Run

- UI discovery uses isolated `--collect-only` subprocesses through `testing/cases/discovery.py`.
- `testing/conftest.py` exports metadata only when `SMARTTEST_PYTEST_COLLECT_OUT` is set. Default discovery scans `testing/tests/`, never `testing/self_tests/`.
- Prefer `@pytest.mark.case_type(...)`; use marker-name fallback only without a case-type marker.
- Runs continue after a failed case unless stop-on-failure is explicitly enabled.

Canonical execution:

```text
UI persisted state -> RunBridge -> RunConfig -> start_pytest_run
-> SMARTTEST_RUN_CONFIG_JSON -> testing.runtime -> case/action/tool
-> structured runtime events -> report store
```

Resolve DUT serial once at the run boundary and carry it in `RunConfig`. Do not transport frontend parameter values in run config, environment variables, feature constructors, or duplicate caches.

## Parameter Contract

- Define schemas in `testing/params/schema.py`, registry/shared scopes in `registry.py`, case exposure/start requirements/env requirements/options sources in `contracts.py`, and start validation in `validation.py`.
- `requires_params` exposes inputs; only `required_at_start=True` blocks a run. Keep markers beside cases and scopes explicit: `global_context`, `case_type_shared`, or `case`.
- Testing metadata is UI-neutral: keys, types, defaults, scopes, groups, option sources, runtime values. Frontend wording belongs to the UI skill.
- Dynamic DUT/env options use contract declarations and `testing/tool/dut_tool/parameter_helper.py`; no page, case, or field-specific refresh helper.
- Frontend values come from `%LOCALAPPDATA%\Amlogic\SmartTest` JSON through `ui/jsonTool.py` and are read at business use through `testing/params/runtime.py`.
- Conversion belongs only to `tools/param_conversion.py`; never add `_int_param`, `_float_param`, `int(float(...))`, or equivalent private converters.
- Pass stable identities across layers (nodeid, serial, source, request id, equipment), not copied values.
- Android-mirrored keys are case-scoped (`caseId:paramId`) and align with `SmartTestCatalog.kt`. Frontend checkpoint `None` means skip: omit it from APK requests; Android readers also treat `"None"`/`"none"` as absent.

## DUT, Serial, And Equipment

- Cases select flow/parameters; reusable actions belong to steps, DUT features, runner helpers, or equipment adapters. Do not embed low-level device commands in cases.
- `BaseDut` contains only truly shared capabilities. Android stays in `duts/android.py`, Linux in `duts/linux.py`. Prefer functions accepting a DUT over mounted feature facades; use returned DUT objects directly, never stale `.dut` wrappers.
- No module outside `SerialTool` imports `serial`, calls `serial.Serial`, enumerates ports, or implements serial I/O/query. Each business owner builds commands and delegates execution to `SerialTool`.
- Use `testing.runtime.test_equipment()` / `TestEquipment`; do not construct lab devices per case. Hardware wrappers remain free of UI/report presentation.
- ADB uses `adb -s <serial>` by default. If the shared resolver marks a serial unsafe, omit `-s` consistently for the full lifecycle and use the same effective serial for install-state keys. Implement this once at the command boundary.

## Steps, Cycles, Events, And Reports

- Declare visible steps before execution. Testing emits structured updates; it never owns a second UI/report row model. Runtime updates update planned rows and preserve nodeid, step/definition ids, event/status, parameters, and cycle identity.
- Repeatable cases use the shared `loop_count`/`cycle_count` model (default `1`). Do not create separate explicit-cycle and ordinary-loop mechanisms.
- For identical cycles, expose one row group and update it each cycle. A cycle transition supplies enough identity for the UI to refresh every title to current `x/x` immediately while later rows remain planned.
- Report JSON/run results/steps/logs are shared contracts. HTML/PDF are export views, never input data. Storage/generation stays UI-free.
- Report logs come from `tools/logging.py` structured records, never stdout mirrors, ANSI parsing, or temporary prints. Preserve `run_id`, `case_nodeid`, `step_id`, `definition_id`, `status`, `duration`, `domain`, `source`, `level`, and structured `extra` where applicable.

## Logging

Runtime business code calls `smart_log(...)` from `tools.logging`. `step_log(...)` may add step semantics only and must delegate to `smart_log`; compatibility APIs such as `FluLogger` remain thin adapters.

`tools/logging.py` alone owns console/static/aggregate output, JSONL, runtime fan-out, domain/source inference, paths, and colors. Static/event/report data never contains ANSI. Preserve business identity in records; command-line maintenance/build/offline scripts may use stdout.

Domain colors: framework cyan, UI magenta, runner blue, test green, DUT yellow, equipment orange, Android bright green, Jira bright magenta, Python white/gray. Severity supplies debug gray, warning bright yellow, error bright red, critical white-on-red. Add colors only in the owner and keep light/dark readability.

Temporary investigation uses `smart_log(...)`, is marked `TEMP_DIAGNOSTIC`, carries identity, and is removed unless durable. Remove one-off debug tests/scripts/probes after validation.

## Android Integration

For APK source/build/sign/install rules use `smarttest-android-workflow`. Testing-side runners may verify the package and report refresh guidance, but must not install/update it during case execution. Desktop package builds do not validate Android artifacts.

## Stress Behavior

- Functional steps remain strict. Stress cases (`case_type("stress")` or `stress`) may soft-fail only detection/checkpoint `AssertionError`, `pytest.fail()`, or `StressCheckFailure`, logging `[stress.soft_failure]` evidence and continuing.
- Never swallow programming/setup/cancellation/system exceptions. Use `stress_tolerant=False` for critical setup/teardown and small step blocks so later loop items can continue.
- Local playback actions schedule from screenshot-derived current time/duration. Retry after revealing controls within the shared limit; skip forward at ≤5 seconds remaining and skip seek-to-end at ≥75%.
- If screenshots cannot provide time/duration, inspect media session: skip the current action only if that file still plays; otherwise stop remaining actions for it. Log action, time, duration, remaining time, and reason. Never special-case a filename/format/path/value.

## Regression And Validation

For bugs/regressions, inspect existing `smart_log` records and persisted state first. Explain evidence, expected flow, mismatch, and owner before changing code. If evidence is insufficient, add only approved minimal `TEMP_DIAGNOSTIC` boundary logs. In dual delivery Atlas may approve an in-scope root-cause fix; otherwise Coco approves analysis first.

Run focused tests for the changed owner, plus applicable discovery/import/compile checks and hardware acceptance. Examples:

```powershell
.\.venv\Scripts\python.exe -m pytest testing\self_tests\runner testing\self_tests\runtime testing\self_tests\params -q
.\.venv\Scripts\python.exe -m pytest testing\self_tests\ui\test_run_bridge.py -q
.\.venv\Scripts\python.exe -m compileall testing\runner testing\runtime testing\steps testing\tool
```

Do not claim DUT/equipment acceptance without that hardware. Remove temporary artifacts, review the scoped diff for duplicate state/transport/helpers, run `git diff --check`, and preserve user changes.
