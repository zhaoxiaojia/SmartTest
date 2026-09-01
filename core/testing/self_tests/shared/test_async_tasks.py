from __future__ import annotations

from threading import Event

from core.async_tasks import AsyncTaskManager, TaskCancelled


def test_manager_runs_root_with_default_global_concurrency() -> None:
    manager = AsyncTaskManager()
    try:
        task = manager.submit("root", lambda token, progress: "done")

        assert task.result(timeout=1) == "done"
        assert manager.snapshot(manager.task_id(task)).state == "completed"
        assert manager.max_workers == 16
    finally:
        manager.close()


def test_manager_cancels_root_and_child_cooperatively() -> None:
    started, release = Event(), Event()
    manager = AsyncTaskManager(max_workers=2)
    try:
        root = manager.submit("root", lambda token, progress: (release.wait(), token.raise_if_cancelled()))
        child = manager.submit_child(manager.task_id(root), "child", lambda token, progress: (
            started.set(), release.wait(), token.raise_if_cancelled(), "never"
        )[-1])
        assert started.wait(1)

        assert manager.cancel(manager.task_id(root))
        release.set()
        try:
            child.result(timeout=1)
        except TaskCancelled:
            pass
        else:
            raise AssertionError("child cancellation was not delivered")
        assert manager.snapshot(manager.task_id(root)).state == "cancelled"
    finally:
        manager.close()


def test_manager_delays_child_visibility_and_coalesces_progress() -> None:
    now = [0.0]
    manager = AsyncTaskManager(max_workers=1, clock=lambda: now[0])
    try:
        root = manager.submit("root", lambda token, progress: "done")
        root.result(timeout=1)
        release, started = Event(), Event()
        child = manager.submit_child(manager.task_id(root), "child", lambda token, progress: (started.set(), release.wait())[-1])
        assert started.wait(1)

        assert manager.snapshot(manager.task_id(root)).visible_child is None
        now[0] = 2.0
        assert manager.snapshot(manager.task_id(root)).visible_child.id == manager.task_id(child)
        release.set(); child.result(timeout=1)
        assert manager.snapshot(manager.task_id(root)).visible_child is None

        updates = []
        task = manager.submit("progress", lambda token, progress: (progress(1, 10), progress(2, 10), "done")[-1])
        task.result(timeout=1)
        updates.append(manager.snapshot(manager.task_id(task)).progress)
        assert updates == [(10, 10)]
    finally:
        manager.close()


def test_manager_reads_validated_visibility_and_progress_intervals(monkeypatch) -> None:
    monkeypatch.setenv("SMARTTEST_ASYNC_MAX_CONCURRENCY", "3")
    monkeypatch.setenv("SMARTTEST_ASYNC_TASK_CHILD_VISIBILITY_SECONDS", "3")
    monkeypatch.setenv("SMARTTEST_ASYNC_TASK_PROGRESS_COALESCE_SECONDS", "0.5")

    manager = AsyncTaskManager.from_environment()
    try:
        assert manager.max_workers == 3
        assert manager.child_visibility_seconds == 3
        assert manager.progress_coalesce_seconds == 0.5
    finally:
        manager.close()


def test_child_snapshot_never_recurses_to_its_running_root() -> None:
    started, release = Event(), Event()
    manager = AsyncTaskManager(max_workers=2, child_visibility_seconds=0)
    try:
        root = manager.submit("root", lambda token, progress: release.wait())
        child = manager.submit_child(manager.task_id(root), "child", lambda token, progress: (started.set(), release.wait())[-1])
        assert started.wait(1)

        assert manager.snapshot(manager.task_id(root)).visible_child.id == manager.task_id(child)
        assert manager.snapshot(manager.task_id(child)).visible_child is None
        release.set(); root.result(timeout=1); child.result(timeout=1)
    finally:
        manager.close()


def test_manager_publishes_coalesced_snapshot_revisions() -> None:
    updates = []
    manager = AsyncTaskManager()
    try:
        unsubscribe = manager.subscribe(updates.append)
        task = manager.submit("root", lambda token, progress: (progress(1, 2), "done")[-1])
        task.result(timeout=1)
        unsubscribe()

        assert updates[-1].id == manager.task_id(task)
        assert updates[-1].revision > 0
    finally:
        manager.close()


def test_long_running_task_reports_state_and_delegates_cancellation():
    from core.async_tasks import AsyncTaskManager
    calls=[]; manager=AsyncTaskManager(max_workers=1)
    task_id=manager.register_long_running("camera", lambda: calls.append("stop"))
    assert manager.snapshot(task_id).state == "running"
    assert manager.cancel(task_id)
    assert calls == ["stop"]
    manager.complete_long_running(task_id)
    assert manager.snapshot(task_id).state == "completed"
    manager.close()


def test_close_cancels_registered_long_running_task():
    from core.async_tasks import AsyncTaskManager
    calls=[]; manager=AsyncTaskManager(max_workers=1)
    manager.register_long_running("run", lambda: calls.append("stop"))
    manager.close()
    assert calls == ["stop"]


def test_coordinator_root_does_not_consume_child_worker_capacity() -> None:
    from threading import Barrier

    release = Event()
    barrier = Barrier(3, timeout=1)
    manager = AsyncTaskManager(max_workers=3)
    try:
        root = manager.submit_coordinator("review", lambda _token, _progress: release.wait(1))
        root_id = manager.task_id(root)
        children = [
            manager.submit_child(root_id, "detail", lambda _token, _progress: barrier.wait())
            for _ in range(3)
        ]
        for child in children:
            child.result(timeout=2)
        release.set()
        root.result(timeout=2)
    finally:
        release.set()
        manager.close()


def test_cancelled_root_rejects_late_child_without_running_it() -> None:
    manager = AsyncTaskManager(max_workers=1)
    calls = []
    try:
        root = manager.register_long_running("review")
        manager.cancel(root)
        child = manager.submit_child(root, "detail", lambda _token, _progress: calls.append("network"))

        assert child.cancelled()
        assert calls == []
        assert manager.snapshot(manager.task_id(child)).state == "cancelled"
    finally:
        manager.close()
