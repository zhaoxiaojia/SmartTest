from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import Any, Iterable

from .binding import CaseParamBinding, ParamGroup
from .options import static_param_options
from .schema import ParamCategory, ParamField, ParamSchema, ParamScope, ParamValueType


@dataclass(frozen=True)
class SchemaRegistry:
    global_context: ParamSchema
    case_type_schemas: dict[str, ParamSchema]
    param_groups: dict[str, ParamGroup] = field(default_factory=dict)

    def get_case_type_schema(self, case_type: str) -> ParamSchema | None:
        return self.case_type_schemas.get(case_type)

    @cached_property
    def fields_by_key(self) -> dict[str, ParamField]:
        fields: dict[str, ParamField] = {}
        schemas = [self.global_context, *self.case_type_schemas.values()]
        for schema in schemas:
            for field_def in schema.fields:
                existing = fields.get(field_def.key)
                if existing and existing != field_def:
                    raise ValueError(f"Duplicate parameter key with conflicting definitions: {field_def.key}")
                fields[field_def.key] = field_def
        return fields

    def get_param(self, key: str) -> ParamField | None:
        return self.fields_by_key.get(key)

    def get_param_group(self, group_id: str) -> ParamGroup | None:
        return self.param_groups.get(group_id)

    def resolve_param_keys(
        self,
        *,
        param_keys: Iterable[str] = (),
        group_ids: Iterable[str] = (),
    ) -> list[str]:
        resolved: list[str] = []
        seen: set[str] = set()

        def add_param_key(raw_key: str) -> None:
            key = str(raw_key).strip()
            if not key:
                return
            if key not in self.fields_by_key:
                raise KeyError(f"Unknown parameter '{key}'")
            if key in seen:
                return
            seen.add(key)
            resolved.append(key)

        for group_id in group_ids:
            normalized_group_id = str(group_id).strip()
            if not normalized_group_id:
                continue
            group = self.param_groups.get(normalized_group_id)
            if group is None:
                raise KeyError(f"Unknown parameter group '{normalized_group_id}'")
            for param_key in group.param_keys:
                add_param_key(param_key)

        for param_key in param_keys:
            add_param_key(param_key)

        return resolved

    def resolve_binding(self, binding: CaseParamBinding) -> list[str]:
        return self.resolve_param_keys(param_keys=binding.param_keys, group_ids=binding.group_ids)


def _case_param_field(
    key: str,
    label: str,
    value_type: ParamValueType,
    category: ParamCategory,
    default: Any = "",
    description: str = "",
) -> ParamField:
    return ParamField(
        key=key,
        label=label,
        type=value_type,
        category=category,
        scope=ParamScope.CASE,
        default=default,
        description=description,
        enum_values=static_param_options(key),
    )


_DEFAULT_ANDROID_PARAM_SPECS = [
    ("emmc_rw:loop_count", "Loop Count", ParamValueType.INT, ParamCategory.EXECUTION, 180, ""),
    ("emmc_rw:source_profile", "Source Profile", ParamValueType.STRING, ParamCategory.EXECUTION, "random1", ""),
    ("emmc_rw:source_size_kb", "Source Size (KB)", ParamValueType.INT, ParamCategory.EXECUTION, 51200, ""),
    ("emmc_rw:min_free_kb", "Minimum Free Space (KB)", ParamValueType.INT, ParamCategory.EXECUTION, 307200, ""),
    ("emmc_rw:work_dir", "Working Directory", ParamValueType.PATH, ParamCategory.EXECUTION, "/data/local/tmp/smarttest/emmc_rw", ""),
    ("auto_reboot:cycle_count", "Cycle Count", ParamValueType.INT, ParamCategory.EXECUTION, 20, ""),
    ("auto_reboot:interval_sec", "Interval Seconds", ParamValueType.INT, ParamCategory.EXECUTION, 100, ""),
    ("auto_reboot:ping_target", "Ping Target", ParamValueType.STRING, ParamCategory.NETWORK, "", ""),
    ("auto_reboot:bt_target", "Bluetooth Target", ParamValueType.ENUM, ParamCategory.NETWORK, "", ""),
    ("auto_suspend:cycle_count", "Cycle Count", ParamValueType.INT, ParamCategory.EXECUTION, 20, ""),
    ("auto_suspend:interval_sec", "Interval Seconds", ParamValueType.INT, ParamCategory.EXECUTION, 100, ""),
    ("auto_suspend:ping_target", "Ping Target", ParamValueType.STRING, ParamCategory.NETWORK, "", ""),
    ("auto_suspend:bt_target", "Bluetooth Target", ParamValueType.ENUM, ParamCategory.NETWORK, "", ""),
    ("wifi_onoff_scan:cycle_count", "Cycle Count", ParamValueType.INT, ParamCategory.EXECUTION, 2, ""),
    ("wifi_onoff_scan:ping_target", "Ping Target", ParamValueType.STRING, ParamCategory.NETWORK, "", ""),
    ("bt_onoff_scan:cycle_count", "Cycle Count", ParamValueType.INT, ParamCategory.EXECUTION, 2, ""),
    ("bt_onoff_scan:bt_target", "Bluetooth Target", ParamValueType.ENUM, ParamCategory.NETWORK, "", ""),
]


def default_registry() -> SchemaRegistry:
    """
    Default schemas shipped with SmartTest.

    v1 provides minimal placeholders. Teams can extend/replace these in Python.
    """
    global_context = ParamSchema(
        schema_id="global_context",
        title="Global",
        fields=[
            ParamField(
                key="dut",
                label="DUT",
                type=ParamValueType.ENUM,
                category=ParamCategory.DEVICE,
                scope=ParamScope.GLOBAL_CONTEXT,
                default="",
            ),
        ],
    )

    case_type_schemas = {
        "default": ParamSchema(
            schema_id="case_type_default",
            title="Default",
            fields=[
                _case_param_field(key, label, value_type, category, default, description)
                for key, label, value_type, category, default, description in _DEFAULT_ANDROID_PARAM_SPECS
            ],
        ),
    }

    param_groups = {
        "dut_identity": ParamGroup(
            group_id="dut_identity",
            title="DUT",
            param_keys=["dut"],
        ),
    }

    return SchemaRegistry(
        global_context=global_context,
        case_type_schemas=case_type_schemas,
        param_groups=param_groups,
    )
