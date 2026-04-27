# Business Test Cases

Pytest business-entry suite for SmartTest. Files under this directory are
discoverable product test cases, not framework self tests.

Current real case layout:

- `testing/tests/android/common/system/`
- `testing/tests/android/common/media/`
- `testing/tests/android/common/wifi_bt/`
- `testing/tests/Smart Home/`

These pytest cases do not reimplement Android-side business logic.
They trigger `android_client` through `adb shell am start ...` and keep
parameter applicability in the `testing/` layer via pytest markers.

Framework/runtime/parameter/runner tests belong in `testing/self_tests/`.
