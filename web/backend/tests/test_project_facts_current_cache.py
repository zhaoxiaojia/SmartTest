from __future__ import annotations

from core.confluence.project import ConfluencePageRef, ProductSpaceRef, Project, ProjectIdentity, ProjectRole
from core.confluence.models import ConfluencePage
from core.domain.detail import DetailSection
from core.domain.values import FieldBag, NamedValue, PersonRef
from fastapi.testclient import TestClient
from smarttest_web.confluence.project_repository import ConfluenceProjectRepository
from smarttest_web.app import create_app
from smarttest_web.database import WebDatabase
from smarttest_web.project_facts_api import ProjectFactsWebOwner, _ProjectFactsGateway
from test_web_session import FakeAuthenticator
from conftest import confirmed_access, MemoryCredentialStore
from smarttest_web.session import PersistentSessionStore


def test_project_facts_owner_reads_and_invalidates_new_project_repository(tmp_path) -> None:
    repository = ConfluenceProjectRepository(WebDatabase(tmp_path / "web.db"))
    repository.save_core((Project(
        ProjectIdentity("900", "P100"), "Project One",
        ProductSpaceRef("DOPL", "DOPL"), ConfluencePageRef("10", "Catalog", version=1),
        status=NamedValue("normal", "Normal"), stage=NamedValue("evt", "EVT"),
    ),))
    owner = ProjectFactsWebOwner(repository=repository)
    access = confirmed_access(repository.database, ('P100',))

    result = owner.query(access, filters={"current stage": ("EVT",)})
    empty_filter = owner.query(access, filters={"current stage": ("DVT",)})

    assert result["state"] == "ready"
    assert [project["project_id"] for project in result["projects"]] == ["P100"]
    assert result["projects"][0]["fields"]["current stage"] == "EVT"
    assert empty_filter["state"] == "ready"
    assert empty_filter["projects"] == []
    owner.invalidate_project("P100", access)
    assert owner.query(access)["state"] == "no_snapshot"


def test_project_facts_exposes_core_product_labels_and_only_catalog_ready_filter_candidates(tmp_path) -> None:
    repository = ConfluenceProjectRepository(WebDatabase(tmp_path / "web.db"))
    repository.save_core((Project(
        ProjectIdentity("900", "P100"), "Project One",
        ProductSpaceRef("DOPL", "China Operator Business"), ConfluencePageRef("10", "Catalog"),
        status=NamedValue("normal", "Normal"),
    ),))
    access = confirmed_access(repository.database, ("P100",))
    access.publish([
        ("catalog", "DOPL", "ready", "DOPL"),
        ("catalog", "TV", "ready", "TV"),
    ], lambda: None)

    result = ProjectFactsWebOwner(repository=repository).query(
        access, filters={"project status": ("DOES NOT MATCH",)},
    )

    assert result["productSpaces"] == [
        {"value": "DOPL", "label": "China Operator Business"},
        {"value": "SDPL", "label": "Smart Device Business"},
        {"value": "TV", "label": "TV Business"},
        {"value": "OOPL", "label": "Global Operator & STB Business"},
    ]
    product_space = next(facet for facet in result["facets"] if facet["key"] == "__product_space__")
    assert product_space["options"] == [
        {"value": "DOPL", "label": "China Operator Business"},
        {"value": "TV", "label": "TV Business"},
    ]


def test_project_facts_query_keeps_its_access_snapshot_during_catalog_replacement(tmp_path) -> None:
    repository = ConfluenceProjectRepository(WebDatabase(tmp_path / "web.db"))
    repository.save_core((Project(
        ProjectIdentity("900", "P100"), "Project One",
        ProductSpaceRef("DOPL", "DOPL"), ConfluencePageRef("10", "Catalog", version=1),
        roles=DetailSection.loaded((ProjectRole(
            NamedValue("fae", "FAE QA"), (PersonRef("alice", display_name="Alice"),),
        ),)),
    ),))
    repository.replace_roles("P100", DetailSection.loaded((ProjectRole(
        NamedValue("fae", "FAE QA"), (PersonRef("alice", display_name="Alice"),),
    ),)))

    class Access:
        def __init__(self): self.catalog_reads = 0
        def require_active(self): return None
        def ids(self, kind, capability):
            if kind == "project" and capability == "catalog":
                self.catalog_reads += 1
                return {"P100"} if self.catalog_reads == 1 else set()
            if kind == "project" and capability == "roles": return {"P100"}
            return set()
        def require(self, kind, resource_id, capability):
            if str(resource_id) not in self.ids(kind, capability): raise PermissionError("permission_denied")
        def allows(self, kind, resource_id, capability): return str(resource_id) in self.ids(kind, capability)

    result = ProjectFactsWebOwner(repository=repository).query(Access())

    assert [row["project_id"] for row in result["projects"]] == ["P100"]
    assert next(group for group in result["ownerHierarchy"] if group["role"] == "FAE QA")["people"][0]["name"] == "Alice"


