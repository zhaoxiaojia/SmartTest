from __future__ import annotations

from threading import RLock

from core.async_tasks import TaskCancelled
from ..task_manager import WEB_TASKS, snapshot_payload


class JiraAnalyticsTasks:
    def __init__(self, manager=WEB_TASKS):
        self.manager = manager
        self._lock = RLock()
        self._sessions = {}

    def submit(self, session_hash, runner, *, card_key=""):
        key = (str(session_hash), str(card_key))
        with self._lock:
            previous = self._sessions.get(key)
            if previous:
                self.manager.cancel(previous)
            future = self.manager.submit("jira-analytics-search", runner)
            task_id = self.manager.task_id(future)
            self._sessions[key] = task_id
            return task_id

    def status(self, session_hash, task_id, *, card_key=""):
        with self._lock:
            if self._sessions.get((str(session_hash), str(card_key))) != str(task_id):
                return None
        return {"id": str(task_id), **snapshot_payload(self.manager.snapshot(task_id))}

    def cancel(self, session_hash, task_id, *, card_key=""):
        with self._lock:
            if self._sessions.get((str(session_hash), str(card_key))) != str(task_id):
                return False
        return self.manager.cancel(str(task_id))

    def clear_session(self, session_hash):
        with self._lock:
            task_ids = [self._sessions.pop(key) for key in tuple(self._sessions) if key[0] == str(session_hash)]
        for task_id in task_ids:
            self.manager.cancel(task_id)


JIRA_ANALYTICS_TASKS = JiraAnalyticsTasks()
