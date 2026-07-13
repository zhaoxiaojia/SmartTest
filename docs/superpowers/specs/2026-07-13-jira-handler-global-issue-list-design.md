# Jira Handler Global Issue List Design

## Goal

Make `jira_handler.py` runnable without command-line business arguments. A user edits a configuration block at the top of the script, runs the file, and obtains one reusable global Jira issue list for format auditing and future business functions.

## Configuration

`JIRA_CONFIG` contains `base_url`, `username`, `password`, `jql`, `jira_url`, `issue_keys`, and `output`. Credentials are read only from this in-file configuration. Exactly one issue source is selected in priority order: explicit `issue_keys`, `jira_url`, then `jql`.

Supported URLs are a single `/browse/KEY-123` issue URL, a Jira issue-search URL containing a URL-encoded `jql` query parameter, and a search URL containing `filter=12345`. A filter URL is resolved through Jira REST to obtain its JQL before the issue search.

## Shared Data Flow

`load_global_issues()` resolves the configured source, requests complete issue fields once, and replaces the contents of the module-level `ISSUE_LIST`. Format auditing consumes `ISSUE_LIST`; future business functions receive or consume that same list and must not independently query Jira.

The script's `main()` performs: validate configuration, load `ISSUE_LIST`, run the enabled business operations, and export the audit workbook. Format auditing is the first enabled operation. The existing validation and XLSX implementation remain the single owners of those responsibilities.

## Error Handling And Security

Missing credentials, an unsupported URL, conflicting or empty source configuration, an unresolved filter, and Jira HTTP errors produce actionable messages. The password must never appear in logs, reports, exceptions, or test output. The script remains portable and standard-library-only.

## Verification

Tests cover source precedence, browse URL extraction, encoded JQL extraction, filter-to-JQL resolution, one shared fetch per run, global list replacement without rebinding, audit consumption of that global list, and direct no-argument execution with patched configuration/network boundaries.
