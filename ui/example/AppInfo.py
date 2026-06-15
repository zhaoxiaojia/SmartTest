import json
from pathlib import Path
import sys

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
    buildTimeChanged = Signal()
    updateCheckUrlChanged = Signal()
    updateDownloadUrlChanged = Signal()

    @Property(str, notify=versionChanged)
    def version(self):
        return self._version

    @version.setter
    def version(self, value):
        self._version = value
        self.versionChanged.emit()

    @Property(str, notify=buildTimeChanged)
    def buildTime(self):
        return self._buildTime

    @buildTime.setter
    def buildTime(self, value):
        self._buildTime = value
        self.buildTimeChanged.emit()

    def __init__(self):
        super().__init__(QGuiApplication.instance())
        manifest = self._load_build_manifest()
        self._version = str(manifest.get("version", "") or "1.0.0")
        self._buildTime = str(manifest.get("built_at", "") or "")
        # OTA endpoints. Leave empty to disable any network access by default.
        self._updateCheckUrl = ""
        self._updateDownloadUrl = ""

    def _load_build_manifest(self):
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
        path = root / "build" / "generated" / "build_manifest.json"
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        if not isinstance(payload, dict):
            return {}
        return payload

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
