from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock, Thread
from typing import Any
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, Property, QStandardPaths, Signal, Slot
from PySide6.QtGui import QGuiApplication

_BING_ARCHIVE_URL = "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1&mkt=zh-CN"


class HomeBridge(QObject):
    wallpaperChanged = Signal()
    _wallpaperReady = Signal(object)

    def __init__(self):
        super().__init__(QGuiApplication.instance())
        self._wallpaper_url = ""
        self._wallpaper_title = ""
        self._wallpaper_copyright = ""
        self._refreshing_wallpaper = False
        self._lock = Lock()
        self._wallpaperReady.connect(self._on_wallpaper_ready)
        self._load_wallpaper_cache()

    def _cache_path(self) -> Path:
        base = Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))
        return base / "home_wallpaper.json"

    def _load_wallpaper_cache(self) -> None:
        path = self._cache_path()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        self._wallpaper_url = str(data.get("url") or "")
        self._wallpaper_title = str(data.get("title") or "")
        self._wallpaper_copyright = str(data.get("copyright") or "")

    def _save_wallpaper_cache(self, data: dict[str, str]) -> None:
        path = self._cache_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            logging.getLogger(__name__).warning("Failed to cache home wallpaper: %s", exc)

    def _fetch_bing_wallpaper(self) -> dict[str, str]:
        request = Request(_BING_ARCHIVE_URL, headers={"User-Agent": "SmartTest"})
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        image = payload["images"][0]
        image_url = str(image.get("url") or "")
        if image_url.startswith("/"):
            image_url = f"https://www.bing.com{image_url}"
        return {
            "url": image_url,
            "title": str(image.get("title") or ""),
            "copyright": str(image.get("copyright") or ""),
        }

    @Slot()
    def refreshWallpaper(self) -> None:
        with self._lock:
            if self._refreshing_wallpaper:
                return
            self._refreshing_wallpaper = True
        Thread(target=self._refresh_wallpaper_worker, daemon=True).start()

    def _refresh_wallpaper_worker(self) -> None:
        try:
            self._wallpaperReady.emit(self._fetch_bing_wallpaper())
        except Exception as exc:
            logging.getLogger(__name__).warning("Failed to refresh home wallpaper: %s", exc)
            with self._lock:
                self._refreshing_wallpaper = False

    def _on_wallpaper_ready(self, data: Any) -> None:
        with self._lock:
            self._refreshing_wallpaper = False
        if not isinstance(data, dict):
            return
        url = str(data.get("url") or "")
        if not url:
            return
        self._wallpaper_url = url
        self._wallpaper_title = str(data.get("title") or "")
        self._wallpaper_copyright = str(data.get("copyright") or "")
        self._save_wallpaper_cache(
            {
                "url": self._wallpaper_url,
                "title": self._wallpaper_title,
                "copyright": self._wallpaper_copyright,
            }
        )
        self.wallpaperChanged.emit()

    def get_wallpaper_url(self) -> str:
        return self._wallpaper_url

    def get_wallpaper_title(self) -> str:
        return self._wallpaper_title

    def get_wallpaper_copyright(self) -> str:
        return self._wallpaper_copyright

    wallpaperUrl = Property(str, get_wallpaper_url, notify=wallpaperChanged)
    wallpaperTitle = Property(str, get_wallpaper_title, notify=wallpaperChanged)
    wallpaperCopyright = Property(str, get_wallpaper_copyright, notify=wallpaperChanged)
