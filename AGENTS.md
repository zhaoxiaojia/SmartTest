# SmartTest Agent Rules (Codex)

This file defines repository-wide hard rules. Detailed task workflows live in project skills under `.codex/skills/`.

## 0. Project Skills

- Use `.codex/skills/smarttest-ui-workflow/SKILL.md` for UI/QML/FluentUI, bridge view models, translations, QRC rebuilds, and source/package UI validation.
- Use `.codex/skills/smarttest-testing-workflow/SKILL.md` for pytest discovery/run flow, parameters, DUT serial handling, lab equipment, steps, reports, and Android mirrored cases.

## 1. Default Priorities

1. Prefer existing FluentUI components/styles/effects from the codebase.
2. Preserve known-good behavior: if the user says "this used to work", treat it as a regression. Default to reading existing `smart_log(...)` records/runtime logs and explaining the suspected root cause first; do not modify code until the user approves the analysis logic.
3. Keep architecture layered: UI (FluentUI/QML) + test runner (pytest) + reserved integrations (debug/Jira).
4. Make changes intentionally: discuss large modules and design first, then implement.
5. Design and verify toward the installed/packaged runtime first. `python main.py` debug runs are useful for development, but final behavior must match the normal installed app.
6. During development/debugging, do not rebuild the packaged app/installer after every change. Rebuild packaged artifacts only when the user explicitly asks, when preparing a release handoff, or when the change specifically targets packaged-runtime behavior.
7. Package Python and Android separately: the desktop app produces an `.exe`, and `android_client/` produces an `.apk`. APK packaging may use a dedicated script, but its output must be copied under `dist/`. After modifying Android APK source under `android_client/`, build/package the APK once before handoff, at minimum with a Gradle APK task such as `.\android_client\gradlew.bat -p android_client :app:assembleDebug` or a stricter relevant task; do not treat an `.exe` package build as APK validation.
8. `android_client` uses `android:sharedUserId="android.uid.system"` and may run as a system priv-app on DUTs. Do not use plain `adb install -r` for privileged cases by default. Use the repository signing/install flow under `android_client/__init__.py`, which platform-signs the debug APK through the local `android_client/signapk/...` assets and installs it through the priv-app path when needed.

## 2. Frontend Hard Rules

- Prefer existing FluentUI QML controls and patterns; do not replace them with Qt Quick Controls or other UI libraries without explicit user approval.
- QML is display-oriented. Bridge/controller Python owns business-facing view models, ordering, grouping, parameter applicability, and Test page relationships.
- Frontend-owned text must use the translation system and ship with both `en_US` and `zh_CN`. External/system text remains raw.
- All fixed frontend display text has one resource entrypoint: `ui/example/example_en_US.ts` and `ui/example/example_zh_CN.ts`. The testing layer must not own UI wording; `testing/` may expose machine-readable keys, types, defaults, scopes, option sources, and runtime results, but not frontend labels, descriptions, hints, titles, locale strings, or bilingual text.
- Custom UI drawing colors must be theme-paired: whenever QML/UI code uses a custom color instead of an existing `FluTheme`/FluentUI semantic color, provide explicit light-theme and dark-theme values and select between them through the current theme state. Do not add single-value hard-coded colors for theme-sensitive UI.
- User-visible UI selections persist by default unless explicitly transient.
- User-configured frontend parameters must use `%LOCALAPPDATA%\Amlogic\SmartTest\test_page_state.json` through `ui/jsonTool.py` as the single source of truth; UI bridges may keep only short-lived render/edit mirrors, and cross-layer flows must pass identity such as nodeid/source/DUT instead of frontend parameter values.
- Run/Report step rendering must consume one bridge-owned step model only. The UI layer owns the visible `list[dict]` step rows and their status/color rendering; testing/runtime code must not build a second frontend step structure.
- Frontend/runtime parameter values must be read through `testing/params/runtime.py`. Parameter type conversion must use `tools/param_conversion.py`. Do not add private `_int_param`, `_float_param`, `int(float(...))`, or equivalent parameter-conversion helpers in runner, pytest cases, feature modules, step planners, or UI bridges.
- For frontend checkpoint-style selections, a user-selected `None` means "do not check". Do not pass that value through to Android APK execution. When APK-backed flows do receive `"None"` or `"none"`, they must treat it as not configured and skip that checkpoint instead of executing a failing validation path.
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

