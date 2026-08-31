from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
import re


@dataclass(frozen=True)
class RuleEntry:
    stable_key: str
    source_page: str
    source_field: str
    output_key: str
    owner: str
    failure_semantic: str


@dataclass(frozen=True)
class AuditAttentionPoint(RuleEntry):
    label: str
    heading_names: tuple[str, ...] = ()
    table_fields: tuple[str, ...] = ()
    use_page_body: bool = False
    table_region_fields: tuple[str, ...] = ()
    heading_boundary: Literal["sibling", "page_end"] = "sibling"

    @property
    def rule_id(self):
        return self.stable_key

    @property
    def page_kind(self):
        return self.source_page

    @property
    def standard_name(self):
        return self.output_key


def _attention(stable_key, source_page, label, output_key, heading_names=(),
               table_fields=(), use_page_body=False, table_region_fields=(),
               heading_boundary="sibling"):
    return AuditAttentionPoint(
        stable_key, source_page, output_key, output_key,
        "extract_page_region", "invalid_format", label, heading_names,
        table_fields, use_page_body, table_region_fields, heading_boundary,
    )


UPDATE_MATRIX_POINTS = (
    _attention("test.weekly", "test_information",
               "Basic Information.Test Information.Phase Status（当前阶段测试状态）",
               "Phase Status", ("Phase Status", "Software Testing Status"), ("Phase Status",)),
    _attention("test.summary", "test_information",
               "Basic Information.Test Information.项目整体状态Summary",
               "Summary", ("Summary",), ("Summary",)),
    _attention("test.tasks", "test_information",
               "Basic Information.Test Information.Task Arrangement of Important Test（Must give ETA）",
               "Task Arrangement", ("Task Arrangement",), ("Task Arrangement",)),
    _attention("test.blocking", "test_information",
               "Basic Information.Test Information.Blocking QA Testing Items",
               "Blocking", ("Blocking",)),
    _attention("plan.test", "test_plan",
               "Basic Information.Test Information.Test Plan.Category", "Category",
               table_region_fields=("Category",)),
    _attention("environment.setup", "environment",
               "Basic Information.Test Information.Test Environment Setup and Precautions.测试环境搭建以及注意事项",
               "测试环境", ("测试环境", "Test Environment"),
               heading_boundary="page_end"),
    _attention("experience.page", "experience",
               "Basic Information.Test Information.Summary of Experience and Typical Cases",
               "Summary of Experience and Typical Cases", use_page_body=True),
    _attention("report.weekly", "report_store",
               "Basic Information.Test Information.Test Report Store",
               "Test Report Store", use_page_body=True),
)


BASIC_INFORMATION_RULE = RuleEntry(
    "page.basic_information", "project", "Basic Information", "basic",
    "locate_basic_information", "Basic Information page was not found",
)

ROLE_RULES = tuple(
    RuleEntry(f"role.{re.sub(r'[^a-z]+', '_', label.casefold()).strip('_')}",
              "basic", label, label, "extract_project_roles", "empty")
    for label in ("Major FAE QA", "FAE QA", "QA Reviewer")
)
ROLE_LABELS = tuple(rule.source_field for rule in ROLE_RULES)

_CONFIRMED_PROJECT_FIELDS = (
    "page", "project id", "date of commercial approval", "support mode",
    "project status", "current stage",
)
PROJECT_FIELD_RULES = tuple(
    RuleEntry(f"project_field.{field.replace(' ', '_')}", "project_space", field,
              field, "normalize_project_field", "discrepancy")
    for field in _CONFIRMED_PROJECT_FIELDS
)
CANONICAL_PROJECT_FIELDS = frozenset(rule.output_key for rule in PROJECT_FIELD_RULES)
PROJECT_FIELD_ALIASES = {"页面": "page", "page": "page"}


def normalize_project_field(value):
    normalized = re.sub(r"\s+", " ", str(value or "")).strip().casefold()
    return PROJECT_FIELD_ALIASES.get(normalized, normalized)
