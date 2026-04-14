from __future__ import annotations


class SystemMixin:
    def reboot(self):
        return self._reboot_impl()

    def _reboot_impl(self):
        self.checkoutput("reboot")
        return None

    def expand_logcat_capacity(self):
        return self._expand_logcat_capacity_impl()

    def _expand_logcat_capacity_impl(self):
        raise NotImplementedError

    def clear_logcat(self):
        return self._clear_logcat_impl()

    def _clear_logcat_impl(self):
        raise NotImplementedError

    def save_logcat(self, filepath, tag=""):
        return self._save_logcat_impl(filepath, tag=tag)

    def _save_logcat_impl(self, filepath, *, tag=""):
        raise NotImplementedError

    def stop_save_logcat(self, log, filepath):
        return self._stop_save_logcat_impl(log, filepath)

    def _stop_save_logcat_impl(self, log, filepath):
        raise NotImplementedError

    def filter_logcat_pid(self):
        return self._filter_logcat_pid_impl()

    def _filter_logcat_pid_impl(self):
        raise NotImplementedError

    def kill_logcat_pid(self):
        return self._kill_logcat_pid_impl()

    def _kill_logcat_pid_impl(self):
        raise NotImplementedError

    def dmesg(self):
        return self.checkoutput(self.DMESG_COMMAND)

    def clear_dmesg(self):
        return self.checkoutput(self.CLEAR_DMESG_COMMAND)

    def wifi_enable(self):
        return self.checkoutput(self.SVC_WIFI_ENABLE)

    def wifi_disable(self):
        return self.checkoutput(self.SVC_WIFI_DISABLE)

    def bluetooth_enable(self):
        return self.checkoutput(self.SVC_BLUETOOTH_ENABLE)

    def bluetooth_disable(self):
        return self.checkoutput(self.SVC_BLUETOOTH_DISABLE)

    def get_country_code(self):
        return self.checkoutput(self.GET_COUNTRY_CODE)

    def set_country_code(self, country_code: str):
        return self.checkoutput(self.SET_COUNTRY_CODE_FORMAT.format(country_code))
