from datetime import datetime, timezone

import pytest

from core.confluence.models import ConfluencePage
from core.tools.common import project_weekly_audit
from core.tools.common.project_weekly_audit.models import ProductLine
from core.tools.common.project_weekly_audit.project_facts import (
    PRODUCT_SPACE_FACET,
    ProjectFactStore,
    ProjectFactsSchemaError,
    query_project_facts,
    refresh_project_catalogs,
    enrich_project_facts,
    refresh_project_facts,
)


def _space(version=1, rows=None):
    rows = rows or [
        ("101", "Alpha", "A", "NORMAL", "Stage 1", "Owner-X"),
        ("102", "Beta", "B", "PAUSED", "Stage 5", "Owner-Y"),
    ]
    body = (
        "<table><tr><th>Page</th><th>Project ID</th><th>Support Mode</th>"
        "<th>Project Status</th><th>Current Stage</th><th>Unexpected Owner</th></tr>"
        + "".join(
            f'<tr><td><a href="/pages/viewpage.action?pageId={pid}">{name}</a></td>'
            f"<td>{name}-ID</td><td>{mode}</td><td>{status}</td><td>{stage}</td><td>{owner}</td></tr>"
            for pid, name, mode, status, stage, owner in rows
        )
        + "</table>"
    )
    return ConfluencePage("space", "Project Space", "https://c/display/X/Project+Space", view_body=body,
                          version=version, updated_at=datetime(2026, 8, version, tzinfo=timezone.utc))


def _basic(pid, version=1):
    body = f"""
    <table>
      <tr><th>Major FAE QA</th><td><ac:link><ri:user ri:account-id="major-{pid}"/></ac:link> Major</td></tr>
      <tr><th>FAE QA</th><td><a href="/people?accountId=fae-{pid}">Fae One</a>, Fae Two</td></tr>
      <tr><th>QA Reviewer</th><td><a data-username="review-{pid}">Reviewer</a></td></tr>
    </table>"""
    return ConfluencePage(pid, f"{pid}-Basic Information", f"https://c/pages/{pid}", body=body,
                          version=version, updated_at=datetime(2026, 8, version, tzinfo=timezone.utc))


class Client:
    def __init__(self, space=None, failures=(), metadata_versions=None, metadata_failure=False):
        self.space = space or _space()
        self.failures = set(failures)
        self.detail_calls = []
        self.metadata_versions = metadata_versions or {"101": 1, "102": 1}
        self.metadata_failure = metadata_failure

    def get_page_by_url(self, url, *, prefer_export=False):
        if "Project+Space" in url:
            return self.space
        pid = url.split("pageId=")[-1]
        return ConfluencePage(pid, f"{pid} Project", url, version=1)

    def get_page_children(self, page_id):
        if self.metadata_failure:
            raise RuntimeError("metadata offline")
        pid = str(page_id).removeprefix("basic-")
        if not str(page_id).startswith("basic-"):
            version = self.metadata_versions.get(pid, 1)
            return [ConfluencePage(f"basic-{pid}", f"{pid}-Basic Information", f"https://c/pages/{pid}",
                                   version=version,
                                   updated_at=datetime(2026, 8, version, tzinfo=timezone.utc))]
        return []

    def get_page(self, pid):
        source_pid = str(pid).removeprefix("basic-")
        self.detail_calls.append(source_pid)
        if source_pid in self.failures:
            raise RuntimeError("offline")
        page = _basic(source_pid, self.metadata_versions.get(source_pid, 1))
        return ConfluencePage(str(pid), page.title, page.url, body=page.body,
                              version=page.version, updated_at=page.updated_at)


