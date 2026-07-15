from __future__ import annotations

import threading
import time

import cv2

from support.logging import smart_log


_BACKENDS = (
    ("DSHOW", cv2.CAP_DSHOW),
    ("MSMF", cv2.CAP_MSMF),
    ("ANY", cv2.CAP_ANY),
)

_PROBE_MODES = (
    (3840, 2160, 30),
    (3840, 2160, 15),
    (2560, 1440, 30),
    (2560, 1440, 15),
    (1920, 1080, 60),
    (1920, 1080, 30),
    (1920, 1080, 15),
    (1280, 720, 60),
    (1280, 720, 30),
    (1024, 768, 30),
    (800, 600, 30),
    (640, 480, 30),
)


class CameraManager:
    def __init__(self) -> None:
        self._capture = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._latest_frame = None
        self._latest_timestamp = 0.0
        self._running = False
        self._read_failures = 0
        self._backend_name = ""
        self._frames_read = 0
        self._last_stats_time = 0.0

    @staticmethod
    def list_devices(max_devices: int = 10) -> list[dict]:
        devices: list[dict] = []
        for device_id in range(max_devices):
            for backend_name, backend in _BACKENDS:
                capture = cv2.VideoCapture(device_id, backend)
                try:
                    if capture.isOpened():
                        devices.append({"device_id": device_id, "name": f"Camera {device_id}", "backend": backend_name})
                        smart_log(
                            "boot video camera detected",
                            domain="equipment",
                            source="boot_video.camera",
                            extra={"device_id": device_id, "backend": backend_name},
                        )
                        break
                finally:
                    capture.release()
        return devices

    @staticmethod
    def probe_modes(device_id: int, stop_event: threading.Event | None = None) -> list[dict]:
        modes: dict[tuple[int, int, int], dict] = {}
        for backend_name, backend in _BACKENDS:
            for width, height, fps in _PROBE_MODES:
                if stop_event is not None and stop_event.is_set():
                    return sorted(modes.values(), key=lambda item: (int(item["width"]) * int(item["height"]), int(item["fps"])), reverse=True)
                capture = cv2.VideoCapture(int(device_id), backend)
                try:
                    if not capture.isOpened():
                        continue
                    capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    capture.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
                    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
                    capture.set(cv2.CAP_PROP_FPS, int(fps))
                    ok, frame = capture.read()
                    if not ok or frame is None:
                        continue
                    actual_height, actual_width = frame.shape[:2]
                    actual_fps = int(round(float(capture.get(cv2.CAP_PROP_FPS) or fps)))
                    if actual_width <= 0 or actual_height <= 0:
                        continue
                    key = (actual_width, actual_height, actual_fps)
                    modes.setdefault(
                        key,
                        {
                            "width": actual_width,
                            "height": actual_height,
                            "fps": actual_fps,
                            "backend": backend_name,
                            "label": f"{actual_width} x {actual_height} @ {actual_fps} fps",
                        },
                    )
                finally:
                    capture.release()
            if modes:
                break
        rows = sorted(modes.values(), key=lambda item: (int(item["width"]) * int(item["height"]), int(item["fps"])), reverse=True)
        smart_log(
            "boot video camera modes probed",
            domain="equipment",
            source="boot_video.camera",
            extra={"device_id": int(device_id), "count": len(rows), "modes": rows[:8]},
        )
        return rows

    def open(self, device_id: int, width: int, height: int, fps: int) -> None:
        self.stop()
        errors: list[str] = []
        for backend_name, backend in _BACKENDS:
            capture = cv2.VideoCapture(int(device_id), backend)
            if not capture.isOpened():
                capture.release()
                errors.append(backend_name)
                continue
            capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
            capture.set(cv2.CAP_PROP_FPS, int(fps))
            self._capture = capture
            self._backend_name = backend_name
            smart_log(
                "boot video camera opened",
                domain="equipment",
                source="boot_video.camera",
                extra={
                    "device_id": int(device_id),
                    "backend": backend_name,
                    "requested_width": int(width),
                    "requested_height": int(height),
                    "requested_fps": int(fps),
                    "actual": self.actual_properties(),
                },
            )
            return
        if "capture" in locals():
            capture.release()
        raise RuntimeError(f"Camera could not be opened: {device_id}; attempted backends={','.join(errors)}")

    def start(self) -> None:
        if self._capture is None:
            raise RuntimeError("Camera is not open.")
        if self._running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._read_loop, name="BootVideoCamera", daemon=True)
        self._running = True
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        self._thread = None
        self._running = False
        capture = self._capture
        self._capture = None
        if capture is not None:
            smart_log(
                "boot video camera closed",
                domain="equipment",
                source="boot_video.camera",
                extra={"backend": self._backend_name},
            )
            capture.release()
        self._backend_name = ""

    def is_running(self) -> bool:
        return self._running

    def get_latest_frame(self, *, copy: bool = True):
        with self._lock:
            if self._latest_frame is None:
                return None
            frame = self._latest_frame.copy() if copy else self._latest_frame
            return frame, self._latest_timestamp

    def actual_properties(self) -> dict:
        capture = self._capture
        if capture is None:
            return {}
        return {
            "backend": self._backend_name,
            "width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
            "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0),
            "fps": float(capture.get(cv2.CAP_PROP_FPS) or 0.0),
        }

    def _read_loop(self) -> None:
        while not self._stop_event.is_set():
            capture = self._capture
            if capture is None:
                break
            ok, frame = capture.read()
            if not ok or frame is None:
                self._read_failures += 1
                if self._read_failures >= 10:
                    smart_log(
                        "boot video camera read failed repeatedly",
                        domain="equipment",
                        source="boot_video.camera",
                        level="error",
                        extra={"failures": self._read_failures, "backend": self._backend_name},
                    )
                    self._running = False
                    break
                time.sleep(0.03)
                continue
            self._read_failures = 0
            with self._lock:
                self._latest_frame = frame
                self._latest_timestamp = time.perf_counter()
            self._frames_read += 1
            self._emit_read_stats()
        self._running = False

    def _emit_read_stats(self) -> None:
        now = time.perf_counter()
        if self._last_stats_time <= 0:
            self._last_stats_time = now
            self._frames_read = 0
            return
        elapsed = now - self._last_stats_time
        if elapsed < 5.0:
            return
        fps = self._frames_read / elapsed if elapsed > 0 else 0.0
        smart_log(
            "boot video camera read stats",
            domain="equipment",
            source="boot_video.camera",
            extra={"read_fps": round(fps, 2), "backend": self._backend_name},
        )
        self._frames_read = 0
        self._last_stats_time = now
