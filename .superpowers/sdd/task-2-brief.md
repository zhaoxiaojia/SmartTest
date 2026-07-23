### Task 2: Jira Create Metadata 与字段 Schema

**Files:**
- Modify: `support/jira_integration/transport/client.py`
- Create: `support/jira_integration/core/create_schema.py`
- Create: `support/jira_integration/services/create_schema_service.py`
- Modify: `support/jira_integration/services/__init__.py`
- Create: `testing/self_tests/support/test_jira_create_schema_service.py`

**Interfaces:**
- Produces: `JiraClient.fetch_create_metadata(project_key: str, issue_type: str) -> dict[str, Any]`。
- Produces: `JiraClient.search_users(query: str, *, project_key: str = "SH") -> list[dict[str, Any]]`。
- Produces: `CreateFieldSchema(field_id, name, required, control, options, value, children)` 和 `JiraCreateSchemaService.schema(project_key, issue_type)`。
- Control 枚举固定为 `text`、`multiline`、`single`、`multi`、`cascade`、`user`。

**Binding rules:**
- Project fixed `SH`; field metadata/required/options come from Jira API for `SH + Issue Type`.
- QML must never infer field types or hard-code candidate lists.
- This task owns transport/schema only; no Redmine mapping, Bridge batch state, or QML.
- Use existing Jira transport error handling and metadata patterns; no parallel client.

- [ ] Write failing transport tests proving `issue/createmeta` params are `projectKeys=SH`, `issuetypeNames=Bug`, `expand=projects.issuetypes.fields` and user search is project-scoped.
- [ ] Write failing schema tests proving native mapping: required summary -> `text`; description -> `multiline`; Channel of Reporter -> `cascade`; components -> `multi`; Jira user custom fields -> `user`; ordinary allowed-values scalar -> `single`; array -> `multi`.
- [ ] Verify RED.
- [ ] Implement minimal `fetch_create_metadata` and `search_users` through `_request`/`_api_path`.
- [ ] Implement immutable presentation-neutral schema dataclasses and deterministic field order from create metadata.
- [ ] A missing project/issue type must raise existing Jira domain error rather than return guessed fields.
- [ ] User results normalize to `{account, display_name, avatar_url}` and retain no secret/token data.
- [ ] Run focused tests, Jira integration regression, py_compile and diff-check.
- [ ] Commit only Task 2 files with `feat: expose Jira create field schema`.

Report full RED/GREEN commands, files, API assumptions, self-review, commit and concerns to `.superpowers/sdd/task-2-report.md`.
