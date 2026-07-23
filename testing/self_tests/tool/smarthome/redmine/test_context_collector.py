import asyncio

from tool.SmartHome.redmine.collector import (
    RedmineContextCollector,
    parse_issue_detail,
    parse_issue_list,
    parse_project_nodes,
)
from tool.SmartHome.redmine.models import RedmineIssueListItem, RedmineProject
from tool.SmartHome.redmine.mapping import map_issue_to_jira, redmine_tracker_to_jira_type
from tool.SmartHome.redmine.query import RedmineQuery, parse_terms


def test_native_query_terms_and_union_parameters():
    assert parse_terms("60371,播放失败；60371\n黑屏") == ("60371", "播放失败", "黑屏")
    branches = RedmineQuery(status="open", subject="Highlight", text="60371 播放失败").branches()
    assert [branch.kind for branch in branches] == ["fulltext", "issue_id"]
    assert ("op[any_searchable]", "*~") in branches[0].params(1, 100)
    assert ("v[issue_id][]", "60371") in branches[1].params(1, 100)
    assert ("v[subject][]", "Highlight") in branches[0].params(1, 100)


def test_native_query_omits_empty_subject_and_splits_exact_ids():
    branches = RedmineQuery(issue_ids=("2", "1"), subject="").branches()
    assert [branch.kind for branch in branches] == ["issue_id", "issue_id"]
    assert [[value for key, value in branch.params(3, 50) if key == "v[issue_id][]"] for branch in branches] == [["2"], ["1"]]


def test_collect_query_executes_union_branches_pages_and_dedupes_descending():
    class Page:
        def __init__(self): self.urls = []
        async def goto(self, url, **_kwargs): self.urls.append(url)
        async def wait_for_selector(self, *_args, **_kwargs): pass
        async def evaluate(self, _script):
            url = self.urls[-1]
            if "page=1&" in url:
                ids = ["10", "9"] if "any_searchable" in url else ["10"]
                total = 101 if "any_searchable" in url else 1
            else:
                ids, total = ["8"], 101
            return {"total": total, "rows": [
                {"id": f"issue-{issue_id}", "cells": [
                    {"className": "id", "text": issue_id, "links": [{"href": f"https://support.amlogic.com/issues/{issue_id}"}]},
                    {"className": "project", "text": "Project", "links": [{"text": "Project", "href": "https://support.amlogic.com/projects/p"}]},
                ]} for issue_id in ids
            ]}
    async def scenario():
        page = Page()
        context = await RedmineContextCollector(page).collect_query(RedmineQuery(text="10 failure"))
        assert [item.id for item in context.projects[0].issues] == ["10", "9", "8"]
        assert len(page.urls) == 3
        assert sum("any_searchable" in url for url in page.urls) == 2
        assert sum("issue_id" in url for url in page.urls) == 1
        assert context.projects[0].project_id == ""
    asyncio.run(scenario())


def test_filter_metadata_maps_tracker_labels_to_native_option_values():
    class Page:
        async def goto(self, url, **_kwargs): self.url = url
        async def wait_for_selector(self, *_args, **_kwargs): pass
        async def evaluate(self, script):
            assert "tracker_id" in script
            return [{"label": "Bug", "value": "1"}, {"label": "Support", "value": "3"}]
    async def scenario():
        metadata = await RedmineContextCollector(Page()).collect_filter_metadata()
        assert metadata == {"Bug": "1", "Support": "3"}
    asyncio.run(scenario())


def test_watched_ids_execute_one_native_request_per_exact_id():
    class Page:
        def __init__(self): self.urls = []
        async def goto(self, url, **_kwargs): self.urls.append(url)
        async def wait_for_selector(self, *_args, **_kwargs): pass
        async def evaluate(self, _script): return {"total": 0, "rows": []}
    async def scenario():
        from urllib.parse import parse_qs, urlsplit
        page = Page()
        await RedmineContextCollector(page).collect_query(RedmineQuery(issue_ids=("10", "11")))
        assert len(page.urls) == 2
        values = [parse_qs(urlsplit(url).query)["v[issue_id][]"] for url in page.urls]
        assert values == [["10"], ["11"]]
    asyncio.run(scenario())


