from __future__ import annotations

from time import monotonic

from core.logging import smart_log
from core.async_tasks import TaskCancelled
from core.jira.gateway import JiraGateway
from core.jira.services.filter_service import build_basic_jql, compose_jql


class JiraAnalyticsService:
    def __init__(self, filters, gateway, mapper, repository, tasks, *, fixed_conditions="", card_key="",
                 roster_fingerprint="", statistics_builder=None, comparison_conditions="",
                 on_error=lambda _error: None):
        self.filters, self.gateway, self.mapper = filters, gateway, mapper
        self.repository, self.tasks = repository, tasks
        self.on_error = on_error
        self.fixed_conditions = fixed_conditions
        self.card_key = card_key
        self.roster_fingerprint = roster_fingerprint
        self.statistics_builder = statistics_builder
        self.comparison_conditions = comparison_conditions

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
        comparison_jql = compose_jql(user_jql, self.comparison_conditions) if self.comparison_conditions else ""
        validation = {key: value for key, value in preview.items() if key not in {"jql", "userJql"}}
        if comparison_jql:
            comparison_validation = self.filters.validate(comparison_jql)
            if not comparison_validation.get("valid"):
                validation = comparison_validation
        current = self.repository.state(session_hash, account, card_key=self.card_key)
        if not validation.get("valid"):
            return {"validation": validation, "taskId": "", "state": current}
        snapshot_id = self.repository.begin(
            session_hash, account, jql, basic if mode == "basic" else {},
            payload.get("sourceFilterId", ""), expires_at=expires_at, user_jql=user_jql, card_key=self.card_key,
            roster_fingerprint=self.roster_fingerprint,
            comparison_jql=comparison_jql,
        )

        def run(token, progress):
            started = monotonic()
            outcome = "failed"
            processed = 0
            def log_stage(stage, since, *, period="both", layer="basic", page_count=0, processed=0, outcome="completed"):
                smart_log("Jira card load stage", platform="web", domain="jira", extra={
                    "card_key": self.card_key, "stage": stage, "period": period, "layer": layer,
                    "duration_ms": round((monotonic() - since) * 1000, 3),
                    "page_count": page_count, "processed": processed, "outcome": outcome,
                })
            try:
                token.raise_if_cancelled()
                layered = bool(self.statistics_builder and comparison_jql)
                rows_by_period = {"current": [], "previous": []}
                availability = {period: {"basic": False, "verify": False} for period in rows_by_period}
                queries = {"current": jql, **({"previous": comparison_jql} if comparison_jql else {})}
                statistics = None
                for layer in (["basic", "verify"] if layered else ["basic"]):
                    for period, query in queries.items():
                        token.raise_if_cancelled()
                        since = monotonic()
                        observed_total = 0
                        def report(count, total):
                            nonlocal observed_total
                            observed_total = max(observed_total, total)
                            token.raise_if_cancelled()
                            progress(processed + count, processed + total)
                        fields = [*JiraGateway.CORE_FIELDS, "comment"] if layer == "basic" else ["key"]
                        rows = self.gateway.search_all_payloads(
                            query, fields=fields, expand=["changelog"] if layer == "verify" else None,
                            page_size=100, progress=report,
                        )
                        processed += len(rows)
                        log_stage("search", since, period=period, layer=layer,
                                  page_count=max(1, (observed_total + 99) // 100), processed=len(rows))
                        token.raise_if_cancelled()
                        since = monotonic()
                        if layer == "basic":
                            rows_by_period[period] = rows
                            for start in range(0, len(rows), 500):
                                token.raise_if_cancelled()
                                self.repository.write_batch(snapshot_id, [self.mapper.from_search(item)
                                    for item in rows[start:start + 500]], period)
                        else:
                            histories = {str(row.get("key") or row.get("id")): row.get("changelog") for row in rows}
                            rows_by_period[period] = [{**row, "changelog": histories.get(str(row.get("key") or row.get("id")))}
                                                     for row in rows_by_period[period]]
                        availability[period][layer] = True
                        log_stage("persist", since, period=period, layer=layer, processed=len(rows))
                        token.raise_if_cancelled()
                        if layered:
                            since = monotonic()
                            statistics = self.statistics_builder(rows_by_period["current"], rows_by_period["previous"])
                            statistics["availability"] = {key: dict(value) for key, value in availability.items()}
                            for key, ready in availability.items():
                                if not ready["verify"]:
                                    for line in statistics.get(key, {}).get("productLines", []):
                                        for person in line.get("people", []):
                                            person.pop("verifyCount", None)
                            token.raise_if_cancelled()
                            facts = statistics.pop("_facts", None)
                            if not self.repository.update_statistics(snapshot_id, statistics, **({"facts": facts} if facts is not None else {})):
                                raise TaskCancelled()
                            log_stage("aggregate", since, period=period, layer=layer, processed=len(rows))
                if not layered:
                    statistics = self.statistics_builder(rows_by_period["current"]) if self.statistics_builder else None
                token.raise_if_cancelled()
                self.repository.activate(snapshot_id, statistics)
                outcome = "completed"
            except TaskCancelled:
                outcome = "cancelled"
                self.repository.finish(snapshot_id, "cancelled")
                raise
            except Exception as error:
                self.repository.finish(snapshot_id, "failed", getattr(error, "code", type(error).__name__))
                self.on_error(error)
                raise
            finally:
                log_stage("complete", started, processed=processed, outcome=outcome)

        task_id = self.tasks.submit(session_hash, run, card_key=self.card_key)
        self.repository.set_task(snapshot_id, task_id, session_hash=session_hash)
        return {"validation": validation, "taskId": task_id, "snapshotId": snapshot_id,
                "state": self.repository.state(session_hash, account, card_key=self.card_key)}
