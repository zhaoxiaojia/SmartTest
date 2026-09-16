from __future__ import annotations

import time
from threading import RLock
from uuid import uuid4

from core.jira.services.team_bug_service import aggregate_team_bugs, load_fae_qa_roster, team_bug_jql
from ..task_manager import WEB_TASKS, snapshot_payload
from .schema import initialize_jira_schema


class JiraTeamBugDashboardRepository:
    def __init__(self, database, *, now=time.time):
        self.database, self._now = database, now
        initialize_jira_schema(database)

    @staticmethod
    def _account(account): return str(account).strip().casefold()

    def read(self, account, roster_fingerprint):
        with self.database.connect() as connection:
            head = connection.execute(
                "SELECT active_snapshot_id,last_error FROM jira_team_bug_accounts WHERE account=?",
                (self._account(account),),
            ).fetchone()
            if not head or not head[0]:
                return None
            total = connection.execute(
                "SELECT team_total FROM jira_team_bug_snapshots WHERE snapshot_id=? AND roster_fingerprint=?",
                (head[0], str(roster_fingerprint)),
            ).fetchone()
            if not total:
                return None
            lines = connection.execute("""SELECT product_line FROM jira_team_bug_lines
                WHERE snapshot_id=? ORDER BY ordinal""", (head[0],)).fetchall()
            rows = connection.execute("""SELECT product_line,identity,display_name,bug_count,
                resolved_count,p0_count,invalid_count FROM jira_team_bug_rows
                WHERE snapshot_id=? ORDER BY product_line,ordinal""", (head[0],)).fetchall()
        keys = ("identity", "displayName", "bugCount", "resolvedCount", "p0Count", "invalidCount")
        line_names = [row[0] for row in lines]
        by_line = {line: [] for line in line_names}
        for line, *values in rows:
            by_line.setdefault(line, []).append(dict(zip(keys, values)))
        result = {"teamTotal": int(total[0]), "productLines": [
            {"id": line, "label": line, "people": by_line.get(line, [])}
            for line in line_names
        ]}
        return result

    def replace(self, account, roster_fingerprint, result):
        account, snapshot_id = self._account(account), uuid4().hex
        with self.database.transaction() as connection:
            previous = connection.execute(
                "SELECT active_snapshot_id FROM jira_team_bug_accounts WHERE account=?", (account,),
            ).fetchone()
            connection.execute("""INSERT INTO jira_team_bug_snapshots
                (snapshot_id,account,roster_fingerprint,team_total,created_at) VALUES(?,?,?,?,?)""",
                (snapshot_id, account, str(roster_fingerprint), int(result["teamTotal"]), self._now()))
            connection.executemany("""INSERT INTO jira_team_bug_lines
                (snapshot_id,ordinal,product_line,project_key) VALUES(?,?,?,?)""", [
                (snapshot_id, index, line["id"], line["id"])
                for index, line in enumerate(result["productLines"])
            ])
            connection.executemany("""INSERT INTO jira_team_bug_rows VALUES(
                ?,?,?,?,?,?,?,?,?)""", [(
                    snapshot_id, line["id"], index, row["identity"], row["displayName"],
                    row["bugCount"], row["resolvedCount"], row["p0Count"], row["invalidCount"],
                ) for line in result["productLines"] for index, row in enumerate(line["people"])])
            connection.execute("""INSERT INTO jira_team_bug_accounts
                (account,active_snapshot_id,last_error,roster_fingerprint) VALUES(?,?, '',?)
                ON CONFLICT(account) DO UPDATE SET active_snapshot_id=excluded.active_snapshot_id,
                last_error='',roster_fingerprint=excluded.roster_fingerprint""",
                (account, snapshot_id, str(roster_fingerprint)))
            if previous and previous[0] and previous[0] != snapshot_id:
                connection.execute("DELETE FROM jira_team_bug_snapshots WHERE snapshot_id=?", (previous[0],))

    def record_failure(self, account, roster_fingerprint, error):
        with self.database.transaction() as connection:
            connection.execute("""INSERT INTO jira_team_bug_accounts(account,last_error,roster_fingerprint)
                VALUES(?,?,?) ON CONFLICT(account) DO UPDATE SET
                last_error=excluded.last_error,roster_fingerprint=excluded.roster_fingerprint""",
                (self._account(account), str(error), str(roster_fingerprint)))

    def error(self, account, roster_fingerprint):
        with self.database.connect() as connection:
            row = connection.execute("""SELECT last_error FROM jira_team_bug_accounts
                WHERE account=? AND roster_fingerprint=?""",
                (self._account(account), str(roster_fingerprint))).fetchone()
        return str(row[0]) if row and row[0] else ""

    def delete_account(self, account):
        account = self._account(account)
        with self.database.transaction() as connection:
            ids = [row[0] for row in connection.execute(
                "SELECT snapshot_id FROM jira_team_bug_snapshots WHERE account=?", (account,))]
            connection.execute("DELETE FROM jira_team_bug_accounts WHERE account=?", (account,))
            connection.executemany("DELETE FROM jira_team_bug_snapshots WHERE snapshot_id=?", ((item,) for item in ids))


