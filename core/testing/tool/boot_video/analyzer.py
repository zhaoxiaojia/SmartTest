from __future__ import annotations

from dataclasses import asdict, dataclass

import cv2


@dataclass(frozen=True)
class FrameAnalysisResult:
    timestamp: float
    logo_score: float
    home_score: float
    best_logo_location: dict[str, int] | None
    best_home_location: dict[str, int] | None
    best_logo_scale: float | None = None
    best_home_scale: float | None = None
    glare_ratio: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class FrameAnalyzer:
    def __init__(self, *, logo_template, home_template) -> None:
        self.logo_template = logo_template
        self.home_template = home_template

    def analyze(self, frame, *, timestamp: float) -> FrameAnalysisResult:
        glare_ratio = self.glare_ratio(frame)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        logo_score, logo_location, logo_scale = self._match(gray, self.logo_template)
        home_score, home_location, home_scale = self._match(gray, self.home_template)
        return FrameAnalysisResult(
            timestamp=float(timestamp),
            logo_score=logo_score,
            home_score=home_score,
            best_logo_location=logo_location,
            best_home_location=home_location,
            best_logo_scale=logo_scale,
            best_home_scale=home_scale,
            glare_ratio=glare_ratio,
        )

    @staticmethod
    def glare_ratio(frame, *, value_threshold: int = 245, saturation_threshold: int = 45) -> float:
        if frame.size == 0:
            return 0.0
        if len(frame.shape) == 2:
            mask = frame >= value_threshold
            return float(cv2.countNonZero(mask.astype("uint8")) / mask.size)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        value = hsv[:, :, 2]
        saturation = hsv[:, :, 1]
        mask = (value >= value_threshold) & (saturation <= saturation_threshold)
        return float(cv2.countNonZero(mask.astype("uint8")) / mask.size)

    @staticmethod
    def _match(gray_frame, template) -> tuple[float, dict[str, int] | None, float | None]:
        if template is None or template.size == 0:
            return 0.0, None, None
        frame_height, frame_width = gray_frame.shape[:2]
        best_score = 0.0
        best_location: dict[str, int] | None = None
        best_scale: float | None = None
        for scale in (1.0, 0.85, 0.75, 0.6, 0.5, 0.4, 0.35, 0.3, 0.25, 0.2, 0.15):
            candidate = template
            if scale != 1.0:
                width = max(1, int(round(template.shape[1] * scale)))
                height = max(1, int(round(template.shape[0] * scale)))
                candidate = cv2.resize(template, (width, height), interpolation=cv2.INTER_AREA)
            tpl_height, tpl_width = candidate.shape[:2]
            if tpl_width > frame_width or tpl_height > frame_height:
                continue
            result = cv2.matchTemplate(gray_frame, candidate, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if float(max_val) > best_score:
                best_score = float(max_val)
                best_location = {"x": int(max_loc[0]), "y": int(max_loc[1])}
                best_scale = scale
        return best_score, best_location, best_scale
