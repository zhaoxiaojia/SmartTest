---
name: smarttest-android-workflow
description: Use when changing SmartTest android_client/, Kotlin APK cases, Android runner/device code, am-start parameters, shared step progress, Gradle APK builds, platform signing, priv-app installation, or desktop-to-APK integration.
---

# SmartTest Android Workflow

## Case And Runner Ownership

- Give every case its own executor under `android_client/app/src/main/java/com/smarttest/mobile/runner/cases/`, grouped by domain when useful.
- Frontend/pytest owns parameter catalogs. APK executors consume parameters supplied in the run request and never define UI-facing catalogs.
- Every parameter is triggerable through the existing `am start` flow using `params` entries `caseId:paramId=value`. Ignore raw keys without `:`; never share unscoped keys between cases.
- Route real device operations through `runner/device/`; never embed shell scripts in UI code. Use `runner/device/log/CommandRecorder` for shell/system history and preserve an imported script's operational flow and intentional deviations in structured logs.
- Use `smart_log(...)`/the shared logging transport and preserve case id, request id, step id, status, serial, and parameters. Do not create a parallel logger.

## Shared Steps

APK cases drive the same steps predeclared by pytest/UI. Call `SmartTestRunStore.updateProgress(...)` and `finishStep(...)` for every visible step; stage text and counters are supplemental, not a substitute for step state.

Cycle ids are stable (`case_id.cycle.<index>.<step>`) and checkpoint helpers receive a matching `stepIdPrefix`. Before handoff, map every planned visible step to a runtime update/finish path. Do not synthesize replacement UI rows in the APK.

Checkpoint parameters received as `None`/`none` are unconfigured and skipped, not failed.

## Build, Sign, Artifact, And Install

- Android and desktop package independently. An `.exe` build never validates the APK.
- The product exposes one APK artifact: the platform-signed APK under `dist/`. Gradle `app-debug.apk` is signing input only, not an installable SmartTest runtime artifact.
- After any APK source change, run at least:

```powershell
.\android_client\gradlew.bat -p android_client :app:assembleDebug
```

Use a stricter relevant task when required, platform-sign through repository assets/flow in `android_client/__init__.py`, copy the signed result under `dist/`, and remove stale ordinary debug artifacts when practical.

- `android:sharedUserId="android.uid.system"` may require a system priv-app. Never default to plain `adb install -r`; use the repository platform-sign/priv-app flow.
- APK install/update has one product entrypoint: the DUT adapter invoked by Test-page DUT refresh. Runner/case execution only verifies installation and gives a clear refresh error; it never installs or updates.
- Privileged and non-privileged cases use the same signed artifact path. The DUT adapter decides provisioning, verifies package path/version/hash/install state, and updates when needed.

## Validation

1. Run focused Kotlin/unit/static checks for the changed owner.
2. Build and platform-sign after APK source changes; verify the signed `dist/` artifact.
3. For case changes, verify `am start` parsing, case-scoped keys, planned/runtime step identity, and checkpoint skip behavior.
4. When a DUT is available, validate through the shared DUT refresh/provisioning entrypoint and then execute the case. State explicitly when hardware validation was unavailable.
5. Review scoped diff, remove temporary diagnostics/stale debug artifacts, and run `git diff --check`.

## Quality Check

Reject APK-owned UI catalogs, unscoped parameters, direct case-local install/ADB/shell helpers, missing step updates, separate privileged artifacts, runner-triggered installation, and claims that desktop packaging validates Android.
