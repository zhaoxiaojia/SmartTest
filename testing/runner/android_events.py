from __future__ import annotations
import re
from dataclasses import dataclass, field
import uuid
from typing import Mapping

from testing.runtime.events import current_case_nodeid, current_step, emit_event


_DYNAMIC_STEP_ID_RE = re.compile(r"^(?P<prefix>.+?)\.(?P<marker>cycle|loop)\.(?P<index>\d+)\.(?P<tail>.+)$", re.IGNORECASE)
_PLANNED_REPEAT_STEP_ID_RE = re.compile(r"^(?P<prefix>.+?)\.(?P<marker>cycle|loop)\.(?P<tail>.+)$", re.IGNORECASE)
_STAGE_LOOP_RE = re.compile(r"\b(?P<marker>cycle|loop)\s+(?P<index>\d+)\s*/\s*(?P<total>\d+)\b", re.IGNORECASE)
_TERMINAL_STATUSES = {"passed", "failed", "skipped", "stopped"}


@dataclass
class _Step:
    title: str
    kind: str
    definition_id: str
    step_id: str = field(default_factory=lambda: f"step:{uuid.uuid4().hex}")
    expected: object = ""
    parent_id: str | None = None
    started: bool = False
    finished: bool = False
    enabled: bool = False

    def __post_init__(self) -> None:
        self.enabled = _emit_step("step_planned", self)

    def start(self) -> None:
        if self.enabled and not self.started:
            self.started = _emit_step("step_started", self)

    def evidence(self, title: str, content: object, *, evidence_type: str = "log", level: str = "info") -> None:
        case_nodeid = current_case_nodeid()
        if not self.enabled or not case_nodeid:
            return
        emit_event(
            "step_evidence",
            case_nodeid=case_nodeid,
            step_id=self.step_id,
            title=title,
            evidence_type=evidence_type,
            level=level,
            content=content,
            meta={},
        )

    def finish(self, status: str, *, error: str = "", actual: object = "") -> None:
        if not self.enabled or self.finished:
            return
        self.start()
        self.finished = True
        case_nodeid = current_case_nodeid()
        if case_nodeid:
            emit_event(
                "step_finished",
                step_id=self.step_id,
                case_nodeid=case_nodeid,
                status=status,
                title=self.title,
                kind=self.kind,
                definition_id=self.definition_id,
                error=error,
                actual=actual,
            )


def _emit_step(event_type: str, step: _Step) -> bool:
    case_nodeid = current_case_nodeid()
    if not case_nodeid:
        return False
    parent = current_step()
    emit_event(
        event_type,
        step_id=step.step_id,
        case_nodeid=case_nodeid,
        parent_id=step.parent_id if step.parent_id is not None else (parent["id"] if parent else None),
        title=step.title,
        phase="call",
        kind=step.kind,
        definition_id=step.definition_id,
        meta={"definition_id": step.definition_id},
        expected=step.expected,
    )
    return True