## 4. Logging / Print Rules

SmartTest runtime logging has one project-owned entrypoint: `tools/logging.py`.

- Runtime business code must use `smart_log(...)` from `tools.logging` for diagnostic output. Do not add direct `print(...)`, `logging.*`, `logging.getLogger(...)`, per-layer logger wrappers, or compatibility forwarding handlers.
- `step_log(...)` is allowed only as a testing-step semantic helper. It must delegate output and static logging to `smart_log(...)`; it must not become a second logging implementation.
- UI compatibility helpers such as `FluentUI.FluLogger` may keep their existing public API only as a thin adapter to `smart_log(...)`.
- `tools/logging.py` owns console output, static log writing, runtime log events, domain/source inference, and log coloring. Other modules must not implement their own color formatting, file log paths, log fan-out, or stdout/stderr mirroring.
- Static logs must be written as structured JSONL without ANSI color codes. Console coloring is display-only, and frontend log coloring must use structured fields produced by `tools/logging.py`.
- `tools/logging.py` also owns the local human-readable aggregate log file. Do not reintroduce root-level `tmp_main_stdout.log`, `tmp_main_stderr.log`, or per-run stdout mirror files as primary debug logs.
- Log records should preserve business identity when available: `domain`, `source`, `case_nodeid`, `step_id`, and structured `extra` fields such as request id, Android case id, definition id, status, DUT serial, parameter keys, or equipment identity.
- Temporary investigation logs must still use `smart_log(...)` and must be removed after debugging unless they provide durable product value.
- Command-line maintenance scripts, build scripts, and offline parsers may keep ordinary stdout output when they are intentionally CLI tools and not part of the SmartTest runtime logging flow.
- Frontend log views must share the same reusable log-list component. Run Logs, Report Logs, and step-related report log views must not implement separate delegates for log rows.
- Frontend log rows should use text color and a narrow left accent bar for visual distinction. Do not color the full row background by default; keep the row background transparent unless a future selected/hover/error interaction explicitly owns that state.

Logging color rules:

- Color assignment is by `domain` first and severity second. Domains distinguish ownership; levels distinguish urgency.
- Current domain palette: `framework` cyan, `ui` magenta, `runner` blue, `test` green, `dut` yellow, `equipment` orange, `android` bright green, `jira` bright magenta, `python` white/gray.
- Current level accents: `debug` gray, `info` default, `warning` bright yellow, `error` bright red, `critical` white-on-red.
- Add new colors only in `tools/logging.py`, keep them readable on dark and light terminals, and avoid reusing a domain color for a domain with a different business owner.
- Never write ANSI color codes into static files, runtime event payloads, reports, or UI data models. Frontend log views may consume structured light/dark color fields produced by `tools/logging.py` when the UI explicitly owns visual rendering.

## 5. Strict Ownership / Decoupling

- All business code must belong to exactly one layer. Do not place "shared" logic into a random folder.
- If ownership is ambiguous, stop and ask the user before writing code.
- Except for test case development under `testing/tests`, changes must be rule/mechanism-level by default.
- Do not add code that only affects one specific case, scenario, parameter value, or condition unless the user explicitly asks for that special handling.
- Static special-case code is not allowed by default. Requirements should be implemented through reusable rules, data contracts, state transitions, or shared mechanisms.
- Do not add case-specific parameter parsing or conversion logic. Extend the shared parameter runtime/conversion contracts instead.

## 6. Architecture Optimization Principles

Apply these principles when improving existing modules or adding new ones:

- Reduce direct module-to-module knowledge; prefer stable interfaces, injected dependencies, and event/message style coordination.
- Keep each module focused on one business responsibility.
- Depend on contracts, protocols, service interfaces, or narrow bridge APIs rather than concrete implementations.
- Hide internal state and expose the minimum surface needed by the caller.
- Prefer composition over inheritance unless there is a true `is-a` relationship.
- Extend behavior with new implementations, adapters, or handlers when practical.
- Pass dependencies in from the outside where practical, especially for services, clients, caches, and adapters.
- Implement what the current product needs; avoid speculative framework layers.

DUT layering rules:

