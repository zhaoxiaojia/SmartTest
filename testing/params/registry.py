from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import Iterable

from .android_catalog import android_catalog_param
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


def _android_catalog_field(
    key: str,
    value_type: ParamValueType,
    category: ParamCategory,
) -> ParamField:
    catalog_param = android_catalog_param(key)
    default = catalog_param.default_value
    if value_type == ParamValueType.INT:
        default = int(default)
    return ParamField(
        key=key,
        label=catalog_param.label,
        type=value_type,
        category=category,
        scope=ParamScope.CASE,
        default=default,
        description=catalog_param.hint,
        enum_values=static_param_options(key),
    )


_DEFAULT_ANDROID_PARAM_SPECS = [
    ("emmc_rw:loop_count", ParamValueType.INT, ParamCategory.EXECUTION),
    ("emmc_rw:source_profile", ParamValueType.STRING, ParamCategory.EXECUTION),
    ("emmc_rw:source_size_kb", ParamValueType.INT, ParamCategory.EXECUTION),
    ("emmc_rw:min_free_kb", ParamValueType.INT, ParamCategory.EXECUTION),
    ("emmc_rw:work_dir", ParamValueType.PATH, ParamCategory.EXECUTION),
    ("auto_reboot:cycle_count", ParamValueType.INT, ParamCategory.EXECUTION),
    ("auto_reboot:interval_sec", ParamValueType.INT, ParamCategory.EXECUTION),
    ("auto_reboot:ping_target", ParamValueType.STRING, ParamCategory.NETWORK),
    ("auto_reboot:bt_target", ParamValueType.ENUM, ParamCategory.NETWORK),
    ("auto_suspend:cycle_count", ParamValueType.INT, ParamCategory.EXECUTION),
    ("auto_suspend:interval_sec", ParamValueType.INT, ParamCategory.EXECUTION),
    ("auto_suspend:ping_target", ParamValueType.STRING, ParamCategory.NETWORK),
    ("auto_suspend:bt_target", ParamValueType.ENUM, ParamCategory.NETWORK),
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
                _android_catalog_field(key, value_type, category)
                for key, value_type, category in _DEFAULT_ANDROID_PARAM_SPECS
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
