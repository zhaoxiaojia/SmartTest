from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ScreenROI:
    x: int
    y: int
    width: int
    height: int

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "ScreenROI":
        raw = data or {}
        return cls(
            x=int(raw.get("x", 0) or 0),
            y=int(raw.get("y", 0) or 0),
            width=int(raw.get("width", 0) or 0),
            height=int(raw.get("height", 0) or 0),
        )

    def to_dict(self) -> dict[str, int]:
        return asdict(self)

    def validate(self, frame_shape: tuple[int, ...]) -> None:
        if self.x < 0 or self.y < 0:
            raise ValueError("ROI x/y must be non-negative.")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("ROI width/height must be positive.")
        if len(frame_shape) < 2:
            raise ValueError("Frame shape is invalid.")
        frame_height, frame_width = int(frame_shape[0]), int(frame_shape[1])
        if self.x + self.width > frame_width or self.y + self.height > frame_height:
            raise ValueError("ROI exceeds frame bounds.")

    def crop(self, frame):
        self.validate(tuple(frame.shape))
        return frame[self.y : self.y + self.height, self.x : self.x + self.width]
