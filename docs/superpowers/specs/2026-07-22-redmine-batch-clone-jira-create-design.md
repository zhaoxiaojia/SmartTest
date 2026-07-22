# Redmine Batch Clone to Jira Create Design

## Objective

Allow a user to select multiple uncloned Redmine issues, review and edit all corresponding Jira creation drafts together, and start creation only after one explicit batch confirmation.

The design reuses the existing Redmine issue list, clone-status detection, Jira authentication/client, and create service. It adds one schema-driven Jira Create QML surface. It does not embed or automate Jira's web create dialog.

## Ownership

### Redmine selection

The Redmine issue-list flow owns only selection and reliable source values:

- Enter and leave Clone selection mode.
- Show one checkbox per issue while selection mode is active.
- Disable selection for rows whose `cloneStatus` is already `cloned`.
- Preserve normal issue selection and detail behavior outside Clone mode.
- Resolve the selected Redmine issues to complete details before opening drafts.
- Supply initial values only when a mapping is explicit.

Redmine does not define Jira controls, Jira required fields, candidate options, or fallback values for unmapped fields.

### Jira create schema and drafts

The Jira creation owner obtains create metadata for the fixed Jira project `SH` and the mapped issue type. It exposes a presentation-neutral schema containing field identity, label, required state, control type, current value, candidate options, loading state, and validation error.

The new Jira Create QML renders that schema:

- Jira text input becomes a QML text input.
- Jira single-select becomes a QML single-select.
- Jira multi-select becomes a QML multi-select.
- Jira cascading select becomes two linked QML selects.
- Jira user picker becomes a searchable user picker backed by Jira API results.
- Multiline Jira fields use multiline QML editors.

QML owns layout and temporary editing interactions. The bridge owns draft identity, schema, option loading, validation, request conversion, and submission state.

## Personnel Configuration

The canonical Amlogic departments become:

- `FAE-QA`
- `FAE-SW`
- `FAE-HW`

The existing `FAE` department is renamed to `FAE-SW` without changing its existing employees or product assignments.

Add Fred Chen with:

- LDAP/Jira account: `fred.chen`
- Display name: `Fred Chen`
- Department: `FAE-SW`
- Grade: `M5`
- SmartHome product-line owner responsibility

Only an authenticated user whose canonical department is exactly `FAE-SW` is automatically used as FAE Coworker. `FAE-QA`, `FAE-HW`, unknown personnel, and other departments leave that field empty for user selection.

## Draft Creation Flow

1. The user clicks Clone in the Redmine issue-list toolbar.
2. Checkboxes appear for all visible issues.
3. Already-cloned issues remain visible but their checkboxes are disabled.
4. The user selects one or more issues and confirms the selection.
5. The bridge loads complete Redmine details and Jira create metadata/options without creating Jira issues.
6. One batch dialog opens with every draft fully expanded in source-list order.
7. The user reviews and edits any prefilled or empty field.
8. One Batch Create action validates every draft locally.
9. If validation fails, no Jira request is sent; the UI scrolls to the first invalid draft/field and shows all errors.
10. If validation passes, the bridge submits drafts sequentially with progress and cancellation disabled once submission begins.

Opening the dialog, loading options, and editing drafts have no Jira creation side effects.

## Confirmed Initial Values

All initial values remain user-editable.

| Jira field | Initial value |
|---|---|
| Project | Fixed `Smart Home Projects (SH)` / key `SH` |
| Issue Type | Redmine `Bug -> Bug`; `Support -> Feature` |
| Channel of Reporter | `Customer-Feedback` with child `None` |
| Summary | Redmine subject |
| Priority | `P2` |
| Severity | `Major` |
| Product | `BDS Reference` |
| Component/s | `Customization` |
| Project ID | Redmine child-project `[Project ID]` value |
| Software Release | Empty unless a later approved mapping exists |
| Reporter | Current authenticated Jira user |
| Manager | Jira user `fred.chen` |
| FAE Coworker | Current LDAP/Jira user only for department `FAE-SW`; otherwise empty |
| FAE Manager | Jira user `fred.chen` |
| Description | Redmine description plus source identity/link; a generated source summary only when description is empty |

