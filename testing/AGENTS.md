<INSTRUCTIONS>
# SmartTest `testing/` Layer Rules

Scope: everything under `testing/`.

For detailed testing workflow, use `.codex/skills/smarttest-testing-workflow/SKILL.md`.

## Layering

- `testing/` must not import UI modules from `ui/`.
- UI/QML must not import `testing/` directly. Expose required operations through a thin Python bridge in `ui/example/bridge/`.
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
- When an `android_client` case is mirrored into `testing/tests`, keep the pytest trigger entry in `testing/`, but align the parameter contract with `android_client/app/src/main/java/com/smarttest/mobile/runner/SmartTestCatalog.kt`.
- Android mirrored parameter keys must stay case-scoped, for example `emmc_rw:loop_count`.

## Actions, DUT, And Equipment

- `testing/tests/` owns case flow and parameter selection only.
- `testing/actions/` owns reusable business action definitions and result normalization.
- `testing/tool/dut_tool/` owns concrete DUT capabilities such as shell commands, UI automation, Wi-Fi, playback, Bluetooth, and device state helpers.
- `testing/tool/equipment.py` owns lab equipment composition such as relays, attenuators, routers, and future配测设备 wrappers.
- Actions may call either `dut_tool` features or an APK runner. The case should not care which bottom layer performs the work.
- Do not put UI logic, QML-facing model building, or pytest collection logic inside `testing/actions/`.
- Do not move low-level device command details into test cases. If a case needs a reusable operation, add an action or tool adapter in the right layer.
</INSTRUCTIONS>
