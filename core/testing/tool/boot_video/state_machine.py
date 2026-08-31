from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BootState(str, Enum):
    IDLE = "idle"
    CAMERA_READY = "camera_ready"
    RECORDING = "recording"
    POWERED_ON = "powered_on"
    LOGO_CANDIDATE = "logo_candidate"
    LOGO_CONFIRMED = "logo_confirmed"
    HOME_CANDIDATE = "home_candidate"
    HOME_CONFIRMED = "home_confirmed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class BootAnalysisConfig:
    logo_threshold: float = 0.8
    home_threshold: float = 0.8
    logo_confirm_frames: int = 3
    home_confirm_frames: int = 3
    home_stable_duration_s: float = 0.5
    timeout_seconds: float = 60.0


@dataclass(frozen=True)
class AnalysisSample:
    timestamp: float
    logo_score: float
    home_score: float


@dataclass(frozen=True)
class BootEvent:
    name: str
    perf_time: float
    wall_time: str = ""
    score: float | None = None


class BootAnalysisStateMachine:
    def __init__(self, config: BootAnalysisConfig) -> None:
        self.config = config
        self.state = BootState.IDLE
        self.events: dict[str, BootEvent] = {}
        self.failure_reason: str | None = None
        self.logo_max = 0.0
        self.home_max = 0.0
        self._logo_hits = 0
        self._home_hits = 0
        self._logo_candidate: BootEvent | None = None
        self._home_candidate: BootEvent | None = None

    def mark_camera_ready(self) -> None:
        self.state = BootState.CAMERA_READY

    def mark_recording(self) -> None:
        self.state = BootState.RECORDING

    def mark_powered_on(self, *, perf_time: float, wall_time: str) -> None:
        self.events["power_on"] = BootEvent("power_on", perf_time, wall_time)
        self.state = BootState.POWERED_ON

    def update(self, sample: AnalysisSample) -> None:
        if self.state in {BootState.COMPLETED, BootState.FAILED, BootState.CANCELLED, BootState.TIMEOUT}:
            return
        self.logo_max = max(self.logo_max, float(sample.logo_score))
        self.home_max = max(self.home_max, float(sample.home_score))
        if self._timed_out(sample.timestamp):
            return
        if "logo_confirmed" not in self.events:
            self._update_logo(sample)
            return
        self._update_home(sample)

    def check_timeout(self, current_perf: float) -> bool:
        if self.state in {BootState.COMPLETED, BootState.FAILED, BootState.CANCELLED, BootState.TIMEOUT}:
            return self.state == BootState.TIMEOUT
        return self._timed_out(current_perf)

    def cancel(self, reason: str = "User cancelled the boot video test.") -> None:
        self.failure_reason = reason
        self.state = BootState.CANCELLED

    def fail(self, reason: str) -> None:
        self.failure_reason = reason
        self.state = BootState.FAILED

    def durations_ms(self) -> dict[str, int | None]:
        power = self.events.get("power_on")
        logo = self.events.get("logo_first_detected")
        home = self.events.get("home_first_detected")
        return {
            "logo_appearance": self._elapsed_ms(power, logo),
            "home_appearance": self._elapsed_ms(power, home),
            "boot_total": self._elapsed_ms(power, home),
        }

    def _update_logo(self, sample: AnalysisSample) -> None:
        if sample.logo_score >= self.config.logo_threshold:
            if self._logo_hits == 0:
                self._logo_candidate = BootEvent(
                    "logo_first_detected",
                    sample.timestamp,
                    score=float(sample.logo_score),
                )
                self.events["logo_first_detected"] = self._logo_candidate
            self._logo_hits += 1
            self.state = BootState.LOGO_CANDIDATE
            if self._logo_hits >= max(1, int(self.config.logo_confirm_frames)):
                self.events["logo_confirmed"] = BootEvent(
                    "logo_confirmed",
                    sample.timestamp,
                    score=float(sample.logo_score),
                )
                self.state = BootState.LOGO_CONFIRMED
            return
        self._logo_hits = 0
        self._logo_candidate = None
        self.events.pop("logo_first_detected", None)
        self.state = BootState.POWERED_ON

    def _update_home(self, sample: AnalysisSample) -> None:
        if sample.home_score >= self.config.home_threshold:
            if self._home_hits == 0:
                self._home_candidate = BootEvent(
                    "home_first_detected",
                    sample.timestamp,
                    score=float(sample.home_score),
                )
                self.events["home_first_detected"] = self._home_candidate
            self._home_hits += 1
            self.state = BootState.HOME_CANDIDATE
            stable_elapsed = sample.timestamp - (self._home_candidate.perf_time if self._home_candidate else sample.timestamp)
            if self._home_hits >= max(1, int(self.config.home_confirm_frames)) and stable_elapsed >= self.config.home_stable_duration_s:
                self.events["home_confirmed"] = BootEvent(
                    "home_confirmed",
                    sample.timestamp,
                    score=float(sample.home_score),
                )
                self.state = BootState.COMPLETED
            return
        self._home_hits = 0
        self._home_candidate = None
        self.events.pop("home_first_detected", None)
        self.state = BootState.LOGO_CONFIRMED

    def _timed_out(self, current_perf: float) -> bool:
        power = self.events.get("power_on")
        if power is None:
            return False
        if current_perf - power.perf_time <= self.config.timeout_seconds:
            return False
        if "logo_confirmed" not in self.events:
            self.failure_reason = "Logo was not confirmed before timeout."
        else:
            self.failure_reason = "Home screen was not confirmed before timeout."
        self.state = BootState.TIMEOUT
        self.events["timeout"] = BootEvent("timeout", current_perf)
        return True

    @staticmethod
    def _elapsed_ms(start: BootEvent | None, end: BootEvent | None) -> int | None:
        if start is None or end is None:
            return None
        return int(round((end.perf_time - start.perf_time) * 1000))
