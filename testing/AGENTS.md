<INSTRUCTIONS>
# SmartTest `testing/` Layer Rules

Scope: everything under `testing/`.

## Layering

- `testing/` must not import UI modules from `ui/`.
- UI/QML must not import `testing/` directly. Expose required operations via a thin Python bridge in `ui/example/bridge/`.

## Pytest discovery for UI

Pytest discovery is performed in a subprocess (`--collect-only`) so collection stays isolated from the UI process.

- Entry point: `testing/cases/discovery.py`
- Collection metadata export: `testing/conftest.py`
- Export is enabled only when env var `SMARTTEST_PYTEST_COLLECT_OUT` is set.

### Case type markers

Preferred marker:

- `@pytest.mark.case_type("stress")`

Fallback marker-as-type (when no `case_type` marker exists):

- `@pytest.mark.stress` (and other agreed names)

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

## Persistent Test page state

Test page selection/order and configs are stored locally (app data directory):

- State model: `testing/state/models.py`
- Store: `testing/state/store.py`
</INSTRUCTIONS>
