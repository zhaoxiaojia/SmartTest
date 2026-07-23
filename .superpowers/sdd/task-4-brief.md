### Task 4: RedmineBridge 批次状态与提交编排

**Files:**
- Modify: `ui/example/bridge/RedmineBridge.py`
- Modify: `testing/self_tests/ui/test_redmine_bridge.py`

**Consumes:** `JiraCreateSchemaService`, `RedmineCloneDraftService`, existing authenticated Jira client/CreateIssueService, existing Redmine context/detail cache, canonical personnel department helper.

**QML contract produced:**
- Properties: `cloneSelectionMode`, `cloneSelectedIds`, `cloneDrafts`, `cloneBatchState`, `cloneBatchLoaded`, `cloneBatchTotal`, `cloneBatchError`, `firstInvalidIssueId`, `firstInvalidFieldId`.
- Slots: `beginCloneSelection()`, `toggleCloneSelection(issue_id, selected)`, `cancelCloneSelection()`, `prepareCloneDrafts()`, `updateCloneDraft(issue_id, field_id, value)`, `submitCloneBatch()`, `retryFailedClones()`, `closeCloneBatch()`, `searchCloneUsers(issue_id, field_id, query)`.

**Binding behavior:**
- State machine: `idle -> selecting -> loading -> editing -> validating -> submitting -> completed/partial_failed`.
- Already cloned rows can never enter selection even if QML sends the slot directly.
- Prepare loads complete Redmine detail, Jira schema, current Jira reporter identity, and personnel department asynchronously; no create call.
- All drafts must validate before the first create call. On error, no create call and first invalid identities are set.
- Immediately before create, recheck existing clone. Create sequentially; continue after individual failure. Duplicate is resolved. Retry sends failed only.
- Successful/duplicate rows update existing clone-status owner so they become non-selectable.
- Submission cannot be cancelled after first create request. Loading/editing batch can be closed.
- LDAP/Jira account generation change invalidates drafts and late futures.
- QML-facing drafts must be plain QVariant-safe dictionaries retaining schema order, control, options, current values, errors and per-draft state.
- Do not implement QML in this task.

**Required tests:**
- Selection mode, direct-slot rejection of cloned row, deterministic source order, cancel cleanup.
- Prepare has zero create calls and emits loading/editing states.
- Exact FAE-SW department lookup and reporter/Jira identity passed into draft mapper.
- Missing required field blocks all network creation and points to first invalid field.
- User update changes draft and revalidates field.
- Success + failure + duplicate continues, records keys/errors and updates clone status.
- Retry submits only failed.
- Recheck catches a clone created during review.
- Account switch/late result invalidation.
- User search generation protection and normalized options.

Use existing executor/future generation patterns in RedmineBridge; do not add a second thread owner. Run focused/full bridge tests, Task 2/3 regressions, pycompile and diff-check. Commit only Task 4 files with `feat: orchestrate Redmine clone batches`. Full report to `.superpowers/sdd/task-4-report.md`.
