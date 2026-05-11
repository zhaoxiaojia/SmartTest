from __future__ import annotations

from pathlib import Path
from threading import Lock, Thread

from PySide6.QtCore import QObject, QStandardPaths, Signal, Slot
from PySide6.QtGui import QGuiApplication

from debug.kpi_video import analyze_kpi_video


class DebugBridge(QObject):
    analysisStarted = Signal(str)
    analysisFinished = Signal("QVariantMap")
    errorOccurred = Signal(str)

    def __init__(self, runtime_root: Path):
        super().__init__(QGuiApplication.instance())
        self._runtime_root = runtime_root
        self._lock = Lock()
        self._running = False

    @Slot(str)
    def analyzeKpiVideo(self, video_path: str) -> None:
        path = str(video_path or "").strip().strip('"')
        if path.startswith("file:///"):
            path = path[8:]
        if not path:
            self.errorOccurred.emit(self.tr("Select a video file first."))
            return

        resolved = Path(path)
        if not resolved.is_absolute():
            resolved = self._runtime_root / resolved

        with self._lock:
            if self._running:
                self.errorOccurred.emit(self.tr("KPI video analysis is already running."))
                return
            self._running = True

        self.analysisStarted.emit(str(resolved))
        Thread(target=self._analyze_worker, args=(resolved,), daemon=True).start()

    def _analyze_worker(self, path: Path) -> None:
        try:
            result = analyze_kpi_video(path, evidence_dir=self._evidence_dir())
        except Exception as exc:
            self.errorOccurred.emit(str(exc))
        else:
            self.analysisFinished.emit(result)
        finally:
            with self._lock:
                self._running = False

    def _evidence_dir(self) -> Path:
        base = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
        return base / "SmartTest" / "debug" / "kpi_video"
