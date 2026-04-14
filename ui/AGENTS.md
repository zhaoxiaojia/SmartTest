<INSTRUCTIONS>
# SmartTest `ui/` Layer Rules

Scope: everything under `ui/`.

## FluentUI first

- Prefer existing FluentUI QML controls/patterns in this repo.
- Avoid introducing alternative UI libraries without explicit approval.
- Before implementing any new frontend/UI requirement, first inspect the available FluentUI controls/patterns in this repo and propose the best matching control(s) for the requirement.
- Pause for user confirmation on the chosen FluentUI control/pattern before modifying UI code.
- Only proceed to implementation after the user confirms the control choice.

## Layering

- Keep UI logic in QML/FluentUI and thin Python bridges (signals/slots).
- Do not import `testing/` from QML. Use bridges registered from Python.

## Bridges

- Bridges live in `ui/example/bridge/`.
- Bridges are registered as QML context properties in `ui/example/main.py`.

Current bridge (Test page):

- `TestPageBridge` provides:
  - pytest discovery results (cases list)
  - ordered selection + reorder API
  - global context (DUT/env/report info) persisted locally
  - per-case-type “special params” persisted locally
</INSTRUCTIONS>
