from dataclasses import asdict

from support.jira_integration.core.third_party_bug import (
    ThirdPartyBugAttachment,
    ThirdPartyBugContext,
    ThirdPartyBugDetail,
    ThirdPartyBugListItem,
    ThirdPartyBugProject,
)
from tool.SmartHome.redmine.models import RedmineIssueDetail, RedmineIssueListItem, RedmineProject


def test_third_party_bug_context_keeps_browse_data_and_detail_data_together():
    item = ThirdPartyBugListItem(id="61043", url="https://support/issues/61043", subject="panel issue")
    detail = ThirdPartyBugDetail(
        id="61043",
        url=item.url,
        subject=item.subject,
        attachments=(ThirdPartyBugAttachment(id="1", filename="log.txt", download_url="https://support/attachments/download/1/log.txt"),),
        list_item=item,
    )
    context = ThirdPartyBugContext(
        account="chao.li",
        projects=(ThirdPartyBugProject(name="BDS", identifier="bds", url="https://support/projects/bds", project_id="AN40BF-A311D2", issues=(item,)),),
        issues=(detail,),
    )

    payload = asdict(context)

    assert payload["projects"][0]["issues"][0]["subject"] == "panel issue"
    assert payload["issues"][0]["attachments"][0]["download_url"].endswith("/log.txt")


def test_redmine_models_reuse_third_party_bug_models():
    assert RedmineIssueListItem is ThirdPartyBugListItem
    assert RedmineIssueDetail is ThirdPartyBugDetail
    assert RedmineProject is ThirdPartyBugProject


def test_context_selects_items_and_replaces_detail_without_callsite_scanning():
    item = ThirdPartyBugListItem(id="61043", url="https://support/issues/61043", subject="old")
    project = ThirdPartyBugProject(name="BDS", identifier="bds", url="https://support/projects/bds", project_id="AN40BF-A311D2", issues=(item,))
    context = ThirdPartyBugContext(projects=(project,))
    detail = ThirdPartyBugDetail(id="61043", url=item.url, project_identifier="bds", subject="new", list_item=item)

    assert context.item_for_issue("61043") == (project, item)

    updated = context.with_detail(detail)

    assert updated.issues == (detail,)
