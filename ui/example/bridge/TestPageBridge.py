from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot, QStandardPaths
from PySide6.QtGui import QGuiApplication

from testing.cases.discovery import PytestDiscoveryError, discover_pytest_cases
from testing.params.adb_devices import list_adb_devices
from testing.params.registry import SchemaRegistry, default_registry
from testing.params.schema import ParamField, ParamSchema, ParamScope, defaults_for_schema
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
        self._cases_by_nodeid: dict[str, dict[str, Any]] = {}
        self._cases_by_file: dict[str, list[dict[str, Any]]] = {}
        self._state_path = self._default_state_path()
        self._state = load_state(self._state_path)
        self._adb_devices: list[str] = []
        self._ensure_state_defaults()

    def _default_state_path(self) -> Path:
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        return Path(base) / "SmartTest" / "test_page_state.json"

    def _ensure_state_defaults(self) -> None:
        global_defaults = defaults_for_schema(self._registry.global_context)
        legacy_dut = self._state.global_context.get("dut_model")
        if "dut" not in self._state.global_context and legacy_dut not in (None, ""):
            self._state.global_context["dut"] = legacy_dut
        self._state.global_context = {
            key: value for key, value in self._state.global_context.items() if key in global_defaults
        }
        for key, value in global_defaults.items():
            self._state.global_context.setdefault(key, value)
        if not hasattr(self._state, "selected_files"):
            self._state.selected_files = []

    def _refresh_adb_devices(self) -> None:
        self._adb_devices = list_adb_devices()

    def _sync_dut_selection(self) -> bool:
        current = str(self._state.global_context.get("dut", "") or "").strip()
        if current and current in self._adb_devices:
            return False
        if len(self._adb_devices) == 1:
            only_device = self._adb_devices[0]
            if current != only_device:
                self._state.global_context["dut"] = only_device
                return True
            return False
        if current:
            self._state.global_context["dut"] = ""
            return True
        return False

    def _field_label(self, field: ParamField) -> str:
        if field.key == "dut":
            return self.tr("DUT")
        return field.label

    def _schema_to_jsonable(self, schema: ParamSchema) -> dict[str, Any]:
        return {
            "schema_id": schema.schema_id,
            "title": schema.title,
            "fields": [self._field_to_jsonable(f) for f in schema.fields],
        }

    def _field_to_jsonable(self, field: ParamField) -> dict[str, Any]:
        return {
            "key": field.key,
            "label": self._field_label(field),
            "type": field.type.value if hasattr(field.type, "value") else field.type,
            "category": field.category.value if hasattr(field.category, "value") else field.category,
            "scope": field.scope.value if hasattr(field.scope, "value") else field.scope,
            "default": field.default,
            "description": field.description,
            "group": field.group,
            "required": field.required,
            "enum_values": self._enum_values_for_field(field),
        }

    def _enum_values_for_field(self, field: ParamField) -> list[str]:
        if field.key == "dut":
            return list(self._adb_devices)
        return list(field.enum_values)

    def _rebuild_case_indexes(self) -> None:
        self._cases_by_nodeid = {}
        self._cases_by_file = {}
        for case in self._cases:
            nodeid = str(case.get("nodeid", "")).strip()
            file_path = str(case.get("file", "")).strip()
            if nodeid:
                self._cases_by_nodeid[nodeid] = case
            if file_path:
                self._cases_by_file.setdefault(file_path, []).append(case)

    def _case_info(self, nodeid: str) -> dict[str, Any] | None:
        normalized = (nodeid or "").strip()
        if not normalized:
            return None
        return self._cases_by_nodeid.get(normalized)

    def _field_for_key(self, key: str) -> ParamField | None:
        normalized = (key or "").strip()
        if not normalized:
            return None
        return self._registry.get_param(normalized)

    def _cases_for_file(self, file_path: str) -> list[dict[str, Any]]:
        normalized = (file_path or "").strip()
        if not normalized:
            return []
        return list(self._cases_by_file.get(normalized, ()))

    def _trimmed_case_path(self, file_path: str) -> str:
        path = str(file_path or "").strip()
        prefix = "testing/tests/"
        if path.startswith(prefix):
            return path[len(prefix) :]
        return path

    def _file_base_name(self, file_path: str) -> str:
        short_file = self._trimmed_case_path(file_path)
        return short_file.split("/")[-1] if short_file else short_file

    def _selected_file_paths_from_cases(self) -> list[str]:
        file_paths: list[str] = []
        seen: set[str] = set()
        for selected in self._state.selected:
            case_info = self._case_info(selected.nodeid)
            if case_info is None:
                continue
            file_path = str(case_info.get("file", "")).strip()
            if not file_path or file_path in seen:
                continue
            seen.add(file_path)
            file_paths.append(file_path)
        return file_paths

    def _reorder_selected_cases_by_file_order(self) -> bool:
        if not self._cases or not self._state.selected:
            return False

        grouped: dict[str, list[SelectedCase]] = {}
        remaining_files: list[str] = []
        for selected in self._state.selected:
            case_info = self._case_info(selected.nodeid)
            if case_info is None:
                continue
            file_path = str(case_info.get("file", "")).strip()
            if not file_path:
                continue
            grouped.setdefault(file_path, []).append(selected)
            if file_path not in remaining_files:
                remaining_files.append(file_path)

        ordered_files = [path for path in self._state.selected_files if path in grouped]
        ordered_files.extend(path for path in remaining_files if path not in ordered_files)
        reordered: list[SelectedCase] = []
        for file_path in ordered_files:
            reordered.extend(grouped.get(file_path, []))

        if [c.nodeid for c in reordered] == [c.nodeid for c in self._state.selected]:
            return False
        self._state.selected = reordered
        return True

    def _sync_selected_file_order(self) -> bool:
        selected_files = self._selected_file_paths_from_cases()
        next_order: list[str] = []
        seen: set[str] = set()

        for file_path in self._state.selected_files:
            if file_path in selected_files and file_path not in seen:
                seen.add(file_path)
                next_order.append(file_path)

        for file_path in selected_files:
            if file_path not in seen:
                seen.add(file_path)
                next_order.append(file_path)

        if next_order == self._state.selected_files:
            return False
        self._state.selected_files = next_order
        return True

    def _resolve_case_value(self, *, nodeid: str, key: str) -> Any:
        case = self._case_info(nodeid)
        field = self._field_for_key(key)
        if case is None or field is None:
            return None

        if field.scope == ParamScope.GLOBAL_CONTEXT:
            return self._state.global_context.get(field.key, field.default)

        if field.scope == ParamScope.CASE_TYPE_SHARED:
            case_type = str(case.get("case_type") or "default")
            case_type_values = self._state.case_type_configs.get(case_type, {})
            return case_type_values.get(field.key, field.default)

        case_values = self._state.case_configs.get(str(case.get("nodeid", "")), {})
        return case_values.get(field.key, field.default)

    def _set_case_param_value(self, *, nodeid: str, key: str, value: Any) -> bool:
        case = self._case_info(nodeid)
        field = self._field_for_key(key)
        if case is None or field is None:
            return False

        if field.scope == ParamScope.GLOBAL_CONTEXT:
            if self._state.global_context.get(field.key) == value:
                return False
            self._state.global_context[field.key] = value
            return True

        if field.scope == ParamScope.CASE_TYPE_SHARED:
            case_type = str(case.get("case_type") or "default")
            self._state.case_type_configs.setdefault(case_type, {})
            if self._state.case_type_configs[case_type].get(field.key) == value:
                return False
            self._state.case_type_configs[case_type][field.key] = value
            return True

        case_nodeid = str(case.get("nodeid", "")).strip()
        if not case_nodeid:
            return False
        self._state.case_configs.setdefault(case_nodeid, {})
        if self._state.case_configs[case_nodeid].get(field.key) == value:
            return False
        self._state.case_configs[case_nodeid][field.key] = value
        return True

    def _selected_nodeids(self) -> list[str]:
        return [c.nodeid for c in self._state.selected]

    def _set_case_selected(self, nodeid: str, selected: bool) -> bool:
        normalized = (nodeid or "").strip()
        if not normalized:
            return False

        if selected:
            if any(c.nodeid == normalized for c in self._state.selected):
                return False
            case_type = "default"
            for case in self._cases:
                if case.get("nodeid") == normalized:
                    case_type = str(case.get("case_type") or "default")
                    break
            self._state.selected.append(SelectedCase(nodeid=normalized, case_type=case_type))
            case_info = self._case_info(normalized)
            if case_info is not None:
                file_path = str(case_info.get("file", "")).strip()
                if file_path and file_path not in self._state.selected_files:
                    self._state.selected_files.append(file_path)
            self._state.case_configs.setdefault(normalized, {})
            schema = self._registry.get_case_type_schema(case_type)
            if schema:
                self._state.case_type_configs.setdefault(case_type, defaults_for_schema(schema))
            return True

        original_len = len(self._state.selected)
        self._state.selected = [case for case in self._state.selected if case.nodeid != normalized]
        case_info = self._case_info(normalized)
        if case_info is not None:
            file_path = str(case_info.get("file", "")).strip()
            if file_path:
                still_selected = any(
                    str((self._case_info(case.nodeid) or {}).get("file", "")).strip() == file_path
                    for case in self._state.selected
                )
                if not still_selected:
                    self._state.selected_files = [path for path in self._state.selected_files if path != file_path]
        # Keep per-case configs on deselect so previously entered values can be restored
        # when the user selects the same case again in a later session.
        return len(self._state.selected) != original_len

    @Slot()
    def discoverCases(self) -> None:
        try:
            cases = discover_pytest_cases(root_dir=self._root_dir, python_executable=sys.executable)
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
        self._rebuild_case_indexes()
        changed = self._sync_selected_file_order()
        changed = self._reorder_selected_cases_by_file_order() or changed
        if changed:
            save_state(self._state_path, self._state)
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
    def selectedFiles(self):
        self._sync_selected_file_order()
        return list(self._state.selected_files)

    @Slot(result="QVariantList")
    def selectedFileRows(self):
        self._sync_selected_file_order()
        rows: list[dict[str, Any]] = []
        for file_path in self._state.selected_files:
            rows.append(
                {
                    "file": file_path,
                    "name": self._file_base_name(file_path),
                    "short_file": self._trimmed_case_path(file_path),
                }
            )
        return rows

    @Slot(result="QVariantList")
    def selectedCaseParamRows(self):
        self._sync_selected_file_order()
        rows: list[dict[str, Any]] = []
        for file_path in self._state.selected_files:
            for case in self._cases_for_file(file_path):
                rows.append(
                    {
                        "nodeid": str(case.get("nodeid", "")),
                        "file": str(case.get("file", "")),
                        "name": str(case.get("name", "")),
                        "case_type": str(case.get("case_type", "default")),
                        "required_params": list(case.get("required_params", [])),
                        "required_param_groups": list(case.get("required_param_groups", [])),
                    }
                )
        return rows

    @Slot(result="QVariantList")
    def activeCaseTypes(self):
        types: list[str] = []
        seen: set[str] = set()
        self._sync_selected_file_order()
        for file_path in self._state.selected_files:
            for case in self._cases_for_file(file_path):
                case_type = str(case.get("case_type", "default"))
                if case_type in seen:
                    continue
                seen.add(case_type)
                types.append(case_type)
        return types

    @Slot(str, "QVariantList", result="QVariantList")
    def caseTree(self, filter_text: str, expanded_keys: list[Any]):
        selected_files = set(self.selectedFiles())
        expanded = {str(item) for item in (expanded_keys or []) if str(item)}
        normalized_filter = str(filter_text or "").strip().lower()

        root: dict[str, Any] = {"folders": [], "files": []}

        def case_matches(file_path: str, case_name: str) -> bool:
            if not normalized_filter:
                return True
            short_file = self._trimmed_case_path(file_path).lower()
            return (
                normalized_filter in str(file_path or "").lower()
                or normalized_filter in short_file
                or normalized_filter in str(case_name or "").lower()
            )

        def sort_nodes(nodes: list[dict[str, Any]]) -> None:
            nodes.sort(key=lambda item: str(item.get("label", "")))

        for case in self._cases:
            file_path = str(case.get("file", "")).strip()
            if not file_path:
                continue
            if not case_matches(file_path, str(case.get("name", ""))):
                continue

            short_file = self._trimmed_case_path(file_path)
            parts = short_file.split("/") if short_file else []
            folder_parts = parts[:-1]
            file_name = parts[-1] if parts else short_file
            parent = root
            folder_path = ""
            for part in folder_parts:
                folder_path = f"{folder_path}/{part}" if folder_path else part
                folder_key = f"folder:{folder_path}"
                folder_node = next((item for item in parent["folders"] if item["key"] == folder_key), None)
                if folder_node is None:
                    folder_node = {"key": folder_key, "label": part, "folders": [], "files": []}
                    parent["folders"].append(folder_node)
                parent = folder_node

            file_key = f"file:{short_file}"
            if not any(item["key"] == file_key for item in parent["files"]):
                parent["files"].append(
                    {
                        "key": file_key,
                        "label": file_name,
                        "file": file_path,
                        "checked": file_path in selected_files,
                    }
                )

        force_expand = bool(normalized_filter)

        def build_folder(node: dict[str, Any]) -> dict[str, Any]:
            sort_nodes(node["folders"])
            sort_nodes(node["files"])
            children = [build_folder(item) for item in node["folders"]]
            children.extend(build_file(item) for item in node["files"])
            return {
                "title": node["label"],
                "_key": node["key"],
                "rowType": "folder",
                "iconSource": "Folder",
                "expanded": force_expand or node["key"] in expanded,
                "children": children,
            }

        def build_file(node: dict[str, Any]) -> dict[str, Any]:
            return {
                "title": node["label"],
                "_key": node["key"],
                "rowType": "file",
                "iconSource": "Document",
                "file": node["file"],
                "checked": node["checked"],
            }

        sort_nodes(root["folders"])
        sort_nodes(root["files"])
        children = [build_folder(item) for item in root["folders"]]
        children.extend(build_file(item) for item in root["files"])
        if not children:
            return []
        return [
            {
                "title": "tests",
                "_key": "root:tests",
                "rowType": "root",
                "iconSource": "Folder",
                "expanded": True,
                "children": children,
            }
        ]

    @Slot(str, result="QVariantMap")
    def caseTypeSchema(self, case_type: str):
        schema = self._registry.get_case_type_schema(case_type) or self._registry.get_case_type_schema("default")
        if not schema:
            return {}
        return self._schema_to_jsonable(schema)

    @Slot(result="QVariantMap")
    def globalSchema(self):
        self._refresh_adb_devices()
        changed = self._sync_dut_selection()
        if changed:
            save_state(self._state_path, self._state)
        return self._schema_to_jsonable(self._registry.global_context)

    @Slot()
    def refreshGlobalSchema(self) -> None:
        self._refresh_adb_devices()
        changed = self._sync_dut_selection()
        if changed:
            save_state(self._state_path, self._state)
        self.stateChanged.emit()

    @Slot(result="QVariantMap")
    def globalContext(self):
        return dict(self._state.global_context)

    @Slot(str, result="QVariantMap")
    def caseTypeConfig(self, case_type: str):
        return dict(self._state.case_type_configs.get(case_type, {}))

    @Slot(str, result="QVariantList")
    def caseParamFields(self, nodeid: str):
        case = self._case_info(nodeid)
        if case is None:
            return []
        required_params = list(case.get("required_params", []))
        return [
            self._field_to_jsonable(field)
            for param_key in required_params
            if (field := self._field_for_key(str(param_key))) is not None
        ]

    @Slot(str, str, result="QVariant")
    def caseParamValue(self, nodeid: str, key: str):
        return self._resolve_case_value(nodeid=nodeid, key=key)

    @Slot(str, bool)
    def setCaseSelected(self, nodeid: str, selected: bool) -> None:
        if not self._set_case_selected(nodeid, selected):
            return
        self._save_and_emit()

    @Slot(str, bool)
    def setFileSelected(self, file_path: str, selected: bool) -> None:
        cases = self._cases_for_file(file_path)
        if not cases:
            return
        changed = False
        normalized = (file_path or "").strip()
        if selected and normalized and normalized not in self._state.selected_files:
            self._state.selected_files.append(normalized)
            changed = True
        if not selected and normalized:
            next_files = [path for path in self._state.selected_files if path != normalized]
            if next_files != self._state.selected_files:
                self._state.selected_files = next_files
                changed = True
        for case in cases:
            changed = self._set_case_selected(str(case.get("nodeid", "")), selected) or changed
        if not changed:
            return
        self._sync_selected_file_order()
        self._reorder_selected_cases_by_file_order()
        self._save_and_emit()

    @Slot(str, result=bool)
    def isCaseSelected(self, nodeid: str) -> bool:
        return any(c.nodeid == nodeid for c in self._state.selected)

    @Slot(int, int)
    def moveSelected(self, from_index: int, to_index: int) -> None:
        self.moveSelectedFile(from_index, to_index)

    @Slot(int, int)
    def moveSelectedFile(self, from_index: int, to_index: int) -> None:
        if from_index == to_index:
            return
        if from_index < 0 or to_index < 0:
            return
        if from_index >= len(self._state.selected_files) or to_index >= len(self._state.selected_files):
            return
        item = self._state.selected_files.pop(from_index)
        self._state.selected_files.insert(to_index, item)
        self._reorder_selected_cases_by_file_order()
        self._save_and_emit()

    @Slot(str, str, "QVariant")
    def setGlobalValue(self, key: str, value: Any) -> None:
        if not key:
            return
        if self._state.global_context.get(key) == value:
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

    @Slot(str, str, "QVariant")
    def setCaseParamValue(self, nodeid: str, key: str, value: Any) -> None:
        if not self._set_case_param_value(nodeid=nodeid, key=key, value=value):
            return
        self._save_and_emit()

    @Slot()
    def reloadState(self) -> None:
        self._state = load_state(self._state_path)
        self._ensure_state_defaults()
        changed = self._sync_selected_file_order()
        changed = self._reorder_selected_cases_by_file_order() or changed
        if changed:
            save_state(self._state_path, self._state)
        self.stateChanged.emit()

    def _save_and_emit(self) -> None:
        save_state(self._state_path, self._state)
        self.stateChanged.emit()