def test_full_catalog_preserves_unknown_columns_and_exact_multi_person_roles(tmp_path):
    assert project_weekly_audit.ProjectFactStore is ProjectFactStore
    client = Client()
    snapshot = refresh_project_facts(client, ProjectFactStore(tmp_path / "facts.json"),
                                     (ProductLine("X", client.space.url, "Line X"),))

    assert [row["project_id"] for row in snapshot["projects"]] == ["Alpha-ID", "Beta-ID"]
    assert snapshot["projects"][1]["fields"]["support mode"] == "B"
    assert snapshot["projects"][1]["fields"]["current stage"] == "Stage 5"
    assert snapshot["projects"][0]["raw_fields"]["Unexpected Owner"] == "Owner-X"
    assert snapshot["projects"][0]["raw_field_html"]["Page"].startswith("<a href=")
    assert snapshot["projects"][0]["catalog_source"]["version"] == 1
    assert snapshot["field_discrepancies"] == ["Unexpected Owner"]
    roles = snapshot["projects"][0]["roles"]
    assert [person["identity"] for person in roles["Major FAE QA"]] == ["major-101"]
    assert [person["name"] for person in roles["FAE QA"]] == ["Fae One", "Fae Two"]
    assert roles["QA Reviewer"][0]["identity"] == "review-101"


def test_structured_role_users_expand_independently_and_ignore_interleaved_notes(tmp_path):
    identities = [f"user-{index:02d}" for index in range(1, 12)]
    entries = "".join(
        f'<ac:link><ri:user ri:userkey="{identity}"/></ac:link> '
        f'{"NPI Owner" if index % 2 else "NPI HDMI/Audio"}<br/>'
        for index, identity in enumerate(identities, 1)
    ) + '<ac:link><ri:user ri:userkey="user-01"/></ac:link> certification description'

    class EspressoClient(Client):
        def get_page(self, pid):
            self.detail_calls.append(str(pid).removeprefix("basic-"))
            body = f"<table><tr><th>FAE QA</th><td>{entries}</td></tr><tr><th>QA Reviewer</th><td>NA, TBD</td></tr></table>"
            return ConfluencePage(str(pid), "Basic Information", "https://c/basic", body=body, version=1)

        def get_user_display_name(self, identity):
            return f"Member {identity.removeprefix('user-')}"

    client = EspressoClient(_space(rows=[("101", "Espresso", "A", "NORMAL", "Stage 3", "Owner-X")]))
    store = ProjectFactStore(tmp_path / "facts.json")
    refresh_project_catalogs(client, store, (ProductLine("X", client.space.url, "Line X"),))
    snapshot = enrich_project_facts(client, store)
    people = snapshot["projects"][0]["roles"]["FAE QA"]
    assert len(people) == 11
    assert [person["identity"] for person in people] == identities
    assert all(person["name"].startswith("Member ") for person in people)
    assert not {"NPI Owner", "NPI HDMI/Audio", "certification description"} & {person["name"] for person in people}
    assert [person["name"] for person in snapshot["projects"][0]["roles"]["QA Reviewer"]] == ["NA", "TBD"]

    hierarchy_people = query_project_facts(snapshot)["ownerHierarchy"][1]["people"]
    assert len(hierarchy_people) == 11
    assert all(len(person["projects"]) == 1 for person in hierarchy_people)


def test_incremental_refresh_skips_unchanged_and_refetches_only_changed_row(tmp_path):
    store = ProjectFactStore(tmp_path / "facts.json")
    first = Client()
    refresh_project_facts(first, store, (ProductLine("X", first.space.url, "Line X"),))
    unchanged = Client()
    refresh_project_facts(unchanged, store, (ProductLine("X", unchanged.space.url, "Line X"),))
    assert unchanged.detail_calls == []

    changed_space = _space(2, [
        ("101", "Alpha", "A", "AT RISK", "Stage 1", "Owner-X"),
        ("102", "Beta", "B", "PAUSED", "Stage 5", "Owner-Y"),
    ])
    changed = Client(changed_space)
    snapshot = refresh_project_facts(changed, store, (ProductLine("X", changed.space.url, "Line X"),))
    assert changed.detail_calls == ["101"]
    assert next(row for row in snapshot["projects"] if row["project_id"] == "Alpha-ID")["fields"]["project status"] == "AT RISK"


