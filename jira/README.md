# Jira page application

This package owns the Jira page workspace, browse and analysis use cases, presentation payloads,
request models, query composition, and dependency composition. Reusable Jira authentication,
transport, field, cache, model, issue, and sync capabilities are owned by
`support.jira_integration`.

UI bridges depend on the public `jira` package boundary. Other product tools that need Jira API
access depend on `support.jira_integration`, not this page package.