class AndroidClientStageTracker:
    def __init__(self, *, case_id: str, request_id: str) -> None:
        self._case_id = case_id
        self._request_id = request_id
        self._parent = _Step(
            title=f"Run android_client case: {case_id}",
            kind="action",
            definition_id="android_client.run_case",
            expected="android_client reports Completed with zero failed cases.",
        )
        self._parent.start()
        self._current_stage: _Step | None = None
        self._current_stage_key = ""
        self._planned_steps: dict[str, _Step] = {}
        self._dynamic_steps: dict[str, _Step] = {}
        self._terminal = False

    def evidence(self, title: str, content: object, *, evidence_type: str = "log", level: str = "info") -> None:
        self._parent.evidence(title, content, evidence_type=evidence_type, level=level)

    def observe_snapshot(self, snapshot: Mapping[str, object]) -> None:
        if not self._parent.enabled:
            return
        self.evidence(
            "android snapshot",
            "",
            evidence_type="status",
            level="info",
        )
        self._sync_planned_steps(snapshot)
        self._sync_step_states(snapshot)
        if self._planned_steps:
            return
        phase = str(snapshot.get("phase", "") or "").strip()
        stage = str(snapshot.get("currentStage", "") or "").strip() or phase or "waiting for android_client status"
        stage_key = f"{phase}:{stage}"
        if stage_key == self._current_stage_key:
            return
        if self._current_stage is not None:
            self._current_stage.finish("passed")
        self._current_stage_key = stage_key
        self._current_stage = _Step(
            title=stage,
            kind="external",
            definition_id="android_client.stage",
            expected="android_client advances to the next stage or terminal status.",
            parent_id=self._parent.step_id,
        )
        self._current_stage.start()

    def _sync_planned_steps(self, snapshot: Mapping[str, object]) -> None:
        planned_steps = snapshot.get("plannedSteps", [])
        if not isinstance(planned_steps, list):
            return
        for item in planned_steps:
            if not isinstance(item, dict):
                continue
            raw_id = str(item.get("id", "") or "").strip()
            if not raw_id or raw_id in self._planned_steps:
                continue
            self._planned_steps[raw_id] = _Step(
                step_id=f"{self._request_id}:{raw_id}",
                title=str(item.get("title", "") or raw_id),
                kind=str(item.get("kind", "") or "action"),
                definition_id=str(item.get("definitionId", "") or raw_id),
                expected=str(item.get("expected", "") or ""),
                parent_id=self._parent.step_id,
            )

    def _sync_step_states(self, snapshot: Mapping[str, object]) -> None:
        states = snapshot.get("stepStates", [])
        if not isinstance(states, list):
            return
        for item in states:
            if not isinstance(item, dict):
                continue
            raw_id = str(item.get("id", "") or "").strip()
            step = self._planned_steps.get(raw_id) or self._dynamic_step(raw_id=raw_id, snapshot=snapshot)
            if step is None:
                self._parent.evidence(
                    "[steps.debug.android_unresolved]",
                    {
                        "raw_id": raw_id,
                        "status": str(item.get("status", "") or ""),
                        "currentStage": str(snapshot.get("currentStage", "") or ""),
                        "currentLoop": snapshot.get("currentLoop", ""),
                        "totalLoops": snapshot.get("totalLoops", ""),
                        "known_planned_ids": sorted(self._planned_steps.keys()),
                        "known_dynamic_ids": sorted(self._dynamic_steps.keys()),
                    },
                    evidence_type="log",
                    level="warning",
                )
                continue
            runtime_title = self._runtime_step_title(raw_id=raw_id, step=step, snapshot=snapshot)
            if runtime_title:
                step.title = runtime_title
            status = str(item.get("status", "") or "").strip()
            if status == "running":
                step.start()
            elif status in _TERMINAL_STATUSES:
                step.finish(status, actual=item.get("actual", ""), error=str(item.get("error", "") or ""))

    def _dynamic_step(self, *, raw_id: str, snapshot: Mapping[str, object]) -> _Step | None:
        if not raw_id:
            return None
        existing = self._dynamic_steps.get(raw_id)
        if existing is not None:
            return existing
        match = _DYNAMIC_STEP_ID_RE.match(raw_id)
        if match is None:
            return None
        step = _Step(
            step_id=f"{self._request_id}:{raw_id}",
            title=self._dynamic_step_title(raw_id=raw_id, snapshot=snapshot),
            kind=self._dynamic_step_kind(match.group("tail")),
            definition_id=f"{match.group('prefix')}.{match.group('marker')}.{match.group('tail')}",
            expected="android_client reports this cycle step finished.",
            parent_id=self._parent.step_id,
        )
        self._dynamic_steps[raw_id] = step
        return step

    def _dynamic_step_title(self, *, raw_id: str, snapshot: Mapping[str, object]) -> str:
        match = _DYNAMIC_STEP_ID_RE.match(raw_id)
        if match is None:
            return raw_id
        marker, index, total = self._snapshot_loop_marker(snapshot)
        label = f"{match.group('marker').capitalize()} {match.group('index')}"
        if marker:
            label = f"{marker.capitalize()} {match.group('index')}"
        tail = match.group("tail").replace("_", " ")
        return f"{label}/{total}: {tail}" if total else f"{label}: {tail}"

    def _runtime_step_title(self, *, raw_id: str, step: _Step, snapshot: Mapping[str, object]) -> str:
        dynamic_match = _DYNAMIC_STEP_ID_RE.match(raw_id)
        if dynamic_match is not None:
            return self._dynamic_step_title(raw_id=raw_id, snapshot=snapshot)
        planned_match = _PLANNED_REPEAT_STEP_ID_RE.match(raw_id)
        if planned_match is None:
            return step.title
        marker, index, total = self._snapshot_loop_marker(snapshot)
        if not index or not total:
            return step.title
        title = str(step.title or raw_id)
        suffix = re.sub(r"^(Cycle|Loop)\s*(\d+\s*/\s*\d+)?\s*:\s*", "", title, count=1, flags=re.IGNORECASE).strip()
        prefix = marker.capitalize() if marker else planned_match.group("marker").capitalize()
        return f"{prefix} {index}/{total}: {suffix or planned_match.group('tail').replace('_', ' ')}"

    def _snapshot_loop_marker(self, snapshot: Mapping[str, object]) -> tuple[str, str, str]:
        stage_match = _STAGE_LOOP_RE.search(str(snapshot.get("currentStage", "") or ""))
        marker = stage_match.group("marker") if stage_match else ""
        index = stage_match.group("index") if stage_match else str(snapshot.get("currentLoop", "") or "")
        total = stage_match.group("total") if stage_match else str(snapshot.get("totalLoops", "") or "")
        return marker, index, total

    def _dynamic_step_kind(self, tail: str) -> str:
        normalized = str(tail or "").lower()
        return "check" if any(token in normalized for token in ("check", "verify", "capture", "ping", "bluetooth")) else "step"

    def status_waiting(self, reason: str) -> None:
        target = self._current_stage or self._parent
        target.evidence("Status channel waiting", reason, evidence_type="status", level="warning")

    def finish(self, status: str, *, error: str = "", actual: object = "") -> None:
        if self._terminal:
            return
        self._terminal = True
        if self._planned_steps:
            for step in self._planned_steps.values():
                if step.started:
                    step.finish("stopped" if status == "failed" else status)
        elif self._current_stage is not None:
            self._current_stage.finish(status, error=error if status == "failed" else "", actual=actual)
        self._parent.finish(status, error=error, actual=actual)
