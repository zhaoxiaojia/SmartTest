from __future__ import annotations

import logging
from html import escape
from pathlib import Path
from threading import Lock, Thread
from typing import Any
from urllib.parse import unquote, urlparse

from PySide6.QtCore import QObject, Property, QT_TRANSLATE_NOOP, QStandardPaths, Signal, Slot
from PySide6.QtGui import QGuiApplication

from AI.core.models import AIChatMessage
from AI.services import AIChatSessionStore, AIChatService, create_default_ai_chat_service

_MAX_ATTACHMENT_BYTES = 1024 * 1024
_SUPPORTED_SUFFIXES = {
    ".txt",
    ".log",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".py",
    ".csv",
    ".ini",
    ".cfg",
}

_AI_BRIDGE_TRANSLATION_MARKERS = (
    QT_TRANSLATE_NOOP("AIBridge", "Ready"),
    QT_TRANSLATE_NOOP("AIBridge", "Thinking..."),
    QT_TRANSLATE_NOOP("AIBridge", "AI request failed: {message}"),
    QT_TRANSLATE_NOOP("AIBridge", "New chat"),
    QT_TRANSLATE_NOOP("AIBridge", "Attachment is only available for text-like files."),
    QT_TRANSLATE_NOOP("AIBridge", "Attachment is too large. Keep files under 1 MB for this preview."),
    QT_TRANSLATE_NOOP("AIBridge", "Attachment could not be read: {message}"),
    QT_TRANSLATE_NOOP("AIBridge", "No response content was returned."),
)

_MCP_SOURCE_ROWS = [
    {"id": "jira", "name": "Jira", "description": "Jira MCP"},
    {"id": "confluence", "name": "Confluence", "description": "Confluence MCP"},
    {"id": "soc_spec_search", "name": "SoC Spec Search", "description": "SoC specification search MCP"},
    {"id": "opengrok", "name": "OpenGrok", "description": "OpenGrok source search MCP"},
    {"id": "gerrit_scgit", "name": "Gerrit SCGit", "description": "Gerrit code review MCP"},
    {"id": "jenkins", "name": "Jenkins", "description": "Jenkins CI MCP"},
]


