from __future__ import annotations

from dataclasses import dataclass

from .schema import ParamSchema


@dataclass(frozen=True)
class SchemaRegistry:
    global_context: ParamSchema
    case_type_schemas: dict[str, ParamSchema]

    def get_case_type_schema(self, case_type: str) -> ParamSchema | None:
        return self.case_type_schemas.get(case_type)


def default_registry() -> SchemaRegistry:
    """
    Default schemas shipped with SmartTest.

    v1 provides minimal placeholders. Teams can extend/replace these in Python.
    """
    from .schema import ParamField

    global_context = ParamSchema(
        schema_id="global_context",
        title="Global",
        fields=[
            ParamField(key="dut_model", label="DUT Model", type="string", default=""),
            ParamField(key="dut_sn", label="DUT SN", type="string", default=""),
            ParamField(key="fw_version", label="FW Version", type="string", default=""),
            ParamField(key="test_env", label="Test Environment", type="string", default=""),
            ParamField(key="operator", label="Operator", type="string", default=""),
        ],
    )

    # Example special parameters. Real projects should expand this list.
    case_type_schemas = {
        "stress": ParamSchema(
            schema_id="case_type_stress",
            title="Stress",
            fields=[
                ParamField(key="duration_s", label="Duration (s)", type="int", default=300),
                ParamField(key="concurrency", label="Concurrency", type="int", default=1),
                ParamField(key="warmup_s", label="Warmup (s)", type="int", default=10),
            ],
        ),
        "default": ParamSchema(
            schema_id="case_type_default",
            title="Default",
            fields=[],
        ),
    }

    return SchemaRegistry(global_context=global_context, case_type_schemas=case_type_schemas)

