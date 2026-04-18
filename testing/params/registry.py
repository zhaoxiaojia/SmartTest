from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import Iterable

from .binding import CaseParamBinding, ParamGroup
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
                key="dut_model",
                label="DUT Model",
                type=ParamValueType.STRING,
                category=ParamCategory.DEVICE,
                scope=ParamScope.GLOBAL_CONTEXT,
                default="",
            ),
            ParamField(
                key="dut_sn",
                label="DUT SN",
                type=ParamValueType.STRING,
                category=ParamCategory.DEVICE,
                scope=ParamScope.GLOBAL_CONTEXT,
                default="",
            ),
            ParamField(
                key="fw_version",
                label="FW Version",
                type=ParamValueType.STRING,
                category=ParamCategory.DEVICE,
                scope=ParamScope.GLOBAL_CONTEXT,
                default="",
            ),
            ParamField(
                key="test_env",
                label="Test Environment",
                type=ParamValueType.STRING,
                category=ParamCategory.ENVIRONMENT,
                scope=ParamScope.GLOBAL_CONTEXT,
                default="",
            ),
            ParamField(
                key="operator",
                label="Operator",
                type=ParamValueType.STRING,
                category=ParamCategory.REPORT,
                scope=ParamScope.GLOBAL_CONTEXT,
                default="",
            ),
            ParamField(
                key="emmc_rw:loop_count",
                label="eMMC Loop Count",
                type=ParamValueType.INT,
                category=ParamCategory.EXECUTION,
                scope=ParamScope.CASE,
                default=180,
            ),
            ParamField(
                key="emmc_rw:source_profile",
                label="eMMC Source Profile",
                type=ParamValueType.STRING,
                category=ParamCategory.EXECUTION,
                scope=ParamScope.CASE,
                default="random1",
            ),
            ParamField(
                key="emmc_rw:source_size_kb",
                label="eMMC Source Size (KB)",
                type=ParamValueType.INT,
                category=ParamCategory.EXECUTION,
                scope=ParamScope.CASE,
                default=51200,
            ),
            ParamField(
                key="emmc_rw:min_free_kb",
                label="eMMC Min Free Space (KB)",
                type=ParamValueType.INT,
                category=ParamCategory.EXECUTION,
                scope=ParamScope.CASE,
                default=307200,
            ),
            ParamField(
                key="emmc_rw:work_dir",
                label="eMMC Work Directory",
                type=ParamValueType.PATH,
                category=ParamCategory.EXECUTION,
                scope=ParamScope.CASE,
                default="/data/local/tmp/smarttest/emmc_rw",
            ),
            ParamField(
                key="auto_reboot:cycle_count",
                label="AutoReboot Cycle Count",
                type=ParamValueType.INT,
                category=ParamCategory.EXECUTION,
                scope=ParamScope.CASE,
                default=20,
            ),
            ParamField(
                key="auto_reboot:interval_sec",
                label="AutoReboot Interval (s)",
                type=ParamValueType.INT,
                category=ParamCategory.EXECUTION,
                scope=ParamScope.CASE,
                default=100,
            ),
            ParamField(
                key="auto_suspend:cycle_count",
                label="AutoSuspend Cycle Count",
                type=ParamValueType.INT,
                category=ParamCategory.EXECUTION,
                scope=ParamScope.CASE,
                default=20,
            ),
            ParamField(
                key="auto_suspend:interval_sec",
                label="AutoSuspend Interval (s)",
                type=ParamValueType.INT,
                category=ParamCategory.EXECUTION,
                scope=ParamScope.CASE,
                default=100,
            ),
            ParamField(
                key="wifi_onoff_scan:cycle_count",
                label="Wi-Fi OnOff Cycle Count",
                type=ParamValueType.INT,
                category=ParamCategory.EXECUTION,
                scope=ParamScope.CASE,
                default=1000,
            ),
            ParamField(
                key="bt_onoff_scan:cycle_count",
                label="BT OnOff Cycle Count",
                type=ParamValueType.INT,
                category=ParamCategory.EXECUTION,
                scope=ParamScope.CASE,
                default=1000,
            ),
        ],
    )

    # Example special parameters. Real projects should expand this list.
    case_type_schemas = {
        "stress": ParamSchema(
            schema_id="case_type_stress",
            title="Stress",
            fields=[
                ParamField(
                    key="duration_s",
                    label="Duration (s)",
                    type=ParamValueType.INT,
                    category=ParamCategory.EXECUTION,
                    scope=ParamScope.CASE_TYPE_SHARED,
                    default=300,
                ),
                ParamField(
                    key="concurrency",
                    label="Concurrency",
                    type=ParamValueType.INT,
                    category=ParamCategory.EXECUTION,
                    scope=ParamScope.CASE_TYPE_SHARED,
                    default=1,
                ),
                ParamField(
                    key="warmup_s",
                    label="Warmup (s)",
                    type=ParamValueType.INT,
                    category=ParamCategory.EXECUTION,
                    scope=ParamScope.CASE_TYPE_SHARED,
                    default=10,
                ),
            ],
        ),
        "default": ParamSchema(
            schema_id="case_type_default",
            title="Default",
            fields=[],
        ),
    }

    param_groups = {
        "dut_identity": ParamGroup(
            group_id="dut_identity",
            title="DUT Identity",
            param_keys=["dut_model", "dut_sn", "fw_version"],
        ),
        "stress_runtime": ParamGroup(
            group_id="stress_runtime",
            title="Stress Runtime",
            param_keys=["duration_s", "concurrency", "warmup_s"],
        ),
    }

    return SchemaRegistry(
        global_context=global_context,
        case_type_schemas=case_type_schemas,
        param_groups=param_groups,
    )