def test_unchanged_catalog_refetches_only_basic_body_with_changed_version(tmp_path):
    store = ProjectFactStore(tmp_path / "facts.json")
    first = Client()
    refresh_project_facts(first, store, (ProductLine("X", first.space.url, "Line X"),))

    changed = Client(metadata_versions={"101": 2, "102": 1})
    snapshot = refresh_project_facts(changed, store, (ProductLine("X", changed.space.url, "Line X"),))

    assert changed.detail_calls == ["101"]
    alpha = next(row for row in snapshot["projects"] if row["project_id"] == "Alpha-ID")
    assert alpha["detail_source"]["version"] == 2


def test_metadata_failure_preserves_roles_as_stale(tmp_path):
    store = ProjectFactStore(tmp_path / "facts.json")
    first = Client()
    refresh_project_facts(first, store, (ProductLine("X", first.space.url, "Line X"),))

    failed = Client(metadata_failure=True)
    snapshot = refresh_project_facts(failed, store, (ProductLine("X", failed.space.url, "Line X"),))

    assert failed.detail_calls == []
    assert {row["status"] for row in snapshot["projects"]} == {"stale"}
    assert snapshot["projects"][0]["roles"]["Major FAE QA"]


def test_partial_failure_retains_stale_fact_and_missing_project_becomes_inactive(tmp_path):
    store = ProjectFactStore(tmp_path / "facts.json")
    first = Client()
    refresh_project_facts(first, store, (ProductLine("X", first.space.url, "Line X"),))
    changed_space = _space(2, [("101", "Alpha", "A", "AT RISK", "Stage 1", "Owner-X")])
    snapshot = refresh_project_facts(Client(changed_space, failures=("101",)), store,
                                     (ProductLine("X", changed_space.url, "Line X"),))
    alpha = next(row for row in snapshot["projects"] if row["project_id"] == "Alpha-ID")
    beta = next(row for row in snapshot["projects"] if row["project_id"] == "Beta-ID")
    assert alpha["status"] == "stale" and alpha["error"]["type"] == "RuntimeError"
    assert alpha["roles"]["Major FAE QA"][0]["identity"] == "major-101"
    assert beta["active"] is False


def test_query_and_facets_are_local_and_cover_normalized_fields(tmp_path):
    store = ProjectFactStore(tmp_path / "facts.json")
    client = Client()
    refresh_project_facts(client, store, (ProductLine("X", client.space.url, "Line X"),))
    result = query_project_facts(store.load(), filters={"unexpected owner": "Owner-Y"}, search="fae-102")
    assert [row["project_id"] for row in result["projects"]] == ["Beta-ID"]
    assert result["facets"]["support mode"] == ["B"]
    assert result["facets"][PRODUCT_SPACE_FACET] == [{"value": "X", "label": "Line X"}]
    assert result["facets"]["major pm"] == []
    assert result["facets"]["date of commercial approval"] == []
    assert [role["role"] for role in result["ownerHierarchy"]] == [
        "Major FAE QA", "FAE QA", "QA Reviewer",
    ]
    assert result["ownerHierarchy"][1]["people"][0]["identity"] == "fae-102"
    assert result["ownerHierarchy"][1]["people"][0]["projects"][0]["project_id"] == "Beta-ID"
    assert client.detail_calls == ["101", "102"]

    scoped = query_project_facts(store.load(), filters={PRODUCT_SPACE_FACET: "X"})
    assert {row["project_id"] for row in scoped["projects"]} == {"Alpha-ID", "Beta-ID"}
    assert query_project_facts(store.load(), filters={PRODUCT_SPACE_FACET: "TV"})["projects"] == []


def test_commercial_approval_filter_uses_existing_year_semantics():
    snapshot = {"source": "test", "projects": [{
        "identity": "DOPL:A", "project_id": "A", "name": "A", "space_key": "DOPL",
        "active": True, "status": "current", "roles": {},
        "fields": {"date of commercial approval": "26 Aug 2026"},
    }]}
    assert query_project_facts(snapshot)["facets"]["date of commercial approval"] == [2026]
    assert len(query_project_facts(snapshot, filters={"date of commercial approval": "2026"})["projects"]) == 1
    assert query_project_facts(snapshot, filters={"date of commercial approval": "2025"})["projects"] == []


