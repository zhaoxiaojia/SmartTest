<INSTRUCTIONS>
# SmartTest `testing/` Layer Rules

Scope: everything under `testing/`.

## Layering

- `testing/` must not import UI modules from `ui/`.
- UI/QML must not import `testing/` directly. Expose required operations via a thin Python bridge in `ui/example/bridge/`.
- `testing/tests/` contains only discoverable business test cases.
- Framework, runner, runtime, parameter, UI bridge, Jira, and AI module tests belong in `testing/self_tests/`.

## Pytest discovery for UI

Pytest discovery is performed in a subprocess (`--collect-only`) so collection stays isolated from the UI process.

- Entry point: `testing/cases/discovery.py`
- Collection metadata export: `testing/conftest.py`
- Export is enabled only when env var `SMARTTEST_PYTEST_COLLECT_OUT` is set.
- Default discovery scans `testing/tests/`, not `testing/self_tests/`.

### Case type markers

Preferred marker:

- `@pytest.mark.case_type("stress")`

Fallback marker-as-type (when no `case_type` marker exists):

- `@pytest.mark.stress` (and other agreed names)

## Test run failure behavior

- All test runs must default to continue-on-failure behavior.
- A failed case must be recorded as failed, but it must not stop the remaining selected cases unless the user explicitly enables stop-on-failure behavior.
- Do not add fail-fast behavior as an implicit default in pytest runners, packaged runners, Android mirrored cases, or UI-triggered runs.

## Factory pattern (schemas)

- Parameter schema definitions: `testing/params/schema.py`
- Schema registry (global + per-case-type special params): `testing/params/registry.py`

## Case-to-parameter mapping

- Use-case/parameter applicability is owned by the `testing/` layer, not by QML.
- Keep parameter definition and parameter binding separate:
  - definitions live in `testing/params/schema.py` and `testing/params/registry.py`
  - bindings are exported during pytest collection in `testing/conftest.py`
- The mapping is many-to-many:
  - one case may require zero, one, or many parameters
  - one parameter may be reused by many cases
- Declare case requirements close to the pytest case with markers:
  - `@pytest.mark.requires_params("operator", "duration_s")`
  - `@pytest.mark.requires_param_groups("stress_runtime")`
- `testing/conftest.py` is responsible for expanding groups into concrete parameter keys and exporting:
  - `required_params`
  - `required_param_groups`
- UI must consume exported metadata through the bridge only. Do not reimplement group expansion or mapping rules in QML.
- Scope rules must stay explicit in the schema:
  - `global_context`: shared global value
  - `case_type_shared`: shared by case type
  - `case`: owned by a single case
- Cases with no mapping must remain valid. The exported required-params list should be empty, not synthesized with placeholder fields.

## android_client case mirroring

- When an `android_client` case is mirrored into `testing/tests`, keep the pytest trigger entry in `testing/`, but align the case parameter contract with `android_client`.
- Treat `android_client/app/src/main/java/com/smarttest/mobile/runner/SmartTestCatalog.kt` as the parameter source of truth for mirrored cases.
- If the Android case declares parameters, the mirrored pytest case must expose the same required parameters to the UI.
- Use case-scoped keys that preserve the Android case id, for example `emmc_rw:loop_count`.
- The Test page UI is only a trigger/config entry for these mirrored cases. Parameter names, defaults, and required-field exposure must stay aligned with the Android case definition.
- When the user starts a mirrored case from the frontend, the selected case parameters must be passed from `testing/` into the pytest run and then into the `android_client` trigger path.

## Persistent Test page state

Test page selection/order and configs are stored locally (app data directory):

- State model: `testing/state/models.py`
- Store: `testing/state/store.py`

## Actions layer

- Shared business actions live in `testing/actions/`.
- Test cases should compose reusable business actions instead of calling low-level DUT or APK runner APIs directly when a shared action already exists.
- The intended ownership chain is:
  - `testing/tests/`: case flow and parameter selection only
  - `testing/actions/`: reusable business action definitions and result normalization
  - `testing/tool/dut_tool/`: concrete DUT capabilities such as shell commands, UI automation, Wi-Fi, playback, Bluetooth, and device state helpers
  - `testing/runner/android_client.py` and `android_client/`: APK trigger/status transport and Android-side case execution
- Actions may call either `dut_tool` features or an APK runner. The case should not care which bottom layer performs the work.
- Do not put UI logic, QML-facing model building, or pytest collection logic inside `testing/actions/`.
- Do not move low-level device command details into test cases. If a case needs a new reusable operation, add an action that delegates to the right `dut_tool` feature or runner adapter.
</INSTRUCTIONS>
