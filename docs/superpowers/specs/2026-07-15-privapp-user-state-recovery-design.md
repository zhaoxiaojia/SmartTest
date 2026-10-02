# Priv-app User State Recovery Design

## Problem

After SmartTest copies its signed APK into `/system/priv-app` and reboots a DUT, Android can still report the package as unavailable when the system package exists but User 0 has `installed=false`. Re-copying the APK does not clear that per-user package-manager state.

## Design

Keep provisioning ownership in `android_client/__init__.py`. After the existing privileged provisioning and reboot completes, perform the current `pm path` verification. If that verification fails, run `cmd package install-existing --user 0 com.smarttest.mobile` once, then repeat the existing package-path and privileged-code-path verification. Do not run the recovery command for already-visible packages and do not change the ordinary user-APK install path.

## Validation

Add a focused unit regression that simulates a missing package after provisioning and verifies one User 0 recovery attempt before success. Validate the original DUT scenario by uninstalling the system app for User 0, refreshing through SmartTest's DUT entrypoint, and confirming `pm path`, `installed=true`, and the `/system/priv-app` code path.
