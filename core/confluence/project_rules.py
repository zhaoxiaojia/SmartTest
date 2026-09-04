from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class RuleEntry:
    stable_key: str
    source_page: str
    source_field: str
    output_key: str
    owner: str
    failure_semantic: str


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
_ROLE_IDS = {rule.source_field.casefold(): rule.stable_key for rule in ROLE_RULES}
MAJOR_QA_ROLE_ID = _ROLE_IDS["major fae qa"]


def canonical_project_role_id(value):
    normalized = re.sub(r"\s+", " ", str(value or "")).strip().casefold()
    return _ROLE_IDS.get(normalized, "")

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
