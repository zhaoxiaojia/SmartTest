from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2

from testing.tool.boot_video.roi import ScreenROI
from testing.tool.boot_video.state_machine import BootEvent


@dataclass
class BootVideoSession:
    test_id: str
    path: Path
    artifacts: dict[str, str] = field(default_factory=dict)


class BootVideoResultWriter:
    def __init__(self, *, root: Path) -> None:
        self.root = Path(root)

    def create_session(self, *, now_text: str | None = None) -> BootVideoSession:
        stamp = now_text or datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.root / stamp
        path.mkdir(parents=True, exist_ok=False)
        return BootVideoSession(test_id=f"boot_{stamp}", path=path)

    def save_frame(self, session: BootVideoSession, name: str, frame) -> Path:
        filename = f"{name}.jpg"
        path = session.path / filename
        if not cv2.imwrite(str(path), frame):
            raise OSError(f"Frame image could not be written: {path}")
        session.artifacts[name] = filename
        return path

    def register_artifact(self, session: BootVideoSession, name: str, filename: str) -> None:
        session.artifacts[name] = filename

    def write_analysis_log(self, session: BootVideoSession, lines: list[str]) -> Path:
        path = session.path / "analysis.log"
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        session.artifacts["analysis_log"] = "analysis.log"
        return path

    def write_result(
        self,
        session: BootVideoSession,
        *,
        status: str,
        camera: dict[str, Any],
        roi: ScreenROI,
        events: dict[str, BootEvent],
        durations_ms: dict[str, int | None],
        scores: dict[str, float],
        failure_reason: str | None,
    ) -> Path:
        payload = {
            "test_id": session.test_id,
            "status": status,
            "camera": dict(camera),
            "roi": roi.to_dict(),
            "timestamps": {name: event.wall_time for name, event in events.items() if event.wall_time},
            "perf_timestamps": {name: event.perf_time for name, event in events.items()},
            "durations_ms": dict(durations_ms),
            "scores": dict(scores),
            "artifacts": dict(session.artifacts),
            "failure_reason": failure_reason,
        }
        path = session.path / "result.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=4, sort_keys=True), encoding="utf-8")
        return path
