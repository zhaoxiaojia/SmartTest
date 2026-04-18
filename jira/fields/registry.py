from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Iterable

from jira.cache.metadata_cache import JiraFieldMetadataCache
from jira.core.models import JiraFieldMetadata
from jira.fields.specs import FieldSpec


@dataclass(frozen=True)
class FieldFetchPlan:
    active_specs: tuple[FieldSpec, ...]
    deferred_specs: tuple[FieldSpec, ...]
    jira_fields: tuple[str, ...]
    expand: tuple[str, ...]

    @property
    def has_deferred_fields(self) -> bool:
        return len(self.deferred_specs) > 0


class FieldRegistry:
    def __init__(self) -> None:
        self._by_name: dict[str, FieldSpec] = {}
        self._metadata_by_id: dict[str, JiraFieldMetadata] = {}

    def register(self, spec: FieldSpec, *aliases: str) -> FieldSpec:
        keys = {spec.name, *aliases}
        canonical = spec
        for key in keys:
            normalized = self._normalize_name(key)
            existing = self._by_name.get(normalized)
            if existing is not None:
                if existing == canonical or _specs_equivalent(existing, canonical):
                    canonical = existing
                    continue
                raise ValueError(f"field alias already registered: {key}")
        for key in keys:
            normalized = self._normalize_name(key)
            self._by_name[normalized] = canonical
        return canonical

    def register_metadata_fields(self, metadata_items: Iterable[JiraFieldMetadata]) -> None:
        for metadata in metadata_items:
            self._metadata_by_id[metadata.field_id] = metadata
            if not metadata.field_id:
                continue
            self._register_metadata_field(metadata)

    @classmethod
    def bootstrap_from_client(
        cls,
        client,
        *,
        metadata_cache: JiraFieldMetadataCache | None = None,
        ttl_seconds: float | None = None,
        include_defaults: bool = True,
    ) -> "FieldRegistry":
        metadata_items = None
        if metadata_cache is not None:
            metadata_items = metadata_cache.get(
                base_url=client.config.base_url,
                ttl_seconds=ttl_seconds,
            )
        if metadata_items is None:
            metadata_items = client.fetch_fields_metadata()
            if metadata_cache is not None:
                metadata_cache.put(base_url=client.config.base_url, metadata_items=metadata_items)

        registry = build_default_registry() if include_defaults else cls()
        registry.register_metadata_fields(metadata_items)
        return registry

    def resolve(self, requested: Iterable[str | FieldSpec]) -> list[FieldSpec]:
        specs: list[FieldSpec] = []
        for item in requested:
            if isinstance(item, FieldSpec):
                specs.append(item)
                continue
            normalized = self._normalize_name(item)
            existing = self._by_name.get(normalized)
            if existing is not None:
                specs.append(existing)
                continue
            specs.append(FieldSpec(name=item, path=item))
        return specs

    def build_plan(self, requested: Iterable[str | FieldSpec], *, include_heavy: bool = False) -> FieldFetchPlan:
        resolved = self.resolve(requested)
        active_specs: list[FieldSpec] = []
        deferred_specs: list[FieldSpec] = []
        jira_fields: set[str] = {"key"}
        expand: set[str] = set()

        for spec in resolved:
            if spec.heavy and not include_heavy:
                deferred_specs.append(spec)
                continue
            active_specs.append(spec)
            jira_fields.update(spec.required_jira_fields())
            expand.update(spec.required_expand())

        return FieldFetchPlan(
            active_specs=tuple(active_specs),
            deferred_specs=tuple(deferred_specs),
            jira_fields=tuple(sorted(jira_fields)),
            expand=tuple(sorted(expand)),
        )

    @staticmethod
    def _normalize_name(name: str) -> str:
        return _normalize_field_alias(name)

    @staticmethod
    def _aliases_from_metadata(metadata: JiraFieldMetadata) -> tuple[str, ...]:
        aliases = {metadata.field_id}
        normalized_name = _normalize_field_alias(metadata.name)
        if normalized_name:
            aliases.add(normalized_name)
        for clause_name in metadata.clause_names:
            if clause_name:
                aliases.add(clause_name)
                aliases.add(_normalize_field_alias(clause_name))
        if metadata.custom and metadata.custom_id is not None:
            aliases.add(f"customfield_{metadata.custom_id}")
        aliases.discard("")
        aliases.discard(metadata.name)
        return tuple(sorted(aliases))

    @staticmethod
    def _spec_from_metadata(metadata: JiraFieldMetadata) -> FieldSpec:
        path = f"fields.{metadata.field_id}"
        schema_type = (metadata.schema_type or "").lower()
        if schema_type == "option":
            path = f"{path}.value"
        elif schema_type in {"user", "priority", "status", "resolution", "issuetype", "project"}:
            path = f"{path}.name" if schema_type != "user" else f"{path}.displayName"
        elif schema_type in {"version", "component"}:
            path = f"{path}.name"
        elif schema_type == "array":
            path = _array_field_path(metadata)
        return FieldSpec(name=metadata.name, path=path, jira_fields=(metadata.field_id,))

    def _register_metadata_field(self, metadata: JiraFieldMetadata) -> None:
        spec = self._spec_from_metadata(metadata)
        canonical_name = spec.name or metadata.field_id
        if self._alias_conflicts(canonical_name, spec):
            canonical_name = metadata.field_id
        canonical_spec = FieldSpec(
            name=canonical_name,
            path=spec.path,
            default=spec.default,
            converter=spec.converter,
            jira_fields=spec.jira_fields,
            expand=spec.expand,
            heavy=spec.heavy,
        )

        accepted_aliases: list[str] = []
        for alias in self._aliases_from_metadata(metadata):
            if self._normalize_name(alias) == self._normalize_name(canonical_spec.name):
                continue
            if self._alias_conflicts(alias, canonical_spec):
                logging.debug(
                    "Skipping conflicting Jira field alias '%s' for field_id=%s name=%s",
                    alias,
                    metadata.field_id,
                    metadata.name,
                )
                continue
            accepted_aliases.append(alias)

        self.register(canonical_spec, *accepted_aliases)

    def _alias_conflicts(self, alias: str, spec: FieldSpec) -> bool:
        normalized = self._normalize_name(alias)
        existing = self._by_name.get(normalized)
        if existing is None:
            return False
        return not (existing == spec or _specs_equivalent(existing, spec))


