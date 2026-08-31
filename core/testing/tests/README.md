# Business Test Cases

Pytest business-entry suite for SmartTest. Files under this directory are
discoverable product test cases, not framework self tests.

Current real case layout:

- `core/testing/tests/android/common/system/`
- `core/testing/tests/android/common/media/`
- `core/testing/tests/android/common/wifi_bt/`
- `core/testing/tests/Smart Home/`

These pytest cases do not reimplement Android-side business logic.
They trigger `android_client` through `adb shell am start ...` and keep
parameter applicability in the `core/testing/` layer via pytest markers.

Framework/runtime/parameter/runner tests belong in `core/testing/self_tests/`.
