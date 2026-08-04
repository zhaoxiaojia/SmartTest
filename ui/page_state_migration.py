from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from PySide6.QtCore import QSettings

from support.logging import smart_log


_SENSITIVE = ("password", "passwd", "secret", "token", "api_key", "apikey", "credential")


@dataclass(frozen=True)
class MigrationReport:
    users: int = 0
    read: int = 0
    migrated: int = 0
    skipped: int = 0
    verified: int = 0
    deleted: bool = False
    attempted: bool = False
    status: str = "not_needed"
    failure_reason: str = ""
    rollback_clean: bool | None = None


def normalize_page_state_user(value: str) -> str:
    account = str(value or "").strip().casefold().rsplit("\\", 1)[-1]
    return account.split("@", 1)[0].strip()


def migrate_frontend_state(
    path: Path,
    settings: QSettings | None = None,
    *,
    settings_targets: Iterable[QSettings] | None = None,
) -> MigrationReport:
    """Atomically retire the legacy JSON only after every supported value reads back."""
    source = Path(path)
    if not source.exists():
        return MigrationReport()
    try:
        original = source.read_bytes()
    except OSError:
        return _failure("source_read_failed")
    try:
        payload = json.loads(original.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError):
        return _failure("parse_failed")
    snapshots: list[tuple[QSettings, dict[str, tuple[bool, Any]]]] = []
    try:
        manifest, users, read, skipped = _manifest(payload)
    except (ValueError, TypeError):
        return _failure("transform_failed")
    targets = _targets(settings, settings_targets)
    phase = "snapshot_failed"
    try:
        for target in targets:
            snapshot = {
                key: (target.contains(key), target.value(key))
                for key in manifest
            }
            snapshots.append((target, snapshot))
            phase = "write_failed"
            for key, value in manifest.items():
                target.setValue(key, value)
        for target in targets:
            phase = "sync_failed"
            target.sync()
            if target.status() != QSettings.Status.NoError:
                raise OSError("QSettings sync failed")
            phase = "readback_failed"
            for key, expected in manifest.items():
                if _plain(target.value(key)) != _plain(expected):
                    raise OSError(f"QSettings readback failed for {key}")
        phase = "delete_failed"
        source.unlink()
        verified = len(manifest) * len(targets)
        report = MigrationReport(
            users, read, len(manifest), skipped, verified, True,
            True, "success", "", True,
        )
        _log_report(report)
        return report
    except (OSError, RuntimeError, TypeError):
        try:
            _rollback(snapshots)
        except (OSError, RuntimeError, TypeError):
            return _failure(
                "rollback_failed", users=users, read=read,
                migrated=len(manifest), skipped=skipped, rollback_clean=False,
            )
        return _failure(
            phase, users=users, read=read, migrated=len(manifest),
            skipped=skipped, rollback_clean=True,
        )


def _failure(
    reason: str,
    *,
    users: int = 0,
    read: int = 0,
    migrated: int = 0,
    skipped: int = 0,
    rollback_clean: bool | None = None,
) -> MigrationReport:
    report = MigrationReport(
        users, read, migrated, skipped, 0, False,
        True, "failed", reason, rollback_clean,
    )
    _log_report(report)
    return report


def _log_report(report: MigrationReport) -> None:
    level = "info" if report.status == "success" else "error"
    message = (
        "Frontend state migration completed."
        if report.status == "success"
        else "Frontend state migration failed."
    )
    try:
        smart_log(
            message,
            level=level,
            domain="ui",
            source="page_state_migration",
            extra={
                "status": report.status,
                "failure_reason": report.failure_reason,
                "users": report.users,
                "read": report.read,
                "migrated": report.migrated,
                "skipped": report.skipped,
                "verified": report.verified,
                "deleted": report.deleted,
                "rollback_clean": report.rollback_clean,
            },
        )
    except OSError:
        pass


