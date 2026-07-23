from support.jira_integration.core.create_schema import (
    CreateFieldControl,
    CreateFieldSchema,
)
from support.jira_integration.core.models import CreateIssueResult
from tool.SmartHome.redmine.clone_controller import RedmineCloneController
from tool.SmartHome.redmine.clone_draft import CloneDraft, CloneDraftField


class IssueOwner:
    def __init__(self):
        self.results = []

    def record_clone_results(self, resolved):
        self.results.append(resolved)


def draft(issue_id="1", *, required_value="ready"):
    return CloneDraft(
        source_id=issue_id,
        source_url=f"https://redmine/issues/{issue_id}",
        fields=(
            CloneDraftField(
                CreateFieldSchema(
                    "summary", "Summary", True, CreateFieldControl.TEXT
                ),
                required_value,
                "" if required_value else "Summary is required",
            ),
            CloneDraftField(
                CreateFieldSchema(
                    "reporter", "Reporter", True, CreateFieldControl.USER
                ),
                "alice",
            ),
            CloneDraftField(
                CreateFieldSchema(
                    "labels", "Labels", False, CreateFieldControl.MULTI
                ),
                [],
            ),
            CloneDraftField(
                CreateFieldSchema(
                    "attachment", "Attachment links", False, CreateFieldControl.TEXT
                ),
                f"https://redmine/issues/{issue_id}",
            ),
        ),
    )


def records(*drafts):
    return [
        {
            "draft": item,
            "state": "editing",
            "key": "",
            "url": "",
            "error": "",
            "errorFieldId": "",
        }
        for item in drafts
    ]


def test_selection_rejects_cloned_rows_and_preserves_source_order():
    controller = RedmineCloneController(IssueOwner())
    rows = [
        {"id": "3", "cloneStatus": "not_cloned"},
        {"id": "1", "cloneStatus": "cloned"},
        {"id": "2", "cloneStatus": "not_cloned"},
    ]

    assert controller.begin_selection()
    controller.toggle_selection("2", True, rows)
    controller.toggle_selection("1", True, rows)
    controller.toggle_selection("3", True, rows)

    assert controller.snapshot.state == "selecting"
    assert controller.snapshot.selected_ids == ("3", "2")


def test_prepare_result_owns_visible_schema_projection_and_seeded_user_options():
    controller = RedmineCloneController(IssueOwner())

    controller.apply_result(
        "prepare", (records(draft()), {"alice": "Alice Reporter"})
    )

    snapshot = controller.snapshot
    assert snapshot.state == "editing"
    assert snapshot.loaded == 1
    assert [item["fieldId"] for item in snapshot.drafts[0]["fields"]] == [
        "summary",
        "reporter",
        "attachment",
    ]
    reporter = snapshot.drafts[0]["fields"][1]
    assert reporter["options"] == [
        {
            "value": "alice",
            "label": "Alice Reporter",
            "avatarUrl": "",
            "children": [],
        }
    ]


def test_local_validation_identifies_first_invalid_field_before_submit():
    controller = RedmineCloneController(IssueOwner())
    controller.apply_result("prepare", (records(draft(required_value="")), {}))

    assert controller.start_submit() is None
    assert controller.snapshot.state == "editing"
    assert controller.snapshot.first_invalid_issue_id == "1"
    assert controller.snapshot.first_invalid_field_id == "summary"

    assert controller.update_draft("1", "summary", "reviewed")
    assert controller.snapshot.first_invalid_issue_id == ""


def test_partial_success_patches_issue_owner_and_retry_selects_failed_only():
    owner = IssueOwner()
    submitted = []

    async def submit(batch):
        submitted.append([item["draft"].source_id for item in batch])
        return []

    controller = RedmineCloneController(owner, submit_records=submit)
    controller.apply_result(
        "prepare", (records(draft("1"), draft("2"), draft("3")), {})
    )
    created = CreateIssueResult(
        created=True, issue_key="SH-1", issue_url="https://jira/SH-1"
    )
    duplicate = CreateIssueResult(
        created=False,
        existing_key="SH-2",
        issue_url="https://jira/SH-2",
    )

    controller.apply_result(
        "submit",
        [
            ("1", "created", created, ""),
            ("2", "duplicate", duplicate, ""),
            ("3", "failed", None, "offline"),
        ],
    )

    assert controller.snapshot.state == "partial_failed"
    assert [item["state"] for item in controller.snapshot.drafts] == [
        "created",
        "duplicate",
        "failed",
    ]
    assert set(owner.results[0]) == {"1", "2"}
    operation = controller.retry_failed()
    assert operation is not None and operation.kind == "submit"
    assert controller.snapshot.state == "submitting"
    operation.awaitable.close()


def test_user_result_replaces_search_hits_but_keeps_current_value_option():
    controller = RedmineCloneController(IssueOwner())
    controller.apply_result("prepare", (records(draft()), {"alice": "Alice"}))

    controller.apply_result(
        "users",
        (
            "1",
            "reporter",
            [
                {
                    "account": "bob",
                    "display_name": "Bob",
                    "avatar_url": "bob.png",
                }
            ],
        ),
    )

    options = controller.snapshot.drafts[0]["fields"][1]["options"]
    assert [item["value"] for item in options] == ["bob", "alice"]
