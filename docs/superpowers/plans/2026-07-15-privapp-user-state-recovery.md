# Priv-app User State Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore SmartTest's User 0 package state when privileged provisioning leaves an existing system package marked uninstalled.

**Architecture:** Extend the existing privileged-install owner with one conditional `install-existing` recovery attempt after reboot. Preserve all current APK hash, package-path, and privileged-path verification.

**Tech Stack:** Python, pytest, Android adb/package manager

## Global Constraints

- Do not change APK source or build a new APK.
- Keep DUT provisioning in `android_client/__init__.py`.
- Use `adb -s <serial>` through the existing command boundary.
- Preserve unrelated workspace changes.

---

### Task 1: Add the package-state recovery regression

**Files:**
- Create: `android_client/tests/test_privapp_install.py`
- Modify: `android_client/__init__.py`

**Interfaces:**
- Consumes: `_run_adb(...)`, `is_test_apk_installed(...)`, `_ensure_privileged_install(...)`
- Produces: `_restore_existing_package_for_user(...) -> bool`

- [x] Write a test where the first install probe is false, recovery succeeds, and the second probe is true.
- [x] Run the focused test and verify it fails because the recovery helper/call is absent.
- [x] Implement one `cmd package install-existing --user 0` attempt and actionable logging.
- [x] Run the focused test and verify it passes.
- [x] Run the surrounding Android/DUT self-tests.

### Task 2: Verify the real DUT refresh flow

**Files:**
- Modify: none

**Interfaces:**
- Consumes: Test-page DUT refresh and `com.smarttest.mobile` package state
- Produces: hardware acceptance evidence

- [ ] Uninstall `com.smarttest.mobile` for User 0 and confirm `installed=false`.
- [ ] Start source SmartTest and invoke the Test-page DUT refresh entrypoint.
- [ ] Confirm `pm path com.smarttest.mobile` returns a `/system/priv-app` APK.
- [ ] Confirm `dumpsys package` reports `User 0 installed=true`.
- [x] Run scoped diff review and `git diff --check`.
