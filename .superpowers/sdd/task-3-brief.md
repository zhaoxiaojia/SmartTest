### Task 3: Redmine Clone 草稿映射与创建请求

**Files:**
- Create: `tool/SmartHome/redmine/clone_draft.py`
- Modify: `tool/SmartHome/redmine/create.py`
- Modify: `support/jira_integration/core/models.py`
- Modify: `support/jira_integration/services/create_issue_service.py`
- Create: `testing/self_tests/tool/smarthome/redmine/test_clone_draft.py`

**Consumes:** Task 2 `CreateFieldSchema`, `CreateFieldOption`, `CreateFieldControl`.

**Produces:**
- `RedmineCloneDraftService.build(issue, project, schema, account, department) -> CloneDraft`.
- Presentation-neutral `CloneDraft` with ordered editable fields, errors, source identity, and `to_request() -> CreateIssueRequest`.
- Extended create request/payload that carries normalized standard/custom field values while `CreateIssueService` remains the only Jira JSON owner.

**Confirmed mappings:**
- Project `SH`; tracker Bug -> Bug, Support -> Feature.
- Channel `Customer-Feedback` + child `None`; Summary subject; Priority P2; Severity Major; Product BDS Reference; Components Customization; Project ID Redmine child `[Project ID]`; Reporter current Jira user (leave schema default/identity input for later Bridge); Manager and FAE Manager `fred.chen`; FAE Coworker current account only when department exactly `FAE-SW`; Description source description plus Redmine identity/link, with generated source summary if empty.
- Software Release and any unmapped required field remain empty.
- Every prefilled value is editable.
- Resolve confirmed labels to current schema option IDs where options exist. If a confirmed option does not exist, leave empty and expose a blocking field error; never invent option IDs.

**TDD cases required:**
- All mappings above for Bug and Support.
- FAE-SW positive and FAE-QA/FAE-HW/unknown negative coworker cases.
- Empty Description produces nonempty Redmine ID/source URL text.
- Redmine Project ID comes from project metadata, not guessed from name/description.
- Missing confirmed option is empty + blocking error.
- User edits replace initial values in `to_request`.
- Payload shapes for text, single, multi, cascade, user and standard components/priority are valid Jira Server shapes.
- Duplicate-detection source labels/source identity remain intact.

Run focused tests, existing Redmine create/model tests, CreateIssueService tests, pycompile and diff-check. Commit only Task 3 files with `feat: map Redmine issues to editable Jira drafts`. Write full report to `.superpowers/sdd/task-3-report.md`.
