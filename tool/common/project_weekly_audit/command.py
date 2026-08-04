from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
from typing import Callable

from support.logging import smart_log
from support.windows_credentials import CredentialNotFoundError, WindowsCredentialError, WindowsCredentialStore

from .models import AuditExecutionContext
from .period import scheduled_reporting_window
from .plans import AuditPlanStore
from .report import export_project_audit_xlsx
from .service import ConfluenceAuditService
from support.confluence_integration import ConfluenceClient, ConfluenceClientConfig

EXIT_SUCCESS = 0
EXIT_CONFIG = 2
EXIT_AUTH = 3
EXIT_AUDIT = 4
EXIT_REPORT = 5


@dataclass
class CommandDependencies:
    plans: object
    credentials: object
    service_factory: Callable
    xlsx_exporter: Callable
    report_dir: Path
    now: Callable[[], datetime]


def run_plan(plan_id: str, dependencies: CommandDependencies | None = None) -> int:
    deps = dependencies or _default_dependencies()
    try:
        plan = deps.plans.load(plan_id)
    except Exception:
        _log(plan_id, "config_failed")
        return EXIT_CONFIG
    run_at = deps.now()
    try:
        username, password = deps.credentials.read(plan.credential_ref)
    except (CredentialNotFoundError, WindowsCredentialError):
        _record(deps, plan.plan_id, "auth_failed", "", run_at)
        _log(plan.plan_id, "auth_failed")
        return EXIT_AUTH
    try:
        service = deps.service_factory(username, password)
        batch = service.run(
            plan.collection_filter,
            scheduled_reporting_window(run_at),
            AuditExecutionContext("scheduled", plan.plan_id),
        )
    except Exception as exc:
        if _is_auth_error(exc):
            _record(deps, plan.plan_id, "auth_failed", "", run_at)
            _log(plan.plan_id, "auth_failed")
            return EXIT_AUTH
        _record(deps, plan.plan_id, "audit_failed", "", run_at)
        _log(plan.plan_id, "audit_failed")
        return EXIT_AUDIT
    finally:
        password = ""
    try:
        report = deps.xlsx_exporter(
            batch,
            deps.report_dir / f"project_weekly_audit_{batch.id}.xlsx",
        )
    except Exception:
        _record(deps, plan.plan_id, "report_failed", "", run_at)
        _log(plan.plan_id, "report_failed")
        return EXIT_REPORT
    if not _record(deps, plan.plan_id, "success", str(report), run_at):
        _log(plan.plan_id, "config_failed")
        return EXIT_CONFIG
    _log(plan.plan_id, "success")
    return EXIT_SUCCESS


def _default_dependencies() -> CommandDependencies:
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    root = root / "Amlogic" / "SmartTest" / "confluence_audit"
    def service_factory(username, password):
        base_url = os.getenv(
            "SMARTTEST_CONFLUENCE_BASE_URL", "https://confluence.amlogic.com",
        )
        client = ConfluenceClient(ConfluenceClientConfig(base_url), username, password)
        return ConfluenceAuditService(client)

    return CommandDependencies(
        plans=AuditPlanStore(root / "plans"),
        credentials=WindowsCredentialStore(),
        service_factory=service_factory,
        xlsx_exporter=export_project_audit_xlsx,
        report_dir=root / "reports",
        now=lambda: datetime.now().astimezone(),
    )


def _record(deps, plan_id, status, report_path, run_at):
    try:
        deps.plans.update_result(
            plan_id, status=status, report_path=report_path, run_at=run_at,
        )
        return True
    except Exception:
        smart_log(
            "Project weekly audit result persistence failed",
            level="error", domain="confluence", source="scheduled_audit",
            extra={"plan_id": plan_id, "status": status},
        )
        return False


def _is_auth_error(exc) -> bool:
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return status in {401, 403}


def _log(plan_id, status):
    smart_log(
        "Project weekly audit command finished",
        level="info" if status == "success" else "error",
        domain="confluence", source="scheduled_audit",
        extra={"plan_id": str(plan_id), "status": status},
    )