class JiraTeamBugTasks:
    def __init__(self, manager=WEB_TASKS):
        self.manager, self._lock, self._accounts = manager, RLock(), {}

    def submit_once(self, account, fingerprint, runner):
        account, fingerprint = str(account).casefold(), str(fingerprint)
        with self._lock:
            previous = self._accounts.get(account)
            if previous and previous[0] == fingerprint and self.manager.snapshot(previous[1]).state in {"queued", "running"}:
                return previous[1]
            if previous and self.manager.snapshot(previous[1]).state in {"queued", "running"}:
                self.manager.cancel(previous[1])
            future = self.manager.submit("jira-team-bugs", runner)
            task_id = self.manager.task_id(future)
            self._accounts[account] = (fingerprint, task_id)
            return task_id

    def status(self, account, fingerprint):
        with self._lock:
            current = self._accounts.get(str(account).casefold())
            task_id = current[1] if current and current[0] == str(fingerprint) else None
        return None if not task_id else {"id": task_id, **snapshot_payload(self.manager.snapshot(task_id))}

    def publish_if_current(self, account, fingerprint, publish):
        account, fingerprint = str(account).casefold(), str(fingerprint)
        with self._lock:
            current = self._accounts.get(account)
            if current is None or current[0] != fingerprint:
                return False
            publish()
            return True

    def clear_account(self, account):
        with self._lock:
            current = self._accounts.pop(str(account).casefold(), None)
            task_id = current[1] if current else None
        if task_id: self.manager.cancel(task_id)


class JiraTeamBugDashboardService:
    FIELDS = ["project", "issuetype", "assignee", "priority", "resolution"]

    def __init__(self, repository, gateway_factory, tasks, roster_owner=load_fae_qa_roster):
        self.repository, self.gateway_factory, self.tasks = repository, gateway_factory, tasks
        self.roster_owner = roster_owner

    def state(self, account, password, *, on_error=lambda _error: None):
        roster = self.roster_owner()
        snapshot = self.repository.read(account, roster.fingerprint)
        if snapshot is not None: return {"state": "ready", **snapshot}
        existing = self.tasks.status(account, roster.fingerprint)
        if existing is not None:
            error = self.repository.error(account, roster.fingerprint)
            return {"state": "failed" if existing["state"] == "failed" else "loading",
                    "task": existing, "error": error}
        error = self.repository.error(account, roster.fingerprint)
        if error:
            return {"state": "failed", "task": None, "error": error}

        def run(token, progress):
            try:
                if token: token.raise_if_cancelled()
                rows = self.gateway_factory(account, password).search_all_payloads(
                    team_bug_jql(roster.accounts), fields=self.FIELDS, progress=progress,
                )
                if token: token.raise_if_cancelled()
                result = aggregate_team_bugs(rows, roster).to_payload()
                self.tasks.publish_if_current(
                    account, roster.fingerprint,
                    lambda: self.repository.replace(account, roster.fingerprint, result),
                )
            except Exception as error:
                self.repository.record_failure(
                    account, roster.fingerprint, getattr(error, "code", type(error).__name__),
                )
                on_error(error)
                raise

        task_id = self.tasks.submit_once(account, roster.fingerprint, run)
        task = self.tasks.status(account, roster.fingerprint) or {"id": task_id, "state": "queued", "progress": {"processed": 0, "total": 0}}
        return {"state": "failed" if task["state"] == "failed" else "loading",
                "task": task, "error": self.repository.error(account, roster.fingerprint)}
