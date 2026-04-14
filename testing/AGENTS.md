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

## Persistent Test page state

Test page selection/order and configs are stored locally (app data directory):

- State model: `testing/state/models.py`
- Store: `testing/state/store.py`
</INSTRUCTIONS>

