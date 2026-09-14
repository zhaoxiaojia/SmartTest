"""Shared audit/report and two-email delivery for every weekly-audit trigger."""

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from time import perf_counter

from core.confluence.audit.models import AuditPeriod
from core.email.audit_report import summarize_audit
from core.logging import smart_log

from ..task_manager import WEB_TASKS


class AuditEmailJob:
    def __init__(self, history):
        self.history = history
        self.root = history.database.path.parent / "audit-email-reports"
        self._tasks = set()
        self._lock = Lock()

    def trigger(
        self,
        account,
        filter_scope,
        access,
        password,
        expires_at,
        facts,
        jira_factory,
        confluence_factory,
        *,
        trigger_source,
    ):
        scope = filter_scope
        period = AuditPeriod(
            datetime.fromisoformat(scope["startDate"]),
            datetime.fromisoformat(scope["endDate"]),
        )
        result = self.history.create(account, scope)
        result.update(source=trigger_source, deliveries={})
        self.history.save(account, result)

        def execute(token, progress):
            try:
                self._run(
                    account,
                    result,
                    access,
                    password,
                    expires_at,
                    facts,
                    jira_factory,
                    confluence_factory,
                    token,
                    period,
                )
            except Exception as error:
                result.update(state="failed", error=type(error).__name__)
                self.history.save(account, result)

        future = WEB_TASKS.submit_coordinator("weekly-audit-email", execute)
        with self._lock:
            self._tasks.add(future)
        return self.history.get(account, result["id"])

    def close(self):
        with self._lock:
            tasks = tuple(self._tasks)
        for future in tasks:
            WEB_TASKS.cancel(WEB_TASKS.task_id(future))
        for future in tasks:
            WEB_TASKS.join(WEB_TASKS.task_id(future))
        with self._lock:
            self._tasks.difference_update(tasks)

    def _run(
        self,
        account,
        result,
        access,
        password,
        expires_at,
        facts,
        jira_factory,
        confluence_factory,
        token,
        period,
    ):
        started = perf_counter()
        result["state"] = "running"
        scope = result["scope"]

        def record(kind, stage, **fields):
            entry = {
                "run_id": result["id"],
                "trigger_source": result["source"],
                "report_type": kind,
                "stage": stage,
                **fields,
            }
            result["evidence"] += "\n" + " ".join(
                f"{key}={value}" for key, value in entry.items()
            )
            self.history.save(account, result)
            smart_log(
                "Weekly audit email "
                + " ".join(f"{key}={value}" for key, value in entry.items()),
                platform="web",
                domain="audit",
                source="audit_email",
                emit_runtime_event=False,
                extra=entry,
            )

        record(
            "both", "started", start_date=scope["startDate"], end_date=scope["endDate"]
        )
        for kind in ("jira", "confluence"):
            report_started = perf_counter()
            stage = "resolving_scope"
            try:
                token.raise_if_cancelled()
                access.require_active()
                result["reports"][kind]["state"] = "running"
                record(kind, stage)
                stage_started = perf_counter()
                if kind == "jira":
                    owner = jira_factory(account, password)
                    resolved = owner.resolve(scope["jira"]["jql"])
                    scope["jiraTemplate"] = scope["jira"]["jql"]
                    scope["jiraInput"] = resolved.jql
                    record(
                        kind,
                        "scope_resolved",
                        duration_ms=round((perf_counter() - stage_started) * 1000, 3),
                        jql=resolved.jql,
                    )
                else:
                    owner = confluence_factory(access, password)
                    resolved = owner.resolve({**scope, **scope["confluence"]})
                    record(
                        kind,
                        "scope_resolved",
                        duration_ms=round((perf_counter() - stage_started) * 1000, 3),
                        project_count=len(getattr(resolved, "projects", ())),
                    )
                stage = "auditing"
                stage_started = perf_counter()
                report = owner.run(
                    resolved,
                    token,
                    lambda step, done=0, total=0: record(
                        kind, step, processed=done, total=total
                    ),
                )
                record(
                    kind,
                    "audit_completed",
                    duration_ms=round((perf_counter() - stage_started) * 1000, 3),
                )
                token.raise_if_cancelled()
                access.require_active()
                stage = "exporting"
                stage_started = perf_counter()
                directory = self.root / result["id"] / kind
                directory.mkdir(parents=True, exist_ok=True)
                paths = (
                    [
                        owner.export(
                            report,
                            directory / f'Jira_Weekly_Review_{result["id"]}.xlsx',
                        )
                    ]
                    if kind == "jira"
                    else owner.export(report, directory)
                )
                record(
                    kind,
                    "export_completed",
                    duration_ms=round((perf_counter() - stage_started) * 1000, 3),
                )
                attachments = [Path(path).name for path in paths]
                token.raise_if_cancelled()
                access.require_active()
                summary = summarize_audit(kind, report)
                self.history.complete_report(
                    account, result, kind, summary, attachments
                )
                record(
                    kind,
                    "report_saved",
                    attachments=attachments,
                    duration_ms=round((perf_counter() - report_started) * 1000, 3),
                    run_elapsed_ms=round((perf_counter() - started) * 1000, 3),
                )
            except Exception as error:
                # External audit/export boundary: retain the other report and safe error evidence.
                code = (
                    str(error)
                    if str(error)
                    in {
                        "invalid_input",
                        "permission_denied",
                        "reauthentication_required",
                        "remote_unavailable",
                        "cancelled",
                    }
                    else type(error).__name__
                )
                result["reports"][kind] = {
                    "state": "failed",
                    "html": "",
                    "error": code,
                    "stage": stage,
                    "attachments": [],
                }
                result["summary"].pop(kind, None)
                record(kind, "failed", error_code=code, failure_stage=stage)
        result["state"] = "running"
        from core.email.outlook import send_email

        for kind, report in result["reports"].items():
            delivery = {"state": "skipped", "error": "report_unavailable"}
            if report["state"] == "completed":
                delivery_started = perf_counter()
                delivery = {
                    "state": "sending",
                    "startedAt": datetime.now(timezone.utc).isoformat(),
                    "recipients": ["fae.qa@amlogic.com"],
                }
                result["deliveries"][kind] = delivery
                record(kind, "smtp_started")
                try:
                    token.raise_if_cancelled()
                    send_email(
                        subject=report["subject"],
                        body=report["html"],
                        body_format="html",
                        template=None,
                        to=delivery["recipients"],
                        attachments=[
                            self.root / result["id"] / kind / name
                            for name in report["attachments"]
                        ],
                    )
                    delivery["state"] = "accepted"
                except Exception as error:
                    delivery.update(state="failed", error=type(error).__name__)
                delivery["finishedAt"] = datetime.now(timezone.utc).isoformat()
            result["deliveries"][kind] = delivery
            record(
                kind,
                f"smtp_{delivery['state']}",
                error_code=delivery.get("error", ""),
                duration_ms=(
                    round((perf_counter() - delivery_started) * 1000, 3)
                    if report["state"] == "completed"
                    else 0
                ),
            )
        accepted = sum(
            item["state"] == "accepted" for item in result["deliveries"].values()
        )
        result["state"] = (
            "completed" if accepted == 2 else "partial" if accepted else "failed"
        )
        record(
            "both",
            "finished",
            state=result["state"],
            email="recorded",
            duration_ms=round((perf_counter() - started) * 1000, 3),
        )
