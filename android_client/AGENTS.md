# android_client Agent Rules

This file applies to the `android_client/` subtree.

## Case Development Flow

1. Every test case must have its own execution file.
   - Put executors under `app/src/main/java/com/smarttest/mobile/runner/cases/`
   - Group by domain when useful, for example `cases/storage/`, `cases/network/`, `cases/power/`

2. If a test case needs parameters, those parameters are owned by the frontend/pytest side.
   - Do not define UI-facing parameter catalogs in the APK.
   - The APK must consume parameters already supplied by the run request.

3. Every case parameter must be triggerable from `am start`.
   - Command-line parameters must be passed through the existing `am start` flow
   - Use the `params` extra in the form `caseId:paramId=value`

4. Parameters are isolated per case, even if names are the same.
   - Never share raw parameter keys across cases
   - Always use `caseId:paramId`
   - The runner must ignore command-line parameter keys that do not contain `:`

## Runner Conventions

- Prefer routing real device operations through `runner/device/`
- Do not embed shell scripts directly in UI code
- Use `runner/device/log/CommandRecorder` to preserve command history when a case executes shell/system actions
- When porting an existing shell script into Kotlin, keep the original operational flow clear in logs and note any intentional deviations