def test_parse_project_options_keeps_every_accessible_project_and_project_id():
    projects = parse_project_nodes(
        [
            {
                "text": "BDS.Cultraview",
                "href": "https://support.amlogic.com/projects/avt-cultraview-bds?jump=projects",
                "className": "project root parent icon icon-user my-project",
                "parentClass": "root",
                "containerText": "BDS.Cultraview",
            },
            {
                "text": "BDS.Cultraview.EDLA.A311D2",
                "href": "https://support.amlogic.com/projects/avt-cultraview-edla-a311d2",
                "className": "project child leaf icon icon-user my-project",
                "parentClass": "child",
                "containerText": "BDS.Cultraview.EDLA.A311D2 [Project ID]:AN40BF-A311D2",
            },
            {
                "text": "Cultraview.A311D2.Android.16",
                "href": "https://support.amlogic.com/projects/cultraview-a311d2-android-16",
                "className": "project child leaf icon icon-user my-project",
                "parentClass": "child",
                "containerText": "Cultraview.A311D2.Android.16 [Project ID]: AN40CY-A311D2",
            },
        ]
    )

    assert projects[0].identifier == "avt-cultraview-bds"
    assert [project.identifier for project in projects] == ["avt-cultraview-bds", "avt-cultraview-edla-a311d2", "cultraview-a311d2-android-16"]
    assert projects[1].project_id == "AN40BF-A311D2"
    assert projects[2].project_id == "AN40CY-A311D2"


def test_project_dom_script_collects_all_project_links_without_hierarchy_inference():
    from tool.SmartHome.redmine.collector import _PROJECTS_SCRIPT
    assert "#projects-index a.project" in _PROJECTS_SCRIPT
    assert "parentHref" not in _PROJECTS_SCRIPT
    assert "walkProject" not in _PROJECTS_SCRIPT


def test_my_page_collects_only_assigned_block_rows():
    class Page:
        async def goto(self, url, **_kwargs): self.url = url
        async def wait_for_selector(self, *_args, **_kwargs): pass
        async def evaluate(self, script):
            assert "block-issuesassignedtome" in script and "block-issuesreportedbyme" not in script
            return [{"id": "issue-7", "projectName": "Child", "projectHref": "https://support.amlogic.com/projects/child", "cells": [{"className": "id", "text": "7", "links": [{"href": "https://support.amlogic.com/issues/7"}]}, {"className": "subject", "text": "Assigned", "links": []}]}]
    async def scenario():
        rows = await RedmineContextCollector(Page()).collect_my_page_assigned()
        assert rows[0]["issue"].id == "7"
        assert rows[0]["project_identifier"] == "child"
    asyncio.run(scenario())


def test_project_options_preserve_all_projects_in_source_order():
    from tool.SmartHome.redmine.collector import project_options
    projects = (
        RedmineProject(name="A", identifier="a", url="/projects/a", project_id="A-ID"),
        RedmineProject(name="A1", identifier="a1", url="/projects/a1"),
        RedmineProject(name="A2", identifier="a2", url="/projects/a2"),
        RedmineProject(name="B", identifier="b", url="/projects/b"),
    )
    assert project_options(projects) == [
        {"id": "a", "label": "A", "projectId": "A-ID"},
        {"id": "a1", "label": "A1", "projectId": ""},
        {"id": "a2", "label": "A2", "projectId": ""},
        {"id": "b", "label": "B", "projectId": ""},
    ]


def test_project_options_keep_all_301_accessible_projects():
    from tool.SmartHome.redmine.collector import project_options
    projects = tuple(RedmineProject(name=f"Complete project label {index}", identifier=f"project-{index}", url=f"/projects/project-{index}") for index in range(301))
    options = project_options(projects)
    assert len(options) == 301
    assert options[-1] == {"id": "project-300", "label": "Complete project label 300", "projectId": ""}


