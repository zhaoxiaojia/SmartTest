from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class KpiInterval:
    sequence: int
    start_frame: int
    end_frame: int
    elapsed_frames: int
    elapsed_seconds: float
    elapsed_ms: float
    start_time: float
    end_time: float


ProgressPayload = dict[str, Any]
