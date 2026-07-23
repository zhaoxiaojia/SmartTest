# Task 2 Report — Mason

## Status

DONE

## Reuse decision

Extended the canonical `JiraClient` transport. Added one create-metadata schema owner because the existing field registry owns search/extraction paths rather than Jira create controls.

## Files

- `support/jira_integration/transport/client.py`
- `support/jira_integration/core/create_schema.py`
- `support/jira_integration/services/create_schema_service.py`
- `support/jira_integration/services/__init__.py`
- `testing/self_tests/support/test_jira_create_schema_service.py`

## RED evidence

- Command: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_jira_create_schema_service.py -q`
- Exit code: 1 during collection.
- Result: expected `ModuleNotFoundError` because `create_schema_service` did not exist.

## GREEN evidence

- Focused command: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_jira_create_schema_service.py -q`
- Exit code: 0; 6 passed.
- Jira regression command: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_jira_create_schema_service.py testing/self_tests/support/test_browser_automation.py testing/self_tests/support/test_third_party_bug_models.py testing/self_tests/jira_tool -q`
- Exit code: 0; 29 passed.
- `py_compile` for all five Task 2 files: exit 0.
- `git diff --check` and `git diff --cached --check`: exit 0.

## API assumptions

- Jira Server create metadata uses `GET rest/api/2/issue/createmeta` with `projectKeys`, `issuetypeNames`, and `expand=projects.issuetypes.fields`.
- Assignable-user search uses `GET rest/api/2/user/assignable/search` with `project` and Jira Server's `username` query parameter.
- User account normalization prefers `name`, then `accountId`, then `key`; only account, display name, and avatar URL leave the transport.
- Create field order follows the Jira metadata `fields` object insertion order.
- Option identity prefers Jira `id`; the display label prefers `value`, `name`, then `displayName`.

## Self-review

- Control values are a closed string enum: text, multiline, single, multi, cascade, user.
- Schema and option dataclasses are frozen and presentation-neutral.
- Mapping uses Jira schema/custom metadata, allowed values, and confirmed semantic names; it does not depend on custom field IDs.
- Cascade options retain normalized child options.
- Missing project, issue type, or fields raises existing `JiraRequestError`; no guessed schema is returned.
- No Redmine mapping, batch state, bridge, QML, cache, secret, or token handling was added.
- The ignored new self-test was force-added because it is an explicitly approved Task 2 file.

## Concerns

- None affecting acceptance.
- No live Jira call was made; API behavior is contract-tested against the accepted Jira Server endpoints and payload shapes.

## Commit

- `6943ecf feat: expose Jira create field schema`

## Workspace

- Task commit is on `main`.
- `.superpowers/` remains untracked task ledger/report content and was not committed.

## Cross-owner rework from Task 3 review

- Added required synthetic `project` and `issuetype` schemas before native Jira fields because real createmeta commonly omits both context fields.
- Synthetic values/options are derived from the matched project and issue-type metadata and remain editable single values (`SH`, selected type name).
- Added native `defaultValue` normalization for text/multiline, single ID, multi IDs, cascade parent/child IDs, and user account.
- RED command: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_jira_create_schema_service.py testing/self_tests/tool/smarthome/redmine/test_clone_draft.py -q`
- RED result: exit 1; 2 failed for missing context fields and overwritten Software Release default.
- Focused GREEN: 18 passed.
- Combined Task 2+3 regression: 51 passed.
- Rework commit: `0861d4a fix: preserve Jira create context and defaults`.
- Concerns: none.
