from __future__ import annotations

import json
import os
import copy
import re
import threading
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from tools.param_conversion import normalize_value, to_bool, to_float, to_int, to_string, to_string_list, wire_string
from ui import jsonTool

from testing.params.registry import SchemaRegistry, default_registry
from testing.params.schema import ParamScope, ParamValueType, defaults_for_schema
from testing.runner.config import RUN_CONFIG_ENV


STEP_EVENTS_OUT_ENV = "SMARTTEST_STEP_EVENTS_OUT"


@dataclass(frozen=True)
class RuntimeConfig:
    nodeids: list[str] = field(default_factory=list)
    dut_serial: str = ""
    equipment: dict[str, Any] = field(default_factory=dict)
    global_context: dict[str, Any] = field(default_factory=dict)


class RunMetaStore:
    def runtime_config(self) -> RuntimeConfig:
        payload = _json_env(RUN_CONFIG_ENV)
        if not isinstance(payload, dict):
            return RuntimeConfig()
        return RuntimeConfig(
            nodeids=[str(item) for item in list(payload.get("nodeids") or [])],
            dut_serial=str(payload.get("dut_serial", "") or "").strip(),
            equipment=dict(payload.get("equipment") or {}) if isinstance(payload.get("equipment"), dict) else {},
            global_context=dict(payload.get("global_context") or {})
            if isinstance(payload.get("global_context"), dict)
            else {},
        )


class CaseStore:
    def __init__(self) -> None:
        self._current_nodeid: ContextVar[str | None] = ContextVar("smarttest_current_case_nodeid", default=None)
        self._current_stress_tolerant: ContextVar[bool] = ContextVar(
            "smarttest_current_case_stress_tolerant",
            default=False,
        )

    def current_nodeid(self) -> str | None:
        return self._current_nodeid.get()

    def set_current_nodeid(self, nodeid: str | None):
        return self._current_nodeid.set(nodeid)

    def reset_current_nodeid(self, token) -> None:
        self._current_nodeid.reset(token)

    def current_stress_tolerant(self) -> bool:
        return bool(self._current_stress_tolerant.get())

    def set_current_stress_tolerant(self, enabled: bool):
        return self._current_stress_tolerant.set(bool(enabled))

    def reset_current_stress_tolerant(self, token) -> None:
        self._current_stress_tolerant.reset(token)


class RuntimeStepStack:
    def __init__(self) -> None:
        self._stack: ContextVar[list[dict[str, Any]]] = ContextVar("smarttest_step_stack", default=[])

    def current_step(self) -> dict[str, Any] | None:
        stack = self._stack.get()
        return stack[-1] if stack else None

    def push(self, step_payload: dict[str, Any]):
        stack = list(self._stack.get())
        stack.append(dict(step_payload))
        return self._stack.set(stack)

    def pop(self, token) -> None:
        self._stack.reset(token)


class EventStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: list[dict[str, Any]] = []

    def emit(self, event_type: str, **payload: Any) -> None:
        event = {
            "type": event_type,
            "timestamp": time.time(),
            **payload,
        }
        self._events.append(dict(event))
        raw_path = os.environ.get(STEP_EVENTS_OUT_ENV, "").strip()
        if not raw_path:
            return
        event_path = Path(raw_path)
        event_path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(event, ensure_ascii=False) + "\n"
        with self._lock:
            with event_path.open("a", encoding="utf-8") as fh:
                fh.write(encoded)

    def snapshot(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._events]

    def clear(self) -> None:
        self._events.clear()


class DisplayStepStore:
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


