from __future__ import annotations

from pathlib import Path

import cv2


class VideoRecorder:
    def __init__(self) -> None:
        self._writer = None

    def start(self, output_path: str | Path, fps: int | float, frame_size: tuple[int, int]) -> None:
        self.stop()
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(path), fourcc, float(fps), frame_size)
        if not writer.isOpened():
            writer.release()
            raise RuntimeError(f"Video encoder could not be initialized: {path}")
        self._writer = writer

    def write(self, frame, timestamp: float) -> None:
        if self._writer is None:
            raise RuntimeError("Video recorder is not running.")
        self._writer.write(frame)

    def stop(self) -> None:
        writer = self._writer
        self._writer = None
        if writer is not None:
            writer.release()

    def is_recording(self) -> bool:
        return self._writer is not None
