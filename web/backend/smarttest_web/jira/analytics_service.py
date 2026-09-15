from __future__ import annotations

from core.async_tasks import TaskCancelled


def _quote(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _multi(field, values):
    clean = [value for value in values or () if str(value).strip()]
    return f"{field} IN ({', '.join(_quote(value) for value in clean)})" if clean else ""


def build_basic_jql(conditions, fields):
    clauses = []
    for key, field in (("project", "project"), ("issueType", "issuetype"), ("status", "status"), ("assignee", "assignee")):
        clause = _multi(field, conditions.get(key))
        if clause: clauses.append(clause)
    if str(conditions.get("containsText") or "").strip():
        clauses.append(f"text ~ {_quote(str(conditions['containsText']).strip())}")
    resolutions = conditions.get("resolution") or ()
    if resolutions:
        clauses.append(_multi("resolution", resolutions))
    for field_id, value in (conditions.get("more") or {}).items():
        metadata = fields.get(field_id) or {}
        if not metadata.get("queryable"):
            raise ValueError(f"advanced_only:{field_id}")
        control = metadata.get("control")
        if value in (None, "", [], {}): continue
        if control in {"multi", "user"}:
            clauses.append(_multi(field_id, value if isinstance(value, list) else [value]))
        elif control == "number":
            clauses.append(f"{field_id} = {float(value):g}")
        elif control == "date" and isinstance(value, dict):
            if value.get("from"): clauses.append(f"{field_id} >= {_quote(value['from'])}")
            if value.get("to"): clauses.append(f"{field_id} <= {_quote(value['to'])}")
        elif control == "text": clauses.append(f"{field_id} ~ {_quote(value)}")
        else: clauses.append(f"{field_id} = {_quote(value)}")
    return " AND ".join(filter(None, clauses))


class JiraAnalyticsService:
    def __init__(self, filters, gateway, mapper, repository, tasks, *, on_error=lambda _error: None):
        self.filters, self.gateway, self.mapper = filters, gateway, mapper
        self.repository, self.tasks = repository, tasks
        self.on_error = on_error

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
        return {**self.filters.validate(jql), "jql": jql}

    def search(self, session_hash, account, expires_at, payload):
        mode = payload.get("mode", "basic")
        basic = payload.get("basic") or {}
        field_map = {item["id"]: item for item in self.filters.fields()} if mode == "basic" else {}
        jql = build_basic_jql(basic, field_map) if mode == "basic" else str(payload.get("jql") or "")
        validation = self.filters.validate(jql)
        current = self.repository.state(session_hash, account)
        if not validation.get("valid"):
            return {"validation": validation, "taskId": "", "state": current}
        snapshot_id = self.repository.begin(
            session_hash, account, jql, basic if mode == "basic" else {},
            payload.get("sourceFilterId", ""), expires_at=expires_at,
        )

        def run(token, progress):
            try:
                token.raise_if_cancelled()
                rows = self.gateway.search_all_payloads(jql)
                total = len(rows)
                for start in range(0, total, 500):
                    token.raise_if_cancelled()
                    batch = [self.mapper.from_search(item) for item in rows[start:start + 500]]
                    self.repository.write_batch(snapshot_id, batch)
                    progress(min(start + len(batch), total), total)
                self.repository.activate(snapshot_id)
            except TaskCancelled:
                self.repository.finish(snapshot_id, "cancelled")
                raise
            except Exception as error:
                self.repository.finish(snapshot_id, "failed", getattr(error, "code", type(error).__name__))
                self.on_error(error)
                raise

        task_id = self.tasks.submit(session_hash, run)
        self.repository.set_task(snapshot_id, task_id)
        return {"validation": validation, "taskId": task_id, "snapshotId": snapshot_id,
                "state": self.repository.state(session_hash, account)}
