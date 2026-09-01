from core.async_tasks import AsyncTaskManager


def snapshot_payload(snapshot):
    """Return the safe root-task fields used by existing Confluence status responses."""
    child = snapshot.visible_child
    return {
        "state": snapshot.state,
        "progress": {"processed": snapshot.progress[0], "total": snapshot.progress[1]},
        "revision": snapshot.revision,
        "visibleChild": None if child is None else {"label": child.label, "state": child.state},
    }


WEB_TASKS = AsyncTaskManager.from_environment()


def close_web_tasks() -> None:
    WEB_TASKS.close()
