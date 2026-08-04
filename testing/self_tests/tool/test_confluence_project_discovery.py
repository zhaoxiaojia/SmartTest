from tool.common.project_weekly_audit.discovery import (
    discover_project_collection,
    discover_project_pages,
)
from tool.common.project_weekly_audit.models import ProjectCandidate, ProjectCollectionFilter
from support.confluence_integration.models import ConfluencePage


def table(rows):
    return (
        "<table>"
        + "".join(f"<tr><td>{key}</td><td>{value}</td></tr>" for key, value in rows)
        + "</table>"
    )


def summary_table(rows):
    headers = (
        "页面", "Date of Commercial approval", "Support Mode",
        "Project Status", "Project ID",
    )
    return (
        "<table><tr>"
        + "".join(f"<th>{header}</th>" for header in headers)
        + "</tr>"
        + "".join(
            "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
            for row in rows
        )
        + "</table>"
    )


def test_summary_tables_are_the_only_catalog_source_and_merge_spaces():
    dopl_url = "https://confluence.amlogic.com/display/DOPL/Project+Space"
    sdpl_url = "https://confluence.amlogic.com/display/SDPL/Project+Space"
    duplicate = (
        '<a href="/pages/viewpage.action?pageId=101">Shared Project</a>',
        "2025-03-04", "A", "NORMAL", "SAME",
    )
    source_urls = {
        dopl_url: ConfluencePage(
            "dopl", "Project Space", dopl_url,
            summary_table([duplicate]) + summary_table([duplicate]),
        ),
        sdpl_url: ConfluencePage(
            "sdpl", "Project Space", sdpl_url,
            summary_table([(
                '<a href="/display/SDPL/Shared+Project">Shared Project</a>',
                "Apr 5, 2026", "B", "WARNING", "SAME",
            )]),
        ),
    }

    class Client:
        def __init__(self):
            self.urls = []

        def get_page_by_url(self, url, *, prefer_export=False):
            assert prefer_export is True
            self.urls.append(url)
            return source_urls[url]

        def get_page_children(self, _page_id):
            raise AssertionError("catalog refresh must not crawl child pages")

    client = Client()
    collection = discover_project_collection(
        client,
        ProjectCollectionFilter(
            "legacy-source", (), (), (),
        ),
    )

    assert [row.project_identity for row in collection.projects] == [
        "DOPL:101", "SDPL:https://confluence.amlogic.com/display/SDPL/Shared+Project",
    ]
    assert [(row.year, row.support_mode, row.project_status) for row in collection.projects] == [
        (2025, "A", "NORMAL"), (2026, "B", "WARNING"),
    ]
    assert client.urls == [dopl_url, sdpl_url]


def test_unified_discovery_keeps_readable_space_and_marks_partial_errors():
    dopl_url = "https://confluence.amlogic.com/display/DOPL/Project+Space"
    dopl = ConfluencePage(
        "dopl", "Project Space", dopl_url,
        summary_table([(
            '<a href="/pages/viewpage.action?pageId=7">Good</a>',
            "2026/07/31", "A", "NORMAL", "",
        )]),
    )

    class Client:
        def get_page_by_url(self, url, *, prefer_export=False):
            assert prefer_export is True
            if "SDPL" in url:
                raise PermissionError("denied")
            return {dopl_url: dopl}[url]

    collection = discover_project_collection(
        Client(),
        ProjectCollectionFilter("legacy-source", (2026,), ("A",), ("NORMAL",)),
    )

    assert [row.project_identity for row in collection.projects] == ["DOPL:7"]
    assert collection.discovery_errors == {
        "space:SDPL": 1,
    }


def test_commercial_approval_day_first_dates_feed_years_and_bad_dates_are_excluded():
    dopl_url = "https://confluence.amlogic.com/display/DOPL/Project+Space"
    sdpl_url = "https://confluence.amlogic.com/display/SDPL/Project+Space"
    pages = {
        dopl_url: ConfluencePage(
            "dopl", "Project Space", dopl_url,
            summary_table([
                ('<a href="/pages/viewpage.action?pageId=21">Alpha</a>',
                 "23 Jun 2026", "A", "NORMAL", "ALPHA"),
                ('<a href="/pages/viewpage.action?pageId=22">Beta</a>',
                 "08 Jul 2026", "B", "NORMAL", "BETA"),
                ('<a href="/pages/viewpage.action?pageId=23">Gamma</a>',
                 "8 Jul 2025", "A", "WARNING", "GAMMA"),
            ]),
        ),
        sdpl_url: ConfluencePage(
            "sdpl", "Project Space", sdpl_url,
            summary_table([
                ('<a href="/pages/viewpage.action?pageId=24">Empty</a>',
                 "", "A", "NORMAL", "EMPTY"),
                ('<a href="/pages/viewpage.action?pageId=25">Malformed</a>',
                 "31 NotAMonth 2026", "A", "NORMAL", "MALFORMED"),
            ]),
        ),
    }

    class Client:
        def get_page_by_url(self, url, *, prefer_export=False):
            assert prefer_export is True
            return pages[url]

    collection = discover_project_collection(
        Client(), ProjectCollectionFilter("legacy-source", ()),
    )

    assert [(row.project_id, row.year) for row in collection.projects] == [
        ("ALPHA", 2026), ("BETA", 2026), ("GAMMA", 2025),
    ]
    assert collection.visible_years == (2025, 2026)
    assert collection.discovery_errors == {"row:SDPL": 2}


