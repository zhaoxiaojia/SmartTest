# Task 3 Report — Mason

## Status

DONE

## Reuse decision

Added one Redmine draft-mapping owner and extended the existing `CreateIssueRequest`/`CreateIssueService`; the existing service remains the sole Jira JSON and duplicate-detection owner.

## Files

- `tool/SmartHome/redmine/clone_draft.py`
- `tool/SmartHome/redmine/create.py`
- `support/jira_integration/core/models.py`
- `support/jira_integration/services/create_issue_service.py`
- `testing/self_tests/tool/smarthome/redmine/test_clone_draft.py`

## RED evidence

- Command: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/tool/smarthome/redmine/test_clone_draft.py -q`
- Exit code: 1 during collection.
- Result: expected `ModuleNotFoundError` because `tool.SmartHome.redmine.clone_draft` did not exist.

## GREEN evidence

- Initial focused result: 9 passed.
- Final regression command: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/tool/smarthome/redmine/test_clone_draft.py testing/self_tests/tool/smarthome/redmine/test_create.py testing/self_tests/tool/smarthome/redmine/test_auth.py testing/self_tests/support/test_third_party_bug_models.py testing/self_tests/jira_tool/test_create_issue_service.py -q`
- Exit code: 0; 31 passed.
- `py_compile` for all Task 3 production/test files: exit 0.
- `git diff --check`, `git diff --cached --check`, and temporary diagnostic scan: exit 0 / clean.

## Mapping and payload assumptions

- Schema semantic names identify dynamic custom fields; custom IDs are never used for discovery.
- Confirmed labels resolve to current schema option IDs; values sent by later edits are expected to remain schema-normalized IDs/accounts.
- `field_controls` disambiguates normalized IDs from legacy name-based `priority`, `components`, and raw `extra_fields`, preserving existing callers.
- Jira Server payload shapes are: single `{id}`, multi `[{id}]`, cascade `{id, child: {id}}`, user `{name}`, and raw text/multiline.
- Current account is used for Reporter and exact `FAE-SW` coworker; Manager and FAE Manager use `fred.chen`.

## Self-review

- Bug/Support, every confirmed mapping, department positive/negatives, empty description, project metadata identity, missing options, unmapped required fields, user edits, payload shapes, existing clone entrypoint, source identity, and duplicate labels are covered.
- Draft fields preserve Jira schema order and remain editable through `CloneDraft.update`.
- Missing confirmed options and unmapped required fields remain empty with blocking field errors.
- Project ID comes only from `RedmineProject.project_id`, not project name/description.
- Existing `CreateIssueService` duplicate JQL and source labels are unchanged.
- Existing raw `extra_fields`, name-based priority/components, and direct Redmine clone behavior remain compatible.
- No Bridge, QML, batch state, async orchestration, or custom-field-ID mapping was added.
- The ignored new self-test was force-added because it is an explicitly approved Task 3 file.

## Concerns

- None affecting acceptance.
- No live Jira create was executed; Jira Server shapes are contract-tested at the sole payload owner.

## Commit

- `c2ce79b feat: map Redmine issues to editable Jira drafts`

## Workspace

- Task commit is on `main`.
- `.superpowers/` remains untracked task ledger/report content and was not committed.

## Review rework — createmeta context and defaults

- Task 2 schema now prepends synthetic `project` and `issuetype` fields to realistic createmeta that omits them, preserving Jira field order after the two context fields.
- Unmapped draft fields now inherit normalized `schema.value`; explicit Redmine mappings still take precedence.
- Missing defaults use stable empty shapes: multi `[]`, cascade `{}`, scalar/text `""`; required empties remain blocking.
- Software Release coverage proves a Jira default ID is retained and a missing default remains empty without inventing an option.
- RED command: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_jira_create_schema_service.py testing/self_tests/tool/smarthome/redmine/test_clone_draft.py -q`
- RED result: exit 1; 2 failed for missing synthetic context and explicit Software Release clearing.
- Focused GREEN: 18 passed.
- Combined regression command covered Task 2 schema/transport/Jira tests plus Task 3 draft/create/auth/model tests.
- Combined result: exit 0; 51 passed.
- `py_compile`, `git diff --check`, `git diff --cached --check`, and diagnostic scan passed.
- Rework commit: `0861d4a fix: preserve Jira create context and defaults`.
- `CreateIssueService` was unchanged and remains the sole payload owner.
- Concerns: no live Jira call; accepted payload/default shapes are contract-tested.
