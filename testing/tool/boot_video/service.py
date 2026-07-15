from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from support.logging import smart_log
from testing.tool.boot_video.analyzer import FrameAnalyzer
from testing.tool.boot_video.camera import CameraManager
from testing.tool.boot_video.power import MockPowerController, PowerController
from testing.tool.boot_video.recorder import VideoRecorder
from testing.tool.boot_video.results import BootVideoResultWriter, BootVideoSession
from testing.tool.boot_video.roi import ScreenROI
from testing.tool.boot_video.state_machine import AnalysisSample, BootAnalysisConfig, BootAnalysisStateMachine, BootState
from testing.tool.boot_video.templates import TemplateManager


@dataclass
class BootVideoSettings:
    device_id: int
    width: int
    height: int
    fps: int
    analysis_fps: int
    roi: ScreenROI
    timeout_seconds: float = 30.0
    logo_template_path: str = ""
    home_template_path: str = ""
    logo_threshold: float = 0.8
    home_threshold: float = 0.8
    logo_confirm_frames: int = 3
    home_confirm_frames: int = 3
    home_stable_duration_s: float = 0.5
    power_delay_seconds: float = 0.0
    glare_skip_ratio: float = 0.08


class BootVideoTestService:
    def __init__(
        self,
        *,
        settings: BootVideoSettings,
        results_root: Path,
        camera=None,
        recorder=None,
        analyzer=None,
        power_controller: PowerController | None = None,
        status_callback: Callable[[dict], None] | None = None,
        preview_callback: Callable[[object, float], None] | None = None,
    ) -> None:
        self.settings = settings
        self.results_root = Path(results_root)
        self.camera = camera or CameraManager()
        self.recorder = recorder or VideoRecorder()
        self.power_controller = power_controller or MockPowerController()
        self.status_callback = status_callback
        self.preview_callback = preview_callback
        self.cancel_requested = False
        self._provided_analyzer = analyzer
        self._analysis_lines: list[str] = []
        self._glare_skipped_frames = 0
        self._last_glare_ratio = 0.0

    def cancel(self) -> None:
        self.cancel_requested = True

    def run(self) -> dict:
        writer = BootVideoResultWriter(root=self.results_root)
        session = writer.create_session()
        state_machine = self._state_machine()
        self._glare_skipped_frames = 0
        self._last_glare_ratio = 0.0
        camera_info = {
            "device_id": self.settings.device_id,
            "width": self.settings.width,
            "height": self.settings.height,
            "fps": self.settings.fps,
        }
        status = BootState.FAILED
        camera_started_by_service = False
        try:
            if self.cancel_requested:
                state_machine.cancel()
                status = state_machine.state
                return self._finish(writer, session, state_machine, status, camera_info)
            analyzer = self._provided_analyzer or self._build_analyzer()
            camera_started_by_service = self._start_camera_if_needed()
            state_machine.mark_camera_ready()
            self._emit_status(state_machine)
            first_frame = self._wait_for_frame()
            frame, _ = first_frame
            self.settings.roi.validate(frame.shape)
            video_path = session.path / "recording.mp4"
            self.recorder.start(video_path, self.settings.fps, (frame.shape[1], frame.shape[0]))
            writer.register_artifact(session, "video", "recording.mp4")
            state_machine.mark_recording()
            self._record_preview_delay(max(0.0, float(self.settings.power_delay_seconds or 0.0)))
            if self.cancel_requested:
                state_machine.cancel()
                status = state_machine.state
                return self._finish(writer, session, state_machine, status, camera_info)
            power = self.power_controller.power_on()
            if not power.success:
                raise RuntimeError(power.message or "Power on failed.")
            state_machine.mark_powered_on(perf_time=power.perf_time, wall_time=power.wall_time)
            self._log(session, "power_on", {"perf_time": power.perf_time})
            status = self._process_loop(writer, session, state_machine, analyzer, camera_info)
        except Exception as exc:
            if not state_machine.failure_reason:
                state_machine.fail(str(exc))
            status = state_machine.state
            smart_log(str(exc), level="error", domain="equipment", source="boot_video", exc_info=True)
        finally:
            try:
                self.recorder.stop()
            finally:
                if camera_started_by_service:
                    self.camera.stop()
                try:
                    self.power_controller.disconnect()
                except Exception:
                    pass
        return self._finish(writer, session, state_machine, status, camera_info)

    def _process_loop(self, writer, session, state_machine, analyzer, camera_info) -> BootState:
        analysis_interval = 1.0 / max(1, int(self.settings.analysis_fps))
        last_analysis = 0.0
        last_frame_timestamp: float | None = None
        while state_machine.state not in {BootState.COMPLETED, BootState.FAILED, BootState.CANCELLED, BootState.TIMEOUT}:
            if self.cancel_requested:
                state_machine.cancel()
                break
            if state_machine.check_timeout(time.perf_counter()):
                self._annotate_glare_timeout(state_machine)
                self._log(session, "state_changed", {"state": state_machine.state.value})
                break
            latest = self._latest_frame(copy=False)
            if latest is None:
                time.sleep(0.01)
                continue
            frame, timestamp = latest
            if last_frame_timestamp is not None and timestamp <= last_frame_timestamp:
                time.sleep(0.01)
                continue
            last_frame_timestamp = timestamp
            self.recorder.write(frame, timestamp)
            if self.preview_callback:
                self.preview_callback(frame, timestamp)
            if timestamp - last_analysis >= analysis_interval:
                last_analysis = timestamp
                power_event = state_machine.events.get("power_on")
                if power_event is not None and timestamp < power_event.perf_time:
                    self._log(session, "analysis_frame_skipped_before_power", {"frame_time": timestamp, "power_time": power_event.perf_time})
                    continue
                roi_frame = self.settings.roi.crop(frame)
                result = analyzer.analyze(roi_frame, timestamp=timestamp)
                self._validate_analysis_result(result)
                glare_ratio = float(getattr(result, "glare_ratio", 0.0) or 0.0)
                if glare_ratio >= self.settings.glare_skip_ratio:
                    self._glare_skipped_frames += 1
                    self._last_glare_ratio = glare_ratio
                    self._emit_status(state_machine, result=result, glare_ratio=glare_ratio)
                    self._log(session, "analysis_frame_skipped_glare", {"glare_ratio": round(glare_ratio, 4)})
                    continue
                previous = state_machine.state
                state_machine.update(AnalysisSample(result.timestamp, result.logo_score, result.home_score))
                self._emit_status(state_machine, result=result, glare_ratio=glare_ratio)
                self._capture_event_frames(writer, session, state_machine, frame)
                if state_machine.state != previous:
                    self._log(session, "state_changed", {"state": state_machine.state.value})
            time.sleep(0.005)
        return state_machine.state

    @staticmethod
    def _validate_analysis_result(result) -> None:
        missing = [field for field in ("timestamp", "logo_score", "home_score") if not hasattr(result, field)]
        if missing:
            raise RuntimeError(f"Analyzer result missing required field(s): {', '.join(missing)}")

    def _annotate_glare_timeout(self, state_machine: BootAnalysisStateMachine) -> None:
        if self._glare_skipped_frames <= 0:
            return
        state_machine.failure_reason = (
            f"{state_machine.failure_reason or 'Boot video analysis timed out.'} "
            f"Skipped {self._glare_skipped_frames} analysis frame(s) for glare; "
            f"last_glare_ratio={round(self._last_glare_ratio, 4)}, "
            f"configured_glare_skip_ratio={self.settings.glare_skip_ratio}."
        )

    def _record_preview_delay(self, delay_seconds: float) -> None:
        if delay_seconds <= 0:
            return
        deadline = time.perf_counter() + delay_seconds
        last_frame_timestamp: float | None = None
        self._log(None, "power_delay_started", {"seconds": delay_seconds})
        while time.perf_counter() < deadline:
            if self.cancel_requested:
                return
            latest = self._latest_frame(copy=False)
            if latest is None:
                time.sleep(0.01)
                continue
            frame, timestamp = latest
            if last_frame_timestamp is not None and timestamp <= last_frame_timestamp:
                time.sleep(0.01)
                continue
            last_frame_timestamp = timestamp
            self.recorder.write(frame, timestamp)
            if self.preview_callback:
                self.preview_callback(frame, timestamp)
            time.sleep(0.005)

    def _finish(
        self,
        writer: BootVideoResultWriter,
        session: BootVideoSession,
        state_machine: BootAnalysisStateMachine,
        status: BootState,
        camera_info: dict,
    ) -> dict:
        writer.write_analysis_log(session, self._analysis_lines)
        result_path = writer.write_result(
            session,
            status=status.value,
            camera=camera_info,
            roi=self.settings.roi,
            events=state_machine.events,
            durations_ms=state_machine.durations_ms(),
            scores={"logo_max": state_machine.logo_max, "home_max": state_machine.home_max},
            failure_reason=state_machine.failure_reason,
        )
        payload = {
            "status": status.value,
            "result_path": str(result_path),
            "result_dir": str(session.path),
            "failure_reason": state_machine.failure_reason or "",
            "durations_ms": state_machine.durations_ms(),
        }
        if self.status_callback:
            self.status_callback(payload)
        return payload

    def _state_machine(self) -> BootAnalysisStateMachine:
        return BootAnalysisStateMachine(
            BootAnalysisConfig(
                logo_threshold=self.settings.logo_threshold,
                home_threshold=self.settings.home_threshold,
                logo_confirm_frames=self.settings.logo_confirm_frames,
                home_confirm_frames=self.settings.home_confirm_frames,
                home_stable_duration_s=self.settings.home_stable_duration_s,
                timeout_seconds=self.settings.timeout_seconds,
            )
        )

    def _build_analyzer(self) -> FrameAnalyzer:
        logo = TemplateManager.load_image(self.settings.logo_template_path)
        home = TemplateManager.load_image(self.settings.home_template_path)
        return FrameAnalyzer(logo_template=logo, home_template=home)

    def _start_camera_if_needed(self) -> bool:
        if getattr(self.camera, "is_running", lambda: False)():
            return False
        if hasattr(self.camera, "open"):
            self.camera.open(self.settings.device_id, self.settings.width, self.settings.height, self.settings.fps)
        if hasattr(self.camera, "start"):
            self.camera.start()
        return True

    def _wait_for_frame(self):
        deadline = time.perf_counter() + 3.0
        while time.perf_counter() < deadline:
            latest = self._latest_frame(copy=False)
            if latest is not None:
                return latest
            time.sleep(0.03)
        raise RuntimeError("Camera did not provide a frame.")

    def _latest_frame(self, *, copy: bool):
        try:
            return self.camera.get_latest_frame(copy=copy)
        except TypeError:
            return self.camera.get_latest_frame()

    def _capture_event_frames(self, writer, session, state_machine, frame) -> None:
        mapping = {
            "logo_first_detected": "logo_first_detected",
            "logo_confirmed": "logo_confirmed",
            "home_first_detected": "home_first_detected",
            "home_confirmed": "home_confirmed",
        }
        for event_name, artifact_name in mapping.items():
            if event_name in state_machine.events and artifact_name not in session.artifacts:
                writer.save_frame(session, artifact_name, frame)

    def _emit_status(self, state_machine, result=None, glare_ratio: float | None = None) -> None:
        if not self.status_callback:
            return
        payload = {
            "state": state_machine.state.value,
            "logo_score": float(getattr(result, "logo_score", 0.0) if result else 0.0),
            "home_score": float(getattr(result, "home_score", 0.0) if result else 0.0),
            "durations_ms": state_machine.durations_ms(),
            "failure_reason": state_machine.failure_reason or "",
            "glare_ratio": float(glare_ratio if glare_ratio is not None else getattr(result, "glare_ratio", 0.0) if result else 0.0),
        }
        self.status_callback(payload)

    def _log(self, session: BootVideoSession | None, event: str, extra: dict) -> None:
        line = f"{datetime.now().astimezone().isoformat(timespec='milliseconds')} {event} {extra}"
        self._analysis_lines.append(line)
        smart_log(event, domain="equipment", source="boot_video", extra=extra)