class ParameterStore:
    def __init__(self, registry: SchemaRegistry | None = None) -> None:
        self._registry = registry or default_registry()
        self._ui_state: Any | None = None

    def bind_ui_state(self, state: Any) -> None:
        self._ui_state = state

    def _case_parameters(self) -> dict[str, dict[str, Any]]:
        if self._ui_state is not None:
            values = getattr(self._ui_state, "case_parameters", {})
            return values if isinstance(values, dict) else {}
        raw_parameters = jsonTool.get_json_value("test_page_state.json", ["case_parameters"], {})
        return raw_parameters if isinstance(raw_parameters, dict) else {}

    def _global_context(self) -> dict[str, Any]:
        if self._ui_state is not None:
            values = getattr(self._ui_state, "global_context", {})
            return values if isinstance(values, dict) else {}
        raw_context = jsonTool.get_json_value("test_page_state.json", ["global_context"], {})
        context = dict(raw_context) if isinstance(raw_context, dict) else {}
        payload = _json_env(RUN_CONFIG_ENV)
        run_context = payload.get("global_context", {}) if isinstance(payload, dict) else {}
        if isinstance(run_context, dict):
            context.update(run_context)
        return context

    def _case_type_configs(self) -> dict[str, dict[str, Any]]:
        if self._ui_state is not None:
            values = getattr(self._ui_state, "case_type_configs", {})
            return values if isinstance(values, dict) else {}
        raw_configs = jsonTool.get_json_value("test_page_state.json", ["case_type_configs"], {})
        return raw_configs if isinstance(raw_configs, dict) else {}

    def _case_parameter_options(self) -> dict[str, dict[str, list[str]]]:
        if self._ui_state is not None:
            values = getattr(self._ui_state, "case_parameter_options", {})
            return values if isinstance(values, dict) else {}
        raw_options = jsonTool.get_json_value("test_page_state.json", ["case_parameter_options"], {})
        return raw_options if isinstance(raw_options, dict) else {}

    def _dynamic_params_by_dut(self) -> dict[str, dict[str, Any]]:
        global_context = self._global_context()
        values = global_context.get("dynamic_params_by_dut")
        if values is None:
            global_context["dynamic_params_by_dut"] = {}
            return global_context["dynamic_params_by_dut"]
        if not isinstance(values, dict):
            raise TypeError("global_context.dynamic_params_by_dut must be a dict")
        return values

    def ensure_persisted_defaults(self) -> bool:
        if self._ui_state is None:
            return False
        changed = False
        global_context = self._global_context()
        global_defaults = defaults_for_schema(self._registry.global_context)
        legacy_dut = global_context.get("dut_model")
        if "dut" not in global_context and legacy_dut not in (None, ""):
            global_context["dut"] = legacy_dut
            changed = True
        preserved_global_keys = {*global_defaults, "equipment", "duts", "dynamic_params_by_dut"}
        next_global_context = {key: value for key, value in global_context.items() if key in preserved_global_keys}
        if next_global_context != global_context:
            global_context.clear()
            global_context.update(next_global_context)
            changed = True
        for key, value in global_defaults.items():
            if key not in global_context:
                global_context[key] = copy.deepcopy(value)
                changed = True
        return changed

    def migrate_case_parameter_values(self, migrate_value: Callable[[str, Any], tuple[Any, bool]]) -> bool:
        changed = False
        for params in self._case_parameters().values():
            if not isinstance(params, dict):
                continue
            for key in list(params):
                next_value, value_changed = migrate_value(str(key), params.get(key))
                if value_changed:
                    params[key] = next_value
                    changed = True
        return changed

    def prune_stored_fixed_enum_values(self) -> list[dict[str, Any]]:
        changes: list[dict[str, Any]] = []
        for values in (self._global_context(), *self._case_type_configs().values(), *self._case_parameters().values()):
            if not isinstance(values, dict):
                continue
            for key in list(values.keys()):
                field = self._registry.get_param(str(key))
                if field is None or field.options_source or not field.enum_values:
                    continue
                if self._is_multi_enum_field(field):
                    current = to_string_list(values.get(key, []))
                    next_values = [value for value in current if value in field.enum_values]
                    if next_values == current:
                        continue
                    values[key] = next_values
                    changes.append({"field": key, "removed": len(current) - len(next_values), "kept": len(next_values)})
                    continue
                field_type = field.type.value if hasattr(field.type, "value") else field.type
                if field_type == ParamValueType.ENUM.value and values.get(key) not in field.enum_values:
                    values[key] = copy.deepcopy(field.default)
                    changes.append({"field": key, "removed": 1, "kept": 1})
        return changes

    def migrate_case_nodeid(self, *, old_nodeid: str, new_nodeid: str) -> bool:
        old_key = str(old_nodeid or "").strip()
        new_key = str(new_nodeid or "").strip()
        parameters = self._case_parameters()
        if not old_key or not new_key or old_key not in parameters or new_key in parameters:
            return False
        parameters[new_key] = dict(parameters.get(old_key, {}))
        return True

    def equipment_config(self) -> dict[str, Any]:
        raw = self._global_context().get("equipment", {})
        return dict(raw) if isinstance(raw, dict) else {}

    def set_equipment_config(self, equipment: dict[str, Any]) -> None:
        self._global_context()["equipment"] = dict(equipment)

    def global_context_snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(self._global_context())

    def selected_dut(self) -> str:
        return str(self._global_context().get("dut", "") or "").strip()

    def dynamic_options(self, *, selected_nodeid: str, case_nodeid: str, key: str) -> list[str]:
        options = self._case_parameter_options()
        preferred_key = str(key or "").strip()
        for nodeid in (str(case_nodeid or "").strip(), str(selected_nodeid or "").strip()):
            values = options.get(nodeid, {})
            if isinstance(values, dict) and preferred_key in values:
                return to_string_list(values.get(preferred_key, []))
        return []

    def _is_multi_enum_field(self, field: Any) -> bool:
        field_type = field.type.value if hasattr(field.type, "value") else field.type
        return field_type == ParamValueType.MULTI_ENUM.value

    def raw_case_values(self, nodeid: str) -> dict[str, Any]:
        requested_nodeid = str(nodeid)
        values = self._case_parameters().get(requested_nodeid)
        result = dict(values) if isinstance(values, dict) else {}
        result.update(self._selected_dut_dynamic_values())
        return result

    def global_value(self, key: str, default: Any = None) -> Any:
        field = self._registry.get_param(str(key or "").strip())
        fallback = field.default if field is not None and default is None else default
        return self.normalize_for_key(str(key or "").strip(), self._global_context().get(str(key), fallback), fallback)

    def case_display_value(self, case: dict[str, Any], key: str) -> Any:
        field = self._registry.get_param(str(key or "").strip())
        if field is None:
            return None
        if field.scope == ParamScope.GLOBAL_CONTEXT:
            value = self._global_context().get(field.key, field.default)
        elif field.scope == ParamScope.CASE_TYPE_SHARED:
            case_type = str(case.get("case_type") or "default")
            value = self._case_type_configs().get(case_type, {}).get(field.key, field.default)
        else:
            case_nodeid = str(case.get("nodeid", "") or "").strip()
            value = self._dynamic_value_for_field(field)
            if value is None:
                value = self._case_parameters().get(case_nodeid, {}).get(field.key, field.default)
        return self.normalize_for_key(field.key, value)

    def set_case_display_value(self, case: dict[str, Any], key: str, value: Any) -> bool:
        field = self._registry.get_param(str(key or "").strip())
        if field is None:
            return False
        if str(getattr(field, "source_kind", "") or "").strip() == "dut_dynamic":
            return self.set_selected_dut_dynamic_value(field.key, value)
        next_value = self.normalize_for_key(field.key, value)
        if field.scope == ParamScope.GLOBAL_CONTEXT:
            context = self._global_context()
            if context.get(field.key) == next_value:
                return False
            context[field.key] = next_value
            return True
        if field.scope == ParamScope.CASE_TYPE_SHARED:
            case_type = str(case.get("case_type") or "default")
            configs = self._case_type_configs()
            configs.setdefault(case_type, {})
            if configs[case_type].get(field.key) == next_value:
                return False
            configs[case_type][field.key] = next_value
            return True
        case_nodeid = str(case.get("nodeid", "") or "").strip()
        if not case_nodeid:
            return False
        parameters = self._case_parameters()
        parameters.setdefault(case_nodeid, {})
        if parameters[case_nodeid].get(field.key) == next_value:
            return False
        parameters[case_nodeid][field.key] = next_value
        return True

    def _selected_dut_dynamic_values(self) -> dict[str, Any]:
        dut = self.selected_dut()
        if not dut:
            return {}
        return self.dut_dynamic_values(dut)

    def _dynamic_value_for_field(self, field: Any) -> Any:
        if str(getattr(field, "source_kind", "") or "").strip() != "dut_dynamic":
            return None
        values = self._selected_dut_dynamic_values()
        if field.key not in values:
            return None
        return values.get(field.key)

    def set_selected_dut_dynamic_value(self, key: str, value: Any) -> bool:
        return self.set_dut_dynamic_value(self.selected_dut(), key, value)

    def dut_dynamic_values(self, dut: str) -> dict[str, Any]:
        normalized_dut = str(dut or "").strip()
        if not normalized_dut:
            return {}
        values = self._dynamic_params_by_dut().get(normalized_dut, {})
        if values is None:
            return {}
        if not isinstance(values, dict):
            raise TypeError(f"dynamic params for DUT {normalized_dut!r} must be a dict")
        return dict(values)

    def dut_dynamic_value(self, dut: str, key: str, default: Any = None) -> Any:
        values = self.dut_dynamic_values(dut)
        return values.get(str(key or "").strip(), default)

    def set_dut_dynamic_value(self, dut: str, key: str, value: Any) -> bool:
        field = self._registry.get_param(str(key or "").strip())
        if field is None:
            return False
        normalized_dut = str(dut or "").strip()
        if not normalized_dut:
            return False
        next_value = self.normalize_for_key(field.key, value)
        by_dut = self._dynamic_params_by_dut()
        values = by_dut.setdefault(normalized_dut, {})
        if not isinstance(values, dict):
            raise TypeError(f"dynamic params for DUT {normalized_dut!r} must be a dict")
        if values.get(field.key) == next_value:
            return False
        values[field.key] = next_value
        return True

    def set_global_value(self, key: str, value: Any) -> bool:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return False
        next_value = self.normalize_for_key(normalized_key, value)
        context = self._global_context()
        if context.get(normalized_key) == next_value:
            return False
        context[normalized_key] = next_value
        return True

    def ensure_case_defaults(self, *, nodeid: str, case_type: str = "default") -> None:
        normalized_nodeid = str(nodeid or "").strip()
        if normalized_nodeid:
            self._case_parameters().setdefault(normalized_nodeid, {})
        schema = self._registry.get_case_type_schema(str(case_type or "default"))
        if schema is not None:
            self._case_type_configs().setdefault(str(case_type or "default"), {
                field.key: copy.deepcopy(field.default) for field in schema.fields
            })

    def prune_multi_enum_to_options(self, *, nodeid: str, key: str, options: list[str]) -> tuple[bool, int, int]:
        field = self._registry.get_param(str(key or "").strip())
        if field is None:
            return False, 0, 0
        field_type = field.type.value if hasattr(field.type, "value") else field.type
        if field_type != "multi_enum":
            return False, 0, 0
        case_values = self._case_parameters().setdefault(str(nodeid or "").strip(), {})
        current = to_string_list(case_values.get(field.key, []))
        next_value = [value for value in current if value in options]
        if next_value == current:
            return False, len(current), len(next_value)
        case_values[field.key] = next_value
        return True, len(current), len(next_value)

    def case_values(self, nodeid: str) -> dict[str, Any]:
        return {
            str(key): self.normalize_for_key(str(key), value)
            for key, value in self.raw_case_values(nodeid).items()
            if str(key).strip()
        }

    def get_value(self, nodeid: str, key: str, default: Any = None) -> Any:
        field = self._registry.get_param(str(key or "").strip())
        fallback = field.default if field is not None and default is None else default
        values = self.raw_case_values(nodeid)
        return self.normalize_for_key(key, values.get(str(key), fallback), default=fallback)

    def get_int(self, nodeid: str, key: str, default: int = 0) -> int:
        return to_int(self.get_value(nodeid, key, default), default=default)

    def get_float(self, nodeid: str, key: str, default: float = 0.0) -> float:
        return to_float(self.get_value(nodeid, key, default), default=default)

    def get_bool(self, nodeid: str, key: str, default: bool = False) -> bool:
        return to_bool(self.get_value(nodeid, key, default), default=default)

    def get_list(self, nodeid: str, key: str, default: list[str] | None = None) -> list[str]:
        value = self.get_value(nodeid, key, default or [])
        return to_string_list(value)

    def get_str(self, nodeid: str, key: str, default: str = "") -> str:
        return to_string(self.get_value(nodeid, key, default), default=default)

    def normalize_for_key(self, key: str, value: Any, default: Any = None) -> Any:
        field = self._registry.get_param(str(key or "").strip())
        if field is None:
            return value if value is not None else default
        fallback = field.default if default is None else default
        return normalize_value(value, field.type, default=fallback)

    def apk_params(self, case_id: str, nodeid: str) -> dict[str, str]:
        normalized_case_id = str(case_id or "").strip()
        prefix = f"{normalized_case_id}:"
        resolved: dict[str, str] = {}
        for field in self._registry.fields_by_key.values():
            key = str(field.key or "").strip()
            if key.startswith(prefix) and field.default not in (None, ""):
                rendered_default = wire_string(field.default, value_type=field.type)
                if _omit_apk_param_value(rendered_default):
                    continue
                resolved[key] = rendered_default
        for key, value in self.raw_case_values(nodeid).items():
            normalized_key = str(key or "").strip()
            if not normalized_key.startswith(prefix):
                continue
            field = self._registry.get_param(normalized_key)
            rendered_value = wire_string(
                self.normalize_for_key(normalized_key, value),
                value_type=field.type if field is not None else None,
            )
            if _omit_apk_param_value(rendered_value):
                resolved.pop(normalized_key, None)
                continue
            resolved[normalized_key] = rendered_value
        return resolved


