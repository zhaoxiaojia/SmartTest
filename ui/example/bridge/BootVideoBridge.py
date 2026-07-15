from __future__ import annotations

import base64
import threading
import time
from pathlib import Path
from typing import Any

import cv2
from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication

from tools.logging import smart_log
from testing.state.local_store import load_json, save_json
from testing.tool.boot_video.analyzer import FrameAnalyzer
from testing.tool.boot_video.camera import CameraManager
from testing.tool.boot_video.roi import ScreenROI
from testing.tool.boot_video.service import BootVideoSettings, BootVideoTestService
from testing.tool.boot_video.templates import TemplateManager

try:
    from example.helper.AppPaths import app_data_dir
except ImportError:  # pragma: no cover
    from ui.example.helper.AppPaths import app_data_dir


class BootVideoBridge(QObject):
    camerasChanged = Signal()
    cameraModesChanged = Signal()
    stateChanged = Signal()
    previewChanged = Signal(str)
    statusUpdated = Signal("QVariantMap")
    testFinished = Signal("QVariantMap")
    errorOccurred = Signal(str)

    def __init__(self, runtime_root: Path):
        super().__init__(QGuiApplication.instance())
        self._runtime_root = runtime_root
        self._state_path = app_data_dir() / "boot_video_state.json"
        self._state = self._load_state()
        self._cameras: list[dict[str, Any]] = []
        self._camera_modes: list[dict[str, Any]] = self._preset_modes()
        self._camera = CameraManager()
        self._service: BootVideoTestService | None = None
        self._worker: threading.Thread | None = None
        self._running = False
        self._last_preview_emit = 0.0
        self._preview_thread: threading.Thread | None = None
        self._preview_stop = threading.Event()
        self._preview_index = 0
        self._preview_dir = app_data_dir() / "boot_video_preview"
        self._analyzer_cache_key: tuple[str, str] | None = None
        self._analyzer_cache: FrameAnalyzer | None = None
        self._preview_stats_started = 0.0
        self._preview_encoded = 0
        self._preview_dropped = 0
        self._preview_encode_ms_total = 0.0
        self._preview_max_width = 1440
        self._preview_interval_s = 1.0 / 12.0
        self._modes_worker: threading.Thread | None = None
        self._modes_probe_stop = threading.Event()
        self._modes_probe_running = False

    @Slot()
    def refreshCameras(self) -> None:
        try:
            self._cameras = CameraManager.list_devices()
            device_id = int(self._state.get("device_id", 0) or 0)
            if self._cameras:
                self._camera_modes = self._preset_modes()
                self._start_modes_probe(device_id)
            else:
                self._camera_modes = []
        except Exception as exc:
            self.errorOccurred.emit(str(exc))
            self._cameras = []
            self._camera_modes = []
        self.camerasChanged.emit()
        self.cameraModesChanged.emit()

    @Slot(result="QVariantList")
    def cameraRows(self):
        return list(self._cameras)

    @Slot(int)
    def refreshCameraModes(self, device_id: int) -> None:
        self._start_modes_probe(int(device_id))

    def _start_modes_probe(self, device_id: int) -> None:
        worker = self._modes_worker
        if worker and worker.is_alive():
            return
        self._modes_probe_stop.clear()
        self._modes_probe_running = True
        self.cameraModesChanged.emit()
        self._modes_worker = threading.Thread(target=self._probe_modes_worker, args=(int(device_id),), name="BootVideoModesProbe", daemon=True)
        self._modes_worker.start()

    def _probe_modes_worker(self, device_id: int) -> None:
        try:
            try:
                modes = CameraManager.probe_modes(int(device_id), stop_event=self._modes_probe_stop)
            except TypeError:
                modes = CameraManager.probe_modes(int(device_id))
            if modes:
                self._camera_modes = modes
                self._select_default_mode_if_needed(force=True)
            elif not self._camera_modes:
                self._camera_modes = self._preset_modes()
        except Exception as exc:
            self.errorOccurred.emit(str(exc))
            self._camera_modes = []
        self._modes_probe_running = False
        self.cameraModesChanged.emit()
        self.stateChanged.emit()

    def _stop_modes_probe(self) -> None:
        self._modes_probe_stop.set()
        worker = self._modes_worker
        if worker and worker.is_alive():
            worker.join(timeout=1.0)

    def _state_mode(self) -> dict[str, Any]:
        width = int(self._state.get("width", 1280) or 1280)
        height = int(self._state.get("height", 720) or 720)
        fps = int(float(self._state.get("fps", 30) or 30))
        return {"width": width, "height": height, "fps": fps, "backend": str(self._state.get("camera_backend", "") or ""), "label": f"{width} x {height} @ {fps} fps"}

    def _preset_modes(self) -> list[dict[str, Any]]:
        presets = [
            (3840, 2160, 30),
            (2560, 1440, 30),
            (1920, 1080, 60),
            (1920, 1080, 30),
            (1280, 720, 60),
            (1280, 720, 30),
            (640, 480, 30),
        ]
        rows: list[dict[str, Any]] = []
        seen: set[tuple[int, int, int]] = set()
        for width, height, fps in presets:
            key = (width, height, fps)
            if key in seen:
                continue
            seen.add(key)
            rows.append({"width": width, "height": height, "fps": fps, "backend": "", "label": f"{width} x {height} @ {fps} fps"})
        return rows

    @Slot(result="QVariantList")
    def cameraModes(self):
        return list(self._camera_modes)

    @Slot(result=bool)
    def isProbingCameraModes(self) -> bool:
        return bool(self._modes_probe_running)

    @Slot(result="QVariantMap")
    def settings(self):
        return dict(self._state)

    @Slot("QVariantMap")
    def saveSettings(self, values) -> None:
        if isinstance(values, dict):
            self._state.update(self._normalized_values(values))
            save_json(self._state_path, self._state)
            self.stateChanged.emit()

    @Slot("QVariant", result=str)
    def localPath(self, value) -> str:
        text = str(value.toString() if hasattr(value, "toString") else value or "").strip()
        if text.startswith("file:///"):
            return QUrl(text).toLocalFile()
        if text.startswith("file://"):
            return QUrl(text).toLocalFile()
        return text

    @Slot("QVariantMap", result=bool)
    def openCamera(self, values) -> bool:
        self._stop_modes_probe()
        self.saveSettings(values)
        try:
            settings = self._settings_from_state(validate_templates=False)
            self._camera.open(settings.device_id, settings.width, settings.height, settings.fps)
            self._camera.start()
            self._apply_actual_camera_properties()
            self._start_preview_worker()
        except Exception as exc:
            self.errorOccurred.emit(str(exc))
            return False
        self.statusUpdated.emit({"state": "camera_ready"})
        return True

    @Slot()
    def closeCamera(self) -> None:
        self._stop_preview_worker()
        self._camera.stop()
        self.statusUpdated.emit({"state": "idle"})

    @Slot("QVariantMap", result=bool)
    def startTest(self, values) -> bool:
        if self._running:
            self.errorOccurred.emit(self.tr("Boot video test is already running."))
            return False
        self.saveSettings(values)
        try:
            settings = self._settings_from_state()
            if Path(settings.logo_template_path).resolve() == Path(settings.home_template_path).resolve():
                raise ValueError(self.tr("Logo and Home templates must be different."))
        except Exception as exc:
            self.errorOccurred.emit(str(exc))
            return False
        self._running = True
        self._stop_preview_worker()
        service = BootVideoTestService(
            settings=settings,
            results_root=self._runtime_root / "results" / "boot_video",
            camera=self._camera,
            status_callback=self._on_service_status,
            preview_callback=self._on_preview_frame,
        )
        self._service = service
        self._worker = threading.Thread(target=self._run_service, args=(service,), daemon=True)
        self._worker.start()
        self.stateChanged.emit()
        return True

    @Slot()
    def stopTest(self) -> None:
        if self._service is not None:
            self._service.cancel()

    @Slot(str, "QVariantMap", result=bool)
    def captureTemplate(self, kind: str, values) -> bool:
        self.saveSettings(values)
        latest = self._camera.get_latest_frame()
        if latest is None:
            self.errorOccurred.emit(self.tr("Open the camera before capturing a template."))
            return False
        frame, _ = latest
        settings = self._settings_from_state(validate_templates=False)
        template_dir = app_data_dir() / "boot_video_templates"
        target = template_dir / ("logo_template.png" if kind == "logo" else "home_template.png")
        try:
            TemplateManager.save_from_frame(frame, settings.roi, target)
        except Exception as exc:
            self.errorOccurred.emit(str(exc))
            return False
        key = "logo_template_path" if kind == "logo" else "home_template_path"
        self._state[key] = str(target)
        save_json(self._state_path, self._state)
        self.stateChanged.emit()
        return True

    @Slot(result=bool)
    def openResultFolder(self) -> bool:
        result_dir = str(self._state.get("last_result_dir", "") or "")
        if not result_dir:
            self.errorOccurred.emit(self.tr("No boot video result folder is available."))
            return False
        return QDesktopServices.openUrl(QUrl.fromLocalFile(result_dir))

    @Slot(result=bool)
    def isRunning(self) -> bool:
        return self._running

    def _run_service(self, service: BootVideoTestService) -> None:
        try:
            result = service.run()
        except Exception as exc:
            self.errorOccurred.emit(str(exc))
            result = {"status": "failed", "failure_reason": str(exc)}
        self._running = False
        if result.get("result_dir"):
            self._state["last_result_dir"] = result["result_dir"]
            save_json(self._state_path, self._state)
        self.testFinished.emit(result)
        self.stateChanged.emit()
        if getattr(self._camera, "is_running", lambda: False)():
            self._start_preview_worker()

    def _on_service_status(self, payload: dict) -> None:
        self.statusUpdated.emit(dict(payload))

    def _on_preview_frame(self, frame, timestamp: float) -> None:
        if timestamp - self._last_preview_emit < self._preview_interval_s:
            self._preview_dropped += 1
            self._emit_preview_stats()
            return
        self._last_preview_emit = timestamp
        started = time.perf_counter()
        preview = self._preview_frame(frame)
        preview = self._tone_map_preview(preview)
        ok, encoded = cv2.imencode(".jpg", preview, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        if not ok:
            return
        self._preview_encode_ms_total += (time.perf_counter() - started) * 1000.0
        self._preview_encoded += 1
        data = base64.b64encode(encoded.tobytes()).decode("ascii")
        self.previewChanged.emit(f"data:image/jpeg;base64,{data}")
        self._emit_preview_stats()

    def _preview_frame(self, frame):
        height, width = frame.shape[:2]
        if width <= self._preview_max_width:
            return frame
        scale = self._preview_max_width / float(width)
        target = (self._preview_max_width, max(1, int(height * scale)))
        return cv2.resize(frame, target, interpolation=cv2.INTER_AREA)

    def _tone_map_preview(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        value = hsv[:, :, 2]
        highlights = value > 210
        if highlights.any():
            compressed = 210 + ((value[highlights].astype("float32") - 210) * 0.45)
            value[highlights] = compressed.clip(0, 255).astype("uint8")
        hsv[:, :, 2] = value
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

    def _emit_preview_stats(self) -> None:
        now = time.perf_counter()
        if self._preview_stats_started <= 0:
            self._preview_stats_started = now
            return
        elapsed = now - self._preview_stats_started
        if elapsed < 5.0:
            return
        encoded = self._preview_encoded
        avg_encode_ms = self._preview_encode_ms_total / encoded if encoded else 0.0
        smart_log(
            "boot video preview stats",
            domain="ui",
            source="BootVideoBridge",
            extra={
                "emit_fps": round(encoded / elapsed, 2) if elapsed > 0 else 0.0,
                "encoded": encoded,
                "dropped": self._preview_dropped,
                "avg_encode_ms": round(avg_encode_ms, 2),
                "max_width": self._preview_max_width,
            },
        )
        self._preview_stats_started = now
        self._preview_encoded = 0
        self._preview_dropped = 0
        self._preview_encode_ms_total = 0.0

    def _emit_template_scores(self, frame, timestamp: float) -> None:
        analyzer = self._preview_analyzer()
        if analyzer is None:
            return
        try:
            settings = self._settings_from_state(validate_templates=False)
            roi_frame = settings.roi.crop(frame)
            result = analyzer.analyze(roi_frame, timestamp=timestamp)
        except Exception:
            return
        self.statusUpdated.emit(
            {
                "state": "camera_ready",
                "logo_score": result.logo_score,
                "home_score": result.home_score,
                "logo_scale": result.best_logo_scale or 0,
                "home_scale": result.best_home_scale or 0,
            }
        )

    def _preview_analyzer(self) -> FrameAnalyzer | None:
        logo_path = self.localPath(self._state.get("logo_template_path", ""))
        home_path = self.localPath(self._state.get("home_template_path", ""))
        if not logo_path or not home_path:
            return None
        key = (logo_path, home_path)
        if self._analyzer_cache_key == key and self._analyzer_cache is not None:
            return self._analyzer_cache
        try:
            analyzer = FrameAnalyzer(
                logo_template=TemplateManager.load_image(logo_path),
                home_template=TemplateManager.load_image(home_path),
            )
        except Exception as exc:
            self.statusUpdated.emit({"state": "camera_ready", "template_error": str(exc)})
            return None
        self._analyzer_cache_key = key
        self._analyzer_cache = analyzer
        return analyzer

    def _apply_actual_camera_properties(self) -> None:
        actual = self._camera.actual_properties() if hasattr(self._camera, "actual_properties") else {}
        if not actual:
            return
        actual_width = int(actual.get("width", 0) or 0)
        actual_height = int(actual.get("height", 0) or 0)
        actual_fps = float(actual.get("fps", 0.0) or 0.0)
        if actual_width > 0:
            self._state["width"] = actual_width
        if actual_height > 0:
            self._state["height"] = actual_height
        if actual_fps > 0:
            self._state["fps"] = actual_fps
        backend = str(actual.get("backend", "") or "")
        if backend:
            self._state["camera_backend"] = backend
        roi = ScreenROI.from_mapping(self._state.get("roi"))
        if actual_width > 0 and actual_height > 0:
            if roi.width <= 0 or roi.height <= 0 or roi.x + roi.width > actual_width or roi.y + roi.height > actual_height:
                self._state["roi"] = {"x": 0, "y": 0, "width": actual_width, "height": actual_height}
        save_json(self._state_path, self._state)
        self.stateChanged.emit()

    def _select_default_mode_if_needed(self, *, force: bool = False) -> None:
        if not self._camera_modes:
            return
        if force or int(self._state.get("width", 0) or 0) <= 0 or int(self._state.get("height", 0) or 0) <= 0:
            selected = self._camera_modes[0]
            self._state["width"] = int(selected["width"])
            self._state["height"] = int(selected["height"])
            self._state["fps"] = int(selected["fps"])
            self._state["roi"] = {"x": 0, "y": 0, "width": int(selected["width"]), "height": int(selected["height"])}
            save_json(self._state_path, self._state)

    def _start_preview_worker(self) -> None:
        self._stop_preview_worker()
        self._preview_stop.clear()
        self._preview_thread = threading.Thread(target=self._preview_loop, name="BootVideoPreview", daemon=True)
        self._preview_thread.start()

    def _stop_preview_worker(self) -> None:
        self._preview_stop.set()
        thread = self._preview_thread
        if thread and thread.is_alive():
            thread.join(timeout=1.5)
        self._preview_thread = None

    def _preview_loop(self) -> None:
        while not self._preview_stop.is_set():
            try:
                latest = self._camera.get_latest_frame(copy=False)
            except TypeError:
                latest = self._camera.get_latest_frame()
            if latest is not None:
                frame, timestamp = latest
                self._on_preview_frame(frame, timestamp)
            time.sleep(0.01)

    def _settings_from_state(self, *, validate_templates: bool = True) -> BootVideoSettings:
        state = self._state
        logo_template_path = self.localPath(state.get("logo_template_path", ""))
        home_template_path = self.localPath(state.get("home_template_path", ""))
        settings = BootVideoSettings(
            device_id=int(state.get("device_id", 0) or 0),
            width=int(state.get("width", 1280) or 1280),
            height=int(state.get("height", 720) or 720),
            fps=int(state.get("fps", 30) or 30),
            analysis_fps=int(state.get("analysis_fps", 5) or 5),
            roi=ScreenROI.from_mapping(state.get("roi")),
            timeout_seconds=float(state.get("timeout_seconds", 30) or 30),
            logo_template_path=logo_template_path,
            home_template_path=home_template_path,
            logo_threshold=float(state.get("logo_threshold", 0.8) or 0.8),
            home_threshold=float(state.get("home_threshold", 0.8) or 0.8),
            logo_confirm_frames=int(state.get("logo_confirm_frames", 3) or 3),
            home_confirm_frames=int(state.get("home_confirm_frames", 3) or 3),
            home_stable_duration_s=float(state.get("home_stable_duration_s", 0.5) or 0.5),
            power_delay_seconds=float(state.get("power_delay_seconds", 0) or 0),
            glare_skip_ratio=float(state.get("glare_skip_ratio", 0.08) or 0.08),
        )
        if validate_templates:
            if not settings.logo_template_path:
                raise ValueError(self.tr("Logo template is not configured."))
            if not settings.home_template_path:
                raise ValueError(self.tr("Home template is not configured."))
        return settings

    def _load_state(self) -> dict[str, Any]:
        return load_json(
            self._state_path,
            {
                "device_id": 0,
                "width": 1280,
                "height": 720,
                "fps": 30,
                "analysis_fps": 5,
                "roi": {"x": 0, "y": 0, "width": 1280, "height": 720},
                "logo_template_path": "",
                "home_template_path": "",
                "logo_threshold": 0.8,
                "home_threshold": 0.8,
                "logo_confirm_frames": 3,
                "home_confirm_frames": 3,
                "home_stable_duration_s": 0.5,
                "power_delay_seconds": 0,
                "glare_skip_ratio": 0.08,
                "timeout_seconds": 30,
                "last_result_dir": "",
                "camera_backend": "",
            },
        )

    def _normalized_values(self, values: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(values)
        for key in ("logo_template_path", "home_template_path"):
            if key in normalized:
                normalized[key] = self.localPath(normalized.get(key, ""))
        return normalized
