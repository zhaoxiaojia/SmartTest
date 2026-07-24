# Jira Format Audit Common Tool Design

## Goal

Add a complete Jira format-audit workflow to SmartTest Common Tools. Authorized users enter either JQL or a Jira URL, start an asynchronous audit, inspect the active rule set and progress, review results, export an XLSX report to the Windows Downloads directory, and reveal the exported file in File Explorer.

## Scope

This delivery includes:

- an independent audit capability under `support/jira_integration`;
- a narrow Qt bridge registered by the desktop application;
- a Jira Format Audit entry and workspace under Common Tools;
- input validation, Jira querying, rule evaluation, progress reporting, result presentation, XLSX export, and file reveal;
- visibility for FAE-QA management grades and developers;
- English and Chinese owned UI text;
- focused business, bridge, permission, QML, translation, and source-runtime validation.

This delivery excludes:

- changes to or imports from root `jira_handler.py`;
- changes to Redmine Clone, its templates, validation, or submission flow;
- Jira issue mutation or automatic issue correction;
- new authentication UI or credential persistence;
- desktop package or installer rebuilds.

Redmine integration with the shared audit rules is deferred to a separate delivery. That later delivery must use a narrow call into the audit capability and may remove only proven duplicate rule code; it must not change unrelated Redmine behavior.

## Ownership and Architecture

`support/jira_integration` is the sole business owner of the new audit models, input resolution, rules, validation, orchestration, and XLSX export. The implementation may use root `jira_handler.py` as a behavioral reference during development, but production code and tests must not import it, execute it, or read it at runtime.

The existing Jira integration remains the owner of authentication and transport:

- `AuthBridge` supplies the authenticated account and transient LDAP credential.
- `JiraBasicAuth` constructs Jira Basic authentication.
- `JiraClient` performs Jira REST requests and paginated JQL searches.

A dedicated Jira audit bridge owns asynchronous execution, UI-facing state, localized fixed text, the last completed result, export coordination, and File Explorer reveal. QML owns layout and presentational interaction only. It must not parse Jira payloads, implement audit rules, build XLSX content, infer progress, or access credentials.

The audit bridge is independent from `JiraBridge`. Both may consume `AuthBridge`, but neither owns or calls the other.

## Access Control

The Common Tools group remains generally available. The Jira Format Audit tool entry is included only when the authenticated personnel record satisfies either condition:

1. department is exactly `FAE-QA` and `career.grade` starts with uppercase `M` after trimming; or
2. `system_roles` contains `developer`, compared case-insensitively.

This admits FAE-QA grades M1 through M5 and grants `chao.li` access through the existing developer role. Non-authorized users must not receive the tool entry in the `ToolBridge.groups` model. Hiding only the QML content is insufficient.

## Input Contract

The page provides one multiline-capable text input accepting either raw JQL or one Jira URL.

When the user presses **Start Audit**:

- whitespace-only input is rejected locally with an owned message requiring JQL or a Jira URL;
- strings recognized as URLs must use HTTP or HTTPS and target the configured Jira host;
- a Jira browse URL resolves to `key = ISSUE-KEY`;
- a Jira filter URL resolves its filter identifier through Jira and uses that filter's JQL;
- a Jira URL containing a `jql` query parameter uses its decoded JQL;
- unsupported or malformed Jira URLs are rejected with an actionable message;
- non-URL input is treated as raw JQL and validated by Jira through the existing search API;
- no audit run starts until the input resolves successfully.

The configured Jira base URL is the existing SmartTest Jira endpoint. User input cannot redirect credentials to another host.

## Rule Capability

The audit package exposes immutable UI-safe rule descriptors and structured audit results. Each rule descriptor includes a stable rule ID, section, field, human-readable requirement, and guidance. Each violation includes the rule ID, Jira key and URL, field, observed display value, reason, and guidance.

The initial rule behavior matches the supported behavior of `jira_handler.py`:

- Summary structure and required values;
- customer and problem-description English checks;
- uppercase chip check;
- allowed Jira module/component checks;
- probability format;
- required Description sections;
- Regression evidence requirements;
- attachment size limit;
- known label-driven conditions;
- unsupported normative-section reporting when applicable.