class TestContext:
    _LOOP_STEP_ID_RE = re.compile(
        r"(?:^|[.:])(?P<marker>cycle|loop)[.:](?P<index>\d+)(?:[.:](?P<tail>[^:]+))?",
        re.IGNORECASE,
    )
    _LOOP_TITLE_RE = re.compile(
        r"\b(?P<marker>Cycle|Loop)\s+(?P<index>\d+)(?:\s*/\s*(?P<total>\d+))?\s*:",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        self.run = RunMetaStore()
        self.cases = CaseStore()
        self._step_stack = RuntimeStepStack()
        self.steps = DisplayStepStore(log=self.append_log_line, on_change=lambda: None)
        self.events = EventStore()
        self.params = ParameterStore()
        self._logs: list[dict[str, Any]] = []
        self._run_id = ""
        self._started_at = ""
        self._finished_at = ""
        self._started_monotonic = 0.0
        self._selected_nodeids: list[str] = []
        self._adb_serial: str | None = None
        self._returncode = 0
        self._stopped = False
        self._last_report: dict[str, Any] = {}
        self._case_start_times: dict[str, float] = {}
        self._case_statuses: dict[str, str] = {}
        self._case_summaries: dict[str, dict[str, Any]] = {}
        self._case_loop_summaries: dict[str, dict[str, Any]] = {}
        self._case_failures: dict[str, dict[str, Any]] = {}
        self._case_artifacts: dict[str, list[dict[str, Any]]] = {}

    def runtime_config(self) -> RuntimeConfig:
        return self.run.runtime_config()

    def current_case_nodeid(self) -> str | None:
        return self.cases.current_nodeid()

    def current_case_stress_tolerant(self) -> bool:
        return self.cases.current_stress_tolerant()

    def current_step(self) -> dict[str, Any] | None:
        return self._step_stack.current_step()

    def push_step(self, step_payload: dict[str, Any]):
        return self._step_stack.push(step_payload)

    def pop_step(self, token) -> None:
        self._step_stack.pop(token)

    def begin_run(self, *, root_dir: Path, run_config: Any, started_at: str | None = None) -> None:
        from testing.steps.planner import build_step_plan

        self._logs = []
        self.steps.reset()
        self.events.clear()
        self._run_id = uuid4().hex
        self._started_at = str(started_at or _now_iso())
        self._finished_at = ""
        self._started_monotonic = time.monotonic()
        self._selected_nodeids = [str(item) for item in list(getattr(run_config, "nodeids", []) or [])]
        self._adb_serial = getattr(run_config, "dut_serial", None)
        self._returncode = 0
        self._stopped = False
        self._last_report = {}
        self.steps.begin_initial_plan()
        try:
            for nodeid in self._selected_nodeids:
                case_title = nodeid.rsplit("::", 1)[-1] if "::" in nodeid else nodeid
                case_row_id = self.steps.ensure_case_row(case_nodeid=nodeid, title=case_title)
                for item in build_step_plan(root_dir=root_dir, nodeid=nodeid):
                    raw_step_id = str(item.get("id", "") or "step")
                    definition_id = str(item.get("definition_id", "") or raw_step_id)
                    self.steps.upsert_step_row(
                        {
                            "step_id": f"plan:{nodeid}:{raw_step_id}",
                            "case_nodeid": nodeid,
                            "parent_id": case_row_id,
                            "title": str(item.get("title", "") or raw_step_id),
                            "kind": str(item.get("kind", "action") or "action"),
                            "definition_id": definition_id,
                            "expected": item.get("expected", ""),
                        },
                        status="planned",
                    )
        finally:
            self.steps.end_initial_plan()

    def apply_event(self, payload: dict[str, Any], *, min_running_display_sec: float = 0.0) -> None:
        event_type = str(payload.get("type", ""))
        if event_type == "case_started":
            self.start_case(payload)
        elif event_type == "case_finished":
            self.finish_case(payload)
        elif event_type == "step_planned":
            self.plan_runtime_step(payload)
        elif event_type == "step_started":
            self.start_step(payload)
        elif event_type == "step_finished":
            self.finish_step(payload, min_running_display_sec=min_running_display_sec)
        elif event_type == "step_evidence":
            self.add_step_evidence(payload)
        elif event_type == "log":
            message = str(payload.get("message", "")).strip()
            line = str(payload.get("line") or "").strip()
            if message or line:
                self.append_log(
                    {
                        "line": line or message,
                        "message": message or line,
                        "level": str(payload.get("level", "info") or "info"),
                        "domain": str(payload.get("domain", "test") or "test"),
                        "source": str(payload.get("source", "") or ""),
                        "case_nodeid": str(payload.get("case_nodeid", "") or ""),
                        "step_id": str(payload.get("step_id", "") or ""),
                        "extra": dict(payload.get("extra") or {}),
                    }
                )

    def start_case(self, payload: dict[str, Any]) -> None:
        self.steps.mark_case_started(payload)

    def finish_case(self, payload: dict[str, Any]) -> None:
        self.steps.mark_case_finished(payload)

    def plan_runtime_step(self, payload: dict[str, Any]) -> None:
        self.steps.upsert_step_row(payload, status="planned", allow_create=False)

    def start_step(self, payload: dict[str, Any]) -> None:
        self.steps.mark_step_started(payload)

    def finish_step(self, payload: dict[str, Any], *, min_running_display_sec: float = 0.0) -> None:
        self.steps.apply_step_finished(payload, min_running_display_sec=min_running_display_sec)
        self._observe_loop_step_finished(payload)

    def add_step_evidence(self, payload: dict[str, Any]) -> None:
        self.steps.apply_step_evidence(payload)

    def set_case_summary(self, case_nodeid: str, summary: dict[str, Any]) -> None:
        nodeid = str(case_nodeid or "").strip()
        if nodeid:
            self._case_summaries[nodeid] = copy.deepcopy(dict(summary))

    def set_case_loop_summary(self, case_nodeid: str, summary: dict[str, Any]) -> None:
        nodeid = str(case_nodeid or "").strip()
        if nodeid:
            self._case_loop_summaries[nodeid] = copy.deepcopy(dict(summary))

    def set_case_failure(self, case_nodeid: str, failure: dict[str, Any]) -> None:
        nodeid = str(case_nodeid or "").strip()
        if nodeid:
            self._case_failures[nodeid] = copy.deepcopy(dict(failure))

    def add_case_artifact(self, case_nodeid: str, artifact: dict[str, Any]) -> None:
        nodeid = str(case_nodeid or "").strip()
        if nodeid:
            self._case_artifacts.setdefault(nodeid, []).append(copy.deepcopy(dict(artifact)))

    def append_log_line(self, line: str) -> None:
        self.append_log({"line": str(line), "domain": "runner", "level": "info", "source": "TestContext"})

    def append_log(self, record: dict[str, Any]) -> None:
        from tools.logging import log_display_fields

        row = dict(record)
        text = str(row.get("line") or row.get("message") or "").rstrip()
        if not text:
            return
        row["line"] = text
        row.update(log_display_fields(domain=row.get("domain"), level=row.get("level")))
        self._logs.append(row)

    def start_case_execution(self, *, nodeid: str, title: str, file: str = "") -> None:
        self._case_start_times[str(nodeid)] = time.monotonic()
        self._case_statuses[str(nodeid)] = "running"
        self.events.emit(
            "case_started",
            case_nodeid=str(nodeid),
            title=str(title),
            file=str(file),
        )

    def update_case_execution(self, *, nodeid: str, when: str, failed: bool, skipped: bool) -> None:
        normalized = str(nodeid)
        if when == "call":
            if failed:
                self._case_statuses[normalized] = "failed"
            elif skipped:
                self._case_statuses[normalized] = "skipped"
            else:
                self._case_statuses[normalized] = "passed"
        elif when == "setup" and failed:
            self._case_statuses[normalized] = "failed"

    def finish_case_execution(self, *, nodeid: str) -> None:
        normalized = str(nodeid)
        status = self._case_statuses.get(normalized, "passed")
        duration_ms = int((time.monotonic() - self._case_start_times.get(normalized, time.monotonic())) * 1000)
        self.events.emit(
            "case_finished",
            case_nodeid=normalized,
            status=status,
            duration_ms=duration_ms,
        )
        self._case_start_times.pop(normalized, None)
        self._case_statuses.pop(normalized, None)

    def step_rows(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.steps.snapshot())

    def log_rows(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._logs)

    def has_steps(self) -> bool:
        return bool(self.steps.rows())

    def has_logs(self) -> bool:
        return bool(self._logs)

    def ui_snapshot(self) -> dict[str, Any]:
        return {
            "steps": self.step_rows(),
            "logs": self.log_rows(),
            "run_id": self._run_id,
            "started_at": self._started_at,
            "selected_nodeids": list(self._selected_nodeids),
            "adb_serial": self._adb_serial,
        }

    def report_snapshot(self) -> dict[str, Any]:
        steps = self.step_rows()
        logs = self.log_rows()
        summary = self._summary_model(steps)
        cases = self._case_models(steps, logs)
        return {
            "run_id": self._run_id,
            "title": f"{(self._finished_at or _now_iso()).replace('T', ' ')[:19]}  {self._status_from_summary(summary)}",
            "started_at": self._started_at,
            "finished_at": self._finished_at,
            "duration_ms": self._duration_ms(),
            "returncode": self._returncode,
            "stopped": self._stopped,
            "status": self._status_from_summary(summary),
            "adb_serial": self._adb_serial,
            "selected_nodeids": list(self._selected_nodeids),
            "summary": summary,
            "counts": dict(summary),
            "cases": cases,
            "steps": steps,
            "logs": logs,
            "failure_analysis": self._failure_analysis_model(cases),
            "duration_ranking": self._duration_ranking_model(cases),
            "log_distribution": self._log_distribution_model(logs),
        }

    def finish_run(self, *, returncode: int, stopped: bool, finished_at: str | None = None) -> dict[str, Any]:
        from tools.report import build_run_report

        self._returncode = int(returncode)
        self._stopped = bool(stopped)
        self._finished_at = str(finished_at or _now_iso())
        snapshot = self.report_snapshot()
        self._last_report = build_run_report(**snapshot)
        return copy.deepcopy(self._last_report)

    def _duration_ms(self) -> int:
        if not self._started_monotonic:
            return 0
        return int((time.monotonic() - self._started_monotonic) * 1000)

    def reset_for_tests(self) -> None:
        self.events.clear()
        self.params = ParameterStore()
        self._logs = []
        self.steps.reset()
        self._run_id = ""
        self._started_at = ""
        self._finished_at = ""
        self._started_monotonic = 0.0
        self._selected_nodeids = []
        self._adb_serial = None
        self._returncode = 0
        self._stopped = False
        self._last_report = {}
        self._case_start_times = {}
        self._case_statuses = {}
        self._case_summaries = {}
        self._case_loop_summaries = {}
        self._case_failures = {}
        self._case_artifacts = {}

    def _summary_model(self, steps: list[dict[str, Any]]) -> dict[str, int]:
        cases = [row for row in steps if str(row.get("kind", "") or "") == "case"]
        return {
            "total": len(cases),
            "passed": sum(1 for row in cases if row.get("status") == "passed"),
            "failed": sum(1 for row in cases if row.get("status") == "failed"),
            "skipped": sum(1 for row in cases if row.get("status") == "skipped"),
            "running": sum(1 for row in cases if row.get("status") == "running"),
        }

    def _status_from_summary(self, summary: dict[str, int]) -> str:
        if self._stopped:
            return "stopped"
        if int(summary.get("failed", 0) or 0) > 0 or self._returncode != 0:
            return "failed"
        if int(summary.get("total", 0) or 0) == 0:
            return "empty"
        return "passed"

    def _case_models(self, steps: list[dict[str, Any]], logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        case_rows = [row for row in steps if str(row.get("kind", "") or "") == "case"]
        if not case_rows:
            case_rows = [
                {
                    "id": f"case:{nodeid}",
                    "kind": "case",
                    "case_nodeid": nodeid,
                    "title": nodeid,
                    "status": "planned",
                    "duration_ms": 0,
                }
                for nodeid in self._selected_nodeids
            ]
        result: list[dict[str, Any]] = []
        for case in case_rows:
            nodeid = str(case.get("case_nodeid", "") or "")
            case_steps = [
                row
                for row in steps
                if str(row.get("case_nodeid", "") or "") == nodeid and str(row.get("kind", "") or "") != "case"
            ]
            case_logs = [row for row in logs if str(row.get("case_nodeid", "") or "") == nodeid]
            key_logs = [
                row
                for row in case_logs
                if str(row.get("level", "") or "").lower() in {"warning", "error", "critical"}
            ]
            result.append(
                {
                    "case": copy.deepcopy(case),
                    "case_summary": copy.deepcopy(self._case_summaries.get(nodeid, {})),
                    "loop_summary": self._case_loop_summary_for(nodeid),
                    "failure": copy.deepcopy(self._case_failures.get(nodeid, {})),
                    "steps": copy.deepcopy(case_steps),
                    "logs": copy.deepcopy(case_logs),
                    "key_logs": copy.deepcopy(key_logs),
                    "artifacts": copy.deepcopy(self._case_artifacts.get(nodeid, [])),
                }
            )
        result.sort(key=lambda item: (0 if item["case"].get("status") == "failed" else 1, str(item["case"].get("title", ""))))
        return result

    def _observe_loop_step_finished(self, payload: dict[str, Any]) -> None:
        case_nodeid = str(payload.get("case_nodeid", "") or "").strip()
        if not case_nodeid:
            return
        position = self._loop_position(payload)
        if position is None:
            return
        index, total = position
        definition_id = str(payload.get("definition_id", "") or "").strip()
        action_id = self._loop_action_id(payload, definition_id=definition_id)
        if not action_id:
            return
        status = str(payload.get("status", "") or "passed").strip().lower() or "passed"
        summary = copy.deepcopy(self._case_loop_summaries.get(case_nodeid, {}))
        summary["observed"] = max(int(summary.get("observed", 0) or 0), index)
        summary["total"] = max(int(summary.get("total", 0) or 0), total or index)
        actions = dict(summary.get("actions", {}) if isinstance(summary.get("actions"), dict) else {})
        counts = dict(actions.get(action_id, {}) if isinstance(actions.get(action_id), dict) else {})
        counts[status] = int(counts.get(status, 0) or 0) + 1
        actions[action_id] = counts
        summary["actions"] = actions
        self._case_loop_summaries[case_nodeid] = summary

    def _case_loop_summary_for(self, case_nodeid: str) -> dict[str, Any]:
        summary = copy.deepcopy(self._case_loop_summaries.get(case_nodeid, {}))
        if not summary:
            return {}
        observed = int(summary.get("observed", 0) or 0)
        total = int(summary.get("total", 0) or 0)
        summary["observed"] = observed
        summary["total"] = total or observed
        summary["actions"] = dict(summary.get("actions", {}) if isinstance(summary.get("actions"), dict) else {})
        return summary

    def _loop_position(self, payload: dict[str, Any]) -> tuple[int, int] | None:
        for value in (payload.get("step_id"), payload.get("id")):
            match = self._LOOP_STEP_ID_RE.search(str(value or ""))
            if match is not None:
                return int(match.group("index")), 0
        title_match = self._LOOP_TITLE_RE.search(str(payload.get("title", "") or ""))
        if title_match is not None:
            index = int(title_match.group("index"))
            total = int(title_match.group("total") or 0)
            return index, total
        return None

    def _loop_action_id(self, payload: dict[str, Any], *, definition_id: str) -> str:
        if definition_id:
            return self._strip_loop_index(definition_id)
        raw_id = str(payload.get("step_id", "") or payload.get("id", "") or "").strip()
        return self._strip_loop_index(raw_id)

    def _strip_loop_index(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        text = re.sub(r"^(?:[^:]+:)+", "", text)
        return re.sub(r"(?i)([.:](?:cycle|loop))[.:]\d+([.:])", r"\1\2", text)

    def _failure_analysis_model(self, cases: list[dict[str, Any]]) -> dict[str, Any]:
        explicit_failures = [case.get("failure") for case in cases if isinstance(case.get("failure"), dict) and case.get("failure")]
        if explicit_failures:
            return copy.deepcopy(explicit_failures[0])
        failed_cases = [
            {
                "case_nodeid": item["case"].get("case_nodeid", ""),
                "title": item["case"].get("title", ""),
            }
            for item in cases
            if item["case"].get("status") == "failed"
        ]
        return {
            "status": "failed" if failed_cases else ("stopped" if self._stopped else "passed"),
            "failed_cases": failed_cases,
            "primary_failure": {},
        }

    def _duration_ranking_model(self, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = [
            {
                "title": str(item["case"].get("title") or item["case"].get("case_nodeid") or ""),
                "case_nodeid": str(item["case"].get("case_nodeid") or ""),
                "duration_ms": int(item["case"].get("duration_ms") or 0),
            }
            for item in cases
        ]
        rows.sort(key=lambda row: row["duration_ms"], reverse=True)
        return rows

    def _log_distribution_model(self, logs: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
        levels: dict[str, int] = {}
        domains: dict[str, int] = {}
        for row in logs:
            level = str(row.get("level", "") or "info").lower()
            domain = str(row.get("domain", "") or "framework").lower()
            levels[level] = levels.get(level, 0) + 1
            domains[domain] = domains.get(domain, 0) + 1
        return {"levels": levels, "domains": domains}


_TEST_CONTEXT = TestContext()


def smarttest_context() -> TestContext:
    return _TEST_CONTEXT


def reset_test_context_for_tests() -> None:
    _TEST_CONTEXT.reset_for_tests()


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _json_env(name: str) -> Any:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _omit_apk_param_value(value: Any) -> bool:
    text = str(value or "").strip()
    return text.lower() == "none"