class AIBridge(QObject):
    stateChanged = Signal()
    loadingChanged = Signal()
    _replyReady = Signal(object)
    _replyFailed = Signal(object)

    def __init__(
        self,
        *,
        store: AIChatSessionStore | None = None,
        chat_service: AIChatService | None = None,
    ):
        super().__init__(QGuiApplication.instance())
        self._store = store or AIChatSessionStore(self._store_path())
        self._chat_service = chat_service or create_default_ai_chat_service()
        self._current_session_id = self._store.first_session_id()
        self._loading = False
        self._status_state: dict[str, Any] = self._translated_state("Ready")
        self._enabled_mcp_sources: set[str] = set()
        self._worker_seq = 0
        self._state_lock = Lock()
        self._replyReady.connect(self._on_reply_ready)
        self._replyFailed.connect(self._on_reply_failed)

    def _t(self, text: str) -> str:
        return self.tr(text)

    def _translated_state(self, template: str, **values: Any) -> dict[str, Any]:
        return {"kind": "translated", "template": template, "values": dict(values)}

    def _render_state_text(self, state: dict[str, Any]) -> str:
        if state.get("kind") == "translated":
            return self._t(str(state.get("template", ""))).format(**dict(state.get("values") or {}))
        return str(state.get("text", "") or "")

    def _store_path(self) -> Path:
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        return Path(base) / "SmartTest" / "AI" / "chat_sessions.json"

    def _share_dir(self) -> Path:
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        return Path(base) / "SmartTest" / "AI" / "shared"

    def _set_loading(self, value: bool) -> None:
        if self._loading == value:
            return
        self._loading = value
        self.loadingChanged.emit()

    @Slot(result="QVariantList")
    def sessions(self):
        return self._store.sessions()

    @Slot(result="QVariantList")
    def projects(self):
        return self._store.projects()

    @Slot(result="QVariantList")
    def messages(self):
        return self._store.messages(self._current_session_id)

    @Slot(result="QVariantList")
    def attachments(self):
        return self._store.attachments(self._current_session_id)

    @Slot(result="QVariantList")
    def mcpSources(self):
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "enabled": row["id"] in self._enabled_mcp_sources,
            }
            for row in _MCP_SOURCE_ROWS
        ]

    @Slot(str, bool)
    def setMcpSourceEnabled(self, source_id: str, enabled: bool) -> None:
        clean_source_id = str(source_id or "").strip()
        valid_ids = {row["id"] for row in _MCP_SOURCE_ROWS}
        if clean_source_id not in valid_ids:
            return
        if enabled:
            self._enabled_mcp_sources.add(clean_source_id)
        else:
            self._enabled_mcp_sources.discard(clean_source_id)
        self.stateChanged.emit()

    @Slot(result=str)
    def currentSessionId(self) -> str:
        return self._current_session_id

    @Slot()
    def newSession(self) -> None:
        self._current_session_id = self._store.create_session(self._t("New chat"))
        self.stateChanged.emit()

    @Slot(str, result=str)
    def createProject(self, title: str) -> str:
        project_id = self._store.create_project(title or self._t("New Project"))
        self.stateChanged.emit()
        return project_id

    @Slot(str, str)
    def renameProject(self, project_id: str, title: str) -> None:
        self._store.rename_project(project_id, title)
        self.stateChanged.emit()

    @Slot(str)
    def deleteProject(self, project_id: str) -> None:
        self._store.delete_project(project_id)
        self.stateChanged.emit()

    @Slot(str, str, bool)
    def setProjectSessionSelected(self, project_id: str, session_id: str, selected: bool) -> None:
        self._store.update_project_session(project_id, session_id, selected)
        self.stateChanged.emit()

    @Slot(str, str)
    def moveSessionToProject(self, session_id: str, project_id: str) -> None:
        if not self._store.session_exists(session_id):
            return
        self._store.update_project_session(project_id, session_id, True)
        self.stateChanged.emit()

    @Slot(str)
    def selectSession(self, session_id: str) -> None:
        if not self._store.session_exists(session_id):
            return
        self._current_session_id = session_id
        self.stateChanged.emit()

    @Slot(str, str)
    def renameSession(self, session_id: str, title: str) -> None:
        self._store.rename_session(session_id, title)
        self.stateChanged.emit()

    @Slot(str)
    def deleteSession(self, session_id: str) -> None:
        self._current_session_id = self._store.delete_session(session_id)
        self.stateChanged.emit()

    @Slot(str, str, result=str)
    def createShareLink(self, session_id: str, title: str) -> str:
        if not self._store.session_exists(session_id):
            return ""
        clean_title = title.strip() or self._t("New chat")
        messages = self._store.messages(session_id)
        share_path = self._share_dir() / f"{session_id}.html"
        share_path.parent.mkdir(parents=True, exist_ok=True)
        share_path.write_text(
            _share_html(title=clean_title, messages=messages),
            encoding="utf-8",
        )
        link = share_path.resolve().as_uri()
        QGuiApplication.clipboard().setText(link)
        return link

    @Slot(str, result=str)
    def createCurrentShareLink(self, title: str) -> str:
        return self.createShareLink(self._current_session_id, title)

    @Slot(str)
    def copyText(self, text: str) -> None:
        if text:
            QGuiApplication.clipboard().setText(text)

    @Slot(str)
    def deleteShareLink(self, session_id: str) -> None:
        share_path = self._share_dir() / f"{session_id}.html"
        if share_path.exists():
            share_path.unlink()

    @Slot(str)
    def addAttachmentFromUrl(self, file_url: str) -> None:
        path = _path_from_url(file_url)
        suffix = path.suffix.lower()
        if suffix not in _SUPPORTED_SUFFIXES:
            self._status_state = self._translated_state("Attachment is only available for text-like files.")
            self.stateChanged.emit()
            return
        try:
            size = path.stat().st_size
            if size > _MAX_ATTACHMENT_BYTES:
                self._status_state = self._translated_state(
                    "Attachment is too large. Keep files under 1 MB for this preview."
                )
                self.stateChanged.emit()
                return
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            self._status_state = self._translated_state("Attachment could not be read: {message}", message=str(exc))
            self.stateChanged.emit()
            return
        self._store.add_attachment(
            self._current_session_id,
            name=path.name,
            path=str(path),
            content=content,
        )
        self._status_state = self._translated_state("Ready")
        self.stateChanged.emit()

    @Slot(str)
    def removeAttachment(self, attachment_id: str) -> None:
        self._store.remove_attachment(self._current_session_id, attachment_id)
        self.stateChanged.emit()

    @Slot(str)
    def copyMessage(self, message_id: str) -> None:
        message = self._store.message(self._current_session_id, message_id)
        if not message:
            return
        content = str(message.get("content", "") or "")
        if content:
            QGuiApplication.clipboard().setText(content)

    @Slot(str)
    def retryMessage(self, message_id: str) -> None:
        if self._loading:
            return
        messages = self._store.messages(self._current_session_id)
        target_index = -1
        for index, message in enumerate(messages):
            if message.get("id") == message_id:
                target_index = index
                break
        if target_index <= 0:
            return
        user_message = None
        for index in range(target_index - 1, -1, -1):
            candidate = messages[index]
            if candidate.get("role") == "user":
                user_message = candidate
                break
        if user_message is None:
            return
        self._store.delete_messages_from(self._current_session_id, str(user_message.get("id", "")))
        self.sendMessage(str(user_message.get("content", "") or ""))

    @Slot(str)
    def sendMessage(self, prompt: str) -> None:
        clean_prompt = prompt.strip()
        if not clean_prompt or self._loading:
            return
        if not self._current_session_id or not self._store.session_exists(self._current_session_id):
            self._current_session_id = self._store.create_session(self._t("New chat"))
        session_id = self._current_session_id
        attachments = self._store.attachments(session_id)
        attachment_ids = [str(attachment.get("id", "")) for attachment in attachments]
        self._store.add_message(
            session_id,
            role="user",
            content=clean_prompt,
            attachment_ids=[attachment_id for attachment_id in attachment_ids if attachment_id],
        )
        assistant_message_id = self._store.add_message(session_id, role="assistant", content="", status="loading")
        self._worker_seq += 1
        worker_id = self._worker_seq
        self._status_state = self._translated_state("Thinking...")
        self._set_loading(True)
        self.stateChanged.emit()
        Thread(
            target=self._run_chat,
            kwargs={
                "worker_id": worker_id,
                "session_id": session_id,
                "assistant_message_id": assistant_message_id,
                "attachments": attachments,
            },
            daemon=True,
        ).start()

    def _run_chat(
        self,
        *,
        worker_id: int,
        session_id: str,
        assistant_message_id: str,
        attachments: list[dict[str, Any]],
    ) -> None:
        try:
            messages = self._messages_for_request(session_id, attachments)
            response = self._chat_service.ask(messages, temperature=0.2)
            text = (response.text or "").strip()
            if not text:
                text = self._t("No response content was returned.")
            self._replyReady.emit(
                {
                    "worker_id": worker_id,
                    "session_id": session_id,
                    "message_id": assistant_message_id,
                    "content": text,
                }
            )
        except Exception as exc:  # noqa: BLE001
            logging.exception("AI chat request failed")
            self._replyFailed.emit(
                {
                    "worker_id": worker_id,
                    "session_id": session_id,
                    "message_id": assistant_message_id,
                    "message": str(exc),
                }
            )

    def _messages_for_request(
        self,
        session_id: str,
        attachments: list[dict[str, Any]],
    ) -> list[AIChatMessage]:
        rows = self._store.messages(session_id)[-16:]
        request_messages: list[AIChatMessage] = []
        for row in rows:
            role = str(row.get("role", "user"))
            if role not in {"user", "assistant"}:
                continue
            if row.get("status") == "loading":
                continue
            content = str(row.get("content", "") or "")
            if role == "user" and row is rows[-2]:
                content = _with_attachment_context(content, attachments)
            request_messages.append(AIChatMessage(role=role, content=content))
        return request_messages

    @Slot(object)
    def _on_reply_ready(self, payload: dict[str, Any]) -> None:
        if int(payload.get("worker_id", 0)) != self._worker_seq:
            return
        self._store.update_message(
            str(payload.get("session_id", "")),
            str(payload.get("message_id", "")),
            content=str(payload.get("content", "")),
            status="done",
        )
        self._status_state = self._translated_state("Ready")
        self._set_loading(False)
        self.stateChanged.emit()

    @Slot(object)
    def _on_reply_failed(self, payload: dict[str, Any]) -> None:
        if int(payload.get("worker_id", 0)) != self._worker_seq:
            return
        message = str(payload.get("message", "") or "Unknown error")
        self._store.update_message(
            str(payload.get("session_id", "")),
            str(payload.get("message_id", "")),
            content=self._t("AI request failed: {message}").format(message=message),
            status="error",
        )
        self._status_state = self._translated_state("AI request failed: {message}", message=message)
        self._set_loading(False)
        self.stateChanged.emit()

    def _get_loading(self) -> bool:
        return self._loading

    def _get_status_text(self) -> str:
        return self._render_state_text(self._status_state)

    loading = Property(bool, _get_loading, notify=loadingChanged)
    statusText = Property(str, _get_status_text, notify=stateChanged)


