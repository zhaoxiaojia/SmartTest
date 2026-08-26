from __future__ import annotations

import re
import os
from threading import Lock
from core.logging import smart_log
from support.confluence_integration import ConfluenceClient, ConfluenceClientConfig

from core.tools.common.project_weekly_audit import (
    PRODUCT_SPACE_FACET,
    PROJECT_SPACE_FILTER_FIELDS,
    PROJECT_SPACE_FACET_DEFINITIONS,
    ProjectFactStore,
    ProjectFactsSchemaError,
    refresh_project_facts,
    query_project_facts,
)


class ProjectFactsWebOwner:
    """Read-only Web transport over the durable Core project-facts owner."""

    def __init__(self, load_snapshot=None, store=None, client_factory=None):
        self._store = store or ProjectFactStore()
        self._load_snapshot = load_snapshot or self._store.load
        self._client_factory = client_factory or self._make_client
        self._refresh_lock = Lock()

    @staticmethod
    def _make_client(username, password):
        base_url = os.getenv("SMARTTEST_CONFLUENCE_BASE_URL", "https://confluence.amlogic.com")
        return ConfluenceClient(ConfluenceClientConfig(base_url), username, password)

    def refresh(self, username, password):
        with self._refresh_lock:
            smart_log("Confluence project facts refresh started (cache=%s)", self._store.resolved_path,
                      platform="web", domain="confluence", source="ProjectFactsWebOwner")
            snapshot = refresh_project_facts(self._client_factory(username, password), self._store)
            counts = {key: sum(1 for row in snapshot.get("projects", []) if row.get("status") == key)
                      for key in ("current", "stale", "failed", "inactive")}
            smart_log("Confluence project facts refresh finished (spaces=%s, projects=%s, result=%s)",
                      len(snapshot.get("sources", [])), len(snapshot.get("projects", [])),
                      "partial_success" if counts["stale"] or counts["failed"] else "ready",
                      platform="web", domain="confluence", source="ProjectFactsWebOwner", extra=counts)
        return self.query()

    def query(self, *, filters=None, search=""):
        try:
            snapshot = self._load_snapshot()
        except ProjectFactsSchemaError:
            return self._state("schema_error")
        if snapshot is None:
            smart_log("Confluence project facts cache miss (cache=%s)", self._store.resolved_path,
                      platform="web", domain="confluence", source="ProjectFactsWebOwner")
            return self._state("no_snapshot")
        smart_log("Confluence project facts cache hit (cache=%s, projects=%s)",
                  self._store.resolved_path, len(snapshot.get("projects", [])),
                  platform="web", domain="confluence", source="ProjectFactsWebOwner")
        result = query_project_facts(snapshot, filters=filters, search=search)
        counts = {
            state: sum(1 for row in snapshot.get("projects", []) if row.get("status") == state)
            for state in ("stale", "failed", "inactive")
        }
        state = "partial_success" if counts["stale"] or counts["failed"] else "ready"
        return {
            "state": state,
            "snapshotTime": snapshot.get("updated_at"),
            "facets": self._facets(snapshot, result.get("facets", {})),
            "projects": result.get("projects", []),
            "ownerHierarchy": result.get("ownerHierarchy", []),
            "discrepancies": snapshot.get("field_discrepancies", []),
            "counts": counts,
        }

    @staticmethod
    def _facets(snapshot, facets):
        labels = {}
        for project in snapshot.get("projects", []):
            for header in project.get("raw_headers", []):
                labels.setdefault(_normalize(header), set()).add(str(header))
        canonical_labels = dict(PROJECT_SPACE_FACET_DEFINITIONS)
        fixed_keys = [key for key, _label in PROJECT_SPACE_FACET_DEFINITIONS]
        raw_order = [
            _normalize(header)
            for project in snapshot.get("projects", []) for header in project.get("raw_headers", [])
        ]
        extra_keys = list(dict.fromkeys(key for key in raw_order if key not in fixed_keys and key in facets))
        extra_keys.extend(key for key in facets if key not in fixed_keys and key not in extra_keys)
        ordered_keys = [*fixed_keys, *extra_keys]
        return [
            {
                "key": key,
                "label": canonical_labels.get(key) or sorted(labels.get(key, {key}), key=str.casefold)[0],
                "labels": sorted(labels.get(key, {canonical_labels.get(key, key)}), key=str.casefold),
                "options": facets.get(key, []),
                **({"source": "Confluence page version metadata"} if key == "__last_updated__" else {}),
            }
            for key in ordered_keys
        ]

    @staticmethod
    def _state(state):
        facets = [
            {"key": key, "label": label, "labels": [label], "options": [],
             **({"source": "Confluence page version metadata"} if key == "__last_updated__" else {})}
            for key, label in PROJECT_SPACE_FACET_DEFINITIONS
        ]
        return {"state": state, "snapshotTime": None, "facets": facets, "projects": [],
                "ownerHierarchy": [{"role": role, "people": []} for role in ("Major FAE QA", "FAE QA", "QA Reviewer")],
                "discrepancies": [], "counts": {"stale": 0, "failed": 0, "inactive": 0}}


def _normalize(value):
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()
