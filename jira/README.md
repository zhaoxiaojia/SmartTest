# Jira Integration Notes

This folder contains SmartTest's Jira integration layer.

The goal is not to wrap a single Jira SDK blindly. The goal is to provide:

- predictable REST behavior against the current Jira deployment
- explicit field projection for large-result queries
- strong handling of nested/custom fields
- fast browse flows for UI
- heavier analysis flows only when the user explicitly asks for them

## Current Assumptions

- The live instance currently behaves like Jira Server / Data Center.
- The active REST path in SmartTest is `.../rest/api/2/...`.
- LDAP credentials are reused for Jira access in the app.
- For SmartTest, browse flows and analysis flows must be separated:
  - browse: light fields, paged, fast response
  - analysis: may request more fields, more pages, and optional AI summarization

This assumption is based on current runtime behavior and Atlassian's Server/Data Center REST documentation, not just local guesses.

## Official References

Primary references used for this folder:

- Atlassian Jira Server / Data Center REST overview:
  - https://developer.atlassian.com/server/jira/platform/about-the-jira-server-rest-apis/
- Atlassian Jira Server / Data Center basic auth:
  - https://developer.atlassian.com/server/jira/platform/basic-authentication/
- Atlassian official REST reference for Jira `api/2/search` and `api/2/field`:
  - https://docs.atlassian.com/software/jira/docs/api/REST/7.1.9/
  - https://docs.atlassian.com/software/jira/docs/api/REST/8.2.6/
- `python-jira` API reference:
  - https://jira.readthedocs.io/en/latest/api.html
- `python-jira` client implementation and examples:
  - https://jira.readthedocs.io/_modules/jira/client.html
  - https://jira.readthedocs.io/examples.html

## What The Official Docs Mean For Our Design

### 1. Search must be field-projected

Jira search supports `fields`, `startAt`, `maxResults`, `expand`, and JQL.
That means our default path must be:

- request only the fields we actually need
- page results with `startAt` and `maxResults`
- avoid `expand` unless the caller explicitly needs it

This is the basis for:

- `jira/fields/`
- `jira/transport/client.py`
- `jira/services/issue_service.py`

### 2. `GET /search` and `POST /search` are not interchangeable in practice

Official Jira REST docs show that `POST /rest/api/2/search` accepts a JSON body with a schema where `validateQuery` is a boolean.
We already hit this in the live environment:

- sending `"strict"` in POST caused HTTP 400
- sending a boolean fixes it

So our transport layer must normalize search arguments differently for:

- GET query params
- POST JSON bodies

Do not assume a Cloud example or browser test automatically matches Server/DC POST behavior.

### 3. `/field` is required for strong custom-field handling

Official `GET /rest/api/2/field` returns:

- field id
- display name
- custom flag
- clause names
- schema data

That is exactly why this project keeps a metadata-driven registry:

- custom fields cannot be hardcoded safely
- display names may collide
- clause names may be ambiguous
- schema is required to infer whether a value should come from:
  - `.value`
  - `.name`
  - `.displayName`
  - `[]`

This is the basis for:

- `jira/fields/registry.py`
- `jira/cache/metadata_cache.py`

### 4. `python-jira` is useful reference material, not our primary hot path

The `python-jira` docs and source are useful because they document:

- `search_issues(...)`
- `fields`
- `expand`
- `json_result`
- `use_post`

But for SmartTest's performance requirements, its object layer is not ideal as the primary large-scale path. Our current design intentionally favors:

- direct REST JSON
- explicit field projection
- local caching/indexing
- delayed hydration of heavier issue details

That tradeoff is intentional.

## Folder Strategy

### `jira/transport/`

Owns raw HTTP calls and REST-level normalization.

Responsibilities:

- authenticate requests
- choose GET vs POST for search
- normalize search parameters
- page through results
- fetch field metadata
- fetch single issue details

It should not own UI rules or AI rules.

### `jira/fields/`

Owns field specification and extraction.

Responsibilities:

- field alias normalization
- field registry
- metadata-driven field registration
- path extraction from nested Jira JSON
- fetch planning: `jira_fields` plus `expand`

It should not own HTTP code.

### `jira/cache/`

Owns local persistence.

Responsibilities:

- metadata cache
- issue store
- search cache
- sync state

It should not own JQL construction policy beyond cache keys and sync state.

### `jira/services/`

Owns business-facing Jira operations.

Responsibilities:

- search records with field specs
- local reprojection of stored issues
- delayed issue hydration
- incremental sync

It should not own QML state or translation logic.

## Performance Rules For This Repo

These rules should guide future Jira changes.

### Browse first, analyze later

If the user is only opening the Jira page or changing filters:

- do not fetch all issues
- do not fetch heavy fields by default
- do not run AI analysis by default
- return the first page quickly
- allow append / load more

### Heavy fields are opt-in

Fields like the following are heavier and should stay deferred unless explicitly requested:

- changelog
- large comments payloads
- worklog
- deeply nested custom structures

### Local store is for response speed

The local issue store exists so we can:

- reuse fetched raw issue JSON
- query common dimensions locally
- support incremental sync
- avoid hitting Jira for every small UI interaction

It is not a license to eagerly sync everything at page-open time.

### Metadata is cacheable

Field metadata changes far less frequently than issue data.
So `/field` should be cached locally with TTL.

## Known Pitfalls Already Seen

### POST search validation mismatch

We already confirmed one live pitfall:

- `POST /search` rejected string `validateQuery`
- the live Jira expected boolean JSON

This is now a transport concern, not a UI concern.

### Alias collisions in field metadata

Different Jira fields can collide on:

- display names
- normalized aliases
- clause names

So metadata registration must:

- merge equivalent specs
- skip ambiguous aliases
- keep stable field ids usable

### QML/bridge failures can look like Jira API failures

We already hit a local bridge regression where a missing Python import (`Path`) broke cache path creation before the real Jira request path even ran.

That means Jira debugging must always separate:

- bridge/runtime errors
- transport/auth errors
- JQL/search errors
- field-mapping errors

## Practical Guidance For Future Work

### When adding a new field

Prefer this order:

1. check whether `/field` metadata already covers it
2. add or refine metadata-to-path inference if needed
3. only add a handwritten default spec when the field is truly common or special

### When adding a new UI browse feature

Prefer:

1. lighter `fields`
2. paged search
3. local reprojection from cached raw issues
4. optional detail hydration on selection

Do not default to full search plus AI.

### When adding a new AI analysis feature

The AI layer should consume:

- a defined issue sample or result set
- explicit field specs
- optionally hydrated issue details

It should not be the component deciding low-level Jira transport behavior.

## Why This README Exists

This folder has already reached the point where "just try another request shape" is no longer a good development strategy.

The integration should be driven by:

- official Jira REST behavior
- explicit field semantics
- performance-aware data access
- local caching and delayed hydration

If future work conflicts with these principles, stop and reassess before adding more code.
