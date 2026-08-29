from __future__ import annotations

import re
import os
import hashlib
from threading import Lock
from core.config.jsonTool import app_data_dir
from core.logging import smart_log
from core.confluence import ConfluenceClient, ConfluenceClientConfig

from core.tools.common.project_weekly_audit import (
    PRODUCT_SPACE_FACET,
    PROJECT_SPACE_FACET_DEFINITIONS,
    refresh_project_catalogs,
    extract_project_detail,
    query_project_facts,
)
from .confluence_repository import ConfluenceCurrentStateRepository
from .confluence_migration import LegacyConfluenceSnapshotMigration
from .confluence_sync import ConfluenceProjectSyncCoordinator
from .session import default_web_database_path


class ProjectFactsWebOwner:
    """Read-only Web transport over the durable Core project-facts owner."""

    def __init__(self, load_snapshot=None, client_factory=None, data_root=None,
                 sync_coordinator=None):
        database_path = ((data_root / "smarttest-web.db") if data_root else default_web_database_path())
        self._repository = ConfluenceCurrentStateRepository(database_path)
        self._sync_coordinator = sync_coordinator or ConfluenceProjectSyncCoordinator(self._repository)
        self._legacy_data_root = data_root or (app_data_dir() / "web" / "confluence-accounts")
        self._legacy_migration = LegacyConfluenceSnapshotMigration(
            self._repository, self._legacy_data_root,
        )
        self._load_snapshot = load_snapshot
        self._client_factory = client_factory or self._make_client
        self._refresh_lock = Lock()

    @staticmethod
    def _make_client(username, password):
        base_url = os.getenv("SMARTTEST_CONFLUENCE_BASE_URL", "https://confluence.amlogic.com")
        return ConfluenceClient(ConfluenceClientConfig(base_url), username, password)

    @staticmethod
    def normalize_account(username):
        return str(username or "").strip().casefold()

    def store_for(self, username):
        account = self.normalize_account(username)
        store = self._repository.account_store(account)
        namespace = hashlib.sha256(account.encode("utf-8")).hexdigest()
        self._legacy_migration.import_account(account, namespace)
        return store

    def refresh(self, username, password):
        store = self.store_for(username)
        with self._refresh_lock:
            smart_log("Confluence project facts refresh started (cache=%s)", store.resolved_path,
                      platform="web", domain="confluence", source="ProjectFactsWebOwner")
            client = self._client_factory(username, password)
            memory = _CatalogSyncBuffer(store.load())
            snapshot = refresh_project_catalogs(client, memory)
            space_keys = sorted({row.get("space_key") for row in snapshot.get("projects", ()) if row.get("space_key")})
            cql = "type=page AND space in (%s)" % ",".join(f'"{key}"' for key in space_keys)
            visible_ids = {page.id for page in client.search_page_metadata(cql)}
            snapshot = {**snapshot, "projects": [row for row in snapshot.get("projects", ())
                                                  if str(row.get("page_id") or "") in visible_ids]}
            store.save(snapshot)
            counts = {key: sum(1 for row in snapshot.get("projects", []) if row.get("status") == key)
                      for key in ("current", "stale", "failed", "inactive")}
            smart_log("Confluence project facts refresh finished (spaces=%s, projects=%s, result=%s)",
                      len(snapshot.get("sources", [])), len(snapshot.get("projects", [])),
                      "partial_success" if counts["stale"] or counts["failed"] else "ready",
                      platform="web", domain="confluence", source="ProjectFactsWebOwner", extra=counts)
        return self.query(username)

    def sync_details(self, username, password, *, filters=None, search="", cancelled=None, progress=None):
        store = self.store_for(username)
        snapshot = store.load()
        if snapshot is None:
            return self.query(username, filters=filters, search=search)
        matched = query_project_facts(snapshot, filters=filters, search=search).get("projects", [])
        client = self._client_factory(username, password)
        progress = progress or (lambda *_: None)
        progress(0, len(matched))

        def fetch(project):
            return extract_project_detail(client, project)

        self._sync_coordinator.sync(matched, fetch, cancelled=cancelled or (lambda: False),
                                    progress=progress)
        return self.query(username, filters=filters, search=search)

    def query(self, username, *, filters=None, search=""):
        store = self.store_for(username)
        try:
            snapshot = self._load_snapshot(username) if self._load_snapshot else store.load()
        except ValueError:
            return self._state("schema_error")
        if snapshot is None:
            smart_log("Confluence project facts cache miss (cache=%s)", store.resolved_path,
                      platform="web", domain="confluence", source="ProjectFactsWebOwner")
            return self._state("no_snapshot")
        smart_log("Confluence project facts cache hit (cache=%s, projects=%s)",
                  store.resolved_path, len(snapshot.get("projects", [])),
                  platform="web", domain="confluence", source="ProjectFactsWebOwner")
        result = query_project_facts(snapshot, filters=filters, search=search)
        counts = {
            state: sum(1 for row in snapshot.get("projects", []) if row.get("status") == state)
            for state in ("stale", "failed", "inactive")
        }
        state = ("loading" if snapshot.get("phase") == "catalog_loading" else
                 "partial_success" if counts["stale"] or counts["failed"] else "ready")
        return {
            "state": state,
            "revision": int(snapshot.get("revision") or 0),
            "accessibleProjectCount": sum(1 for row in snapshot.get("projects", ()) if row.get("active", True)),
            "catalogProgress": snapshot.get("catalog_progress"),
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
        return {"state": state, "revision": 0, "accessibleProjectCount": 0,
                "snapshotTime": None, "catalogProgress": None,
                "facets": facets, "projects": [],
                "ownerHierarchy": [{"role": role, "people": []} for role in ("Major FAE QA", "FAE QA", "QA Reviewer")],
                "discrepancies": [], "counts": {"stale": 0, "failed": 0, "inactive": 0}}


def _normalize(value):
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


class _CatalogSyncBuffer:
    """Transient buffer used only until catalog visibility is atomically replaced."""

    def __init__(self, snapshot=None):
        self._snapshot = snapshot

    def load(self):
        return self._snapshot

    def save(self, snapshot):
        self._snapshot = snapshot
