from __future__ import annotations

from testing.tool.dut_tool.features.base import FeatureBase


class SettingsFeature(FeatureBase):
    def accept_mobile_terms_keep_wlan_enabled(self):
        """
        Accept the mobile terms dialog path that keeps wlan0 enabled.
        """
        for x, y in self.dut.MOBILE_TERMS_KEEP_WLAN_TAPS:
            self.dut.tap(x, y)
        return None

    def open_mobile_settings(self):
        return self.dut.run_device_shell(
            f"am start -n {self.dut.CMCC_MOBILE_SETTINGS_COMPONENT}"
        )

    def open_android_tv_settings(self):
        return self.dut.run_device_shell(
            f"am start -n {self.dut.ANDROID_TV_SETTINGS_COMPONENT}"
        )

    def open_more_settings(self):
        return self.dut.run_device_shell(
            f"am start -n {self.dut.DROIDLOGIC_MORE_SETTINGS_COMPONENT}"
        )

