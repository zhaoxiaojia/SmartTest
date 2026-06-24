from __future__ import annotations
import re
import time
from typing import Any, Callable


class StepStore:
    _REPEAT_RUNTIME_TITLE_RE = re.compile(r"^(?P<marker>Cycle|Loop)\s+(?P<index>\d+)(?:\/(?P<total>\d+))?:\s*(?P<suffix>.+)$")
    _REPEAT_ROW_TITLE_RE = re.compile(r"^(?P<marker>Cycle|Loop)(?:\s+\d+(?:\/\d+)?)?:\s*(?P<suffix>.+)$")

    def __init__(self, *, log: Callable[[str], None], on_change: Callable[[], None]) -> None:
        self._log = log
        self._on_change = on_change
        self.reset()

    def reset(self) -> None:
        self._steps: list[dict[str, Any]] = []
        self._step_index: dict[str, int] = {}
        self._step_alias_index: dict[tuple[str, str], str | None] = {}
        self._building_initial_plan = False
        self._hidden_step_ids: set[str] = set()
        self._step_started_at: dict[str, float] = {}
        self._case_repeat_context: dict[str, str] = {}

    def rows(self) -> list[dict[str, Any]]:
        return self._steps

    def begin_initial_plan(self) -> None:
        self._building_initial_plan = True

    def end_initial_plan(self) -> None:
        self._building_initial_plan = False

    def ensure_case_row(self, *, case_nodeid: str, title: str) -> str:
        row_id = f"case:{case_nodeid}"
        index = self._step_index.get(row_id)
        if index is not None:
            return row_id
        self._step_index[row_id] = len(self._steps)
        self._steps.append(
            {
                "id": row_id,
                "title": title,
                "status": "planned",
                "depth": 0,
                "phase": "call",
                "kind": "case",
                "definition_id": "",
                "case_nodeid": case_nodeid,
                "parent_id": "",
                "expected": "",
                "actual": "",
                "error": "",
                "duration_ms": 0,
                "evidence": [],
            }
        )
        self._on_change()
        return row_id

    def mark_case_started(self, payload: dict[str, Any]) -> None:
        case_nodeid = str(payload.get("case_nodeid", "") or "")
        title = str(payload.get("title", "") or case_nodeid)
        row_id = self.ensure_case_row(case_nodeid=case_nodeid, title=title)
        self._set_case_status(row_id, status="running", title=title)

    def upsert_step_row(self, payload: dict[str, Any], *, status: str, allow_create: bool = True) -> str:
        case_nodeid = str(payload.get("case_nodeid", ""))
        parent_id = str(payload.get("parent_id") or self._ensure_case_parent_id(case_nodeid))
        parent_index = self._step_index.get(parent_id)
        parent_depth = int(self._steps[parent_index].get("depth", 0)) if parent_index is not None else 0
        original_step_id = str(payload.get("step_id", "") or payload.get("id", ""))
        if self._is_framework_step(payload) or self._is_case_execute_summary_step(payload):
            if original_step_id:
                self._hidden_step_ids.add(original_step_id)
            return original_step_id
        step_id = original_step_id if self._building_initial_plan else self._resolve_step_row_id(payload)
        if not step_id:
            return ""
        row = {
            "id": step_id,
            "title": str(payload.get("title", "")),
            "status": status,
            "depth": parent_depth + 1,
            "phase": str(payload.get("phase", "call")),
            "kind": str(payload.get("kind", "action")),
            "definition_id": str(payload.get("definition_id", "") or ""),
            "case_nodeid": case_nodeid,
            "parent_id": parent_id,
            "expected": payload.get("expected", ""),
            "actual": payload.get("actual", ""),
            "error": str(payload.get("error", "") or ""),
            "duration_ms": int(payload.get("duration_ms", 0) or 0),
            "evidence": [],
        }
        index = self._step_index.get(step_id)
        if index is None:
            if not allow_create:
                self._log_unmatched_runtime_step(event_type=f"step_{status}", payload=payload)
                if original_step_id:
                    self._hidden_step_ids.add(original_step_id)
                return ""
            self._step_index[step_id] = len(self._steps)
            self._steps.append(row)
            self._register_step_aliases(step_id, payload)
        else:
            if status == "planned":
                self._register_step_aliases(step_id, payload)
                return step_id
            existing = self._steps[index]
            evidence = list(existing.get("evidence", []) or [])
            preserved_parent_id = existing.get("parent_id", "")
            preserved_depth = existing.get("depth", row["depth"])
            preserved_definition_id = existing.get("definition_id", "")
            update_values = {key: value for key, value in row.items() if value not in ("", {}, [])}
            if existing.get("title") and not self._should_refresh_runtime_title(payload):
                update_values.pop("title", None)
            if status == "running":
                existing["actual"] = ""
                existing["error"] = ""
                existing["duration_ms"] = 0
                existing["evidence"] = []
            existing.update(update_values)
            if preserved_parent_id and parent_id not in self._step_index:
                existing["parent_id"] = preserved_parent_id
                existing["depth"] = preserved_depth
            if preserved_definition_id and row.get("definition_id"):
                existing["definition_id"] = preserved_definition_id
            existing["status"] = status
            existing["evidence"] = evidence
            self._register_step_aliases(step_id, payload)
        self._apply_repeat_group_context(payload, status=status)
        self._on_change()
        return step_id

    def _ensure_case_parent_id(self, case_nodeid: str) -> str:
        row_id = f"case:{case_nodeid}"
        if row_id in self._step_index:
            return row_id
        return self.ensure_case_row(case_nodeid=case_nodeid, title=case_nodeid)

    def mark_step_started(self, payload: dict[str, Any]) -> None:
        step_id = self.upsert_step_row(payload, status="running", allow_create=False)
        if not step_id:
            return
        self._step_started_at[step_id] = float(payload.get("timestamp", time.time()) or time.time())

    def apply_step_finished(self, payload: dict[str, Any], *, min_running_display_sec: float) -> tuple[bool, int | None, dict[str, Any] | None]:
        original_step_id = str(payload.get("step_id", ""))
        if original_step_id in self._hidden_step_ids:
            return False, None, None
        step_id = self._resolve_step_row_id(payload)
        index = self._step_index.get(step_id)
        if index is None:
            self._log_unmatched_runtime_step(event_type="step_finished", payload=payload)
            return False, None, None
        row = self._steps[index]
        row["status"] = str(payload.get("status", "passed"))
        title = str(payload.get("title", "") or "").strip()
        if title and self._should_refresh_runtime_title(payload):
            row["title"] = title
        self._apply_repeat_group_context(payload, status="finished")
        row["actual"] = payload.get("actual", "")
        row["error"] = str(payload.get("error", "") or "")
        if "duration_ms" in payload:
            row["duration_ms"] = int(payload.get("duration_ms", 0) or 0)
        else:
            started_at = self._step_started_at.pop(step_id, None)
            if started_at is not None:
                row["duration_ms"] = int((float(payload.get("timestamp", time.time())) - started_at) * 1000)
        self._on_change()
        return True, None, None

    def apply_step_evidence(self, payload: dict[str, Any]) -> None:
        step_id = str(payload.get("step_id", "") or "")
        if step_id in self._hidden_step_ids:
            return
        step_id = self._resolve_step_row_id(payload)
        index = self._step_index.get(step_id)
        if index is None:
            return
        evidence = {
            "title": str(payload.get("title", "") or ""),
            "type": str(payload.get("evidence_type", "log") or "log"),
            "level": str(payload.get("level", "info") or "info"),
            "content": payload.get("content", ""),
            "meta": dict(payload.get("meta", {}) if isinstance(payload.get("meta", {}), dict) else {}),
        }
        items = list(self._steps[index].get("evidence", []) or [])
        items.append(evidence)
        self._steps[index]["evidence"] = items
        self._on_change()

    def mark_case_finished(self, payload: dict[str, Any]) -> None:
        case_nodeid = str(payload.get("case_nodeid", "") or "")
        planned_count = sum(
            1
            for row in self._steps
            if str(row.get("case_nodeid", "") or "") == case_nodeid
            and str(row.get("status", "") or "") == "planned"
            and str(row.get("kind", "") or "") != "case"
        )
        if planned_count:
            planned_rows = [
                {
                    "id": str(row.get("id", "") or ""),
                    "status": str(row.get("status", "") or ""),
                    "definition_id": str(row.get("definition_id", "") or ""),
                    "title": str(row.get("title", "") or ""),
                }
                for row in self._steps
                if str(row.get("case_nodeid", "") or "") == case_nodeid
                and str(row.get("status", "") or "") == "planned"
                and str(row.get("kind", "") or "") != "case"
            ]
            self._log(
                "[steps.trace] case_finished_kept_planned "
                f"case={case_nodeid} status={str(payload.get('status', '') or '<empty>')} "
                f"count={planned_count} rows={planned_rows}"
            )
        row_id = f"case:{case_nodeid}"
        index = self._step_index.get(row_id)
        if index is not None:
            self._set_case_status(
                row_id,
                status=str(payload.get("status", "passed")),
                duration_ms=int(payload.get("duration_ms", 0) or 0),
            )

    def _set_case_status(self, row_id: str, *, status: str, title: str = "", duration_ms: int | None = None) -> None:
        index = self._step_index.get(row_id)
        if index is None:
            return
        row = self._steps[index]
        if str(row.get("kind", "") or "") != "case":
            return
        changed = False
        if row.get("status") != status:
            row["status"] = status
            changed = True
        if title and row.get("title") != title:
            row["title"] = title
            changed = True
        if duration_ms is not None and row.get("duration_ms") != duration_ms:
            row["duration_ms"] = duration_ms
            changed = True
        if changed:
            self._on_change()

    def snapshot(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._steps]

    def snapshot_for_compare(self) -> list[dict[str, str]]:
        return [
            {
                "case_nodeid": str(row.get("case_nodeid", "") or ""),
                "id": str(row.get("id", "") or ""),
                "kind": str(row.get("kind", "") or ""),
                "definition_id": str(row.get("definition_id", "") or ""),
                "title": str(row.get("title", "") or ""),
                "status": str(row.get("status", "") or ""),
            }
            for row in self._steps
        ]

    def _apply_repeat_group_context(self, payload: dict[str, Any], *, status: str) -> None:
        title = str(payload.get("title", "") or "").strip()
        match = self._REPEAT_RUNTIME_TITLE_RE.match(title)
        if match is None:
            return
        case_nodeid = str(payload.get("case_nodeid", "") or "")
        marker = match.group("marker")
        index = match.group("index")
        total = match.group("total")
        prefix = f"{marker} {index}/{total}" if total else f"{marker} {index}"
        current_row_id = self._resolve_step_row_id(payload)
        current_index = self._step_index.get(current_row_id)
        repeat_rows: list[tuple[int, dict[str, Any], re.Match[str]]] = []
        for row_index, row in enumerate(self._steps):
            if str(row.get("case_nodeid", "") or "") != case_nodeid:
                continue
            if str(row.get("kind", "") or "") == "case":
                continue
            row_title = str(row.get("title", "") or "").strip()
            row_match = self._REPEAT_ROW_TITLE_RE.match(row_title)
            if row_match is None:
                continue
            repeat_rows.append((row_index, row, row_match))

        if not repeat_rows:
            return

        previous_prefix = self._case_repeat_context.get(case_nodeid, "")
        if not total and previous_prefix.startswith(f"{marker} {index}/"):
            prefix = previous_prefix
        if status == "running" and previous_prefix and previous_prefix != prefix:
            for row_index, row, _ in repeat_rows:
                if current_index is not None and row_index == current_index:
                    continue
                row["status"] = "planned"
                row["actual"] = ""
                row["error"] = ""
                row["duration_ms"] = 0
                row["evidence"] = []

        self._case_repeat_context[case_nodeid] = prefix

        for row_index, row, row_match in repeat_rows:
            suffix = row_match.group("suffix")
            row["title"] = f"{prefix}: {suffix}"
            if status == "running" and current_index is not None and row_index > current_index:
                row["status"] = "planned"
                row["actual"] = ""
                row["error"] = ""
                row["duration_ms"] = 0
                row["evidence"] = []

    def _should_refresh_runtime_title(self, payload: dict[str, Any]) -> bool:
        return bool(self._REPEAT_RUNTIME_TITLE_RE.match(str(payload.get("title", "") or "").strip()))

    def _resolve_step_row_id(self, payload: dict[str, Any]) -> str:
        step_id = str(payload.get("step_id", "") or payload.get("id", ""))
        if step_id in self._step_index:
            index = self._step_index[step_id]
            row_id = str(self._steps[index].get("id", "") or step_id)
            self._register_step_aliases(row_id, payload)
            return row_id
        case_nodeid = str(payload.get("case_nodeid", "") or "")
        for alias in self._step_aliases(payload):
            row_id = self._step_alias_index.get((case_nodeid, alias))
            if row_id and row_id in self._step_index:
                self._step_index[step_id] = self._step_index[row_id]
                self._register_step_aliases(row_id, payload)
                return row_id
        return step_id

    def _step_aliases(self, payload: dict[str, Any]) -> list[str]:
        aliases: list[str] = []
        for key in ("step_id", "id", "definition_id", "title"):
            value = str(payload.get(key, "") or "").strip()
            if value:
                aliases.append(value)
                aliases.append(value.rsplit(":", 1)[-1])
        raw_id = str(payload.get("step_id", "") or payload.get("id", "") or "").rsplit(":", 1)[-1]
        segments = [part for part in raw_id.replace("-", ".").replace("_", ".").split(".") if part]
        for index in range(len(segments)):
            aliases.append("_".join(segments[index:]))
        normalized: list[str] = []
        for value in aliases:
            item = "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")
            if item and item not in normalized:
                normalized.append(item)
        return normalized

    def _register_step_aliases(self, row_id: str, payload: dict[str, Any]) -> None:
        case_nodeid = str(payload.get("case_nodeid", "") or "")
        for alias in self._step_aliases(payload):
            key = (case_nodeid, alias)
            existing = self._step_alias_index.get(key)
            if existing is None and key in self._step_alias_index:
                continue
            if existing is not None and existing != row_id:
                self._step_alias_index[key] = None
                continue
            self._step_alias_index[key] = row_id

    def _is_framework_step(self, payload: dict[str, Any]) -> bool:
        definition_id = str(payload.get("definition_id", "") or "")
        return definition_id in {"android_client.run_case", "android_client.stage"}

    def _is_case_execute_summary_step(self, payload: dict[str, Any]) -> bool:
        original_step_id = str(payload.get("step_id", "") or payload.get("id", "") or "")
        raw_id = original_step_id.rsplit(":", 1)[-1]
        definition_id = str(payload.get("definition_id", "") or "")
        title = str(payload.get("title", "") or "").strip().lower()
        return (
            title.startswith("execute ")
            and (raw_id.endswith(".execute") or definition_id.endswith(".execute") or raw_id == "execute_case")
        )

    def _log_unmatched_runtime_step(self, *, event_type: str, payload: dict[str, Any]) -> None:
        self._log(
            "[steps.trace] unmatched_runtime_step "
            f"event={event_type} case={str(payload.get('case_nodeid', '') or '<empty>')} "
            f"step_id={str(payload.get('step_id', '') or payload.get('id', '') or '<empty>')} "
            f"definition_id={str(payload.get('definition_id', '') or '<empty>')} "
            f"kind={str(payload.get('kind', '') or '<empty>')} "
            f"title={str(payload.get('title', '') or '<empty>')}"
        )