- Treat `testing/tool/dut_tool/duts/` as the device contract boundary.
- Treat `testing/tool/pc_tool/serial_tool.py` as the only serial-port implementation boundary. Do not import `serial`, call `serial.Serial`, enumerate serial ports, or implement serial read/write/query helpers anywhere else. USB relay, DUT serial flows, and future serial-backed tools must prepare their own business commands and execute them through `SerialTool`.
- Put only truly shared DUT capabilities into `BaseDut`. Do not push Android-only or Linux-only business behavior into `BaseDut` just to make the class look uniform.
- Put Android-specific behavior in `testing/tool/dut_tool/duts/android.py` and Linux-specific behavior in `testing/tool/dut_tool/duts/linux.py`.
- Prefer business functions that accept a `dut` object over mounted feature facade objects such as `dut.system`, `dut.wifi`, or similar wrapper layers.
- Do not re-introduce feature-wrapper attachment patterns unless there is a concrete extension need that cannot be handled by a direct DUT method or a pure helper function.
- When a helper returns a DUT instance, treat it as the final business object. Do not wrap it again or access stale compatibility fields such as `.dut` on the returned object.
- Repeated case execution still uses `cycle`/`loop_count` semantics, but the Run page should not expand all repeated rows at once when every cycle has the same structure. Show one visible cycle window per repeated step group, refresh that same row set as the current cycle advances, and avoid stacking identical cycle rows in the UI.
- When a repeated case enters a new loop/cycle, the entire visible repeat group must refresh to the current `x/x` title immediately. Do not wait for each individual step row to start before updating its loop/cycle label. Status progression remains per-row: earlier rows may be `passed`, the current row may be `running`, and later rows should remain `planned`.

Before finalizing a refactor, check:

- Does this reduce coupling, or just move code around?
- Is each module/class easier to describe in one sentence?
- Is the new abstraction needed now?
- Did business ownership remain clear by layer?
- Did extension points improve without making the common path harder?

## 7. Bug Fix Policy (No Workarounds)

For every bug, regression, unexpected behavior, or "not working as expected" report:

- Do not modify business code first.
- First inspect existing `smart_log(...)` records/runtime logs and the relevant persisted state/config files.
- Explain the observed evidence, expected data flow, suspected mismatch, and proposed fix location.
- Wait for the user to confirm the analysis process before changing code.
- If logs are missing, ask to add minimal diagnostic `smart_log(...)` calls or add only explicitly approved temporary boundary logs before implementing a fix.

When the user says a feature "was working before":

- Do not bypass it with a new implementation.
- Do not paper over it with a different code path.
- First inspect existing `smart_log(...)` records/runtime logs from the broken flow and explain the suspected root cause.
- Do not modify code until the user approves the analysis logic.
- After approval, fix the root cause where it belongs.
- Keep any approved fix scoped to the bug; do not refactor unrelated areas.

For bug investigations:

- Use existing `smart_log(...)` records or runtime logs from the relevant flow before changing behavior.
- If current logs are insufficient, add minimal temporary `smart_log(...)` calls at flow boundaries.
- Debug logs should expose business identity such as selected nodeid, Android case id, request id, step id, definition id, status, and parameter set.
- Fix the exact mismatch or failing transition first.
- Remove temporary debug logs after they have served their purpose.
- Do not add case-specific fixes for examples such as eMMC or reboot; fix the shared mechanism.

## 8. Minimal-Defense Coding Style

- Do not add broad `try/except` blocks to suppress errors.
- Do not add speculative guard checks that merely avoid crashes without addressing the cause.
- Use concise value normalization where appropriate.
- Handle errors at external I/O boundaries and user-input boundaries to produce clear, actionable messages.
- Temporary self tests created for debugging must be removed after the debugging/validation cycle. Recreate focused self tests next time they are needed; do not keep debug-only tests in the repository.

## 9. Collaboration Workflow For Large Modules

For any large business module request (new subsystem, cross-layer changes, new data model, new UI navigation concept), discuss first:

- proposed module boundaries
- folder layout
- public interfaces (signals/slots, Python APIs)
- expected flows (UI -> controller -> runner -> results)

Only implement after the user confirms the approach.

## 10. External Links / Upstream Coupling

- Do not add hard-coded links to upstream author repos or services.
- OTA/update mechanisms must be configurable through SmartTest-owned endpoints and disabled by default.
