from __future__ import annotations

import json
import time
from uuid import uuid4

from .issue_repository import JiraIssueRepository
from .schema import initialize_jira_schema


class JiraAnalyticsRepository:
    def __init__(self, database, *, now=time.time):
        self.database, self._now = database, now
        initialize_jira_schema(database)
        self.issues = JiraIssueRepository(database)

    def begin(self, session_hash, account, jql, basic, source_filter_id, *, expires_at):
        snapshot_id = uuid4().hex
        now = self._now()
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM jira_analytics_queries WHERE expires_at<=?", (now,))
            connection.execute("""INSERT INTO jira_analytics_queries
                (session_hash,account,pending_snapshot_id,expires_at) VALUES(?,?,?,?)
                ON CONFLICT(session_hash) DO UPDATE SET account=excluded.account,
                pending_snapshot_id=excluded.pending_snapshot_id,task_id='',expires_at=excluded.expires_at""",
                (str(session_hash), str(account).casefold(), snapshot_id, float(expires_at)))
            connection.execute("""INSERT INTO jira_analytics_snapshots
                (snapshot_id,session_hash,account,jql,basic_json,source_filter_id,state,created_at)
                VALUES(?,?,?,?,?,?,?,?)""", (snapshot_id, str(session_hash), str(account).casefold(),
                str(jql), json.dumps(basic or {}, ensure_ascii=False, sort_keys=True),
                str(source_filter_id or ""), "pending", now))
        return snapshot_id

    def set_task(self, snapshot_id, task_id):
        with self.database.transaction() as connection:
            connection.execute("""UPDATE jira_analytics_queries SET task_id=?
                WHERE pending_snapshot_id=?""", (str(task_id), str(snapshot_id)))

    def write_batch(self, snapshot_id, issues):
        rows = list(issues)
        self.issues.save_core(rows)
        with self.database.transaction() as connection:
            offset = int(connection.execute(
                "SELECT count(*) FROM jira_analytics_snapshot_issues WHERE snapshot_id=?", (snapshot_id,)
            ).fetchone()[0])
            for index, issue in enumerate(rows, offset):
                connection.execute("""INSERT OR IGNORE INTO jira_analytics_snapshot_issues
                    (snapshot_id,issue_id,ordinal) VALUES(?,?,?)""",
                    (snapshot_id, issue.identity.id, index))

    def activate(self, snapshot_id):
        with self.database.transaction() as connection:
            cursor = connection.execute("""UPDATE jira_analytics_queries
                SET active_snapshot_id=?,pending_snapshot_id='',task_id=''
                WHERE pending_snapshot_id=?""", (snapshot_id, snapshot_id))
            if not cursor.rowcount:
                connection.execute("UPDATE jira_analytics_snapshots SET state='stale' WHERE snapshot_id=?", (snapshot_id,))
                return False
            connection.execute("UPDATE jira_analytics_snapshots SET state='active' WHERE snapshot_id=?", (snapshot_id,))
            return True

    def finish(self, snapshot_id, state, error=""):
        with self.database.transaction() as connection:
            connection.execute("UPDATE jira_analytics_snapshots SET state=?,error=? WHERE snapshot_id=?",
                               (str(state), str(error), str(snapshot_id)))
            connection.execute("""UPDATE jira_analytics_queries SET pending_snapshot_id='',task_id=''
                WHERE pending_snapshot_id=?""", (str(snapshot_id),))

    def state(self, session_hash, account):
        with self.database.connect() as connection:
            row = connection.execute("""SELECT active_snapshot_id,pending_snapshot_id,task_id
                FROM jira_analytics_queries WHERE session_hash=? AND account=? AND expires_at>?""",
                (str(session_hash), str(account).casefold(), self._now())).fetchone()
            if row is None:
                return {"activeSnapshotId": "", "pendingSnapshotId": "", "taskId": "", "activeJql": ""}
            active_jql = ""
            if row[0]:
                value = connection.execute("SELECT jql FROM jira_analytics_snapshots WHERE snapshot_id=?", (row[0],)).fetchone()
                active_jql = value[0] if value else ""
            return {"activeSnapshotId": row[0], "pendingSnapshotId": row[1], "taskId": row[2], "activeJql": active_jql}

    def issue_keys(self, session_hash, account):
        with self.database.connect() as connection:
            return [row[0] for row in connection.execute("""SELECT i.issue_key
                FROM jira_analytics_queries q
                JOIN jira_analytics_snapshot_issues m ON m.snapshot_id=q.active_snapshot_id
                JOIN jira_issues i ON i.issue_id=m.issue_id
                WHERE q.session_hash=? AND q.account=? AND q.expires_at>?
                ORDER BY m.ordinal""", (str(session_hash), str(account).casefold(), self._now()))]

    def delete_session(self, session_hash):
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM jira_analytics_queries WHERE session_hash=?", (str(session_hash),))

    def delete_account(self, account):
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM jira_analytics_queries WHERE account=?", (str(account).casefold(),))

    def cleanup(self):
        with self.database.transaction() as connection:
            return connection.execute("DELETE FROM jira_analytics_queries WHERE expires_at<=?", (self._now(),)).rowcount
