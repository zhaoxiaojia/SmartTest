# Task 4 Report — Mason

## Status

DONE

## Reuse decision

Extended `RedmineBridge` as the existing UI-state owner, reused its `_AsyncLoopWorker`, callback/generation pattern, Redmine context/detail cache, Jira client/CreateIssueService, clone checker, and `_apply_clone_status`; no second executor, payload builder, or clone-status model was added.

## Files

- `ui/example/bridge/RedmineBridge.py`
- `testing/self_tests/ui/test_redmine_bridge.py`

## RED evidence

- Command: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/ui/test_redmine_bridge.py -q -k "clone_batch_selection"`
- Exit code: 1.
- Result: expected `AttributeError`; `beginCloneSelection` did not exist.

## GREEN evidence

- Initial selection GREEN: 1 passed.
- New batch contract subset: 5 passed.
- Full bridge suite: 39 passed.
- Final combined command covered full RedmineBridge, Task 2 schema, Jira create/model, and Task 3 draft/create/auth regressions.
- Final combined result: exit 0; 77 passed.
- `py_compile` for Bridge and bridge tests: exit 0.
- `git diff --check`, `git diff --cached --check`, and diagnostic scan: clean.

## State and dependency behavior

- State owner implements idle, selecting, loading, editing, validating, submitting, completed, and partial_failed.
- Selection is re-derived from source issue-row order; direct attempts to select cloned rows are rejected.
- Prepare uses the existing worker, complete cached details or the existing collector, Jira create schema, uniquely matched current Jira account, and canonical `employee_department`.
- Jira schema/client/CreateIssueService share one authenticated client; existing clone checker now reuses that service.
- Every draft is validated before submission. The first draft/field error, including invalid direct-slot edits, blocks all create calls.
- Submission rechecks external URL immediately before create, proceeds sequentially after individual failures, and retries failed records only.
- Created and duplicate results update `_apply_clone_status`, making resolved rows non-selectable through the existing owner.
- Account/login/close generations invalidate drafts and late callbacks. User-search results share the same clone generation protection.
- Loading/editing can close; close is ignored while submitting.

## QML contract review

- Added all requested properties and slots without changing QML.
- `cloneDrafts` contains only QVariant-safe dictionaries/lists/scalars.
- Draft and field order matches selected issue/source order and Jira schema order.
- Field payload includes fieldId, name, required, control, options, value, error; draft payload includes issueId, sourceUrl, errors, state, key, url, error.
- User options normalize to value, label, avatarUrl, children.

## Concerns

- None affecting acceptance.
- No live Redmine/Jira batch creation was executed; orchestration and owner boundaries are contract-tested with deterministic fakes.

## Commit

- `66ddf12 feat: orchestrate Redmine clone batches`

## Workspace

- Task commit is on `main`.
- `.superpowers/` remains untracked task ledger/report content and was not committed.
