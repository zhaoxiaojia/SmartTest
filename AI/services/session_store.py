from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


class AIChatSessionStore:
    def __init__(self, store_path: Path):
        self._store_path = store_path
        self._data = self._load()
        self._data.setdefault("sessions", [])
        self._data.setdefault("projects", _default_projects())

    def sessions(self) -> list[dict[str, Any]]:
        return [
            {
                "id": session["id"],
                "title": session["title"],
                "preview": _session_preview(session),
                "updated_at": session.get("updated_at", session.get("created_at", 0)),
                "message_count": len(session.get("messages", [])),
            }
            for session in sorted(
                self._data["sessions"],
                key=lambda item: int(item.get("updated_at", item.get("created_at", 0))),
                reverse=True,
            )
        ]

    def projects(self) -> list[dict[str, Any]]:
        return [
            {
                "id": project["id"],
                "title": project["title"],
                "session_ids": list(project.get("session_ids", [])),
                "file_ids": list(project.get("file_ids", [])),
                "context": str(project.get("context", "") or ""),
                "created_at": project.get("created_at", 0),
                "updated_at": project.get("updated_at", project.get("created_at", 0)),
            }
            for project in sorted(
                self._data["projects"],
                key=lambda item: int(item.get("updated_at", item.get("created_at", 0))),
                reverse=False,
            )
        ]

    def create_project(self, title: str | None = None) -> str:
        now = int(time.time())
        project_id = uuid.uuid4().hex
        self._data["projects"].append(
            {
                "id": project_id,
                "title": (title or "New Project").strip() or "New Project",
                "session_ids": [],
                "file_ids": [],
                "context": "",
                "created_at": now,
                "updated_at": now,
            }
        )
        self._save()
        return project_id

    def rename_project(self, project_id: str, title: str) -> None:
        project = self._require_project(project_id)
        clean_title = title.strip()
        if not clean_title:
            return
        project["title"] = clean_title[:80]
        project["updated_at"] = int(time.time())
        self._save()

    def delete_project(self, project_id: str) -> None:
        self._data["projects"] = [
            project
            for project in self._data["projects"]
            if project.get("id") in {"default-new-project"} or project.get("id") != project_id
        ]
        self._save()

    def update_project_session(self, project_id: str, session_id: str, selected: bool) -> None:
        project = self._require_project(project_id)
        session_ids = list(project.get("session_ids", []))
        if selected and session_id not in session_ids:
            session_ids.append(session_id)
        if not selected:
            session_ids = [item for item in session_ids if item != session_id]
        project["session_ids"] = session_ids
        project["updated_at"] = int(time.time())
        self._save()

    def session_exists(self, session_id: str) -> bool:
        return self._find_session(session_id) is not None

    def first_session_id(self) -> str:
        sessions = self.sessions()
        if not sessions:
            return ""
        return str(sessions[0]["id"])

    def create_session(self, title: str | None = None) -> str:
        now = int(time.time())
        session_id = uuid.uuid4().hex
        self._data["sessions"].append(
            {
                "id": session_id,
                "title": (title or "New chat").strip() or "New chat",
                "created_at": now,
                "updated_at": now,
                "messages": [],
                "attachments": [],
            }
        )
        self._save()
        return session_id

    def rename_session(self, session_id: str, title: str) -> None:
        session = self._require_session(session_id)
        clean_title = title.strip()
        if not clean_title:
            return
        session["title"] = clean_title[:80]
        session["updated_at"] = int(time.time())
        self._save()

    def delete_session(self, session_id: str) -> str:
        self._data["sessions"] = [session for session in self._data["sessions"] if session["id"] != session_id]
        for project in self._data["projects"]:
            project["session_ids"] = [item for item in project.get("session_ids", []) if item != session_id]
        self._save()
        return self.first_session_id()

    def messages(self, session_id: str) -> list[dict[str, Any]]:
        if not session_id:
            return []
        session = self._require_session(session_id)
        return list(session.get("messages", []))

    def message(self, session_id: str, message_id: str) -> dict[str, Any] | None:
        session = self._require_session(session_id)
        for message in session.get("messages", []):
            if message.get("id") == message_id:
                return dict(message)
        return None

    def attachments(self, session_id: str) -> list[dict[str, Any]]:
        if not session_id:
            return []
        session = self._require_session(session_id)
        return list(session.get("attachments", []))

    def add_message(
        self,
        session_id: str,
        *,
        role: str,
        content: str,
        status: str = "done",
        attachment_ids: list[str] | None = None,
    ) -> str:
        session = self._require_session(session_id)
        now = int(time.time())
        message_id = uuid.uuid4().hex
        session.setdefault("messages", []).append(
            {
                "id": message_id,
                "role": role,
                "content": content,
                "status": status,
                "created_at": now,
                "attachment_ids": list(attachment_ids or []),
            }
        )
        if role == "user" and session.get("title") == "New chat":
            session["title"] = _title_from_message(content)
        session["updated_at"] = now
        self._save()
        return message_id

    def update_message(self, session_id: str, message_id: str, *, content: str, status: str) -> None:
        session = self._require_session(session_id)
        for message in session.get("messages", []):
            if message.get("id") == message_id:
                message["content"] = content
                message["status"] = status
                session["updated_at"] = int(time.time())
                self._save()
                return

    def delete_messages_from(self, session_id: str, message_id: str) -> None:
        session = self._require_session(session_id)
        messages = list(session.get("messages", []))
        for index, message in enumerate(messages):
            if message.get("id") == message_id:
                session["messages"] = messages[:index]
                session["updated_at"] = int(time.time())
                self._save()
                return

    def add_attachment(self, session_id: str, *, name: str, path: str, content: str) -> str:
        session = self._require_session(session_id)
        now = int(time.time())
        attachment_id = uuid.uuid4().hex
        session.setdefault("attachments", []).append(
            {
                "id": attachment_id,
                "name": name,
                "path": path,
                "content": content,
                "size": len(content.encode("utf-8", errors="ignore")),
                "created_at": now,
            }
        )
        session["updated_at"] = now
        self._save()
        return attachment_id

    def remove_attachment(self, session_id: str, attachment_id: str) -> None:
        session = self._require_session(session_id)
        session["attachments"] = [
            attachment for attachment in session.get("attachments", []) if attachment.get("id") != attachment_id
        ]
        session["updated_at"] = int(time.time())
        self._save()

    def _load(self) -> dict[str, Any]:
        if not self._store_path.exists():
            return {"sessions": [], "projects": _default_projects()}
        with self._store_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        sessions = payload.get("sessions") if isinstance(payload, dict) else None
        projects = payload.get("projects") if isinstance(payload, dict) else None
        return {
            "sessions": sessions if isinstance(sessions, list) else [],
            "projects": projects if isinstance(projects, list) else _default_projects(),
        }

    def _save(self) -> None:
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        with self._store_path.open("w", encoding="utf-8") as handle:
            json.dump(self._data, handle, ensure_ascii=False, indent=2)

    def _find_session(self, session_id: str) -> dict[str, Any] | None:
        for session in self._data["sessions"]:
            if session.get("id") == session_id:
                return session
        return None

    def _require_session(self, session_id: str) -> dict[str, Any]:
        session = self._find_session(session_id)
        if session is None:
            raise KeyError(f"AI chat session not found: {session_id}")
        return session

    def _require_project(self, project_id: str) -> dict[str, Any]:
        for project in self._data["projects"]:
            if project.get("id") == project_id:
                return project
        raise KeyError(f"AI project not found: {project_id}")


def _title_from_message(content: str) -> str:
    first_line = " ".join(content.strip().splitlines()).strip()
    if not first_line:
        return "New chat"
    return first_line[:40]


def _session_preview(session: dict[str, Any]) -> str:
    messages = list(session.get("messages", []))
    for message in reversed(messages):
        content = " ".join(str(message.get("content", "") or "").split())
        if content:
            return content[:80]
    return ""


def _default_projects() -> list[dict[str, Any]]:
    now = int(time.time())
    return [
        {
            "id": "default-new-project",
            "title": "New Project",
            "session_ids": [],
            "file_ids": [],
            "context": "",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "default-test-notes",
            "title": "Test Notes",
            "session_ids": [],
            "file_ids": [],
            "context": "",
            "created_at": now,
            "updated_at": now,
        },
    ]
