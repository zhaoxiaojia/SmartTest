from __future__ import annotations

from pathlib import Path

import cv2

from testing.tool.boot_video.roi import ScreenROI


class TemplateManager:
    @staticmethod
    def load_image(path: str | Path):
        template_path = Path(path)
        if not template_path.exists():
            raise FileNotFoundError(f"Template file not found: {template_path}")
        image = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        if image is None or image.size == 0:
            raise ValueError(f"Template image could not be read: {template_path}")
        return image

    @staticmethod
    def save_from_frame(frame, roi: ScreenROI, output_path: str | Path) -> Path:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        cropped = roi.crop(frame)
        if not cv2.imwrite(str(target), cropped):
            raise OSError(f"Template image could not be written: {target}")
        return target
