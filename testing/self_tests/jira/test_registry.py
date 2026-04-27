from jira.core.models import JiraFieldMetadata
from jira.fields.registry import (
    FieldRegistry,
    build_default_registry,
    infer_field_spec_from_metadata,
    registry_from_metadata,
)
from jira.fields.specs import FieldSpec


def test_registry_builds_lightweight_plan_by_default() -> None:
    registry = build_default_registry()

    plan = registry.build_plan(["summary", "status", "changelog_statuses"], include_heavy=False)

    assert [spec.name for spec in plan.active_specs] == ["summary", "status"]
    assert [spec.name for spec in plan.deferred_specs] == ["changelog_statuses"]
    assert plan.jira_fields == ("key", "status", "summary")
    assert plan.expand == ()


def test_registry_builds_heavy_plan_when_requested() -> None:
    registry = build_default_registry()

    plan = registry.build_plan(["summary", "changelog_statuses"], include_heavy=True)

    assert [spec.name for spec in plan.active_specs] == ["summary", "changelog_statuses"]
    assert plan.jira_fields == ("key", "summary")
    assert plan.expand == ("changelog",)


def test_registry_accepts_inline_field_specs() -> None:
    registry = FieldRegistry()
    custom_spec = FieldSpec(name="wifi_domain", path="fields.customfield_12345.value")

    plan = registry.build_plan([custom_spec])

    assert [spec.name for spec in plan.active_specs] == ["wifi_domain"]
    assert plan.jira_fields == ("customfield_12345", "key")


def test_registry_registers_metadata_driven_custom_fields() -> None:
    metadata = [
        JiraFieldMetadata(
            field_id="customfield_12345",
            name="Failure Root Cause",
            schema_type="option",
            custom=True,
            custom_id=12345,
            clause_names=("cf[12345]", "Failure Root Cause"),
        ),
        JiraFieldMetadata(
            field_id="customfield_20001",
            name="Verification Owners",
            schema_type="array",
            custom=True,
            custom_id=20001,
            schema_custom="com.atlassian.jira.plugin.system.customfieldtypes:multiselect",
        ),
    ]

    registry = registry_from_metadata(metadata)

    option_plan = registry.build_plan(["failure_root_cause"])
    multi_plan = registry.build_plan(["verification_owners"])
    raw_id_plan = registry.build_plan(["customfield_12345"])

    assert option_plan.active_specs[0].path == "fields.customfield_12345.value"
    assert option_plan.jira_fields == ("customfield_12345", "key")
    assert multi_plan.active_specs[0].path == "fields.customfield_20001[].value"
    assert raw_id_plan.active_specs[0].name == "Failure Root Cause"


def test_registry_registers_standard_metadata_name_aliases() -> None:
    metadata = [
        JiraFieldMetadata(
            field_id="customfield_30001",
            name="Wi-Fi Domain",
            schema_type="string",
            custom=True,
            custom_id=30001,
            clause_names=("cf[30001]",),
        )
    ]

    registry = registry_from_metadata(metadata)
    plan = registry.build_plan(["wifi_domain", "cf[30001]"])

    assert [spec.name for spec in plan.active_specs] == ["Wi-Fi Domain", "Wi-Fi Domain"]


def test_registry_merges_equivalent_standard_metadata_fields() -> None:
    metadata = [
        JiraFieldMetadata(
            field_id="labels",
            name="Labels",
            schema_type="array",
            schema_custom="com.atlassian.jira.plugin.system.customfieldtypes:labels",
            clause_names=("labels",),
        )
    ]

    registry = registry_from_metadata(metadata)
    plan = registry.build_plan(["labels"])

    assert [spec.name for spec in plan.active_specs] == ["labels"]
    assert plan.active_specs[0].path == "fields.labels[]"


def test_registry_skips_conflicting_metadata_aliases_but_keeps_field_id() -> None:
    metadata = [
        JiraFieldMetadata(
            field_id="timeoriginalestimate",
            name="Original Estimate",
            schema_type="number",
            clause_names=("original_estimate",),
        ),
        JiraFieldMetadata(
            field_id="aggregatetimeoriginalestimate",
            name="Original Estimate",
            schema_type="number",
            clause_names=("original_estimate",),
        ),
    ]

    registry = registry_from_metadata(metadata)
    field_id_plan = registry.build_plan(["aggregatetimeoriginalestimate"])

    assert [spec.name for spec in field_id_plan.active_specs] == ["aggregatetimeoriginalestimate"]


def test_metadata_inference_handles_option_and_user_arrays() -> None:
    option_field = JiraFieldMetadata(
        field_id="customfield_40001",
        name="Failure Category",
        schema_type="option",
        custom=True,
        custom_id=40001,
    )
    user_array_field = JiraFieldMetadata(
        field_id="customfield_40002",
        name="Reviewers",
        schema_type="array",
        schema_items="user",
        custom=True,
        custom_id=40002,
    )

    option_spec = infer_field_spec_from_metadata(option_field)
    user_array_spec = infer_field_spec_from_metadata(user_array_field)

    assert option_spec.path == "fields.customfield_40001.value"
    assert user_array_spec.path == "fields.customfield_40002[].displayName"
