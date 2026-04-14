from __future__ import annotations


class AppMixin:
    def start_activity(self, packageName, activityName, intentname=""):
        return self._start_activity_impl(packageName, activityName, intentname=intentname)

    def _start_activity_impl(self, packageName, activityName, *, intentname=""):
        raise NotImplementedError

    def app_stop(self, app_name):
        return self._app_stop_impl(app_name)

    def _app_stop_impl(self, app_name):
        raise NotImplementedError
