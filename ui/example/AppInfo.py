from PySide6.QtCore import QObject, Signal, Property
from PySide6.QtGui import QGuiApplication
from qasync import asyncSlot

from FluentUI.Singleton import Singleton
import example.helper.Async as Async
from example.component.Callback import Callback


# noinspection PyPep8Naming
@Singleton
class AppInfo(QObject):
    versionChanged = Signal()
    updateCheckUrlChanged = Signal()
    updateDownloadUrlChanged = Signal()

    @Property(str, notify=versionChanged)
    def version(self):
        return self._version

    @version.setter
    def version(self, value):
        self._version = value
        self.versionChanged.emit()

    def __init__(self):
        super().__init__(QGuiApplication.instance())
        # App semantic version. Keep this in sync with your release process.
        self._version = "0.1.0"
        # OTA endpoints. Leave empty to disable any network access by default.
        self._updateCheckUrl = ""
        self._updateDownloadUrl = ""

    @Property(str, notify=updateCheckUrlChanged)
    def updateCheckUrl(self):
        return self._updateCheckUrl

    @updateCheckUrl.setter
    def updateCheckUrl(self, value):
        self._updateCheckUrl = value or ""
        self.updateCheckUrlChanged.emit()

    @Property(str, notify=updateDownloadUrlChanged)
    def updateDownloadUrl(self):
        return self._updateDownloadUrl

    @updateDownloadUrl.setter
    def updateDownloadUrl(self, value):
        self._updateDownloadUrl = value or ""
        self.updateDownloadUrlChanged.emit()

    @asyncSlot(Callback)
    async def checkUpdate(self, callback: Callback):
        callback.onStart()
        try:
            if not self._updateCheckUrl:
                callback.onError(code=0, errorString="Update check disabled")
                return
            r = await Async.http().get(self._updateCheckUrl)
            callback.onSuccess(await r.text())
        except Exception as exc:
            callback.onError(errorString="Error: {}".format(exc))
        finally:
            callback.onFinish()