def test_query_filters_use_or_within_fields_and_and_across_fields():
    snapshot = {"source": "test", "projects": [
        {"project_id": "A", "name": "A", "space_key": "DOPL", "active": True, "roles": {},
         "fields": {"support mode": "A", "project status": "NORMAL", "date of commercial approval": "2025-01-01"}},
        {"project_id": "B", "name": "B", "space_key": "SDPL", "active": True, "roles": {},
         "fields": {"support mode": "B", "project status": "NORMAL", "date of commercial approval": "2026-01-01"}},
        {"project_id": "C", "name": "C", "space_key": "TV", "active": True, "roles": {},
         "fields": {"support mode": "C", "project status": "CLOSED", "date of commercial approval": "2026-01-01"}},
    ]}
    result = query_project_facts(snapshot, filters={
        "support mode": ["A", "B", ""], "project status": ["NORMAL"],
        "date of commercial approval": ["2025", "2026"],
    })
    assert [row["project_id"] for row in result["projects"]] == ["A", "B"]


def test_query_logs_bounded_filter_summary_without_project_or_person_data(monkeypatch):
    records = []
    monkeypatch.setattr("core.tools.common.project_weekly_audit.project_facts.smart_log",
                        lambda message, *args, **kwargs: records.append((message % args, kwargs)))
    monkeypatch.setattr("core.tools.common.project_weekly_audit.project_collection.smart_log",
                        lambda message, *args, **kwargs: records.append((message % args, kwargs)))
    snapshot = {"source": "test", "projects": [{
        "project_id": "SECRET-PROJECT", "name": "Secret", "space_key": "DOPL",
        "active": True, "roles": {"FAE QA": [{"name": "Private Person", "identity": "uid-secret"}]},
        "fields": {"support mode": "A"},
    }]}
    query_project_facts(snapshot, filters={
        "support mode": ["A"], "project owner": ["Private Person"],
        "project id": ["SECRET-PROJECT"], "unexpected identity": ["uid-secret"],
    }, search="Private Person")
    message, kwargs = records[-1]
    assert "input=1 matched=0 excluded=1" in message
    assert kwargs["extra"]["filters"] == {
        "support mode": {"values": ["a"], "selected_count": 1},
        "project owner": {"selected_count": 1},
        "project id": {"selected_count": 1},
        "unexpected identity": {"selected_count": 1},
    }
    assert kwargs["extra"]["search_enabled"] is True
    assert "SECRET-PROJECT" not in str(records)
    assert "Private Person" not in str(records) and "uid-secret" not in str(records)


def test_store_rejects_corrupt_or_unknown_schema(tmp_path):
    path = tmp_path / "facts.json"
    path.write_text("not-json", encoding="utf-8")
    with pytest.raises(ProjectFactsSchemaError):
        ProjectFactStore(path).load()
    path.write_text('{"schema_version": 999, "projects": []}', encoding="utf-8")
    with pytest.raises(ProjectFactsSchemaError):
        ProjectFactStore(path).load()


def test_relative_store_uses_app_data_and_missing_is_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    store = ProjectFactStore("facts/project.json")
    assert store.load() is None
    store.save({"schema_version": 1, "projects": []})
    assert store.resolved_path == tmp_path / "Amlogic" / "SmartTest" / "facts" / "project.json"
    assert store.load()["projects"] == []


def test_roles_are_read_from_basic_information_child_when_catalog_links_project_root(tmp_path):
    class HierarchyClient(Client):
        def get_page_by_url(self, url, *, prefer_export=False):
            if "Project+Space" in url:
                return self.space
            return ConfluencePage("root", "Alpha Project", url, version=1)

        def get_page_children(self, page_id):
            if page_id == "root":
                return [ConfluencePage("section", "Project Details", "https://c/section", version=2)]
            if page_id == "section":
                return [ConfluencePage("basic", "2. Alpha-Basic Information", "https://c/basic", version=3)]
            return []

        def get_page(self, page_id):
            return _basic("basic", 3)

    client = HierarchyClient(_space(rows=[("101", "Alpha", "A", "NORMAL", "Stage 1", "Owner-X")]))
    snapshot = refresh_project_facts(client, ProjectFactStore(tmp_path / "facts.json"),
                                     (ProductLine("X", client.space.url, "Line X"),))
    assert snapshot["projects"][0]["detail_source"]["page_id"] == "basic"
    assert snapshot["projects"][0]["detail_path"] == ["root", "section", "basic"]
    assert snapshot["projects"][0]["roles"]["Major FAE QA"][0]["identity"] == "major-basic"