def test_project_facts_web_path_pages_current_projects(tmp_path) -> None:
    repository = ConfluenceProjectRepository(WebDatabase(tmp_path / "web.db"))
    repository.save_core(tuple(
        Project(
            ProjectIdentity(str(index), f"P{index}"), f"Project {index}",
            ProductSpaceRef("DOPL"), ConfluencePageRef("10"),
        )
        for index in (1, 2)
    ))
    owner = ProjectFactsWebOwner(repository=repository)
    confirmed_access(repository.database, ('P1', 'P2'))
    sessions = PersistentSessionStore(path=repository.database.path, credential_store=MemoryCredentialStore())
    client = TestClient(create_app(
        project_facts_owner=lambda: owner, authenticator=FakeAuthenticator,
        session_store=lambda: sessions,
    ), base_url="https://testserver")
    client.post("/api/auth/login", json={"username": "coco", "password": "secret"})

    response = client.get("/api/confluence/project-facts", params={"page": 1, "pageSize": 1})

    assert [row["project_id"] for row in response.json()["projects"]] == ["P2"]
    assert response.json()["pagination"] == {"page": 1, "pageSize": 1, "total": 2}


def test_page_entry_catalog_refresh_is_limited_to_four_product_spaces(tmp_path) -> None:
    repository = ConfluenceProjectRepository(WebDatabase(tmp_path / "web.db"))
    owner = ProjectFactsWebOwner(repository=repository)

    class Service:
        def __init__(self):
            self.scopes = []

        def refresh_projects(self, scope):
            self.scopes.append(scope)
            return {"projects": (), "failed": ()}

    service = Service()
    owner._service = lambda _username, _password: service

    owner.refresh(confirmed_access(repository.database), "secret")

    assert len(service.scopes) == 1
    assert service.scopes[0].product_space_keys == ("TV", "SDPL", "DOPL", "OOPL")


def test_project_facts_owner_queries_persisted_dynamic_fields_and_owner_clusters(tmp_path) -> None:
    repository = ConfluenceProjectRepository(WebDatabase(tmp_path / "web.db"))
    project = Project(
        ProjectIdentity("TV:P100", "P100"), "Project One",
        ProductSpaceRef("TV", "TV Business"),
        ConfluencePageRef("900", "Project One", "https://c/pages/900"),
        roles=DetailSection.loaded((ProjectRole(
            NamedValue(name="FAE QA"), (PersonRef("u1", display_name="Alice"),),
        ),)),
        facts=DetailSection.loaded(FieldBag.from_mapping({
            "project id": "P100", "project owner": "Alice", "odm": "ODM-X",
            "unexpected owner": "Alice",
        })),
    )
    repository.save_core((project,))
    repository.replace_roles("P100", project.roles)
    repository.replace_facts("P100", project.facts)

    result = ProjectFactsWebOwner(repository=repository).query(
        confirmed_access(repository.database, ('P100',)), filters={"odm": ("ODM-X",)}, search="Alice",
    )

    assert [row["project_id"] for row in result["projects"]] == ["P100"]
    assert next(facet for facet in result["facets"] if facet["key"] == "odm")["options"] == ["ODM-X"]
    assert next(facet for facet in result["facets"] if facet["key"] == "unexpected owner") == {
        "key": "unexpected owner", "label": "Unexpected Owner",
        "labels": ["Unexpected Owner"], "options": ["Alice"],
    }
    fae = next(group for group in result["ownerHierarchy"] if group["role"] == "FAE QA")
    assert fae["people"][0]["name"] == "Alice"


def test_page_entry_persists_recent_client_catalog_contract_for_all_four_spaces(tmp_path) -> None:
    class CatalogClient:
        def get_page_by_url(self, url, *, prefer_export=False):
            del prefer_export
            space = url.split("/display/")[1].split("/")[0]
            body = (
                "<table><tr><th>页面</th><th>Project ID</th><th>ODM</th>"
                "<th>Current Stage</th></tr>"
                f'<tr><td><a href="/pages/viewpage.action?pageId={space}01">{space} Project</a></td>'
                f"<td>{space}-100</td><td>ODM-{space}</td><td>EVT</td></tr></table>"
            )
            return ConfluencePage(
                f"catalog-{space}", "Project Space", url,
                view_body=body, version=3,
            )

    repository = ConfluenceProjectRepository(WebDatabase(tmp_path / "web.db"))
    owner = ProjectFactsWebOwner(
        repository=repository,
        client_factory=lambda _username, _password: CatalogClient(),
    )

    result = owner.refresh(confirmed_access(repository.database), "secret")

    assert result["accessibleProjectCount"] == 4
    assert {row["space_key"] for row in result["projects"]} == {"TV", "SDPL", "DOPL", "OOPL"}
    assert next(facet for facet in result["facets"] if facet["key"] == "odm")["options"] == [
        "ODM-DOPL", "ODM-OOPL", "ODM-SDPL", "ODM-TV",
    ]


def test_apply_catalog_roundtrip_keeps_dynamic_fields_for_detail_extraction(tmp_path) -> None:
    repository = ConfluenceProjectRepository(WebDatabase(tmp_path / "web.db"))
    project = Project(
        ProjectIdentity("TV:P100", "P100"), "Project One", ProductSpaceRef("TV"),
        ConfluencePageRef("900", "Project One", "https://c/pages/900"),
        facts=DetailSection.loaded(FieldBag.from_mapping({"odm": "ODM-X"})),
    )
    repository.save_core((project,))
    repository.replace_facts("P100", project.facts)

    payload = _ProjectFactsGateway(object(), repository).get_project_catalog("P100")

    assert payload["fields"]["odm"] == "ODM-X"
