from __future__ import annotations

import json
from pathlib import Path

import pytest

from jira import JiraConversationController


def _id_factory(*values: str):
    ids = iter(values)
    return lambda: next(ids)


def _system_row(message: str = "Workspace ready", timestamp: str = "Ready") -> dict[str, object]:
    return {
        "role": "assistant",
        "author": "SmartTest AI",
        "message_template": message,
        "message_values": {},
        "timestamp_template": timestamp,
        "timestamp_values": {},
    }


@pytest.mark.parametrize(
    "contents",
    [
        None,
        "{not valid json",
        json.dumps({"conversations": "not-a-list"}),
    ],
)
def test_load_missing_or_malformed_history_starts_empty(tmp_path: Path, contents: str | None):
    history_path = tmp_path / "Jira" / "ai_conversation_history.json"
    if contents is not None:
        history_path.parent.mkdir(parents=True)
        history_path.write_text(contents, encoding="utf-8")

    controller = JiraConversationController(
        history_path,
        initial_row=_system_row(),
        id_factory=_id_factory("session-a"),
    )

    assert controller.history_rows() == []
    assert controller.current_conversation_id == "session-a"
    assert controller.conversation_rows() == [_system_row()]


def test_load_malformed_history_fields_rejects_invalid_entry(tmp_path: Path):
    history_path = tmp_path / "history.json"
    history_path.write_text(
        json.dumps(
            {
                "conversations": [
                    {
                        "id": "saved",
                        "title": None,
                        "preview": None,
                        "updated_at": "not-a-timestamp",
                        "messages": "not-a-list",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    controller = JiraConversationController(
        history_path,
        initial_row=_system_row(),
        id_factory=_id_factory("session-a"),
    )

    assert controller.history_rows() == []


def test_load_sanitizes_nested_message_rows_before_restore(tmp_path: Path):
    history_path = tmp_path / "history.json"
    history_path.write_text(
        json.dumps(
            {
                "conversations": [
                    {
                        "id": "safe",
                        "title": "Saved",
                        "preview": "Answer",
                        "updated_at": 10,
                        "messages": [
                            {
                                "role": "user",
                                "author": "coco",
                                "message": "valid raw Jira text",
                                "timestamp": "then",
                            },
                            {
                                "role": "assistant",
                                "message_template": "Matched {count}",
                                "message_values": {"count": 2, "active": True, "note": None},
                                "timestamp_template": "Ready",
                                "timestamp_values": {},
                            },
                            {"role": 7, "message": "bad role"},
                            {"role": "assistant", "message": ["bad message"]},
                            {
                                "role": "assistant",
                                "message_template": "Bad {value}",
                                "message_values": {"value": {"nested": "mapping"}},
                            },
                            {"role": "assistant", "message": "bad actions", "actions": ["open", 3]},
                            {"role": "assistant", "message": "transient", "is_progress": True},
                            {"role": "assistant", "message": "unknown", "unexpected": "field"},
                            {
                                "role": "assistant",
                                "message_template": "Missing {missing}",
                                "message_values": {},
                            },
                            {
                                "role": "assistant",
                                "message_template": "Broken {",
                                "message_values": {},
                            },
                            {
                                "role": "assistant",
                                "message_template": "Unsafe {user.name}",
                                "message_values": {"user": "coco"},
                            },
                        ],
                    },
                    {
                        "id": "invalid-entry",
                        "title": "Invalid",
                        "preview": "",
                        "updated_at": 0,
                        "messages": {"role": "user", "message": "not a list"},
                    },
                    {
                        "id": "",
                        "title": "Missing identity",
                        "preview": "",
                        "updated_at": 0,
                        "messages": [{"role": "user", "message": "orphan"}],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    controller = JiraConversationController(
        history_path,
        initial_row=_system_row(),
        id_factory=_id_factory("session-a"),
    )

    assert controller.history_rows() == [
        {
            "id": "safe",
            "title": "Saved",
            "preview": "Answer",
            "updated_at": 10,
            "message_count": 2,
        }
    ]
    assert controller.restore("safe") is True
    assert controller.conversation_rows() == [
        {
            "role": "user",
            "author": "coco",
            "message": "valid raw Jira text",
            "timestamp": "then",
        },
        {
            "role": "assistant",
            "message_template": "Matched {count}",
            "message_values": {"count": 2, "active": True, "note": None},
            "timestamp_template": "Ready",
            "timestamp_values": {},
        },
    ]


def test_append_and_replace_rows_keep_external_text_raw(tmp_path: Path):
    controller = JiraConversationController(
        tmp_path / "history.json",
        initial_row=_system_row(),
        id_factory=_id_factory("session-a"),
    )

    controller.append_user(author="coco", message="查询 RK-123 风险", timestamp="刚刚")
    controller.replace_progress(message="正在搜索 Jira...", timestamp="刚刚")
    controller.replace_progress(message="正在生成回答...", timestamp="刚刚")
    controller.remove_progress()
    controller.append_assistant(message="RK-123 原始 Jira 内容", timestamp="刚刚")
    controller.append_system(message_template="Request failed", timestamp_template="Error")

    rows = controller.conversation_rows()
    assert [row["role"] for row in rows] == ["assistant", "user", "assistant", "assistant"]
    assert rows[1]["message"] == "查询 RK-123 风险"
    assert rows[2]["message"] == "RK-123 原始 Jira 内容"
    assert rows[3]["message_template"] == "Request failed"
    assert "message" not in rows[3]


def test_persist_builds_title_preview_and_raw_history_summary(tmp_path: Path):
    history_path = tmp_path / "history.json"
    controller = JiraConversationController(
        history_path,
        initial_row=_system_row(),
        id_factory=_id_factory("session-a"),
        clock=lambda: 1234,
    )
    controller.append_user(author="coco", message="A" * 70, timestamp="now")
    controller.append_assistant(message="latest\n  answer   from Jira", timestamp="now")
    controller.replace_progress(message="transient progress", timestamp="now")

    controller.persist()

    payload = json.loads(history_path.read_text(encoding="utf-8"))
    assert payload["conversations"][0]["title"] == "A" * 60
    assert payload["conversations"][0]["preview"] == "latest answer from Jira"
    assert payload["conversations"][0]["updated_at"] == 1234
    assert len(payload["conversations"][0]["messages"]) == 2
    assert all("is_progress" not in row for row in payload["conversations"][0]["messages"])
    assert controller.history_rows() == [
        {
            "id": "session-a",
            "title": "A" * 60,
            "preview": "latest answer from Jira",
            "updated_at": 1234,
            "message_count": 2,
        }
    ]


def test_restore_replaces_current_rows_and_identity(tmp_path: Path):
    history_path = tmp_path / "history.json"
    history_path.write_text(
        json.dumps(
            {
                "conversations": [
                    {
                        "id": "saved",
                        "title": "Saved question",
                        "preview": "Saved answer",
                        "updated_at": 10,
                        "messages": [
                            {"role": "user", "author": "coco", "message": "Saved question", "timestamp": "then"},
                            {
                                "role": "assistant",
                                "author": "SmartTest AI",
                                "message": "Saved answer",
                                "timestamp": "then",
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    controller = JiraConversationController(
        history_path,
        initial_row=_system_row(),
        id_factory=_id_factory("session-a"),
    )

    assert controller.restore("missing") is False
    assert controller.restore("saved") is True
    assert controller.current_conversation_id == "saved"
    assert [row["message"] for row in controller.conversation_rows()] == ["Saved question", "Saved answer"]


def test_clear_persists_current_session_and_starts_new_raw_system_row(tmp_path: Path):
    history_path = tmp_path / "history.json"
    controller = JiraConversationController(
        history_path,
        initial_row=_system_row(),
        id_factory=_id_factory("session-a", "session-b"),
        clock=lambda: 99,
    )
    controller.append_user(author="coco", message="Keep this", timestamp="now")
    controller.replace_progress(message="Do not keep this", timestamp="now")
    cleared_row = _system_row("Session cleared", "Reset")

    controller.clear(initial_row=cleared_row)

    assert controller.current_conversation_id == "session-b"
    assert controller.conversation_rows() == [cleared_row]
    assert controller.history_rows()[0]["id"] == "session-a"
    assert controller.restore("session-a") is True
    assert controller.conversation_rows()[0]["message"] == "Keep this"
    assert all(row.get("is_progress") is not True for row in controller.conversation_rows())