def _path_from_url(file_url: str) -> Path:
    parsed = urlparse(str(file_url))
    if parsed.scheme == "file":
        path_text = unquote(parsed.path)
        if path_text.startswith("/") and len(path_text) > 3 and path_text[2] == ":":
            path_text = path_text[1:]
        return Path(path_text)
    return Path(str(file_url))


def _with_attachment_context(prompt: str, attachments: list[dict[str, Any]]) -> str:
    if not attachments:
        return prompt
    parts = [prompt, "", "Attached files:"]
    for attachment in attachments:
        name = str(attachment.get("name", "attachment"))
        content = str(attachment.get("content", ""))
        parts.append(f"\n--- {name} ---\n{content[:12000]}")
    return "\n".join(parts)


def _share_html(*, title: str, messages: list[dict[str, Any]]) -> str:
    rows = []
    for message in messages:
        role = str(message.get("role", "assistant"))
        content = str(message.get("content", "") or "")
        if not content:
            continue
        role_label = "You" if role == "user" else "SmartTest AI"
        rows.append(
            "\n".join(
                [
                    f'<section class="message {escape(role)}">',
                    f"<div class=\"role\">{escape(role_label)}</div>",
                    f"<pre>{escape(content)}</pre>",
                    "</section>",
                ]
            )
        )
    body = "\n".join(rows) or '<p class="empty">No messages</p>'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    body {{
      margin: 0;
      background: #ffffff;
      color: #111111;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
      font-size: 16px;
      line-height: 1.55;
    }}
    main {{
      max-width: 860px;
      margin: 0 auto;
      padding: 42px 28px 64px;
    }}
    h1 {{
      font-size: 24px;
      line-height: 1.35;
      margin: 0 0 28px;
    }}
    .message {{
      margin: 0 0 28px;
    }}
    .message.user {{
      display: flex;
      flex-direction: column;
      align-items: flex-end;
    }}
    .role {{
      color: #6b7280;
      font-size: 13px;
      margin-bottom: 8px;
    }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-wrap: break-word;
      font: inherit;
    }}
    .user pre {{
      max-width: 560px;
      background: #f0f0f0;
      border-radius: 18px;
      padding: 12px 16px;
    }}
    .assistant pre {{
      max-width: 760px;
    }}
    .empty {{
      color: #6b7280;
    }}
  </style>
</head>
<body>
  <main>
    <h1>{escape(title)}</h1>
    {body}
  </main>
</body>
</html>
"""