def test_parse_issue_list_uses_table_class_names_as_raw_fields():
    issues = parse_issue_list(
        [
            {
                "id": "issue-61903",
                "cells": [
                    {"className": "id", "text": "61903", "links": [{"text": "61903", "href": "https://support.amlogic.com/issues/61903"}]},
                    {"className": "tracker", "text": "Bug", "links": []},
                    {"className": "status", "text": "Feedback", "links": []},
                    {"className": "priority", "text": "High", "links": []},
                    {"className": "subject", "text": "Panel spread-spectrum issue", "links": []},
                    {"className": "assigned_to", "text": "h shen", "links": []},
                    {"className": "updated_on", "text": "07/16/2026 02:42 PM", "links": []},
                    {"className": "category", "text": "Panel", "links": []},
                    {"className": "watcher_users", "text": "Xin Wang1-aml", "links": [{"text": "Xin Wang1-aml", "href": "https://support.amlogic.com/users/1126"}]},
                ],
            }
        ]
    )

    assert issues[0].id == "61903"
    assert issues[0].tracker == "Bug"
    assert issues[0].status == "Feedback"
    assert issues[0].priority == "High"
    assert issues[0].subject == "Panel spread-spectrum issue"


def test_redmine_tracker_maps_to_jira_issue_type():
    assert redmine_tracker_to_jira_type("Bug") == "Bug"
    assert redmine_tracker_to_jira_type("Support") == "Feature"
    assert redmine_tracker_to_jira_type("Unknown") == "Bug"


def test_parse_issue_detail_collects_attributes_comments_and_attachment_metadata():
    detail = parse_issue_detail(
        {
            "href": "https://support.amlogic.com/issues/61903",
            "h1": "BDS.Cultraview > BDS.Cultraview.EDLA.A311D2",
            "issueHeader": "Panel spread-spectrum issue",
            "description": "Please check how to enable spread spectrum.",
            "attrs": [
                {"label": "Status:", "value": "Feedback"},
                {"label": "Priority:", "value": "High"},
                {"label": "Assignee:", "value": "h shen"},
                {"label": "Category:", "value": "Panel"},
            ],
            "journals": [
                {
                    "id": "change-450495",
                    "author": "h shen",
                    "header": "Updated by h shen 1 day ago #1",
                    "note": "Customer software version is not ready.",
                    "details": ["Status changed from New to Feedback"],
                }
            ],
            "attachments": [
                {
                    "id": "185862",
                    "filename": "clipboard-202607161358-prplh.png",
                    "size": "59.5 KB",
                    "author": "Xin Wang1-aml",
                    "created_at": "07/16/2026 01:58 PM",
                    "detail_url": "https://support.amlogic.com/attachments/185862",
                    "download_url": "https://support.amlogic.com/attachments/download/185862/clipboard-202607161358-prplh.png",
                }
            ],
        },
        list_item=RedmineIssueListItem(id="61903", url="https://support.amlogic.com/issues/61903", tracker="Bug"),
    )

    assert detail.id == "61903"
    assert detail.attributes["Status"] == "Feedback"
    assert detail.comments[0].note == "Customer software version is not ready."
    assert detail.comments[0].details == ("Status changed from New to Feedback",)
    assert detail.attachments[0].filename == "clipboard-202607161358-prplh.png"


def test_parse_issue_detail_falls_back_to_redmine_content_text_when_dom_sections_are_empty():
    detail = parse_issue_detail(
        {
            "href": "https://support.amlogic.com/issues/61043",
            "contentText": """
Bug #61043 OPEN
金锐显 -A311D2-Android16-EDLA项目 硬件是16GB（4GB*4颗），要求能做到可以显示16GB
Added by h shen about 1 month ago. Updated 15 days ago.
Status: New
Priority: Urgent
Assignee: h shen
Category: DDR
Start date: 06/16/2026
% Done: 0%
Description
硬件是16GB（4GB*4颗），要求能做到可以显示16GB
Files
55036e5a.diff (978 Bytes) Defeng Zhai, 06/22/2026 11:01 AM
History Notes Property changes
Updated by Defeng Zhai 30 days ago #2
Assignee changed from Defeng Zhai to h shen
有些问题需要确认下:
1、你们产品形态 规格是什么？
""",
        },
        list_item=RedmineIssueListItem(
            id="61043",
            url="https://support.amlogic.com/issues/61043",
            tracker="Bug",
            subject="金锐显 -A311D2-Android16-EDLA项目 硬件是16GB（4GB*4颗），要求能做到可以显示16GB",
        ),
    )

    assert detail.subject == "金锐显 -A311D2-Android16-EDLA项目 硬件是16GB（4GB*4颗），要求能做到可以显示16GB"
    assert detail.description == "硬件是16GB（4GB*4颗），要求能做到可以显示16GB"
    assert detail.attributes["Status"] == "New"
    assert detail.attributes["Priority"] == "Urgent"
    assert detail.attributes["Assignee"] == "h shen"
    assert detail.attributes["Category"] == "DDR"


