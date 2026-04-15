from __future__ import annotations

from testing.tool.dut_tool.features.base import FeatureBase


class StabilityFeature(FeatureBase):
    def get_stability_apk_download_url(self) -> str:
        return self.dut.STABILITY_APK_DOWNLOAD_URL

    def list_stability_apk_packages(self) -> list[str]:
        return list(self.dut.STABILITY_APK_PACKAGES)

    def disable_remote_control(self):
        return self.dut.run_device_shell(self.dut.DISABLE_REMOTE_CONTROL_COMMAND)

    def enable_bluetooth_hci_logging(self) -> list[str]:
        outputs: list[str] = []
        for command in self.dut.ENABLE_BLUETOOTH_HCI_LOGGING_COMMANDS:
            outputs.append(self.dut.run_device_shell(command))
        return outputs

    def get_connected_bluetooth_mac_addresses(self) -> list[str]:
        output = self.dut.run_device_shell(self.dut.CONNECTED_BLUETOOTH_MAC_COMMAND) or ""
        return [line.strip() for line in output.splitlines() if line.strip()]

