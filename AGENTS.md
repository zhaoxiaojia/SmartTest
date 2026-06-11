# SmartTest Agent Rules (Codex)

This file defines repository-wide hard rules. Detailed task workflows live in project skills under `.codex/skills/`.

## 0. Project Skills

- Use `.codex/skills/smarttest-ui-workflow/SKILL.md` for UI/QML/FluentUI, bridge view models, translations, QRC rebuilds, and source/package UI validation.
- Use `.codex/skills/smarttest-testing-workflow/SKILL.md` for pytest discovery/run flow, parameters, DUT serial handling, lab equipment, steps, reports, and Android mirrored cases.

## 1. Default Priorities

1. Prefer existing FluentUI components/styles/effects from the codebase.
2. Preserve known-good behavior: if the user says "this used to work", treat it as a regression and fix root cause.
3. Keep architecture layered: UI (FluentUI/QML) + test runner (pytest) + reserved integrations (debug/Jira).
4. Make changes intentionally: discuss large modules and design first, then implement.
5. Design and verify toward the installed/packaged runtime first. `python main.py` debug runs are useful for development, but final behavior must match the normal installed app.
6. During development/debugging, do not rebuild the packaged app/installer after every change. Rebuild packaged artifacts only when the user explicitly asks, when preparing a release handoff, or when the change specifically targets packaged-runtime behavior.

## 2. Frontend Hard Rules

- Prefer existing FluentUI QML controls and patterns; do not replace them with Qt Quick Controls or other UI libraries without explicit user approval.
- QML is display-oriented. Bridge/controller Python owns business-facing view models, ordering, grouping, parameter applicability, and Test page relationships.
- Frontend-owned text must use the translation system and ship with both `en_US` and `zh_CN`. External/system text remains raw.
- All fixed frontend display text has one resource entrypoint: `ui/example/example_en_US.ts` and `ui/example/example_zh_CN.ts`. The testing layer must not own UI wording; `testing/` may expose machine-readable keys, types, defaults, scopes, option sources, and runtime results, but not frontend labels, descriptions, hints, titles, locale strings, or bilingual text.
- Custom UI drawing colors must be theme-paired: whenever QML/UI code uses a custom color instead of an existing `FluTheme`/FluentUI semantic color, provide explicit light-theme and dark-theme values and select between them through the current theme state. Do not add single-value hard-coded colors for theme-sensitive UI.
- User-visible UI selections persist by default unless explicitly transient.
- User-configured frontend parameters must use `%LOCALAPPDATA%\Amlogic\SmartTest\test_page_state.json` through `ui/jsonTool.py` as the single source of truth; UI bridges may keep only short-lived render/edit mirrors, and cross-layer flows must pass identity such as nodeid/source/DUT instead of frontend parameter values.
- Frontend/runtime parameter values must be read through `testing/params/runtime.py`. Parameter type conversion must use `tools/param_conversion.py`. Do not add private `_int_param`, `_float_param`, `int(float(...))`, or equivalent parameter-conversion helpers in runner, pytest cases, feature modules, step planners, or UI bridges.
- QRC-backed changes must rebuild the relevant `resource_rc.py` before handoff.
- Distinguish source-run validation from packaged app validation. Do not imply `SmartTest.exe` contains source edits unless a packaging/build step has been completed.

## 3. Backend/Framework Layering

Target architecture:

- `ui/`: QML/FluentUI app code, UI assets, and thin Python bridges.
- `testing/`: pytest invocation, collection, runtime config, actions, tools, reporting, cancellation, and tests.
- `debug/`: reserved for debugging utilities, log viewers, tooling.
- `jira/`: reserved for Jira integration (API client, auth, mappings).

Guidelines:

- Keep pytest logic isolated: no UI imports inside runner/runtime/action/tool code, except `ui/jsonTool.py` for persisted frontend configuration.
- UI/QML must not import `testing/` directly; use registered Python bridges.
- When adding new modules, put them into the appropriate layer folder even if the feature is not finished yet.

## 4. Strict Ownership / Decoupling

- All business code must belong to exactly one layer. Do not place "shared" logic into a random folder.
- If ownership is ambiguous, stop and ask the user before writing code.
- Except for test case development under `testing/tests`, changes must be rule/mechanism-level by default.
- Do not add code that only affects one specific case, scenario, parameter value, or condition unless the user explicitly asks for that special handling.
- Static special-case code is not allowed by default. Requirements should be implemented through reusable rules, data contracts, state transitions, or shared mechanisms.
- Do not add case-specific parameter parsing or conversion logic. Extend the shared parameter runtime/conversion contracts instead.

## 5. Architecture Optimization Principles

Apply these principles when improving existing modules or adding new ones:

- Reduce direct module-to-module knowledge; prefer stable interfaces, injected dependencies, and event/message style coordination.
- Keep each module focused on one business responsibility.
- Depend on contracts, protocols, service interfaces, or narrow bridge APIs rather than concrete implementations.
- Hide internal state and expose the minimum surface needed by the caller.
- Prefer composition over inheritance unless there is a true `is-a` relationship.
- Extend behavior with new implementations, adapters, or handlers when practical.
- Pass dependencies in from the outside where practical, especially for services, clients, caches, and adapters.
- Implement what the current product needs; avoid speculative framework layers.

Before finalizing a refactor, check:

- Does this reduce coupling, or just move code around?
- Is each module/class easier to describe in one sentence?
- Is the new abstraction needed now?
- Did business ownership remain clear by layer?
- Did extension points improve without making the common path harder?

## 6. Bug Fix Policy (No Workarounds)

When the user says a feature "was working before":

- Do not bypass it with a new implementation.
- Do not paper over it with a different code path.
- Find the root cause and fix it where it belongs.
- Keep the fix scoped to the bug; do not refactor unrelated areas.

For bug investigations:

- Use logs or prints from the relevant flow before changing behavior.
- If current logs are insufficient, add minimal temporary prints at flow boundaries.
- Debug prints should expose business identity such as selected nodeid, Android case id, request id, step id, definition id, status, and parameter set.
- Fix the exact mismatch or failing transition first.
- Remove temporary debug prints after they have served their purpose.
- Do not add case-specific fixes for examples such as eMMC or reboot; fix the shared mechanism.

## 7. Minimal-Defense Coding Style

- Do not add broad `try/except` blocks to suppress errors.
- Do not add speculative guard checks that merely avoid crashes without addressing the cause.
- Use concise value normalization where appropriate.
- Handle errors at external I/O boundaries and user-input boundaries to produce clear, actionable messages.

## 8. Collaboration Workflow For Large Modules

For any large business module request (new subsystem, cross-layer changes, new data model, new UI navigation concept), discuss first:

- proposed module boundaries
- folder layout
- public interfaces (signals/slots, Python APIs)
- expected flows (UI -> controller -> runner -> results)

Only implement after the user confirms the approach.

## 9. External Links / Upstream Coupling

- Do not add hard-coded links to upstream author repos or services.
- OTA/update mechanisms must be configurable through SmartTest-owned endpoints and disabled by default.
