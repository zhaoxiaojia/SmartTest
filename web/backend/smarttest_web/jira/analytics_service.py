from __future__ import annotations

from core.async_tasks import TaskCancelled
from core.jira.services.filter_service import build_basic_jql, compose_jql


class JiraAnalyticsService:
    def __init__(self, filters, gateway, mapper, repository, tasks, *, fixed_conditions="", card_key="", on_error=lambda _error: None):
        self.filters, self.gateway, self.mapper = filters, gateway, mapper
        self.repository, self.tasks = repository, tasks
        self.on_error = on_error
        self.fixed_conditions = fixed_conditions
        self.card_key = card_key

    def schema(self):
        fields = self.filters.fields()
        by_id = {item["id"].casefold(): item for item in fields}
        fixed = [by_id[field_id] for field_id in ("project", "issuetype", "status", "assignee", "resolution") if field_id in by_id]
        return {"fixed": fixed, "more": [
            item for item in fields
            if item["id"].casefold() not in {"project", "issuetype", "status", "resolution", "text", "assignee"}
        ]}

    def suggestions(self, field_name, query=""):
        return self.filters.suggestions(field_name, query)

    def preview(self, payload):
        mode = payload.get("mode", "advanced")
        if mode == "basic":
            fields = {item["id"]: item for item in self.filters.fields()}
            jql = build_basic_jql(payload.get("basic") or {}, fields)
        else:
            jql = str(payload.get("jql") or "")
        effective = compose_jql(jql, self.fixed_conditions)
        validation = self.filters.validate(effective) if effective else {"valid": True, "errors": []}
        return {**validation, "jql": effective, "userJql": jql}

    def search(self, session_hash, account, expires_at, payload):
        mode = payload.get("mode", "basic")
        basic = payload.get("basic") or {}
        preview = self.preview({**payload, "mode": mode})
        jql, user_jql = preview["jql"], preview["userJql"]
        validation = {key: value for key, value in preview.items() if key not in {"jql", "userJql"}}
        current = self.repository.state(session_hash, account, card_key=self.card_key)
        if not validation.get("valid"):
            return {"validation": validation, "taskId": "", "state": current}
        snapshot_id = self.repository.begin(
            session_hash, account, jql, basic if mode == "basic" else {},
            payload.get("sourceFilterId", ""), expires_at=expires_at, user_jql=user_jql, card_key=self.card_key,
        )

        def run(token, progress):
            try:
                token.raise_if_cancelled()
                def fetch_progress(processed, total):
                    token.raise_if_cancelled()
                    progress(processed, total)
                rows = self.gateway.search_all_payloads(jql, progress=fetch_progress)
                total = len(rows)
                for start in range(0, total, 500):
                    token.raise_if_cancelled()
                    batch = [self.mapper.from_search(item) for item in rows[start:start + 500]]
                    self.repository.write_batch(snapshot_id, batch)
                self.repository.activate(snapshot_id)
            except TaskCancelled:
                self.repository.finish(snapshot_id, "cancelled")
                raise
            except Exception as error:
                self.repository.finish(snapshot_id, "failed", getattr(error, "code", type(error).__name__))
                self.on_error(error)
                raise

        task_id = self.tasks.submit(session_hash, run, card_key=self.card_key)
        self.repository.set_task(snapshot_id, task_id)
        return {"validation": validation, "taskId": task_id, "snapshotId": snapshot_id,
                "state": self.repository.state(session_hash, account, card_key=self.card_key)}