def build_default_registry() -> FieldRegistry:
    registry = FieldRegistry()
    registry.register(FieldSpec(name="key", path="key"))
    registry.register(FieldSpec(name="id", path="id"))
    registry.register(FieldSpec(name="summary", path="fields.summary"))
    registry.register(FieldSpec(name="status", path="fields.status.name"))
    registry.register(FieldSpec(name="assignee", path="fields.assignee.displayName"))
    registry.register(FieldSpec(name="reporter", path="fields.reporter.displayName"))
    registry.register(FieldSpec(name="priority", path="fields.priority.name"))
    registry.register(FieldSpec(name="labels", path="fields.labels[]"))
    registry.register(FieldSpec(name="components", path="fields.components[].name"))
    registry.register(FieldSpec(name="fix_versions", path="fields.fixVersions[].name"), "fixVersions")
    registry.register(FieldSpec(name="updated", path="fields.updated"))
    registry.register(FieldSpec(name="created", path="fields.created"))
    registry.register(
        FieldSpec(
            name="changelog_statuses",
            path="changelog.histories[].items[].toString",
            heavy=True,
        )
    )
    return registry


def registry_from_metadata(metadata_items: Iterable[JiraFieldMetadata]) -> FieldRegistry:
    registry = build_default_registry()
    registry.register_metadata_fields(metadata_items)
    return registry


def infer_field_spec_from_metadata(metadata: JiraFieldMetadata) -> FieldSpec:
    return FieldRegistry._spec_from_metadata(metadata)


def _normalize_field_alias(value: str) -> str:
    cleaned = (value or "").strip().lower()
    cleaned = cleaned.replace("-", "").replace("_", " ")
    cleaned = re.sub(r"[^a-z0-9\s\[\]]+", " ", cleaned)
    return "_".join(part for part in cleaned.split())


def _array_field_path(metadata: JiraFieldMetadata) -> str:
    base = f"fields.{metadata.field_id}[]"
    schema_items = (metadata.schema_items or "").lower()
    schema_custom = (metadata.schema_custom or "").lower()
    if "labels" in schema_custom or metadata.field_id == "labels":
        return base
    if schema_items in {"string", "number", "date", "datetime"}:
        return base
    if schema_items == "user":
        return f"{base}.displayName"
    if schema_items == "option" or "multiselect" in schema_custom or "select" in schema_custom:
        return f"{base}.value"
    if schema_items in {"version", "component", "status", "priority", "resolution", "issuetype", "project"}:
        return f"{base}.name"
    return f"{base}.name"


def _specs_equivalent(left: FieldSpec, right: FieldSpec) -> bool:
    return (
        left.path == right.path
        and left.default == right.default
        and left.converter is right.converter
        and left.heavy == right.heavy
        and left.required_jira_fields() == right.required_jira_fields()
        and left.required_expand() == right.required_expand()
    )