def test_status_catalog_entry_ascends_to_root_and_caches_resolved_ids(tmp_path):
    root = ConfluencePage("root", "Alpha", "https://c/root")
    status = ConfluencePage("status", "1. Alpha-Project Status Report", "https://c/status")
    basic = ConfluencePage("basic", "2. Alpha-Basic Information", "https://c/basic", version=3)

    class SiblingClient(Client):
        def get_page_by_url(self, url, *, prefer_export=False):
            if "Project+Space" in url:
                return self.space
            return status

        def get_parent_page(self, page_id):
            return root

        def get_page_children(self, page_id):
            return [status, basic] if page_id == "root" else []

        def get_page(self, page_id):
            return _basic("basic", 3)

    space = _space(rows=[("", "Alpha", "A", "NORMAL", "Stage 1", "Owner-X")])
    # Keep a catalog URL with no pageId while retaining a stable business project ID.
    space = ConfluencePage(space.id, space.title, space.url,
                           view_body=space.view_body.replace("pageId=", "project/"), version=space.version,
                           updated_at=space.updated_at)
    client = SiblingClient(space)
    snapshot = refresh_project_facts(client, ProjectFactStore(tmp_path / "facts.json"),
                                     (ProductLine("X", space.url, "Line X"),))
    row = snapshot["projects"][0]
    assert row["status"] == "current"
    assert row["entry_page_id"] == "status"
    assert row["root_page_id"] == "root"
    assert row["detail_source"]["page_id"] == "basic"


def test_url_less_catalog_reuses_resolved_root_when_url_resolution_later_fails(tmp_path):
    root = ConfluencePage("root", "Alpha", "https://c/root")
    status = ConfluencePage("status", "1. Alpha-Project Status Report", "https://c/status")
    basic = ConfluencePage("basic", "2. Alpha-Basic Information", "https://c/basic", version=3)

    class CachedRootClient(Client):
        def __init__(self, space, *, reject_project_url=False):
            super().__init__(space)
            self.reject_project_url = reject_project_url
            self.project_url_calls = 0

        def get_page_by_url(self, url, *, prefer_export=False):
            if "Project+Space" in url:
                return self.space
            self.project_url_calls += 1
            if self.reject_project_url:
                raise RuntimeError("URL resolution unavailable")
            return status

        def get_parent_page(self, page_id):
            return root

        def get_page_children(self, page_id):
            return [status, basic] if page_id == "root" else []

        def get_page(self, page_id):
            if page_id == "root":
                return root
            return _basic("basic", 3)

    space = _space(rows=[("", "Alpha", "A", "NORMAL", "Stage 1", "Owner-X")])
    space = ConfluencePage(space.id, space.title, space.url,
                           view_body=space.view_body.replace("pageId=", "project/"), version=space.version,
                           updated_at=space.updated_at)
    store = ProjectFactStore(tmp_path / "facts.json")
    first = CachedRootClient(space)
    refresh_project_facts(first, store, (ProductLine("X", space.url, "Line X"),))
    second = CachedRootClient(space, reject_project_url=True)

    snapshot = refresh_project_facts(second, store, (ProductLine("X", space.url, "Line X"),))

    assert second.project_url_calls == 0
    assert snapshot["projects"][0]["status"] == "current"
    assert snapshot["projects"][0]["root_page_id"] == "root"
    assert snapshot["projects"][0]["detail_source"]["page_id"] == "basic"