def test_redmine_issue_maps_to_jira_shaped_payload_without_redmine_field_layout():
    project = RedmineProject(
        name="BDS.Cultraview.EDLA.A311D2",
        identifier="avt-cultraview-edla-a311d2",
        url="https://support.amlogic.com/projects/avt-cultraview-edla-a311d2",
        project_id="AN40BF-A311D2",
    )
    issue = parse_issue_detail(
        {
            "href": "https://support.amlogic.com/issues/61903",
            "issueHeader": "Panel spread-spectrum issue",
            "description": "Please check how to enable spread spectrum.",
            "attrs": [
                {"label": "Status:", "value": "Feedback"},
                {"label": "Priority:", "value": "High"},
                {"label": "Assignee:", "value": "h shen"},
                {"label": "Category:", "value": "Panel"},
            ],
            "journals": [{"id": "change-1", "author": "h shen", "note": "comment body", "details": []}],
            "attachments": [{"id": "185862", "filename": "a.png", "download_url": "https://support.amlogic.com/attachments/download/185862/a.png"}],
        },
        list_item=RedmineIssueListItem(id="61903", url="https://support.amlogic.com/issues/61903", tracker="Bug"),
    )

    payload = map_issue_to_jira(issue, project=project, project_key="TV")

    assert payload["source"]["project_id"] == "AN40BF-A311D2"
    assert payload["fields"]["project"]["key"] == "TV"
    assert payload["fields"]["issuetype"] == {"name": "Bug"}
    assert payload["fields"]["summary"] == "Panel spread-spectrum issue"
    assert payload["fields"]["priority"] == {"name": "High"}
    assert payload["fields"]["components"] == [{"name": "Panel"}]
    assert payload["comments"][0]["body"] == "comment body"
    assert payload["attachments"][0]["filename"] == "a.png"


def test_redmine_support_maps_to_jira_feature():
    issue = parse_issue_detail(
        {"href": "https://support.amlogic.com/issues/62000", "issueHeader": "feature request", "attrs": []},
        list_item=RedmineIssueListItem(id="62000", url="https://support.amlogic.com/issues/62000", tracker="Support"),
    )

    assert map_issue_to_jira(issue)["fields"]["issuetype"] == {"name": "Feature"}


def test_context_collector_keeps_browser_generic_and_builds_context_from_page_contracts():
    class FakePage:
        def __init__(self):
            self.urls = []

        async def goto(self, url, **_kwargs):
            self.urls.append(url)

        async def evaluate(self, _script):
            url = self.urls[-1]
            if url.endswith("/projects"):
                return [
                    {
                        "text": "BDS.Cultraview.EDLA.A311D2",
                        "href": "https://support.amlogic.com/projects/avt-cultraview-edla-a311d2",
                        "className": "project root leaf icon icon-user my-project",
                        "parentClass": "root",
                        "containerText": "BDS.Cultraview.EDLA.A311D2 [Project ID]:AN40BF-A311D2",
                    }
                ]
            if "/issues?" in url and "set_filter=1" in url and "tracker_id" not in url:
                return {
                    "total": 2,
                    "rows": [
                        {
                            "id": "issue-61903",
                            "cells": [
                                {"className": "id", "text": "61903", "links": [{"text": "61903", "href": "https://support.amlogic.com/issues/61903"}]},
                                {"className": "tracker", "text": "Bug", "links": []},
                                {"className": "subject", "text": "subject", "links": []},
                            ],
                        },
                        {
                            "id": "issue-62000",
                            "cells": [
                                {"className": "id", "text": "62000", "links": [{"text": "62000", "href": "https://support.amlogic.com/issues/62000"}]},
                                {"className": "tracker", "text": "Support", "links": []},
                                {"className": "subject", "text": "support subject", "links": []},
                            ],
                        },
                    ],
                }
            raise AssertionError(url)

    context = asyncio.run(RedmineContextCollector(FakePage(), account="alice").collect_context())

    assert context.account == "alice"
    assert context.projects[0].project_id == "AN40BF-A311D2"
    assert context.projects[0].issues[0].id == "61903"
    assert [issue.tracker for issue in context.projects[0].issues] == ["Bug", "Support"]


