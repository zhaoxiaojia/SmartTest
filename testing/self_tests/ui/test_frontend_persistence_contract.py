from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QSettings

from ui import page_state_migration
from ui.page_state_migration import migrate_frontend_state


ROOT = Path(__file__).resolve().parents[3]
QML = ROOT / "ui/example/imports/example/qml"


class MemorySettings:
    def __init__(self, values=None, *, fail_sync=False, corrupt_readback=False, fail_rollback=False):
        self.values = dict(values or {})
        self.fail_sync = fail_sync
        self.corrupt_readback = corrupt_readback
        self.fail_rollback = fail_rollback
        self.synced = False
        self.sync_calls = 0

    def contains(self, key):
        return key in self.values

    def value(self, key):
        value = self.values.get(key)
        if self.corrupt_readback and self.synced and key.endswith("/darkMode"):
            self.corrupt_readback = False
            return -1
        return value

    def setValue(self, key, value):
        self.values[key] = value

    def remove(self, key):
        self.values.pop(key, None)

    def sync(self):
        self.sync_calls += 1
        if self.fail_rollback and self.sync_calls >= 2:
            raise OSError("rollback sync failed")
        self.synced = True

    def status(self):
        if self.fail_sync:
            self.fail_sync = False
            return QSettings.Status.AccessError
        return QSettings.Status.NoError


def _global_fixture(path):
    path.write_bytes(b'{"version":1,"users":{"global":{"global":{"darkMode":{"type":"int","value":2},"language":{"type":"string","value":"zh_CN"}}}}}')


def test_explicit_qml_schemas_have_stable_business_keys():
    jira = (QML / "state/JiraPageState.qml").read_text(encoding="utf-8")
    assert 'category: "users/" + account + "/jira"' in jira
    assert "selectedBoardId" in jira and "selectedTimeframeId" in jira
    assert "currentIndex" not in jira and "objectName" not in jira


def test_user_settings_are_lifecycle_guarded_and_logout_clears_ui():
    jira = (QML / "page/T_Jira.qml").read_text(encoding="utf-8")
    assert "active: AuthBridge.authenticated" in jira
    assert 'pageStateAccount || ""' in jira
    assert "onActiveChanged" in jira and "clearFilterState()" in jira
    assert "users/anonymous" not in jira and "FrontendStateBridge" not in jira


def test_legacy_migration_covers_users_and_converts_indices_to_ids(tmp_path):
    source = tmp_path / "frontend_state.json"
    source.write_text(json.dumps({"version": 1, "users": {
        "global": {"global": {
            "darkMode": {"type": "int", "value": 2},
            "windowState": {"type": "object", "value": {"tourShown": True}},
        }},
        "Alice@example.com": {"jira": {"filterState": {"type": "object", "value": {
            "boardIndex": 1, "timeframeIndex": 2, "projects": ["tv"],
        }}}},
        "BOB": {"jiraAudit": {"jiraAuditInput": {"type": "string", "value": "project = TV"}}},
    }}), encoding="utf-8")
    settings = QSettings(str(tmp_path / "state.ini"), QSettings.Format.IniFormat)
    report = migrate_frontend_state(source, settings)
    assert report.deleted and report.users == 2 and not source.exists()
    assert settings.value("users/alice/jira/selectedBoardId") == "ready_for_test"
    assert settings.value("users/alice/jira/selectedTimeframeId") == "last_90_days"
    assert settings.value("users/bob/jiraAudit/auditInput") == "project = TV"


def test_unknown_scope_preserves_legacy_bytes(tmp_path):
    source = tmp_path / "frontend_state.json"
    original = b'{"version":1,"users":{"alice":{"unknown":{"x":{"type":"string","value":"x"}}}}}'
    source.write_bytes(original)
    report = migrate_frontend_state(source, QSettings(str(tmp_path / "state.ini"), QSettings.Format.IniFormat))
    assert report.attempted and report.status == "failed"
    assert report.failure_reason == "transform_failed"
    assert not report.deleted and source.read_bytes() == original


