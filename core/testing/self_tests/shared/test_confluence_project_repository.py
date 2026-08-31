from __future__ import annotations

from core.confluence.project import ProjectDetails, ProjectQuery
from core.confluence.project_mapper import ConfluenceProjectMapper
from core.confluence.project_repository import ProjectRepository
from core.domain.detail import DetailState


CATALOG_ROW = {
    "identity": "DOPL:P100",
    "project_id": "P100",
    "name": "Project One",
    "space_key": "DOPL",
    "page_id": "900",
    "page_url": "https://confluence.example/pages/900",
    "fields": {
        "project status": "NORMAL",
        "current stage": "EVT",
        "support mode": "A",
        "oem/operator": "Customer A",
    },
    "catalog_source": {"page_id": "10", "title": "DOPL Projects", "version": 4},
}


class RecordingConfluenceGateway:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def query_project_catalog(self, query, page):
        self.calls.append(("query", query, page))
        return {"projects": [CATALOG_ROW], "page": 0, "page_size": 50, "total": 1}

    def get_project_catalog(self, project_id):
        self.calls.append(("get", project_id))
        return CATALOG_ROW

    def load_project_sections(self, project_id, sections):
        self.calls.append(("details", project_id, sections))
        return {
            "roles": {
                "Major FAE QA": [{"identity": "u1", "name": "Alice"}],
            }
        }


def test_confluence_mapper_creates_lightweight_project_without_page_body() -> None:
    project = ConfluenceProjectMapper().from_catalog(CATALOG_ROW)

    assert project.identity.project_id == "P100"
    assert project.catalog_page.page_id == "900"
    assert project.catalog_page.url == "https://confluence.example/pages/900"
    assert project.status.name == "NORMAL"
    assert dict(project.facts.value.values) == CATALOG_ROW["fields"]
    assert project.roles.state is DetailState.UNLOADED
    assert not hasattr(project, "body")
    assert not hasattr(project, "table_row")


def test_project_repository_query_does_not_load_details_or_page_tree() -> None:
    gateway = RecordingConfluenceGateway()
    repository = ProjectRepository(gateway, ConfluenceProjectMapper())
    query = ProjectQuery(search="one")

    page = repository.query(query, page=0)

    assert [project.identity.project_id for project in page.projects] == ["P100"]
    assert gateway.calls == [("query", query, 0)]


def test_project_repository_loads_only_declared_section() -> None:
    gateway = RecordingConfluenceGateway()
    mapper = ConfluenceProjectMapper()
    repository = ProjectRepository(gateway, mapper)
    project = mapper.from_catalog(CATALOG_ROW)

    loaded = repository.load_details(project, ProjectDetails(roles=True))

    assert gateway.calls == [("details", "P100", ("roles",))]
    assert loaded.roles.state is DetailState.LOADED
    assert loaded.roles.value[0].role.name == "Major FAE QA"
    assert loaded.milestones.state is DetailState.UNLOADED
    assert loaded.evidence.state is DetailState.UNLOADED
