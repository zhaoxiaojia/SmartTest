from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
import json
from pathlib import Path
import re
from uuid import uuid4

from .models import ProjectCollectionFilter
from .discovery import UNIFIED_SOURCE


@dataclass(frozen=True)
class AuditPlan:
    plan_id: str
    name: str
    collection_filter: ProjectCollectionFilter
    enabled: bool
    credential_ref: str
    task_name: str
    created_at: datetime
    updated_at: datetime
    last_run_at: datetime | None = None
    last_status: str = ""
    last_report_path: str = ""


class AuditPlanStore:
    VERSION = 1

    def __init__(self, root: Path):
        self.root = Path(root)

    def save(self, plan: AuditPlan) -> Path:
        plan_id = self._plan_id(plan.plan_id)
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{plan_id}.json"
        temporary = self.root / f".{plan_id}-{uuid4().hex}.tmp"
        payload = asdict(plan)
        payload["schema_version"] = self.VERSION
        try:
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, default=_json, indent=2),
                encoding="utf-8",
            )
            temporary.replace(path)
        finally:
            if temporary.exists():
                temporary.unlink()
        return path

    def load(self, plan_id: str) -> AuditPlan:
        value = self._plan_id(plan_id)
        data = json.loads((self.root / f"{value}.json").read_text(encoding="utf-8"))
        schema_version = data.get("schema_version")
        if type(schema_version) is not int or schema_version != self.VERSION:
            raise ValueError("Unsupported or missing audit plan schema version")
        raw_payload_id = data.get("plan_id")
        if not isinstance(raw_payload_id, str):
            raise ValueError("Invalid audit plan id in stored plan")
        payload_id = self._plan_id(raw_payload_id)
        if payload_id != value:
            raise ValueError("Audit plan id does not match the requested plan")
        filter_values = dict(data["collection_filter"])
        for key in (
            "years", "support_modes", "project_statuses",
            "current_stages", "included_project_ids",
            "product_line_keys",
        ):
            filter_values[key] = tuple(filter_values.get(key, ()))
        filter_values["source_url"] = UNIFIED_SOURCE
        filter_values["current_stages"] = ()
        return AuditPlan(
            plan_id=payload_id,
            name=data["name"],
            collection_filter=ProjectCollectionFilter(**filter_values),
            enabled=bool(data["enabled"]),
            credential_ref=data["credential_ref"],
            task_name=data["task_name"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            last_run_at=(
                datetime.fromisoformat(data["last_run_at"])
                if data.get("last_run_at") else None
            ),
            last_status=data.get("last_status", ""),
            last_report_path=data.get("last_report_path", ""),
        )

    def list(self) -> list[AuditPlan]:
        if not self.root.exists():
            return []
        return [
            self.load(path.stem)
            for path in sorted(self.root.glob("*.json"), key=lambda item: item.stem)
        ]

    def update_result(
        self,
        plan_id: str,
        *,
        status: str,
        report_path: str,
        run_at: datetime,
    ) -> AuditPlan:
        plan = self.load(plan_id)
        updated = replace(
            plan,
            updated_at=run_at,
            last_run_at=run_at,
            last_status=str(status),
            last_report_path=str(report_path),
        )
        self.save(updated)
        return updated

    @staticmethod
    def _plan_id(plan_id) -> str:
        value = str(plan_id)
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError("Invalid audit plan id")
        return value


def _json(value):
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Unsupported plan value: {type(value).__name__}")
