from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot, QStandardPaths
from PySide6.QtGui import QGuiApplication

from testing.cases.discovery import PytestDiscoveryError, discover_pytest_cases
from testing.params.registry import SchemaRegistry, default_registry
from testing.params.schema import ParamField, ParamSchema, defaults_for_schema
from testing.state.models import SelectedCase, TestPageState
from testing.state.store import load_state, save_state


class TestPageBridge(QObject):
    casesChanged = Signal()
    stateChanged = Signal()
    errorOccurred = Signal(str)

    def __init__(self, root_dir: Path):
        super().__init__(QGuiApplication.instance())
        self._root_dir = root_dir.resolve()
        self._registry: SchemaRegistry = default_registry()
        self._cases: list[dict[str, Any]] = []
        self._state_path = self._default_state_path()
        self._state = load_state(self._state_path)
        self._ensure_state_defaults()

    def _default_state_path(self) -> Path:
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        return Path(base) / "SmartTest" / "test_page_state.json"

    def _ensure_state_defaults(self) -> None:
        global_defaults = defaults_for_schema(self._registry.global_context)
        for key, value in global_defaults.items():
            self._state.global_context.setdefault(key, value)

    def _schema_to_jsonable(self, schema: ParamSchema) -> dict[str, Any]:
        return {
            "schema_id": schema.schema_id,
            "title": schema.title,
            "fields": [self._field_to_jsonable(f) for f in schema.fields],
        }

    def _field_to_jsonable(self, field: ParamField) -> dict[str, Any]:
        return {
            "key": field.key,
            "label": field.label,
            "type": field.type.value if hasattr(field.type, "value") else field.type,
            "default": field.default,
            "description": field.description,
            "group": field.group,
            "required": field.required,
            "enum_values": field.enum_values,
        }

    def _selected_nodeids(self) -> list[str]:
        return [c.nodeid for c in self._state.selected]

    def _matched_case_nodeids(self) -> list[str]:
        selected = set(self._selected_nodeids())
        return [str(item.get("nodeid", "")) for item in self._cases if str(item.get("nodeid", "")) in selected]

    @Slot()
    def discoverCases(self) -> None:
        try:
            cases = discover_pytest_cases(root_dir=self._root_dir)
        except PytestDiscoveryError as e:
            self.errorOccurred.emit(str(e))
            return
        except Exception as e:  # noqa: BLE001
            self.errorOccurred.emit(f"Pytest discovery failed: {e}")
            return

        self._cases = [
            {
                "nodeid": c.nodeid,
                "file": c.file,
                "name": c.name,
                "markers": c.markers,
                "case_type": c.case_type,
                "required_params": c.required_params,
                "required_param_groups": c.required_param_groups,
            }
            for c in cases
        ]
        self.casesChanged.emit()

    @Slot(result="QVariantList")
    def cases(self):
        return self._cases

    @Slot(result="QVariantList")
    def caseRows(self):
        selected = set(self._selected_nodeids())
        rows = [
            {
                "nodeid": str(item.get("nodeid", "")),
                "file": str(item.get("file", "")),
                "name": str(item.get("name", "")),
                "markers": list(item.get("markers", [])),
                "case_type": str(item.get("case_type", "default")),
                "required_params": list(item.get("required_params", [])),
                "required_param_groups": list(item.get("required_param_groups", [])),
                "selected": str(item.get("nodeid", "")) in selected,
            }
            for item in self._cases
        ]
        return rows

    @Slot(result="QVariantList")
    def selectedCases(self):
        selected = [{"nodeid": c.nodeid, "case_type": c.case_type} for c in self._state.selected]
        return selected

    @Slot(result="QVariantList")
    def activeCaseTypes(self):
        types = []
        seen = set()
        for c in self._state.selected:
            if c.case_type in seen:
                continue
            seen.add(c.case_type)
            types.append(c.case_type)
        return types

    @Slot(str, result="QVariantMap")
    def caseTypeSchema(self, case_type: str):
        schema = self._registry.get_case_type_schema(case_type) or self._registry.get_case_type_schema("default")
        if not schema:
            return {}
        return self._schema_to_jsonable(schema)

    @Slot(result="QVariantMap")
    def globalSchema(self):
        return self._schema_to_jsonable(self._registry.global_context)

    @Slot(result="QVariantMap")
    def globalContext(self):
        return dict(self._state.global_context)

    @Slot(str, result="QVariantMap")
    def caseTypeConfig(self, case_type: str):
        return dict(self._state.case_type_configs.get(case_type, {}))

    @Slot(str, bool)
    def setCaseSelected(self, nodeid: str, selected: bool) -> None:
        nodeid = (nodeid or "").strip()
        if not nodeid:
            return
        if selected:
            if any(c.nodeid == nodeid for c in self._state.selected):
                return
            case_type = "default"
            for c in self._cases:
                if c.get("nodeid") == nodeid:
                    case_type = str(c.get("case_type") or "default")
                    break
            self._state.selected.append(SelectedCase(nodeid=nodeid, case_type=case_type))
            self._state.case_configs.setdefault(nodeid, {})
            schema = self._registry.get_case_type_schema(case_type)
            if schema:
                self._state.case_type_configs.setdefault(case_type, defaults_for_schema(schema))
        else:
            self._state.selected = [c for c in self._state.selected if c.nodeid != nodeid]
            self._state.case_configs.pop(nodeid, None)
        self._save_and_emit()

    @Slot(str, result=bool)
    def isCaseSelected(self, nodeid: str) -> bool:
        return any(c.nodeid == nodeid for c in self._state.selected)

    @Slot(int, int)
    def moveSelected(self, from_index: int, to_index: int) -> None:
        if from_index == to_index:
            return
        if from_index < 0 or to_index < 0:
            return
        if from_index >= len(self._state.selected) or to_index >= len(self._state.selected):
            return
        item = self._state.selected.pop(from_index)
        self._state.selected.insert(to_index, item)
        self._save_and_emit()

    @Slot(str, str, "QVariant")
    def setGlobalValue(self, key: str, value: Any) -> None:
        if not key:
            return
        self._state.global_context[key] = value
        self._save_and_emit()

    @Slot(str, str, "QVariant")
    def setCaseTypeValue(self, case_type: str, key: str, value: Any) -> None:
        if not case_type or not key:
            return
        self._state.case_type_configs.setdefault(case_type, {})
        self._state.case_type_configs[case_type][key] = value
        self._save_and_emit()

    @Slot()
    def reloadState(self) -> None:
        self._state = load_state(self._state_path)
        self._ensure_state_defaults()
        self.stateChanged.emit()

    def _save_and_emit(self) -> None:
        save_state(self._state_path, self._state)
        self.stateChanged.emit()
