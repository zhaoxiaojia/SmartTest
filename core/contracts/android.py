"""Stable identifiers shared by the desktop Android runner and APK owner."""

PACKAGE_NAME = "com.smarttest.mobile"
PRIVILEGED_CASE_IDS = frozenset(
    {"auto_reboot", "auto_suspend", "wifi_onoff_scan", "bt_onoff_scan"}
)
