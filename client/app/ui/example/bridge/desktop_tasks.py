from core.async_tasks import AsyncTaskManager


DESKTOP_TASKS = AsyncTaskManager.from_environment()


def close_desktop_tasks() -> None:
    DESKTOP_TASKS.close()
