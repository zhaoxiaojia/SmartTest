from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from threading import Thread
import time
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QGuiApplication

from testing.cases.catalog import is_packaged_runtime, load_packaged_test_catalog
from testing.cases.discovery import PytestDiscoveryError, discover_pytest_cases
from testing.params.options import normalize_option_values, option_cache_key
from testing.params.registry import SchemaRegistry, default_registry
from testing.params.runtime import runtime_params
from testing.params.requirements import required_params_for_case
from testing.params.schema import ParamField, ParamSchema, ParamScope, ParamValueType, defaults_for_schema
from testing.state.models import SelectedCase, TestPageState
from testing.state.store import ensure_state, load_state, save_state
from testing.tool.dut_tool.parameter_adapter import DutParameterAdapter

try:
    from example.helper.AppPaths import app_data_dir
    from example.helper.TranslateHelper import TranslateHelper
    from example.helper.TsTextCatalog import TsTextCatalog
except ImportError:  # pragma: no cover - direct unit-test imports may use the ui.example package path
    from ui.example.helper.AppPaths import app_data_dir
    from ui.example.helper.TranslateHelper import TranslateHelper
    from ui.example.helper.TsTextCatalog import TsTextCatalog


class TestPageBridge(QObject):
    casesChanged = Signal()
    stateChanged = Signal()
    errorOccurred = Signal(str)
    _discoveryResult = Signal("QVariantList", int)
    _discoveryError = Signal(str, int)
    _adbRefreshResult = Signal("QVariantList", int)
    _paramOptionsRefreshResult = Signal("QVariantMap")

    def __init__(self, root_dir: Path):
        super().__init__(QGuiApplication.instance())
        self._root_dir = root_dir.resolve()
        self._registry: SchemaRegistry = default_registry()
        self._cases: list[dict[str, Any]] = []
        self._cases_by_nodeid: dict[str, dict[str, Any]] = {}
        self._cases_by_file: dict[str, list[dict[str, Any]]] = {}
        self._state_path = self._default_state_path()
        self._trace_log_path = self._state_path.parent / "test_page_trace.log"
        self._text_catalog = TsTextCatalog(self._root_dir, trace=self._trace)
        self._dut_parameter_adapter = DutParameterAdapter()
        self._state = ensure_state(self._state_path)
        self._adb_devices: list[str] = []
        self._param_options: dict[str, list[str]] = {}
        self._adb_refresh_running = False
        self._adb_refresh_started = False
        self._param_options_refreshing: set[str] = set()
        self._discovery_running = False
        self._discovery_loaded = False
        self._discoveryResult.connect(self._apply_discovery_result)
        self._discoveryError.connect(self._apply_discovery_error)
        self._adbRefreshResult.connect(self._apply_adb_refresh_result)
        self._paramOptionsRefreshResult.connect(self._apply_param_options_refresh_result)
        TranslateHelper().currentChanged.connect(self._handle_language_changed)
        state_changed = self._ensure_state_defaults()
        state_changed = self._sync_dut_selection() or state_changed
        if state_changed:
            save_state(self._state_path, self._state)

    def _trace(self, stage: str, **values: Any) -> None:
        details = " ".join(f"{key}={values[key]}" for key in sorted(values))
        line = f"{_trace_timestamp()} [TEST_UI] {stage} {details}".rstrip()
        print(line)
        try:
            self._trace_log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._trace_log_path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except Exception:
            pass

    def _default_state_path(self) -> Path:
        return app_data_dir() / "test_page_state.json"

    def _ensure_state_defaults(self) -> bool:
        changed = False
        global_defaults = defaults_for_schema(self._registry.global_context)
        legacy_dut = self._state.global_context.get("dut_model")
        if "dut" not in self._state.global_context and legacy_dut not in (None, ""):
            self._state.global_context["dut"] = legacy_dut
            changed = True
        preserved_global_keys = {*global_defaults, "equipment", "test_equipment"}
        next_global_context = {
            key: value for key, value in self._state.global_context.items() if key in preserved_global_keys
        }
        if next_global_context != self._state.global_context:
            changed = True
        self._state.global_context = next_global_context
        for key, value in global_defaults.items():
            if key not in self._state.global_context:
                self._state.global_context[key] = value
                changed = True
        if not hasattr(self._state, "selected_files"):
            self._state.selected_files = []
            changed = True
        changed = self._migrate_local_playback_storage_paths() or changed
        changed = self._prune_stored_fixed_enum_values() or changed
        return changed

    def _migrate_local_playback_storage_paths(self) -> bool:
        old_default = "/storage/emulated/0/Movies"
        legacy_default = "/mnt/media_rw"
        legacy_movies_default = "/mnt/media_rw/*/Movies"
        new_default = "/storage/*/Movies /storage/*/Video"
        changed = False
        for params in self._state.case_parameters.values():
            if not isinstance(params, dict):
                continue
            media_dir = params.get("local_playback_stress:media_dir")
            if media_dir in (old_default, legacy_default, legacy_movies_default):
                params["local_playback_stress:media_dir"] = new_default
                changed = True
            elif isinstance(media_dir, str) and media_dir.startswith("/mnt/media_rw/"):
                params["local_playback_stress:media_dir"] = _storage_playback_path(media_dir)
                changed = True
            media_files = params.get("local_playback_stress:media_files")
            if isinstance(media_files, list):
                next_files = [_storage_playback_path(str(value or "").strip()) for value in media_files]
                if next_files != media_files:
                    params["local_playback_stress:media_files"] = next_files
                    changed = True
        return changed

    def _prune_stored_fixed_enum_values(self) -> bool:
        changed = False
        for values in (
            self._state.global_context,
            *self._state.case_type_configs.values(),
            *self._state.case_parameters.values(),
        ):
            if not isinstance(values, dict):
                continue
            for key in list(values.keys()):
                field = self._field_for_key(key)
                if field is None or field.options_source or not field.enum_values:
                    continue
                if self._is_multi_enum_field(field):
                    current = normalize_option_values(values.get(key, []))
                    next_values = [value for value in current if value in field.enum_values]
                    if next_values == current:
                        continue
                    values[key] = next_values
                    self._trace(
                        "param_fixed_enum_pruned",
                        field=key,
                        removed=len(current) - len(next_values),
                        kept=len(next_values),
                    )
                    changed = True
                    continue
                field_type = field.type.value if hasattr(field.type, "value") else field.type
                if field_type == ParamValueType.ENUM.value and values.get(key) not in field.enum_values:
                    values[key] = field.default
                    self._trace("param_fixed_enum_reset", field=key)
                    changed = True
        return changed

    def _refresh_adb_devices(self) -> None:
        self._adb_devices = self._dut_parameter_adapter.refresh_duts()

    def _load_cached_adb_devices(self) -> list[str]:
        return []

    def _save_cached_adb_devices(self, devices: list[str]) -> None:
        return

    def _handle_language_changed(self) -> None:
        self.stateChanged.emit()

    def _schedule_adb_refresh(self, reason: str) -> None:
        if self._adb_refresh_running:
            self._trace("adb_refresh_skip_running", reason=reason)
            return
        self._adb_refresh_running = True
        self._trace("adb_refresh_start", reason=reason)
        selected_serial = self._current_dut_serial() if reason == "user_refresh" else ""
        Thread(target=self._refresh_adb_devices_worker, args=(selected_serial,), daemon=True).start()

    def _current_dut_serial(self) -> str:
        return str(self._state.global_context.get("dut", "") or "").strip()

    def _schedule_param_options_refresh(self, source: str, reason: str, *, nodeid: str = "") -> None:
        normalized_source = str(source or "").strip()
        if not normalized_source:
            self._trace("param_options_refresh_skip_empty_source", reason=reason)
            return
        selected_serial = self._current_dut_serial()
        normalized_nodeid = str(nodeid or "").strip()
        cache_key = _param_options_cache_key(normalized_source, selected_serial, normalized_nodeid)
        if cache_key in self._param_options_refreshing:
            self._trace(
                "param_options_refresh_skip_running",
                reason=reason,
                source=normalized_source,
                dut=selected_serial or "<default>",
                cache_key=cache_key,
                nodeid=normalized_nodeid or "<none>",
            )
            return
        self._param_options_refreshing.add(cache_key)
        self._trace(
            "param_options_refresh_start",
            reason=reason,
            source=normalized_source,
            dut=selected_serial or "<default>",
            cache_key=cache_key,
            nodeid=normalized_nodeid or "<none>",
        )
        Thread(
            target=self._refresh_param_options_worker,
            args=(normalized_source, selected_serial, cache_key, normalized_nodeid),
            daemon=True,
        ).start()

    def _refresh_adb_devices_worker(self, selected_serial: str = "") -> None:
        started_at = time.monotonic()
        devices = self._dut_parameter_adapter.refresh_duts(selected_serial=selected_serial)
        self._adbRefreshResult.emit(devices, int((time.monotonic() - started_at) * 1000))

    def _refresh_param_options_worker(self, source: str, selected_serial: str, cache_key: str, nodeid: str) -> None:
        started_at = time.monotonic()
        payload: dict[str, Any] = {
            "source": source,
            "dut": selected_serial,
            "cache_key": cache_key,
            "nodeid": nodeid,
            "options": [],
            "error": "",
            "elapsed_ms": 0,
        }
        result = self._dut_parameter_adapter.refresh_case_parameter_options(
            source,
            selected_serial or None,
            nodeid=nodeid,
        )
        payload["options"] = result.options
        payload["error"] = result.error
        payload["elapsed_ms"] = int((time.monotonic() - started_at) * 1000)
        self._paramOptionsRefreshResult.emit(payload)

    @Slot("QVariantList", int)
    def _apply_adb_refresh_result(self, devices: list[Any], elapsed_ms: int) -> None:
        self._adb_refresh_running = False
        normalized: list[str] = []
        for value in devices:
            serial = str(value or "").strip()
            if serial and serial not in normalized:
                normalized.append(serial)
        self._adb_devices = normalized
        self._save_cached_adb_devices(self._adb_devices)
        changed = self._sync_dut_selection()
        if changed:
            save_state(self._state_path, self._state)
        self._trace("adb_refresh_done", devices=len(self._adb_devices), elapsed_ms=elapsed_ms)
        self._refresh_selected_param_options("adb_refresh_done")
        self.stateChanged.emit()

    @Slot("QVariantMap")
    def _apply_param_options_refresh_result(self, payload: dict[str, Any]) -> None:
        source = str(payload.get("source", "") or "").strip()
        cache_key = str(payload.get("cache_key", "") or "").strip()
        elapsed_ms = int(payload.get("elapsed_ms", 0) or 0)
        error = str(payload.get("error", "") or "").strip()
        if cache_key:
            self._param_options_refreshing.discard(cache_key)
        if error:
            self._trace(
                "param_options_refresh_error",
                source=source,
                dut=str(payload.get("dut", "") or "").strip() or "<default>",
                cache_key=cache_key,
                elapsed_ms=elapsed_ms,
                error=error,
            )
            if cache_key and self._param_options.get(cache_key):
                self._param_options[cache_key] = []
            self.stateChanged.emit()
            return

        options = _storage_playback_options(normalize_option_values(payload.get("options", [])))
        if not cache_key:
            cache_key = _param_options_cache_key(
                source,
                str(payload.get("dut", "") or "").strip(),
                str(payload.get("nodeid", "") or "").strip(),
            )
        changed = cache_key not in self._param_options or self._param_options.get(cache_key, []) != options
        if changed:
            self._param_options[cache_key] = options
        state_synced = self._sync_dynamic_values_from_options(
            source=source,
            nodeid=str(payload.get("nodeid", "") or "").strip(),
            options=options,
        )
        if state_synced:
            save_state(self._state_path, self._state)
        self._refresh_options_dependent_on_source(source=source, nodeid=str(payload.get("nodeid", "") or "").strip())
        self._trace(
            "param_options_refresh_done",
            source=source,
            dut=str(payload.get("dut", "") or "").strip() or "<default>",
            cache_key=cache_key,
            options=len(options),
            changed=changed,
            state_synced=state_synced,
            elapsed_ms=elapsed_ms,
        )
        if changed or state_synced:
            self.stateChanged.emit()

    def _sync_dynamic_values_from_options(self, *, source: str, nodeid: str, options: list[str]) -> bool:
        normalized_source = str(source or "").strip()
        if not normalized_source:
            return False
        normalized_nodeid = str(nodeid or "").strip()
        next_options = _storage_playback_options(normalize_option_values(options))
        changed = False
        for selected in self._state.selected:
            if normalized_nodeid and str(selected.nodeid or "").strip() != normalized_nodeid:
                continue
            case = self._case_info(selected.nodeid)
            if case is None:
                continue
            case_nodeid = str(case.get("nodeid", "") or "").strip()
            if not case_nodeid:
                continue
            case_values = self._state.case_parameters.setdefault(case_nodeid, {})
            for param_key in list(case.get("required_params", [])):
                field = self._field_for_key(str(param_key))
                if field is None or str(field.options_source or "").strip() != normalized_source:
                    continue
                if self._is_multi_enum_field(field):
                    continue
                next_value = _dynamic_value_for_field(field, next_options)
                raw_current = normalize_option_values(case_values.get(field.key, []))
                current = case_values.get(field.key, field.default)
                if next_value == current:
                    continue
                case_values[field.key] = next_value
                self._trace(
                    "param_options_synced_selected_values",
                    nodeid=case_nodeid,
                    field=field.key,
                    source=normalized_source,
                    previous=_value_size(current),
                    next=_value_size(next_value),
                )
                changed = True
        return changed

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

    def _selected_option_refresh_targets(self) -> list[tuple[str, str]]:
        targets: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for selected in self._state.selected:
            case = self._case_info(selected.nodeid)
            if case is None:
                self._trace("param_options_selected_case_missing", nodeid=selected.nodeid)
                continue
            nodeid = str(selected.nodeid or "").strip()
            blocked_sources = self._dependent_sources_for_case(case)
            for param_key in list(case.get("required_params", [])):
                field = self._field_for_key(str(param_key))
                source = str(field.options_source if field is not None else "").strip()
                if source in blocked_sources:
                    continue
                target = (source, nodeid)
                if source and target not in seen:
                    seen.add(target)
                    targets.append(target)
        self._trace(
            "param_options_selected_targets",
            selected=len(self._state.selected),
            targets=",".join(f"{source}@{nodeid}" for source, nodeid in targets) or "<none>",
            dut=self._current_dut_serial() or "<default>",
        )
        return targets

    def _refresh_selected_param_options(self, reason: str) -> None:
        targets = self._selected_option_refresh_targets()
        if not targets:
            self._trace("param_options_refresh_no_sources", reason=reason)
        for source, nodeid in targets:
            self._schedule_param_options_refresh(source, reason, nodeid=nodeid)

    def _refresh_options_affected_by_param_change(self, *, nodeid: str, key: str) -> None:
        field = self._field_for_key(key)
        if field is None:
            return
        sources = [str(source or "").strip() for source in field.refreshes_options_sources]
        sources = [source for source in sources if source]
        if not sources:
            return
        selected_nodeids = set(self._selected_nodeids())
        normalized_nodeid = str(nodeid or "").strip()
        if normalized_nodeid not in selected_nodeids:
            self._trace(
                "param_dependency_refresh_skip_unselected",
                nodeid=normalized_nodeid or "<none>",
                key=key,
            )
            return
        for source in sources:
            self._schedule_param_options_refresh(
                source,
                f"param_dependency_changed:{key}",
                nodeid=normalized_nodeid,
            )

    def _refresh_options_dependent_on_source(self, *, source: str, nodeid: str) -> None:
        normalized_source = str(source or "").strip()
        normalized_nodeid = str(nodeid or "").strip()
        if not normalized_source or not normalized_nodeid:
            return
        case = self._case_info(normalized_nodeid)
        if case is None:
            return
        for param_key in list(case.get("required_params", [])):
            field = self._field_for_key(str(param_key))
            if field is None or str(field.options_source or "").strip() != normalized_source:
                continue
            for dependent_source in field.refreshes_options_sources:
                normalized_dependent = str(dependent_source or "").strip()
                if not normalized_dependent:
                    continue
                self._schedule_param_options_refresh(
                    normalized_dependent,
                    f"param_source_refreshed:{field.key}",
                    nodeid=normalized_nodeid,
                )

    def _dependent_sources_for_case(self, case: dict[str, Any]) -> set[str]:
        sources: set[str] = set()
        for param_key in list(case.get("required_params", [])):
            field = self._field_for_key(str(param_key))
            if field is None or not str(field.options_source or "").strip():
                continue
            sources.update(str(source or "").strip() for source in field.refreshes_options_sources)
        return {source for source in sources if source}

    def _param_text_key(self, param_key: str, part: str) -> str:
        normalized = str(param_key or "").strip().replace(":", ".")
        return f"test.param.{normalized}.{part}"

    def _fixed_text(self, key: str) -> str:
        return self._text_catalog.text(
            locale=TranslateHelper().current,
            context="TestPageBridge",
            source=key,
        )

    def _field_label(self, field: ParamField) -> str:
        return self._fixed_text(self._param_text_key(field.key, "label"))

    def _field_description(self, field: ParamField) -> str:
        return self._fixed_text(self._param_text_key(field.key, "description"))

    def _scope_label(self, scope: Any) -> str:
        raw_scope = scope.value if hasattr(scope, "value") else str(scope or "")
        labels = {
            ParamScope.GLOBAL_CONTEXT.value: "test.param.scope.global_context",
            ParamScope.CASE_TYPE_SHARED.value: "test.param.scope.case_type_shared",
            ParamScope.CASE.value: "test.param.scope.case",
        }
        return self._fixed_text(labels.get(str(raw_scope), labels[ParamScope.CASE.value]))

    def _schema_to_jsonable(self, schema: ParamSchema) -> dict[str, Any]:
        return {
            "schema_id": schema.schema_id,
            "title": self._fixed_text(f"test.schema.{schema.schema_id}.title"),
            "title_source": "fixed",
            "fields": [self._field_to_jsonable(f) for f in schema.fields],
        }

    def _field_to_jsonable(self, field: ParamField, *, nodeid: str = "") -> dict[str, Any]:
        return {
            "key": field.key,
            "label": self._field_label(field),
            "label_source": "fixed",
            "type": field.type.value if hasattr(field.type, "value") else field.type,
            "category": field.category.value if hasattr(field.category, "value") else field.category,
            "scope": field.scope.value if hasattr(field.scope, "value") else field.scope,
            "scope_label": self._scope_label(field.scope),
            "scope_label_source": "fixed",
            "default": field.default,
            "description": self._field_description(field),
            "description_source": "fixed",
            "group": field.group,
            "required": False,
            "enum_values": self._enum_values_for_field(field, nodeid=nodeid),
            "enum_values_source": "dynamic" if field.options_source else "fixed",
            "options_source": field.options_source,
            "refreshes_options_sources": list(field.refreshes_options_sources),
        }

    def _enum_values_for_field(self, field: ParamField, *, nodeid: str = "") -> list[str]:
        if field.key == "dut":
            return list(self._adb_devices)
        source = str(field.options_source or "").strip()
        if source:
            cache_key = _param_options_cache_key(source, self._current_dut_serial(), nodeid)
            values = _storage_playback_options(list(self._param_options.get(cache_key, [])))
            self._trace(
                "param_options_read_cache",
                field=field.key,
                source=source,
                dut=self._current_dut_serial() or "<default>",
                cache_key=cache_key,
                nodeid=str(nodeid or "").strip() or "<none>",
                options=len(values),
            )
            return values
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

    def _migrate_legacy_android_selection(self) -> bool:
        by_android_id = {
            str(case.get("android_case_id", "") or ""): str(case.get("nodeid", "") or "")
            for case in self._cases
            if str(case.get("android_case_id", "") or "") and str(case.get("nodeid", "") or "")
        }
        if not by_android_id:
            return False

        changed = False
        for selected in self._state.selected:
            raw_nodeid = str(selected.nodeid or "").strip()
            if not raw_nodeid.startswith("android://"):
                continue
            case_id = raw_nodeid[len("android://") :].strip()
            mapped_nodeid = by_android_id.get(case_id, "")
            if not mapped_nodeid:
                self._trace("legacy_android_selection_unmapped", case_id=case_id)
                continue
            selected.nodeid = mapped_nodeid
            selected.case_type = str((self._case_info(mapped_nodeid) or {}).get("case_type", selected.case_type))
            if raw_nodeid in self._state.case_parameters and mapped_nodeid not in self._state.case_parameters:
                self._state.case_parameters[mapped_nodeid] = dict(self._state.case_parameters.get(raw_nodeid, {}))
            self._trace("legacy_android_selection_migrated", from_nodeid=raw_nodeid, to_nodeid=mapped_nodeid)
            changed = True
        return changed

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

    def _is_multi_enum_field(self, field: ParamField) -> bool:
        field_type = field.type.value if hasattr(field.type, "value") else field.type
        return field_type == ParamValueType.MULTI_ENUM.value

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
        cases = self._cases_for_file(file_path)
        if len(cases) == 1:
            return str(cases[0].get("title", "") or cases[0].get("name", "") or file_path)
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
            value = self._state.global_context.get(field.key, field.default)
            return normalize_option_values(value) if self._is_multi_enum_field(field) else value

        if field.scope == ParamScope.CASE_TYPE_SHARED:
            case_type = str(case.get("case_type") or "default")
            case_type_values = self._state.case_type_configs.get(case_type, {})
            value = case_type_values.get(field.key, field.default)
            return normalize_option_values(value) if self._is_multi_enum_field(field) else value

        case_values = self._state.case_parameters.get(str(case.get("nodeid", "")), {})
        value = case_values.get(field.key, field.default)
        return normalize_option_values(value) if self._is_multi_enum_field(field) else value

    def _set_case_param_value(self, *, nodeid: str, key: str, value: Any) -> bool:
        case = self._case_info(nodeid)
        field = self._field_for_key(key)
        if case is None or field is None:
            return False
        next_value = runtime_params().normalize_for_key(field.key, value)

        if field.scope == ParamScope.GLOBAL_CONTEXT:
            if self._state.global_context.get(field.key) == next_value:
                return False
            self._state.global_context[field.key] = next_value
            return True

        if field.scope == ParamScope.CASE_TYPE_SHARED:
            case_type = str(case.get("case_type") or "default")
            self._state.case_type_configs.setdefault(case_type, {})
            if self._state.case_type_configs[case_type].get(field.key) == next_value:
                return False
            self._state.case_type_configs[case_type][field.key] = next_value
            return True

        case_nodeid = str(case.get("nodeid", "")).strip()
        if not case_nodeid:
            return False
        self._state.case_parameters.setdefault(case_nodeid, {})
        if self._state.case_parameters[case_nodeid].get(field.key) == next_value:
            return False
        self._state.case_parameters[case_nodeid][field.key] = next_value
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
            self._state.case_parameters.setdefault(normalized, {})
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
        started_at = time.monotonic()
        self._trace(
            "discover_start",
            packaged=is_packaged_runtime(),
            root_dir=str(self._root_dir),
            executable=sys.executable,
        )
        if self._discovery_loaded and self._cases:
            self._trace(
                "discover_cached",
                cases=len(self._cases),
                elapsed_ms=int((time.monotonic() - started_at) * 1000),
            )
            self.casesChanged.emit()
            return
        if self._discovery_running:
            self._trace(
                "discover_skip_running",
                elapsed_ms=int((time.monotonic() - started_at) * 1000),
            )
            return
        self._discovery_running = True
        if not self._adb_refresh_started:
            self._adb_refresh_started = True
            self._schedule_adb_refresh("page_init_async")
        Thread(target=self._discover_cases_worker, args=(started_at,), daemon=True).start()

    def _discover_cases_worker(self, started_at: float) -> None:
        if is_packaged_runtime():
            load_started = time.monotonic()
            cases = load_packaged_test_catalog()
            self._trace(
                "catalog_loaded",
                cases=len(cases),
                elapsed_ms=int((time.monotonic() - load_started) * 1000),
            )
            if not cases:
                self._discoveryError.emit("Packaged test catalog is missing or empty.", int((time.monotonic() - started_at) * 1000))
                return
            rows = [
                {
                    "nodeid": str(c.get("nodeid", "")),
                    "file": str(c.get("file", "")),
                    "name": str(c.get("name", "")),
                    "markers": [str(m) for m in list(c.get("markers") or [])],
                    "case_type": str(c.get("case_type", "default")),
                    "required_params": [str(p) for p in list(c.get("required_params") or [])],
                    "required_param_groups": [str(g) for g in list(c.get("required_param_groups") or [])],
                    "required_equipment": [str(e) for e in list(c.get("required_equipment") or [])],
                    "android_case_id": str(c.get("android_case_id", "")),
                }
                for c in cases
            ]
            self._discoveryResult.emit(rows, int((time.monotonic() - started_at) * 1000))
            return
        try:
            collect_started = time.monotonic()
            cases = discover_pytest_cases(root_dir=self._root_dir, python_executable=sys.executable)
            self._trace(
                "pytest_collect_done",
                cases=len(cases),
                elapsed_ms=int((time.monotonic() - collect_started) * 1000),
            )
        except PytestDiscoveryError as e:
            self._discoveryError.emit(str(e), int((time.monotonic() - started_at) * 1000))
            return
        except Exception as e:  # noqa: BLE001
            self._discoveryError.emit(f"Pytest discovery failed: {e}", int((time.monotonic() - started_at) * 1000))
            return

        rows = [
            {
                "nodeid": c.nodeid,
                "file": c.file,
                "name": c.name,
                "markers": c.markers,
                "case_type": c.case_type,
                "required_params": c.required_params,
                "required_param_groups": c.required_param_groups,
                "required_equipment": c.required_equipment,
                "android_case_id": c.android_case_id,
            }
            for c in cases
        ]
        self._discoveryResult.emit(rows, int((time.monotonic() - started_at) * 1000))

    @Slot("QVariantList", int)
    def _apply_discovery_result(self, rows: list[dict[str, Any]], elapsed_ms: int) -> None:
        self._cases = [dict(row) for row in rows]
        self._rebuild_case_indexes()
        changed = self._migrate_legacy_android_selection()
        changed = self._sync_selected_file_order() or changed
        changed = self._reorder_selected_cases_by_file_order() or changed
        if changed:
            save_state(self._state_path, self._state)
        self._discovery_running = False
        self._discovery_loaded = True
        self.casesChanged.emit()
        self._trace(
            "discover_done",
            cases=len(self._cases),
            elapsed_ms=elapsed_ms,
        )
        self._refresh_selected_param_options("discover_done")

    @Slot(str, int)
    def _apply_discovery_error(self, message: str, elapsed_ms: int) -> None:
        self._discovery_running = False
        self._trace("discover_error", elapsed_ms=elapsed_ms, error=message)
        self.errorOccurred.emit(message)

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
                "required_equipment": list(item.get("required_equipment", [])),
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
                    "file_source": "dynamic",
                    "name": self._file_base_name(file_path),
                    "name_source": "dynamic",
                    "short_file": self._trimmed_case_path(file_path),
                    "short_file_source": "dynamic",
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
                        "nodeid_source": "dynamic",
                        "file": str(case.get("file", "")),
                        "file_source": "dynamic",
                        "name": str(case.get("name", "")),
                        "name_source": "dynamic",
                        "case_type": str(case.get("case_type", "default")),
                        "case_type_source": "dynamic",
                        "required_params": list(case.get("required_params", [])),
                        "required_param_groups": list(case.get("required_param_groups", [])),
                        "required_equipment": list(case.get("required_equipment", [])),
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

    def _selected_required_equipment(self) -> list[str]:
        required: list[str] = []
        seen: set[str] = set()
        for selected in self._state.selected:
            case = self._case_info(selected.nodeid)
            if case is None:
                continue
            for value in list(case.get("required_equipment", [])):
                kind = str(value or "").strip().lower()
                if not kind or kind in seen:
                    continue
                seen.add(kind)
                required.append(kind)
        return required

    def _equipment_config(self) -> dict[str, Any]:
        raw = self._state.global_context.get("equipment", {})
        return dict(raw) if isinstance(raw, dict) else {}

    def _relay_type_rows(self) -> list[dict[str, Any]]:
        return [
            {"value": "snmp_pdu", "label": self.tr("test.env.relay.type.snmp_pdu"), "label_source": "fixed"},
            {"value": "usb_relay", "label": self.tr("test.env.relay.type.usb_relay"), "label_source": "fixed"},
        ]

    def _relay_fields(self, relay_type: str, config: dict[str, Any]) -> list[dict[str, Any]]:
        normalized_type = str(relay_type or "").strip() or "snmp_pdu"
        if normalized_type == "usb_relay":
            specs = [
                {
                    "key": "port",
                    "label": self.tr("test.env.relay.usb_relay.port.label"),
                    "label_source": "fixed",
                    "type": "string",
                    "default": "",
                    "description": self.tr("test.env.relay.usb_relay.port.description"),
                    "description_source": "fixed",
                },
                {
                    "key": "mode",
                    "label": self.tr("test.env.relay.usb_relay.mode.label"),
                    "label_source": "fixed",
                    "type": "enum",
                    "default": "NO",
                    "enum_values": ["NO", "NC"],
                    "enum_values_source": "fixed",
                    "description": "",
                    "description_source": "fixed",
                },
                {
                    "key": "press_seconds",
                    "label": self.tr("test.env.relay.usb_relay.press_seconds.label"),
                    "label_source": "fixed",
                    "type": "int",
                    "default": 1,
                    "description": "",
                    "description_source": "fixed",
                },
            ]
        else:
            specs = [
                {
                    "key": "ip",
                    "label": self.tr("test.env.relay.snmp_pdu.ip.label"),
                    "label_source": "fixed",
                    "type": "string",
                    "default": "",
                    "description": self.tr("test.env.relay.snmp_pdu.ip.description"),
                    "description_source": "fixed",
                },
                {
                    "key": "port",
                    "label": self.tr("test.env.relay.snmp_pdu.port.label"),
                    "label_source": "fixed",
                    "type": "int",
                    "default": 1,
                    "description": "",
                    "description_source": "fixed",
                },
            ]
        fields: list[dict[str, Any]] = []
        for spec in specs:
            field = dict(spec)
            field["value"] = config.get(str(field["key"]), field.get("default", ""))
            field["value_source"] = "user"
            field.setdefault("enum_values", [])
            field.setdefault("enum_values_source", "fixed")
            fields.append(field)
        return fields

    def _env_default_config(self, kind: str, device_type: str | None = None) -> dict[str, Any]:
        normalized_kind = str(kind or "").strip().lower()
        if normalized_kind == "relay":
            relay_type = str(device_type or "").strip() or "snmp_pdu"
            config: dict[str, Any] = {"type": relay_type}
            for field in self._relay_fields(relay_type, {}):
                config[str(field["key"])] = field.get("default", "")
            return config
        return {"type": str(device_type or "").strip()}

    def _env_equipment_row(self, kind: str) -> dict[str, Any] | None:
        normalized_kind = str(kind or "").strip().lower()
        config = self._equipment_config().get(normalized_kind, {})
        config = dict(config) if isinstance(config, dict) else {}
        if normalized_kind == "relay":
            relay_type = str(config.get("type") or "snmp_pdu").strip() or "snmp_pdu"
            return {
                "kind": "relay",
                "kind_source": "fixed",
                "label": self.tr("test.env.relay.label"),
                "label_source": "fixed",
                "type": relay_type,
                "type_source": "user",
                "typeLabel": self.tr("test.env.equipment.type.label"),
                "typeLabel_source": "fixed",
                "typeOptions": self._relay_type_rows(),
                "fields": self._relay_fields(relay_type, config),
            }
        return None

    @Slot(result="QVariantList")
    def envEquipmentRows(self):
        rows: list[dict[str, Any]] = []
        for kind in self._selected_required_equipment():
            row = self._env_equipment_row(kind)
            if row is not None:
                rows.append(row)
        return rows

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
                    folder_node = {
                        "key": folder_key,
                        "label": part,
                        "label_source": "dynamic",
                        "folders": [],
                        "files": [],
                    }
                    parent["folders"].append(folder_node)
                parent = folder_node

            file_key = f"file:{short_file}"
            if not any(item["key"] == file_key for item in parent["files"]):
                parent["files"].append(
                    {
                        "key": file_key,
                        "label": file_name,
                        "label_source": "dynamic",
                        "file": file_path,
                        "file_source": "dynamic",
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
                "title_source": node.get("label_source", "dynamic"),
                "_key": node["key"],
                "rowType": "folder",
                "iconSource": "Folder",
                "expanded": force_expand or node["key"] in expanded,
                "children": children,
            }

        def build_file(node: dict[str, Any]) -> dict[str, Any]:
            return {
                "title": node["label"],
                "title_source": node.get("label_source", "dynamic"),
                "_key": node["key"],
                "rowType": "file",
                "iconSource": "Document",
                "file": node["file"],
                "file_source": node.get("file_source", "dynamic"),
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
                "title_source": "dynamic",
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
        return self._schema_to_jsonable(self._registry.global_context)

    @Slot()
    def refreshGlobalSchema(self) -> None:
        self._schedule_adb_refresh("user_refresh")

    @Slot(result="QVariantMap")
    def globalContext(self):
        return dict(self._state.global_context)

    @Slot(str, str)
    def setEnvEquipmentType(self, kind: str, device_type: str) -> None:
        normalized_kind = str(kind or "").strip().lower()
        normalized_type = str(device_type or "").strip()
        if not normalized_kind or not normalized_type:
            return
        equipment = self._equipment_config()
        next_config = self._env_default_config(normalized_kind, normalized_type)
        if equipment.get(normalized_kind) == next_config:
            return
        equipment[normalized_kind] = next_config
        self._state.global_context["equipment"] = equipment
        self._save_and_emit()

    @Slot(str, str, result="QVariant")
    def envEquipmentValue(self, kind: str, key: str) -> Any:
        normalized_kind = str(kind or "").strip().lower()
        normalized_key = str(key or "").strip()
        if not normalized_kind or not normalized_key:
            return ""
        current = self._equipment_config().get(normalized_kind, {})
        if not isinstance(current, dict):
            return ""
        if normalized_key in current:
            return current.get(normalized_key)
        default_config = self._env_default_config(normalized_kind, str(current.get("type") or ""))
        return default_config.get(normalized_key, "")

    @Slot(str, str, "QVariant")
    def setEnvEquipmentValue(self, kind: str, key: str, value: Any) -> None:
        normalized_kind = str(kind or "").strip().lower()
        normalized_key = str(key or "").strip()
        if not normalized_kind or not normalized_key:
            return
        equipment = self._equipment_config()
        current = equipment.get(normalized_kind, {})
        config = dict(current) if isinstance(current, dict) else {}
        if "type" not in config:
            config = self._env_default_config(normalized_kind)
        if config.get(normalized_key) == value:
            return
        config[normalized_key] = value
        equipment[normalized_kind] = config
        self._state.global_context["equipment"] = equipment
        self._save_and_emit()

    @Slot(str, result="QVariantMap")
    def caseTypeConfig(self, case_type: str):
        return dict(self._state.case_type_configs.get(case_type, {}))

    @Slot(str, result="QVariantList")
    def caseParamFields(self, nodeid: str):
        case = self._case_info(nodeid)
        if case is None:
            return []
        required_params = list(case.get("required_params", []))
        required_param_keys = set(required_params_for_case(case))
        fields: list[dict[str, Any]] = []
        for param_key in required_params:
            field = self._field_for_key(str(param_key))
            if field is None:
                continue
            jsonable = self._field_to_jsonable(field, nodeid=nodeid)
            jsonable["required"] = field.key in required_param_keys
            fields.append(jsonable)
        return fields

    @Slot(str, str)
    def refreshCaseParamOptions(self, nodeid: str, key: str) -> None:
        case = self._case_info(nodeid)
        field = self._field_for_key(key)
        if case is None or field is None:
            self._trace("param_options_manual_refresh_missing_field", nodeid=nodeid, key=key)
            return
        source = str(field.options_source or "").strip()
        if not source:
            self._trace("param_options_manual_refresh_no_source", nodeid=nodeid, key=key)
            return
        self._schedule_param_options_refresh(
            source,
            f"manual_field_refresh:{key}",
            nodeid=nodeid,
        )

    @Slot(str, str, result="QVariant")
    def caseParamValue(self, nodeid: str, key: str):
        return self._resolve_case_value(nodeid=nodeid, key=key)

    @Slot(str, str, str, result=bool)
    def caseParamListContains(self, nodeid: str, key: str, value: str) -> bool:
        values = normalize_option_values(self._resolve_case_value(nodeid=nodeid, key=key))
        return str(value or "").strip() in values

    @Slot(str, bool)
    def setCaseSelected(self, nodeid: str, selected: bool) -> None:
        if not self._set_case_selected(nodeid, selected):
            return
        self._save_and_emit()
        if selected:
            self._refresh_selected_param_options("case_selected")

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
        if selected:
            self._refresh_selected_param_options("file_selected")

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
        if key == "dut":
            self._refresh_selected_param_options("dut_changed")
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
        self._refresh_options_affected_by_param_change(nodeid=nodeid, key=key)

    @Slot(str, str, str, bool)
    def setCaseParamListItemSelected(self, nodeid: str, key: str, value: str, selected: bool) -> None:
        option = str(value or "").strip()
        if not option:
            return
        current = normalize_option_values(self._resolve_case_value(nodeid=nodeid, key=key))
        if selected and option not in current:
            current.append(option)
        if not selected:
            current = [item for item in current if item != option]
        if not self._set_case_param_value(nodeid=nodeid, key=key, value=current):
            return
        self._save_and_emit()

    @Slot()
    def reloadState(self) -> None:
        self._state = load_state(self._state_path)
        changed = self._ensure_state_defaults()
        changed = self._sync_selected_file_order() or changed
        changed = self._reorder_selected_cases_by_file_order() or changed
        if changed:
            save_state(self._state_path, self._state)
        self.stateChanged.emit()

    def _save_and_emit(self) -> None:
        save_state(self._state_path, self._state)
        self.stateChanged.emit()


def _trace_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _storage_playback_path(value: str) -> str:
    path = str(value or "").strip()
    if path.startswith("/mnt/media_rw/"):
        return "/storage/" + path[len("/mnt/media_rw/") :]
    return path


def _storage_playback_options(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        path = _storage_playback_path(value)
        if path and path not in normalized:
            normalized.append(path)
    return normalized


def _param_options_cache_key(source: str, selected_serial: str | None = None, nodeid: str = "") -> str:
    base_key = option_cache_key(source, selected_serial)
    normalized_nodeid = str(nodeid or "").strip()
    if not normalized_nodeid:
        return base_key
    return f"{base_key}#{normalized_nodeid}"


def _dynamic_value_for_field(field: ParamField, options: list[str]) -> Any:
    if not options:
        return field.default
    return options[0]


def _value_size(value: Any) -> int:
    if isinstance(value, (list, tuple, set)):
        return len(value)
    if value in (None, ""):
        return 0
    return 1
