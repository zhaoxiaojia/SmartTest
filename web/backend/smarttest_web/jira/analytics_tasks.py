from __future__ import annotations

from ..task_manager import WEB_TASKS, ScopedTaskIndex, snapshot_payload


class JiraAnalyticsTasks:
    def __init__(self, manager=WEB_TASKS):
        self.manager = manager
        self._index = ScopedTaskIndex(manager)

    def submit(self, session_hash, runner, *, card_key=""):
        key = (str(session_hash), str(card_key))
        future = self.manager.submit("jira-analytics-search", runner)
        task_id = self.manager.task_id(future)
        self._index.replace(key, task_id)
        return task_id

    def status(self, session_hash, task_id, *, card_key=""):
        if not self._index.owns((session_hash, card_key), task_id):
            return None
        return {"id": str(task_id), **snapshot_payload(self.manager.snapshot(task_id))}

    def cancel(self, session_hash, task_id, *, card_key=""):
        if not self._index.owns((session_hash, card_key), task_id):
            return False
        return self.manager.cancel(str(task_id))

    def clear_session(self, session_hash):
        self._index.clear_prefix(session_hash)


JIRA_ANALYTICS_TASKS = JiraAnalyticsTasks()
