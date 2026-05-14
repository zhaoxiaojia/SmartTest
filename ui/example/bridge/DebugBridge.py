from __future__ import annotations

from pathlib import Path
from threading import Lock, Thread

from PySide6.QtCore import QObject, QStandardPaths, Signal, Slot
from PySide6.QtGui import QGuiApplication

from debug.kpi_video import load_kpi_review_frame, mark_kpi_review_frame, prepare_kpi_review_session


class DebugBridge(QObject):
    reviewProgress = Signal("QVariantMap")
    reviewPrepared = Signal("QVariantMap")
    reviewFrameLoaded = Signal("QVariantMap")
    reviewFrameMarked = Signal("QVariantMap")
    errorOccurred = Signal(str)

    def __init__(self, runtime_root: Path):
        super().__init__(QGuiApplication.instance())
        self._runtime_root = runtime_root
        self._lock = Lock()
        self._review_running = False
        self._review_session: dict | None = None

    @Slot(str)
    def prepareKpiReview(self, video_path: str) -> None:
        path = self._resolve_video_path(video_path)
        if path is None:
            return

        with self._lock:
            if self._review_running:
                self.errorOccurred.emit(self.tr("KPI video loading is already running."))
                return
            self._review_running = True

        Thread(target=self._prepare_review_worker, args=(path,), daemon=True).start()

    def _prepare_review_worker(self, path: Path) -> None:
        try:
            session = prepare_kpi_review_session(
                path,
                work_root=self._review_work_dir(),
                progress_callback=self.reviewProgress.emit,
            )
            frame = load_kpi_review_frame(session, frame_index=0)
        except Exception as exc:
            self.errorOccurred.emit(str(exc))
        else:
            self._review_session = session
            self.reviewPrepared.emit(session)
            self.reviewFrameLoaded.emit(frame)
        finally:
            with self._lock:
                self._review_running = False

    @Slot(int)
    def loadKpiReviewFrame(self, frame_index: int) -> None:
        if not self._review_session:
            self.errorOccurred.emit(self.tr("Load a KPI video first."))
            return
        try:
            frame = load_kpi_review_frame(self._review_session, frame_index=frame_index)
        except Exception as exc:
            self.errorOccurred.emit(str(exc))
        else:
            self.reviewFrameLoaded.emit(frame)

    @Slot(int)
    def stepKpiReviewFrame(self, delta: int) -> None:
        if not self._review_session:
            self.errorOccurred.emit(self.tr("Load a KPI video first."))
            return
        frame_count = int(self._review_session.get("frame_count", 0) or 0)
        if frame_count <= 0:
            self.errorOccurred.emit(self.tr("No frames available in current video."))
            return
        current = int(self._review_session.get("last_frame_index", 0) or 0)
        target = max(0, min(frame_count - 1, current + int(delta)))
        self.loadKpiReviewFrame(target)

    @Slot(int, str)
    def markKpiReviewFrame(self, frame_index: int, marker: str) -> None:
        if not self._review_session:
            self.errorOccurred.emit(self.tr("Load a KPI video first."))
            return
        try:
            frame = mark_kpi_review_frame(self._review_session, frame_index=frame_index, marker=marker)
        except Exception as exc:
            self.errorOccurred.emit(str(exc))
        else:
            self.reviewFrameMarked.emit(frame)

    def _resolve_video_path(self, video_path: str) -> Path | None:
        path = str(video_path or "").strip().strip('"')
        if path.startswith("file:///"):
            path = path[8:]
        if not path:
            self.errorOccurred.emit(self.tr("Select a video file first."))
            return None
        resolved = Path(path)
        if not resolved.is_absolute():
            resolved = self._runtime_root / resolved
        return resolved

    def _review_work_dir(self) -> Path:
        base = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
        return base / "SmartTest" / "debug" / "kpi_review"
