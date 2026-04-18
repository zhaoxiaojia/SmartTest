# Tests

Pytest business-entry suite for SmartTest.

Current real case layout:

- `testing/tests/IPTV/system/`
- `testing/tests/IPTV/media/`
- `testing/tests/IPTV/wifi_bt/`
- `testing/tests/Smart Home/`

These pytest cases do not reimplement Android-side business logic.
They trigger `mobile_android` through `adb shell am start ...` and keep
parameter applicability in the `testing/` layer via pytest markers.