def _targets(
    settings: QSettings | None,
    settings_targets: Iterable[QSettings] | None,
) -> tuple[QSettings, ...]:
    if settings is not None and settings_targets is not None:
        raise ValueError("Provide settings or settings_targets, not both.")
    if settings_targets is not None:
        targets = tuple(settings_targets)
        if not targets:
            raise ValueError("At least one QSettings target is required.")
        return targets
    if settings is not None:
        return (settings,)
    return _production_targets()


def _production_targets() -> tuple[QSettings, QSettings]:
    return tuple(
        QSettings(
            QSettings.Format.NativeFormat,
            QSettings.Scope.UserScope,
            "Amlogic",
            application,
        )
        for application in ("SmartTest", "SmartTestTool")
    )  # type: ignore[return-value]


def _rollback(snapshots: list[tuple[QSettings, dict[str, tuple[bool, Any]]]]) -> None:
    for target, snapshot in snapshots:
        for key, (existed, value) in snapshot.items():
            if existed:
                target.setValue(key, value)
            else:
                target.remove(key)
        target.sync()


def _manifest(payload: Any) -> tuple[dict[str, Any], int, int, int]:
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("unsupported frontend state")
    users = payload.get("users")
    if not isinstance(users, dict):
        raise ValueError("invalid frontend state users")
    manifest: dict[str, Any] = {}
    read = skipped = 0
    actual_users: set[str] = set()
    for raw_user, scopes in users.items():
        if not isinstance(raw_user, str) or not isinstance(scopes, dict):
            raise ValueError("invalid frontend state scope")
        user = normalize_page_state_user(raw_user)
        for scope, entries in scopes.items():
            if not isinstance(scope, str) or not isinstance(entries, dict):
                raise ValueError("invalid frontend state entries")
            for key, entry in entries.items():
                read += 1
                if _sensitive(scope, key) or not _valid_entry(entry):
                    skipped += 1
                    continue
                category, values = _transform(user, scope, key, entry["value"])
                if category is None:
                    skipped += 1
                    continue
                if user and user != "global":
                    actual_users.add(user)
                for target_key, value in values.items():
                    manifest[f"{category}/{target_key}"] = value
    return manifest, len(actual_users), read, skipped


def _transform(user: str, scope: str, key: str, value: Any):
    if user == "global" and scope == "global":
        if key in {"darkMode", "useSystemAppBar", "language"}:
            return "global/application", {key: value}
        if key == "windowState" and isinstance(value, dict):
            return "global/window", value
    if not user or user == "anonymous":
        return None, {}
    categories = {"jira": "jira", "tool": "tool", "jiraAudit": "jiraAudit"}
    page = categories.get(scope)
    if page is None:
        raise ValueError(f"unknown legacy scope: {scope}")
    if key == "filterState" and page == "jira" and isinstance(value, dict):
        converted = dict(value)
        boards = ("open_work", "ready_for_test", "closed_bugs")
        times = ("last_7_days", "last_30_days", "last_90_days", "this_year")
        if "boardIndex" in converted:
            index = converted.pop("boardIndex")
            if type(index) is not int or not 0 <= index < len(boards):
                raise ValueError("unmappable board index")
            converted["selectedBoardId"] = boards[index]
        if "timeframeIndex" in converted:
            index = converted.pop("timeframeIndex")
            if type(index) is not int or not 0 <= index < len(times):
                raise ValueError("unmappable timeframe index")
            converted["selectedTimeframeId"] = times[index]
        return f"users/{user}/jira", converted
    if page == "jiraAudit" and key == "jiraAuditInput":
        return f"users/{user}/jiraAudit", {"auditInput": value}
    return f"users/{user}/{page}", {key: value}


def _valid_entry(entry: Any) -> bool:
    return isinstance(entry, dict) and "value" in entry and isinstance(entry.get("type"), str)


def _sensitive(*parts: str) -> bool:
    name = "_".join(map(str, parts)).casefold().replace("-", "_")
    return any(part in name for part in _SENSITIVE)


def _plain(value: Any) -> Any:
    if hasattr(value, "toVariant"):
        value = value.toVariant()
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _plain(child) for key, child in value.items()}
    return value