def test_context_collector_reads_all_issue_pages():
    class FakePage:
        def __init__(self):
            self.urls = []

        async def goto(self, url, **_kwargs):
            self.urls.append(url)

        async def evaluate(self, _script):
            url = self.urls[-1]
            assert "per_page=100" in url
            page = 2 if "page=2" in url else 1
            offset = 100 if page == 2 else 0
            count = 38 if page == 2 else 100
            return {
                "total": 138,
                "pagination": f"({offset + 1}-{offset + count}/138)",
                "rows": [
                    {
                        "id": f"issue-{offset + idx + 1}",
                        "cells": [
                            {"className": "id", "text": str(offset + idx + 1), "links": [{"text": str(offset + idx + 1), "href": f"https://support.amlogic.com/issues/{offset + idx + 1}"}]},
                            {"className": "tracker", "text": "Bug", "links": []},
                            {"className": "status", "text": "Closed", "links": []},
                            {"className": "subject", "text": "subject", "links": []},
                        ],
                    }
                    for idx in range(count)
                ],
            }

    project = RedmineProject(name="BDS", identifier="bds", url="https://support/projects/bds", project_id="AN40BF-A311D2")
    issues = asyncio.run(RedmineContextCollector(FakePage(), account="alice").collect_issue_list(project))

    assert len(issues) == 138
    assert issues[0].id == "1"
    assert issues[-1].id == "138"


def test_context_collector_reports_issue_loading_progress():
    progress = []

    class FakePage:
        def __init__(self):
            self.urls = []

        async def goto(self, url, **_kwargs):
            self.urls.append(url)

        async def evaluate(self, _script):
            url = self.urls[-1]
            page = 2 if "page=2" in url else 1
            offset = 100 if page == 2 else 0
            count = 20 if page == 2 else 100
            return {
                "total": 120,
                "pagination": f"({offset + 1}-{offset + count}/120)",
                "rows": [
                    {
                        "id": f"issue-{offset + idx + 1}",
                        "cells": [
                            {"className": "id", "text": str(offset + idx + 1), "links": [{"text": str(offset + idx + 1), "href": f"https://support.amlogic.com/issues/{offset + idx + 1}"}]},
                            {"className": "tracker", "text": "Bug", "links": []},
                        ],
                    }
                    for idx in range(count)
                ],
            }

    project = RedmineProject(name="BDS", identifier="bds", url="https://support/projects/bds", project_id="AN40BF-A311D2")
    collector = RedmineContextCollector(FakePage(), account="alice", progress_callback=lambda loaded, total, label: progress.append((loaded, total, label)))

    issues = asyncio.run(collector.collect_issue_list(project))

    assert len(issues) == 120
    assert progress[0] == (100, 120, "BDS")
    assert progress[-1] == (120, 120, "BDS")


def test_collect_context_scopes_issue_lists_to_selected_project_identifiers(monkeypatch):
    projects = (
        RedmineProject(name="A", identifier="a", url="/a", project_id="A"),
        RedmineProject(name="B", identifier="b", url="/b", project_id="B"),
        RedmineProject(name="Other", identifier="other", url="/other", project_id="O"),
    )
    collector = RedmineContextCollector(object(), account="alice")
    calls = []
    async def collect_projects(): return projects
    async def collect_issue_list(project): calls.append(project.identifier); return ()
    monkeypatch.setattr(collector, "collect_projects", collect_projects)
    monkeypatch.setattr(collector, "collect_issue_list", collect_issue_list)
    asyncio.run(collector.collect_context(project_identifiers={"b"}))
    assert calls == ["b"]