def test_stage_domain_uses_selected_space_union_independent_of_other_filters():
    snapshot = {"projects": [
        {"project_id": "A", "space_key": "DOPL", "active": True, "fields": {"current stage": "1 EVALUATION", "project status": "NORMAL"}},
        {"project_id": "B", "space_key": "SDPL", "active": True, "fields": {"current stage": "3 EVT", "project status": "PAUSED"}},
    ], "stage_domains": {"DOPL": ["1 EVALUATION", "2 DEVELOPMENT"], "SDPL": ["3 EVT"]}}
    all_spaces = query_project_facts(snapshot, filters={"project status": "NORMAL"})
    assert all_spaces["facets"]["current stage"] == ["1 EVALUATION", "2 DEVELOPMENT", "3 EVT"]
    dopl = query_project_facts(snapshot, filters={PRODUCT_SPACE_FACET: "DOPL", "project status": "PAUSED"})
    assert dopl["projects"] == []
    assert dopl["facets"]["current stage"] == ["1 EVALUATION", "2 DEVELOPMENT"]


def test_empty_snapshot_source_display_name_does_not_override_all_core_labels():
    snapshot = {"sources": [
        {"space_key": "DOPL", "display_name": None}, {"space_key": "SDPL", "display_name": ""},
        {"space_key": "TV", "display_name": None}, {"space_key": "OOPL", "display_name": ""},
    ], "projects": [
        {"project_id": key, "space_key": key, "active": True, "fields": {}}
        for key in ("DOPL", "SDPL", "TV", "OOPL")
    ]}
    options = query_project_facts(snapshot)["facets"][PRODUCT_SPACE_FACET]
    assert dict((item["value"], item["label"]) for item in options) == {
        "DOPL": "China Operator Business", "SDPL": "Smart Device Business",
        "TV": "TV Business", "OOPL": "Global Operator & STB Business",
    }


def test_permission_denied_space_is_silently_removed_from_account_snapshot(tmp_path):
    store = ProjectFactStore(tmp_path / "facts.json")
    client = Client()
    refresh_project_facts(client, store, (ProductLine("X", client.space.url, "Line X"),))

    class ForbiddenError(RuntimeError):
        response = type("Response", (), {"status_code": 403})()

    class ForbiddenClient(Client):
        def get_page_by_url(self, url, *, prefer_export=False):
            raise ForbiddenError("private details must not leak")

    snapshot = refresh_project_facts(
        ForbiddenClient(), store, (ProductLine("X", client.space.url, "Line X"),),
    )
    assert snapshot["projects"] == []
    assert snapshot["sources"] == []


def test_catalog_initialization_fetches_four_catalogs_and_no_project_details(tmp_path):
    class CatalogOnlyClient(Client):
        def __init__(self):
            super().__init__(_space(rows=[("101", "Alpha", "A", "NORMAL", "Stage 1", "Owner-X")]))
            self.catalog_calls = 0

        def get_page_by_url(self, url, *, prefer_export=False):
            self.catalog_calls += 1
            return self.space

        def get_page_children(self, page_id):
            raise AssertionError("catalog initialization must not discover project pages")

        def get_page(self, page_id):
            raise AssertionError("catalog initialization must not fetch Basic Information")

    client = CatalogOnlyClient()
    lines = tuple(ProductLine(key, f"https://c/{key}/Project+Space", key) for key in ("A", "B", "C", "D"))
    snapshot = refresh_project_catalogs(client, ProjectFactStore(tmp_path / "facts.json"), lines)
    assert client.catalog_calls == 4
    assert snapshot["phase"] == "catalog_ready"
    assert len(snapshot["projects"]) == 4


def test_detail_enrichment_fetches_only_matches_and_reuses_valid_cache(tmp_path):
    store = ProjectFactStore(tmp_path / "facts.json")
    client = Client()
    refresh_project_catalogs(client, store, (ProductLine("X", client.space.url, "Line X"),))
    client.detail_calls.clear()

    enrich_project_facts(client, store, filters={"support mode": "missing"})
    assert client.detail_calls == []
    enrich_project_facts(client, store, filters={"support mode": "A"})
    assert client.detail_calls == ["101"]
    client.detail_calls.clear()
    enrich_project_facts(client, store, filters={"support mode": "A"})
    assert client.detail_calls == []