def test_project_page_discovery_stays_within_project_root():
    root = ConfluencePage("root", "Snake117", "https://c/root")
    correct = ConfluencePage(
        "correct", "Snake117-Project Status Report", "https://c/correct",
    )
    info = ConfluencePage(
        "info", "Snake117-Test Information", "https://c/info",
    )
    plan = ConfluencePage("plan", "Snake117-Test Plan", "https://c/plan")
    sibling_duplicate = ConfluencePage(
        "duplicate", "Snake117-Project Status Report", "https://c/duplicate",
    )

    class Client:
        def get_page_by_url(self, url):
            assert url == root.url
            return root

        def get_page_children(self, page_id):
            return {
                root.id: [correct, info],
                info.id: [plan],
                "unrelated": [sibling_duplicate],
            }.get(page_id, [])

    project = ProjectCandidate(
        root.id, "BT20AG-S905L4", root.title, root.url, root.url,
        space_key="DOPL", page_identity=root.id,
    )
    pages, errors = discover_project_pages(Client(), project, return_errors=True)

    assert pages["status"].id == correct.id
    assert pages["test_information"].id == info.id
    assert pages["test_plan"].id == plan.id
    assert errors == {}


def test_status_entry_ascends_to_project_root_and_discovers_basic_information_children():
    root = ConfluencePage("root", "Muffin314", "https://c/root")
    status = ConfluencePage(
        "status", "1. Muffin314-Project Status Report", "https://c/status",
    )
    basic = ConfluencePage(
        "basic", "2.★Muffin314-Basic Information", "https://c/basic",
    )
    nested = [
        ConfluencePage("info", "Muffin314-Test Information", "https://c/info"),
        ConfluencePage("plan", "Muffin314-Test Plan", "https://c/plan"),
        ConfluencePage(
            "environment", "Muffin314-Test Environment Setup and Precautions",
            "https://c/environment",
        ),
        ConfluencePage(
            "experience", "Muffin314-Summary of Experience and Typical Cases",
            "https://c/experience",
        ),
        ConfluencePage(
            "report", "Muffin314-Test Report Store", "https://c/report",
        ),
    ]

    class Client:
        def get_page_by_url(self, url):
            assert url == status.url
            return status

        def get_parent_page(self, page_id):
            assert page_id == status.id
            return root

        def get_page_children(self, page_id):
            return {
                root.id: [status, basic],
                basic.id: nested,
            }.get(page_id, [])

    project = ProjectCandidate(
        status.id, "Muffin314", status.title, status.url, status.url,
    )
    pages, errors = discover_project_pages(Client(), project, return_errors=True)

    assert set(pages) == {
        "status", "test_information", "test_plan", "environment",
        "experience", "report_store",
    }
    assert errors == {}


def test_project_page_branch_error_keeps_other_discovered_pages():
    root = ConfluencePage("root", "P1", "https://c/root")
    plan = ConfluencePage("plan", "P1-Test Plan", "https://c/plan")

    class Client:
        def get_page_by_url(self, _url):
            return root

        def get_page_children(self, page_id):
            if page_id == plan.id:
                raise PermissionError("denied")
            return [plan] if page_id == root.id else []

    project = ProjectCandidate(root.id, "P1", "P1", root.url, root.url)
    pages, errors = discover_project_pages(Client(), project, return_errors=True)

    assert pages["test_plan"] == plan
    assert errors["test_plan"].startswith("PermissionError|")


def test_foreign_descendant_page_is_not_selected_for_project():
    root = ConfluencePage("root", "Snake114", "https://c/root")
    own = ConfluencePage(
        "status", "Snake114-Project Status Report", "https://c/status",
    )
    foreign = ConfluencePage(
        "plan", "Snake117-Test Plan", "https://c/plan",
    )

    class Client:
        def get_page_by_url(self, _url):
            return root

        def get_page_children(self, page_id):
            return [own, foreign] if page_id == root.id else []

    project = ProjectCandidate(root.id, "Snake114", root.title, root.url, root.url)
    pages, errors = discover_project_pages(Client(), project, return_errors=True)

    assert set(pages) == {"status"}
    assert errors["test_plan"].startswith("ForeignProjectPage|")
