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
