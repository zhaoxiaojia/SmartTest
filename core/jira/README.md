# Jira page application

This package owns the Jira page workspace, browse and analysis use cases, presentation payloads,
request models, query composition, and dependency composition. Reusable Jira authentication,
transport, field, cache, model, issue, and sync capabilities are owned by
`core.jira`.

UI bridges depend on the public `core.jira` package boundary. Other product tools that need Jira API
access is owned by `core.jira`; neutral cross-tracker contracts are owned by `core.issues`.
