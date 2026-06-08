<INSTRUCTIONS>
# SmartTest `testing/` Layer Rules

Scope: everything under `testing/`.

For detailed testing workflow, use `.codex/skills/smarttest-testing-workflow/SKILL.md`.

## Layering

- `testing/` must not import UI modules from `ui/`, except `ui/jsonTool.py` when loading persisted frontend configuration and `ui/yamlTool.py` when loading shared YAML configuration.
- UI/QML must not import `testing/` directly. Expose required operations through a thin Python bridge in `ui/example/bridge/`.
- Avoid package-level re-export facades and pass-through functions in `testing/`. Import from the module that owns the behavior, unless a boundary is explicitly stable for external callers.
- `testing/tests/` contains only discoverable business test cases.
- Framework, runner, runtime, parameter, UI bridge, Jira, and AI module tests belong in `testing/self_tests/`.

## Pytest Discovery And Run Behavior

- UI-facing pytest discovery must run in an isolated subprocess through `testing/cases/discovery.py`.
- Collection metadata is exported from `testing/conftest.py` only when `SMARTTEST_PYTEST_COLLECT_OUT` is set.
- Default discovery scans `testing/tests/`, not `testing/self_tests/`.
- All test runs default to continue-on-failure. A failed case is recorded as failed but must not stop remaining selected cases unless stop-on-failure is explicitly enabled.

## Parameters And Android Mirroring

- Parameter schema definitions live in `testing/params/schema.py`.
- Schema registry and shared/per-case-type parameter contracts live in `testing/params/registry.py`.
- Use-case/parameter applicability is owned by the `testing/` layer, not QML.
- Declare case requirements close to pytest cases with `requires_params` and `requires_param_groups` markers.
- Required case parameters are centrally owned by `testing/params/required_params.yaml`. Only parameters listed there are run-blocking required values; every other applicable case parameter is optional by default.
- When discussing or implementing new test cases or parameter changes, explicitly ask/confirm which case parameters are required before updating `testing/params/required_params.yaml`.
- When an `android_client` case is mirrored into `testing/tests`, keep the pytest trigger entry in `testing/`, but align the parameter contract with `android_client/app/src/main/java/com/smarttest/mobile/runner/SmartTestCatalog.kt`.
- Android mirrored parameter keys must stay case-scoped, for example `emmc_rw:loop_count`.
- Frontend user configuration and parameter values must be loaded from `%LOCALAPPDATA%\Amlogic\SmartTest` JSON through `ui/jsonTool.py`. Do not pass frontend configuration through runner fields, environment variables, or layer-specific parameter helper modules.

## Steps, DUT, And Equipment

- `testing/tests/` owns case flow and parameter selection only.
- `testing/steps/definitions.py` owns reusable step definitions, planning decisions, and check executors used by declared plans.
- `testing/runner/android_client.py` owns Android client trigger helpers and Android client case plan composition.
- `testing/tool/dut_tool/` owns concrete DUT capabilities such as shell commands, UI automation, Wi-Fi, playback, Bluetooth, and device state helpers.
- `testing/tool/dut_tool/features/` owns reusable DUT business features such as playback and system controls.
- `testing/tool/equipment.py` owns lab equipment composition such as relays, attenuators, routers, and future配测设备 wrappers.
- Step definitions may call either `dut_tool` features or runner helpers. The case should not care which bottom layer performs the work.
- Do not put UI logic, QML-facing model building, or pytest collection logic inside step definitions or DUT features.
- Do not move low-level device command details into test cases. If a case needs a reusable operation, add a DUT feature, step definition, or tool adapter in the right layer.
</INSTRUCTIONS>