def test_legacy_cached_detail_is_reparsed_once_only_when_matched(tmp_path):
    store = ProjectFactStore(tmp_path / "facts.json")
    store.save({"schema_version": 1, "projects": [
        {"identity": "X:Alpha-ID", "project_id": "Alpha-ID", "name": "Alpha", "space_key": "X",
         "page_id": "101", "page_url": "https://c/pages/viewpage.action?pageId=101", "active": True,
         "status": "current", "fields": {"support mode": "A"}, "detail_source": {"page_id": "basic-101", "version": 1},
         "roles": {"FAE QA": [{"name": "NPI Owner", "identity": ""}]}}
    ]})
    client = Client()

    enrich_project_facts(client, store, filters={"support mode": "missing"})
    assert client.detail_calls == []
    first = enrich_project_facts(client, store, filters={"support mode": "A"})
    assert client.detail_calls == ["101"]
    assert first["projects"][0]["detail_source"]["role_parser_version"] == 2
    client.detail_calls.clear()
    enrich_project_facts(client, store, filters={"support mode": "A"})
    assert client.detail_calls == []


def test_detail_enrichment_resolves_role_names_once_and_keeps_safe_fallbacks(tmp_path):
    class IdentityClient(Client):
        def __init__(self):
            super().__init__(_space(rows=[
                ("101", "Alpha", "A", "NORMAL", "Stage 1", "Owner-X"),
                ("102", "Beta", "A", "NORMAL", "Stage 1", "Owner-X"),
            ]))
            self.user_calls = []

        def get_page(self, page_id):
            self.detail_calls.append(str(page_id).removeprefix("basic-"))
            return ConfluencePage(str(page_id), "Basic Information", f"https://c/{page_id}", body="""
                <table>
                  <tr><th>Major FAE QA</th><td><ri:user ri:account-id="account-1"/></td></tr>
                  <tr><th>FAE QA</th><td><ri:user ri:account-id="missing-user"/></td></tr>
                  <tr><th>QA Reviewer</th><td><a data-account-id="account-3">Carol Wu</a></td></tr>
                </table>
            """, version=1)

        def get_user_display_name(self, identity):
            self.user_calls.append(identity)
            if identity == "account-1": return "Alice Chen"
            raise RuntimeError("not visible")

    client = IdentityClient()
    store = ProjectFactStore(tmp_path / "facts.json")
    refresh_project_catalogs(client, store, (ProductLine("X", client.space.url, "Line X"),))
    snapshot = enrich_project_facts(client, store)
    assert client.user_calls == ["account-1", "missing-user"]
    for row in snapshot["projects"]:
        assert row["roles"]["Major FAE QA"] == [{"name": "Alice Chen", "identity": "account-1"}]
        assert row["roles"]["FAE QA"] == [{"name": "missing-user", "identity": "missing-user"}]
        assert row["roles"]["QA Reviewer"] == [{"name": "Carol Wu", "identity": "account-3"}]


def test_cached_current_detail_resolves_unreadable_name_without_refetching_pages(tmp_path):
    snapshot = {"schema_version": 1, "projects": [{
        "identity": "X:A", "project_id": "A", "name": "Alpha", "space_key": "X",
        "page_id": "status", "page_url": "https://c/status", "active": True, "status": "current",
        "fields": {}, "detail_source": {"page_id": "basic", "version": 1, "role_parser_version": 2},
        "roles": {"Major FAE QA": [{"name": "account-1", "identity": "account-1"}],
                  "FAE QA": [{"name": "account-1", "identity": "account-1"}], "QA Reviewer": []},
    }]}
    store = ProjectFactStore(tmp_path / "facts.json")
    store.save(snapshot)

    class CachedClient:
        def __init__(self): self.user_calls = []
        def get_user_display_name(self, identity): self.user_calls.append(identity); return "Alice Chen"
        def get_page_by_url(self, *_args, **_kwargs): raise AssertionError("cached detail must not rediscover pages")
        def get_page(self, *_args, **_kwargs): raise AssertionError("cached detail must not be fetched")

    client = CachedClient()
    updated = enrich_project_facts(client, store)
    assert client.user_calls == ["account-1"]
    assert updated["projects"][0]["roles"]["Major FAE QA"][0]["name"] == "Alice Chen"
    assert store.load()["projects"][0]["roles"]["FAE QA"][0]["name"] == "Alice Chen"
