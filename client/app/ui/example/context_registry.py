from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import QObject
from PySide6.QtQml import QQmlApplicationEngine

from support.logging import smart_log


def register_context_objects(
    engine: QQmlApplicationEngine,
    objects: Mapping[str, QObject],
) -> dict[str, QObject]:
    """Register and retain the single production instance of each QML context object."""
    retained = dict(objects)
    engine._context_objects = retained
    engine.destroyed.connect(retained.clear)
    context = engine.rootContext()
    for name, instance in retained.items():
        context.setContextProperty(name, instance)
    smart_log(
        "QML context objects registered (objects=%s)",
        ",".join(sorted(retained)),
        domain="ui",
        source="context_registry",
        extra={"objects": sorted(retained)},
    )
    return retained


def start_context_services(engine: QQmlApplicationEngine) -> bool:
    """Start context-owned services once, after QML has produced a root object."""
    if getattr(engine, "_context_services_started", False) or not engine.rootObjects():
        return False
    retained = getattr(engine, "_context_objects", {})
    auth = retained.get("AuthBridge")
    if auth is not None:
        auth.restoreStartupSession()
    engine._context_services_started = True
    return True