def test_unmappable_index_preserves_legacy_bytes(tmp_path):
    source = tmp_path / "frontend_state.json"
    original = json.dumps({"version": 1, "users": {"alice": {"jira": {"filterState": {
        "type": "object", "value": {"boardIndex": 99},
    }}}}}).encode()
    source.write_bytes(original)
    report = migrate_frontend_state(source, QSettings(str(tmp_path / "state.ini"), QSettings.Format.IniFormat))
    assert not report.deleted and source.read_bytes() == original


def test_production_migration_covers_both_application_namespaces_before_delete(tmp_path, monkeypatch):
    source = tmp_path / "frontend_state.json"
    _global_fixture(source)
    desktop = QSettings(str(tmp_path / "SmartTest.ini"), QSettings.Format.IniFormat)
    tool = QSettings(str(tmp_path / "SmartTestTool.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(page_state_migration, "_production_targets", lambda: (desktop, tool))
    report = migrate_frontend_state(source)
    assert report.deleted and report.verified == 4 and not source.exists()
    for target in (desktop, tool):
        assert target.value("global/application/darkMode") == 2
        assert target.value("global/application/language") == "zh_CN"


def test_sync_failure_rolls_back_all_targets_and_preserves_source(tmp_path):
    source = tmp_path / "frontend_state.json"
    _global_fixture(source)
    original = source.read_bytes()
    existing = {"global/application/darkMode": 1}
    desktop = MemorySettings(existing)
    tool = MemorySettings(existing, fail_sync=True)
    report = migrate_frontend_state(source, settings_targets=(desktop, tool))
    assert not report.deleted and source.read_bytes() == original
    assert desktop.values == existing and tool.values == existing


def test_readback_failure_restores_preexisting_values_and_removes_new_keys(tmp_path):
    source = tmp_path / "frontend_state.json"
    _global_fixture(source)
    original = source.read_bytes()
    existing = {"global/application/darkMode": 0}
    target = MemorySettings(existing, corrupt_readback=True)
    report = migrate_frontend_state(source, settings_targets=(target,))
    assert not report.deleted and source.read_bytes() == original
    assert target.values == existing


def test_no_source_is_distinct_from_attempted_failure(tmp_path):
    report = migrate_frontend_state(tmp_path / "missing.json", settings_targets=(MemorySettings(),))
    assert not report.attempted
    assert report.status == "not_needed" and report.failure_reason == ""


def test_failure_log_contains_only_fixed_status_and_counts(tmp_path, monkeypatch):
    source = tmp_path / "frontend_state.json"
    secret_value = "do-not-log-this-value"
    source.write_text(secret_value, encoding="utf-8")
    records = []
    monkeypatch.setattr(page_state_migration, "smart_log", lambda message, **kwargs: records.append((message, kwargs)))
    report = migrate_frontend_state(source, settings_targets=(MemorySettings(),))
    rendered = repr(records)
    assert report.failure_reason == "parse_failed"
    assert records and secret_value not in rendered
    assert "parse_failed" in rendered and "failed" in rendered


def test_rollback_failure_has_distinct_status_and_preserves_source(tmp_path):
    source = tmp_path / "frontend_state.json"
    _global_fixture(source)
    original = source.read_bytes()
    target = MemorySettings(corrupt_readback=True, fail_rollback=True)
    report = migrate_frontend_state(source, settings_targets=(target,))
    assert report.failure_reason == "rollback_failed"
    assert report.rollback_clean is False
    assert source.read_bytes() == original


def test_anonymous_legacy_state_is_not_written(tmp_path):
    source = tmp_path / "frontend_state.json"
    source.write_text(json.dumps({"version": 1, "users": {"anonymous": {"jiraAudit": {
        "jiraAuditInput": {"type": "string", "value": "project = SECRET"},
    }}}}), encoding="utf-8")
    target = MemorySettings()
    report = migrate_frontend_state(source, settings_targets=(target,))
    assert report.deleted and report.skipped == 1
    assert target.values == {}
    assert not any(key.startswith("users/anonymous/") for key in target.values)
