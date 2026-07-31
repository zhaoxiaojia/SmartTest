from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from support.confluence_audit.command import CommandDependencies, run_plan
from support.confluence_audit.models import (
    AuditBatch, AuditExecutionContext, AuditPeriod, ProjectCollectionFilter,
)
from support.confluence_audit.plans import AuditPlan
from support.windows_credentials import CredentialNotFoundError
from main import _background_command


TZ = ZoneInfo("Asia/Shanghai")


def _plan():
    now = datetime(2026, 7, 29, tzinfo=TZ)
    return AuditPlan(
        "plan-a", "Weekly", ProjectCollectionFilter("https://c/projects", (2026,)),
        True, "cred-a", "task-a", now, now,
    )


class Plans:
    def __init__(self):
        self.plan = _plan()
        self.results = []
        self.fail_update = False

    def load(self, plan_id):
        if plan_id != self.plan.plan_id:
            raise FileNotFoundError(plan_id)
        return self.plan

    def update_result(self, plan_id, **kwargs):
        if self.fail_update:
            raise OSError("result store unavailable")
        self.results.append((plan_id, kwargs))
        return self.plan


class Credentials:
    def __init__(self, missing=False):
        self.missing = missing

    def read(self, credential_ref):
        if self.missing:
            raise CredentialNotFoundError(credential_ref)
        return "ldap-user", "synthetic-password"


class Service:
    def __init__(self, batch):
        self.batch = batch
        self.calls = []

    def run(self, criteria, period, context):
        self.calls.append((criteria, period, context))
        return self.batch


def _dependencies(tmp_path, *, missing_credential=False):
    plans = Plans()
    batch = AuditBatch(
        "batch-a",
        AuditPeriod(
            datetime(2026, 7, 27, tzinfo=TZ),
            datetime(2026, 7, 31, tzinfo=TZ),
        ),
        datetime(2026, 7, 31, tzinfo=TZ),
    )
    service = Service(batch)
    xlsx_calls = []

    def xlsx_export(batch_value, output_path):
        xlsx_calls.append((batch_value, output_path))
        return Path(output_path)

    deps = CommandDependencies(
        plans=plans,
        credentials=Credentials(missing_credential),
        service_factory=lambda username, password: service,
        xlsx_exporter=xlsx_export,
        report_dir=tmp_path / "reports",
        now=lambda: datetime(2026, 7, 31, 0, 5, tzinfo=TZ),
    )
    return deps, service, xlsx_calls


def test_run_plan_uses_same_audit_service_and_records_xlsx(tmp_path):
    deps, service, xlsx_calls = _dependencies(tmp_path)
    assert run_plan("plan-a", deps) == 0
    assert service.calls[0][0] == deps.plans.plan.collection_filter
    assert service.calls[0][2] == AuditExecutionContext("scheduled", "plan-a")
    assert service.calls[0][1] == AuditPeriod(
        datetime(2026, 7, 27, tzinfo=TZ),
        datetime(2026, 7, 31, tzinfo=TZ),
    )
    assert len(xlsx_calls) == 1
    assert deps.plans.results[0][1]["status"] == "success"
    assert deps.plans.results[0][1]["report_path"].endswith(".xlsx")


def test_missing_credential_records_auth_failure_without_deleting_plan(tmp_path):
    deps, service, xlsx_calls = _dependencies(tmp_path, missing_credential=True)
    assert run_plan("plan-a", deps) == 3
    assert not service.calls and not xlsx_calls
    assert deps.plans.results[0][1]["status"] == "auth_failed"
    assert deps.plans.plan.plan_id == "plan-a"


def test_command_never_logs_or_serializes_password(monkeypatch, tmp_path):
    deps, service, xlsx_calls = _dependencies(tmp_path)
    log_calls = []
    monkeypatch.setattr(
        "support.confluence_audit.command.smart_log",
        lambda *args, **kwargs: log_calls.append((args, kwargs)),
    )
    run_plan("plan-a", deps)
    serialized = repr((
        log_calls, deps.plans.results, deps.plans.plan,
        service.calls, xlsx_calls,
    ))
    assert "synthetic-password" not in serialized
    assert "ldap-user" not in serialized
    assert "https://c/projects" in serialized


def test_http_auth_failure_is_recorded_as_auth_failure(tmp_path):
    deps, service, _ = _dependencies(tmp_path)

    class Response:
        status_code = 403

    class Forbidden(RuntimeError):
        response = Response()

    service.run = lambda *args: (_ for _ in ()).throw(Forbidden("forbidden"))
    assert run_plan("plan-a", deps) == 3
    assert deps.plans.results[0][1]["status"] == "auth_failed"


def test_success_result_store_failure_returns_config_error(tmp_path):
    deps, _, _ = _dependencies(tmp_path)
    deps.plans.fail_update = True
    assert run_plan("plan-a", deps) == 2


def test_main_background_switch_runs_plan_before_gui_startup():
    calls = []
    assert _background_command(
        ["SmartTest.exe", "--project-weekly-audit-plan", "plan-a"],
        lambda plan_id: calls.append(plan_id) or 4,
    ) == 4
    assert calls == ["plan-a"]
    assert _background_command(["SmartTest.exe"], lambda _: 0) is None
    assert _background_command(
        ["SmartTest.exe", "--project-weekly-audit-plan"], lambda _: 0,
    ) == 2
