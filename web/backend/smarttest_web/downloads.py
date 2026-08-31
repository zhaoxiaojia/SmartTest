from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
from threading import RLock
from uuid import uuid4

from core.config.jsonTool import app_data_dir


class DownloadNotFoundError(KeyError):
    pass


@dataclass(frozen=True)
class DownloadArtifact:
    id: str
    session_id: str
    file_path: Path
    file_name: str
    media_type: str


class DownloadArtifactService:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or (app_data_dir() / "web" / "downloads"))
        if self.root.exists():
            for child in self.root.iterdir():
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
        self.root.mkdir(parents=True, exist_ok=True)
        self._artifacts: dict[str, DownloadArtifact] = {}
        self._lock = RLock()

    def task_dir(self, audit_id: str) -> Path:
        target = self.root / audit_id
        target.mkdir(parents=True, exist_ok=True)
        return target

    def register(
        self, session_id: str, file_path: str | Path, file_name: str, media_type: str,
    ) -> DownloadArtifact:
        path = Path(file_path).resolve()
        if not path.is_file() or self.root.resolve() not in path.parents:
            raise ValueError("download_expired")
        artifact = DownloadArtifact(
            uuid4().hex, session_id, path, str(file_name), str(media_type),
        )
        with self._lock:
            self._artifacts[artifact.id] = artifact
        return artifact

    def stage(
        self, session_id: str, source_path: str | Path, file_name: str, media_type: str,
    ) -> DownloadArtifact:
        source = Path(source_path)
        target = self.task_dir(uuid4().hex) / file_name
        shutil.copy2(source, target)
        return self.register(session_id, target, file_name, media_type)

    def get(self, download_id: str, session_id: str) -> DownloadArtifact:
        with self._lock:
            artifact = self._artifacts.get(download_id)
        if (
            artifact is None
            or artifact.session_id != session_id
            or not artifact.file_path.is_file()
        ):
            raise DownloadNotFoundError(download_id)
        return artifact

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            artifacts = [
                artifact for artifact in self._artifacts.values()
                if artifact.session_id == session_id
            ]
            for artifact in artifacts:
                self._artifacts.pop(artifact.id, None)
        for artifact in artifacts:
            artifact.file_path.unlink(missing_ok=True)
            parent = artifact.file_path.parent
            if parent != self.root and parent.exists() and not any(parent.iterdir()):
                parent.rmdir()

    def close(self) -> None:
        with self._lock:
            self._artifacts.clear()
        if not self.root.exists():
            return
        for child in self.root.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