Rules are implemented within `support/jira_integration`; embedded defaults must be deterministic and testable. The audit runtime must not depend on root `jira规范.md`, because the feature must remain independently deployable. If Markdown rule loading is retained, it is an explicit optional override over embedded defaults and failures must not silently change the active rule set.

## Execution and Progress

Audit execution runs outside the QML/UI thread. Only one audit may run per bridge instance.

The UI-facing state machine is:

- `idle`: ready for input;
- `resolving`: validating input and resolving URL/filter JQL;
- `fetching`: querying Jira;
- `auditing`: evaluating fetched issues;
- `completed`: complete result available;
- `failed`: actionable failure displayed.

Progress includes a stage label, processed count, total count, and normalized percentage. Fetch progress must be emitted by bounded Jira page retrieval rather than appearing frozen until `search_all` completes. Audit progress advances per processed issue. A stale background result must not overwrite the state of a newer run.

Jira credentials and raw authorization values must never appear in models, logs, errors, exports, or QML.

## Result Presentation

The workspace has four visible regions:

1. input and Start Audit action;
2. expandable or scrollable active-rule details;
3. current state, progress bar, processed/total counts, and status message;
4. completed summary and violation rows.

The completed summary shows total issues, passed issues, failed issues, and total violations. Violation rows expose Jira key, failed field/section, rule, reason, and guidance. Jira-originated content remains raw; fixed UI labels and messages are translated through the existing translation files.

Starting a new valid audit clears the previous completed result. Invalid input leaves the last completed result intact but displays the validation error.

## Export and File Reveal

Export is enabled only for a successfully completed audit. It creates a unique `.xlsx` file in the current Windows user's Downloads known folder. The filename contains a stable Jira-audit prefix and a local timestamp so an existing export is not overwritten.

The workbook contains:

- an audit summary with resolved JQL and generation time;
- active rule details;
- per-issue audit status;
- one row per violation with Jira link, field, observed value, rule ID, requirement, reason, and guidance.

Export returns the absolute generated path to the bridge. The UI displays the path and enables **Show in Folder**. On Windows, that action launches File Explorer with the generated file selected. It is rejected cleanly if no export exists or the file has subsequently been removed.

## Error Handling

The bridge presents concise owned messages for:

- missing input;
- malformed or unsupported URL;
- foreign Jira host;
- invalid JQL;
- missing authenticated credential;
- Jira authentication, permission, network, timeout, or response failures;
- empty result sets;
- export failure;
- missing exported file or File Explorer launch failure.

Internal exception details may be logged without secrets. User-facing messages must not include authorization headers, passwords, or unbounded Jira response bodies.

## Validation

Functional acceptance requires:

- unit tests for URL/JQL resolution and rejection;
- rule tests covering every supported rule and representative passing issues;
- audit orchestration tests for counts, progress, empty results, and failures;
- XLSX tests for workbook structure, report contents, unique Downloads paths, and no overwrite;
- bridge tests for the state machine, stale-run protection, input errors, authentication reuse, export, and file reveal;
- permission tests for FAE-QA M grades, FAE-QA individual grades, other departments, developer casing, and `chao.li`;
- QML source checks and both-language owned-translation validation;
- rebuilt QRC resources when QML or translation resources require it;
- focused test suite, `git diff --check`, and bounded source startup validation from the repository root.

## Acceptance Criteria

The delivery passes only when:

- authorized users can see and open Jira Format Audit in Common Tools;
- unauthorized users receive no entry;
- empty and malformed input is rejected before work begins;
- supported Jira URLs and valid JQL execute through the existing authenticated Jira client;
- rules and progress are visible during the workflow;
- completed results accurately expose passed/failed counts and violations;
- XLSX export lands in Downloads and can be revealed in File Explorer;
- `jira_handler.py` is unchanged and absent from runtime dependencies;
- Redmine files and behavior are unchanged;
- no credentials are persisted or leaked;
- focused tests and source validation pass without weakening existing tests.