The currently observed Jira field identifiers are discovery hints, not hard-coded UI contracts:

- Channel of Reporter: `customfield_12200`
- Severity: `customfield_10109`
- Product: `customfield_10107`
- Project ID: `customfield_10407`
- Software Release: `customfield_10300`
- Manager: `customfield_10700`
- FAE Coworker: `customfield_10409`
- FAE Manager: `customfield_11002`

Field metadata is resolved by Jira API for project `SH` and the mapped issue type. A missing required field, missing option, ambiguous user, or changed field identifier remains visible and blocks submission rather than being guessed.

## Batch Dialog Layout

The dialog follows Jira Create Issue's vertical field order and required markers while using existing FluentUI controls and theme tokens.

- Header: selected count, loading/validation/submission status, close action before submission.
- Scroll area: one expanded card per Redmine issue, identified by Redmine ID and summary.
- Each card: schema fields in Jira order, required markers, inline help/error text, and current draft values.
- Sticky footer: Cancel and Batch Create. Batch Create shows the number of drafts.
- During metadata loading, draft skeleton/progress is shown and Batch Create is disabled.
- During submission, edits and closing are disabled and aggregate progress is shown.

The expected batch is small; virtualization and collapsed cards are not introduced.

## Submission and Recovery

Jira does not provide an atomic multi-issue transaction. After all local validation passes, drafts are created sequentially:

- Successful drafts show the new Jira key/link and immediately update Redmine clone status.
- Duplicate detection returns the existing Jira key/link and treats the draft as resolved rather than creating again.
- A failed draft retains all user edits and shows the server error.
- Submission continues for remaining validated drafts.
- A retry action submits failed drafts only; successful or duplicate drafts cannot be selected again.

No automatic rollback is attempted for already-created Jira issues.

## API and Cache Rules

- Reuse the existing authenticated Jira client and `CreateIssueService`.
- Extend the existing create request model for required custom fields; do not construct Jira JSON in QML.
- Candidate values must come from Jira create metadata or Jira picker APIs, never hard-coded lists. Confirmed initial labels such as `Major` and `Customization` are resolved to current Jira option identities before submission.
- Cache stable create metadata/options by Jira base URL, project key, issue type, and field identity with the existing metadata-cache mechanism where applicable.
- User searches and dependent-field options remain asynchronous and generation-protected.
- Drafts are transient and account-bound. LDAP/Jira account change closes or invalidates drafts and late results.

## Error Handling

- Redmine details unavailable: omit that issue from the dialog and report it before review begins.
- Jira metadata unavailable: keep the dialog in a retryable loading/error state; do not fall back to guessed fields.
- Required option no longer exists: clear the invalid initial value and require user selection.
- `fred.chen` not uniquely resolved: block the affected drafts and show the user-picker error.
- Already-cloned status changes while reviewing: recheck immediately before submission and mark that draft resolved/skipped.
- Account changes: invalidate the batch and require selection again under the new account.

## Validation

Automated coverage must include:

- Clone-mode selection, already-cloned disabled state, cancel/confirm behavior, and normal list behavior restoration.
- Mapping of Bug/Support and all confirmed initial values.
- Exact `FAE-SW` coworker behavior, including negative `FAE-QA` and `FAE-HW` cases.
- Jira metadata to text/single/multi/cascade/user/multiline schema conversion.
- Dependent option loading and stale-result protection.
- Multiple expanded drafts, editable prefilled values, and one batch confirmation.
- All-or-none local validation before the first network create call.
- Sequential success, duplicate, partial failure, and failed-only retry.
- Account switch invalidation.
- QML runtime loading, translations, theme/resource integration, and source startup.

No package build is required during ordinary implementation. Package validation is required at release handoff if packaged behavior is requested.
