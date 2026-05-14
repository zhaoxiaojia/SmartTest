from __future__ import annotations

import json
import re
import base64
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import cv2


ProgressCallback = Callable[[dict[str, Any]], None]
SCHEMA = "smarttest.kpi_manual_review.v1"


def prepare_kpi_review_session(
    video_path: str | Path,
    *,
    work_root: str | Path,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    path = Path(video_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"KPI source video not found: {path}")

    metadata = video_metadata(path)
    session_id = f"{_safe_stem(path)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    session_dir = Path(work_root) / session_id
    frames_dir = session_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    session: dict[str, Any] = {
        "schema": SCHEMA,
        "session_id": session_id,
        "video": str(path),
        "session_dir": str(session_dir),
        "frames_dir": str(frames_dir),
        "fps": metadata["fps"],
        "width": metadata["width"],
        "height": metadata["height"],
        "frame_count": metadata["frame_count"],
        "duration_seconds": metadata["duration_seconds"],
        "last_frame_index": 0,
        "pending_start_frame": -1,
        "events": [],
        "marks": {},
    }
    _save_session(session)
    if progress_callback is not None:
        progress_callback(
            {
                "type": "review_ready",
                "processed_frames": 1 if metadata["frame_count"] else 0,
                "frame_count": metadata["frame_count"],
                "progress_percent": 100 if metadata["frame_count"] else 0,
            }
        )
    return session


def load_kpi_review_frame(session: dict[str, Any], *, frame_index: int) -> dict[str, Any]:
    frame_count = int(session.get("frame_count", 0) or 0)
    if frame_count <= 0:
        raise ValueError("No readable frames in KPI review session")
    index = max(0, min(frame_count - 1, int(frame_index)))
    image_path = _ensure_frame_image(session, index)
    session["last_frame_index"] = index
    _save_session(session)
    return _frame_payload(session, index, image_path)


def mark_kpi_review_frame(session: dict[str, Any], *, frame_index: int, marker: str) -> dict[str, Any]:
    index = int(frame_index)
    marker = str(marker or "").strip().lower()
    if marker not in {"start", "end", "clear"}:
        raise ValueError(f"Unsupported KPI marker: {marker}")

    marks = dict(session.get("marks", {}) or {})
    pending_start = int(session.get("pending_start_frame", -1) or -1)
    completed_event: dict[str, Any] | None = None

    if marker == "clear":
        marks.pop(str(index), None)
        if pending_start == index:
            pending_start = -1
    elif marker == "start":
        if pending_start >= 0:
            marks.pop(str(pending_start), None)
        pending_start = index
        marks[str(index)] = "start"
    else:
        if pending_start < 0:
            raise ValueError("Mark a KPI start frame before marking an end frame.")
        if index < pending_start:
            raise ValueError("KPI end frame must be greater than or equal to the start frame.")
        marks[str(index)] = "end"
        completed_event = calculate_kpi_interval(
            fps=float(session.get("fps", 0.0) or 0.0),
            start_frame=pending_start,
            end_frame=index,
            sequence=len(session.get("events", []) or []) + 1,
        )
        session["events"] = list(session.get("events", []) or []) + [completed_event]
        pending_start = -1

    session["marks"] = marks
    session["pending_start_frame"] = pending_start
    _save_session(session)
    frame = load_kpi_review_frame(session, frame_index=index)
    frame["completed_event"] = completed_event or {}
    frame["events"] = list(session.get("events", []) or [])
    frame["pending_start_frame"] = pending_start
    return frame


def calculate_kpi_interval(*, fps: float, start_frame: int, end_frame: int, sequence: int = 1) -> dict[str, Any]:
    elapsed_frames = max(0, int(end_frame) - int(start_frame))
    elapsed_seconds = elapsed_frames / fps if fps > 0 else 0.0
    return {
        "sequence": int(sequence),
        "start_frame": int(start_frame),
        "end_frame": int(end_frame),
        "elapsed_frames": elapsed_frames,
        "elapsed_seconds": round(elapsed_seconds, 6),
        "elapsed_ms": round(elapsed_seconds * 1000.0, 3),
        "start_time": round(int(start_frame) / fps, 6) if fps > 0 else 0.0,
        "end_time": round(int(end_frame) / fps, 6) if fps > 0 else 0.0,
    }


def video_metadata(video_path: str | Path) -> dict[str, Any]:
    path = Path(video_path)
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError(f"Unable to open video file: {path}")
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0) or 30.0
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        return {
            "video": str(path),
            "fps": fps,
            "width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
            "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0),
            "frame_count": frame_count,
            "duration_seconds": frame_count / fps if fps > 0 else 0.0,
        }
    finally:
        capture.release()


def _ensure_frame_image(session: dict[str, Any], frame_index: int) -> Path:
    frames_dir = Path(str(session["frames_dir"]))
    frames_dir.mkdir(parents=True, exist_ok=True)
    image_path = frames_dir / f"frame_{frame_index:06d}.jpg"
    if image_path.exists():
        return image_path

    capture = cv2.VideoCapture(str(session["video"]))
    if not capture.isOpened():
        raise ValueError(f"Unable to open video file: {session['video']}")
    try:
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        if not ok:
            raise ValueError(f"Unable to read frame {frame_index} from {session['video']}")
        if not cv2.imwrite(str(image_path), frame):
            raise ValueError(f"Unable to write KPI review frame: {image_path}")
    finally:
        capture.release()
    return image_path


def _frame_payload(session: dict[str, Any], frame_index: int, image_path: Path) -> dict[str, Any]:
    fps = float(session.get("fps", 0.0) or 0.0)
    marks = dict(session.get("marks", {}) or {})
    image_bytes = image_path.read_bytes()
    return {
        "frame_index": frame_index,
        "frame_time": round(frame_index / fps, 6) if fps > 0 else 0.0,
        "image": str(image_path),
        "image_url": image_path.resolve().as_uri(),
        "image_data_url": "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode("ascii"),
        "mark": marks.get(str(frame_index), ""),
        "pending_start_frame": int(session.get("pending_start_frame", -1) or -1),
        "events": list(session.get("events", []) or []),
    }


def _save_session(session: dict[str, Any]) -> None:
    session_dir = Path(str(session["session_dir"]))
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "session.json").write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_stem(path: Path) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.stem).strip("._")
    return cleaned or "kpi_video"
