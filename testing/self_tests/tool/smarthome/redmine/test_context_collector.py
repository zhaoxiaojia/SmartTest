import asyncio

from tool.SmartHome.redmine.collector import (
    RedmineContextCollector,
    parse_issue_detail,
    parse_issue_list,
    parse_project_nodes,
)
from tool.SmartHome.redmine.models import RedmineIssueListItem, RedmineProject
from tool.SmartHome.redmine.mapping import map_issue_to_jira, redmine_tracker_to_jira_type


def test_parse_project_tree_extracts_project_id_and_parent_child_relationship():
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
    assert projects[0].children == ("avt-cultraview-edla-a311d2", "cultraview-a311d2-android-16")
    assert projects[1].parent_identifier == "avt-cultraview-bds"
    assert projects[1].project_id == "AN40BF-A311D2"
    assert projects[2].project_id == "AN40CY-A311D2"


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
            if "issues?set_filter=1" in url and "tracker_id=1" not in url:
                return [
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
                ]
            raise AssertionError(url)

    context = asyncio.run(RedmineContextCollector(FakePage(), account="alice").collect_context())

    assert context.account == "alice"
    assert context.projects[0].project_id == "AN40BF-A311D2"
    assert context.projects[0].issues[0].id == "61903"
    assert [issue.tracker for issue in context.projects[0].issues] == ["Bug", "Support"]
