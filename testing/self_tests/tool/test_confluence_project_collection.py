from datetime import datetime
from zoneinfo import ZoneInfo

from tool.common.project_weekly_audit.models import (
    ConfluenceProject,
    ProjectCollectionFilter,
)
from tool.common.project_weekly_audit.project_collection import (
    default_project_filter,
    filter_projects,
)


PROJECT_SPACE_URL = "https://confluence.amlogic.com/display/QA/Project+Space"


def project(
    project_id,
    *,
    year=2026,
    space_key="DOPL",
    page_identity=None,
    support_mode="A",
    current_stage="IN DEVELOPMENT",
    project_status="",
    name=None,
):
    return ConfluenceProject(
        year=year,
        project_id=project_id,
        name=name or project_id,
        status_page_id=f"status-{project_id}",
        status_url=f"https://confluence.amlogic.com/status/{project_id}",
        home_url=f"https://confluence.amlogic.com/home/{project_id}",
        support_mode=support_mode,
        current_stage=current_stage,
        project_status=project_status,
        space_key=space_key,
        page_identity=page_identity or f"page-{project_id}",
    )


def test_default_filter_uses_current_and_previous_year():
    criteria = default_project_filter(
        datetime(2026, 7, 29, tzinfo=ZoneInfo("Asia/Shanghai")),
        PROJECT_SPACE_URL,
    )
    assert criteria.years == (2025, 2026)
    assert criteria.support_modes == ("A",)
    assert criteria.project_statuses == ("NORMAL",)
    assert criteria.current_stages == ()


def test_default_filter_does_not_restrict_current_stage():
    criteria = default_project_filter(
        datetime(2026, 7, 29, tzinfo=ZoneInfo("Asia/Shanghai")),
        PROJECT_SPACE_URL,
    )
    collection = filter_projects(
        [project("P1", current_stage="POC", project_status="NORMAL")],
        criteria,
    )
    assert [row.project_id for row in collection.projects] == ["P1"]


def test_empty_year_selection_means_all_catalog_years():
    collection = filter_projects(
        [project("P1", year=2025), project("P2", year=2026)],
        ProjectCollectionFilter(PROJECT_SPACE_URL, ()),
    )
    assert [row.project_id for row in collection.projects] == ["P1", "P2"]


def test_space_qualified_root_identity_preserves_same_project_metadata():
    collection = filter_projects(
        [
            project(
                "SAME", space_key="DOPL", page_identity="100",
                name="Shared title",
            ),
            project(
                "SAME", space_key="SDPL", page_identity="100",
                name="Shared title",
            ),
        ],
        ProjectCollectionFilter(PROJECT_SPACE_URL, (2026,)),
    )

    assert [row.project_identity for row in collection.projects] == [
        "DOPL:100", "SDPL:100",
    ]
    selected = filter_projects(
        collection.projects,
        ProjectCollectionFilter(
            PROJECT_SPACE_URL, (2026,), included_project_ids=("SDPL:100",),
        ),
    )
    assert [row.project_identity for row in selected.projects] == ["SDPL:100"]


def test_current_stage_and_non_filter_attributes_do_not_affect_eligibility():
    collection = filter_projects(
        [
            project(
                "P1", current_stage="DELAY", name="One",
                project_status="NORMAL",
            ),
            project(
                "P2", current_stage="", name="Two",
                project_status="NORMAL",
            ),
        ],
        ProjectCollectionFilter(
            PROJECT_SPACE_URL, (2026,), ("A",), ("NORMAL",),
            ("IN DEVELOPMENT",),
        ),
    )

    assert [row.project_id for row in collection.projects] == ["P1", "P2"]


def test_filter_normalizes_values_and_applies_explicit_project_selection():
    collection = filter_projects(
        [
            project("P1", support_mode=" a ", current_stage="2 IN DEVELOPMENT"),
            project("P2", support_mode="B", current_stage="2 IN DEVELOPMENT"),
            project("P3", year=2025, support_mode="A", current_stage="PENDING"),
        ],
        ProjectCollectionFilter(
            PROJECT_SPACE_URL, (2025, 2026), ("A",), (), ("IN DEVELOPMENT",),
            ("DOPL:page-P1",),
        ),
    )
    assert [row.project_id for row in collection.projects] == ["P1"]
    assert collection.excluded_counts == {
        "support_mode": 1, "project_selection": 1,
    }


def test_collection_id_is_stable_when_input_order_changes():
    criteria = ProjectCollectionFilter(
        PROJECT_SPACE_URL, (2025, 2026), ("A",), (), ("IN DEVELOPMENT",)
    )
    first = filter_projects([project("P1"), project("P2")], criteria)
    second = filter_projects([project("P2"), project("P1")], criteria)
    assert first.collection_id == second.collection_id
    assert [row.project_id for row in first.projects] == ["P1", "P2"]


def test_product_line_filter_is_part_of_stable_collection_identity():
    projects = [project("M1", space_key="DOPL"), project("M2", space_key="TV")]
    dopl = filter_projects(
        projects,
        ProjectCollectionFilter("source", (), product_line_keys=("DOPL",)),
    )
    television = filter_projects(
        projects,
        ProjectCollectionFilter("source", (), product_line_keys=("TV",)),
    )

    assert [row.space_key for row in dopl.projects] == ["DOPL"]
    assert [row.space_key for row in television.projects] == ["TV"]
    assert dopl.collection_id != television.collection_id


def test_filter_applies_year_status_and_selection_with_first_reason_counts():
    criteria = ProjectCollectionFilter(
        PROJECT_SPACE_URL,
        (2025, 2026),
        ("A",),
        ("ACTIVE",),
        ("IN DEVELOPMENT",),
        ("DOPL:page-P1",),
    )
    collection = filter_projects(
        [
            project("OLD", year=2024, project_status="ACTIVE"),
            project("PAUSED", project_status="PAUSED"),
            project("PENDING", project_status="ACTIVE", current_stage="POC"),
            project("P2", project_status="ACTIVE"),
            project("P1", project_status=" active ", current_stage=" 2  in development "),
        ],
        criteria,
    )
    assert [row.project_id for row in collection.projects] == ["P1"]
    assert collection.excluded_counts == {
        "year": 1,
        "project_status": 1,
        "project_selection": 2,
    }


def test_filter_diagnostic_counts_each_active_filter_independently(monkeypatch):
    records = []
    monkeypatch.setattr(
        "tool.common.project_weekly_audit.project_collection.smart_log",
        lambda message, **kwargs: records.append((message, kwargs)),
    )
    criteria = ProjectCollectionFilter(
        PROJECT_SPACE_URL, (2026,), ("A",), ("NORMAL",),
    )

    filter_projects([
        project("INCLUDED", project_status="NORMAL"),
        project("MODE", support_mode="B", project_status="NORMAL"),
        project("STATUS", project_status="WARNING"),
        project("BOTH", support_mode="B", project_status="WARNING"),
    ], criteria)

    assert records == [(
        "Confluence project filters evaluated",
        {
            "domain": "confluence",
            "source": "project_collection",
            "extra": {
                "source_url": PROJECT_SPACE_URL,
                "input_count": 4,
                "active_filters": {
                    "years": [2026],
                    "support_modes": ["A"],
                    "project_statuses": ["NORMAL"],
                    "project_selection_count": 0,
                    "product_line_keys": [],
                },
                "independent_excluded_counts": {
                    "year": 0,
                    "support_mode": 2,
                    "project_status": 2,
                },
                "pipeline_excluded_counts": {
                    "support_mode": 2,
                    "project_status": 1,
                },
                "final_candidate_count": 1,
            },
        },
    )]
