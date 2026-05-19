from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import Any, Iterable

from .binding import CaseParamBinding, ParamGroup
from .android_catalog import load_android_catalog_params
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


def _android_value_type(param_id: str) -> ParamValueType:
    if param_id.endswith("_dir"):
        return ParamValueType.PATH
    if param_id.endswith("_target") and param_id.startswith("bt"):
        return ParamValueType.ENUM
    if param_id.endswith("_count") or param_id.endswith("_sec") or param_id.endswith("_kb"):
        return ParamValueType.INT
    return ParamValueType.STRING


def _android_category(param_id: str) -> ParamCategory:
    if "target" in param_id:
        return ParamCategory.NETWORK
    return ParamCategory.EXECUTION


def _android_default_value(raw_value: str, value_type: ParamValueType) -> Any:
    if value_type == ParamValueType.INT:
        try:
            return int(str(raw_value).strip())
        except ValueError:
            return 0
    return raw_value


def _android_catalog_fields() -> list[ParamField]:
    fields: list[ParamField] = []
    for key, param in sorted(load_android_catalog_params().items()):
        value_type = _android_value_type(param.param_id)
        fields.append(
            _case_param_field(
                key,
                param.label,
                value_type,
                _android_category(param.param_id),
                _android_default_value(param.default_value, value_type),
                param.hint,
            )
        )
    return fields


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
            fields=_android_catalog_fields(),
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
