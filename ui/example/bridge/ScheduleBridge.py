from __future__ import annotations

from PySide6.QtCore import QObject, Property, Signal, Slot


class ScheduleBridge(QObject):
    rowsChanged = Signal()
    toolOpenRequested = Signal(str)

    def __init__(self, providers: dict[str, QObject]):
        super().__init__()
        self._providers = dict(providers)
        for provider in self._providers.values():
            provider.scheduleRowsChanged.connect(self.rowsChanged)

    @Property("QVariantList", notify=rowsChanged)
    def rows(self):
        return [
            dict(row)
            for provider in self._providers.values()
            for row in provider.scheduleRows
            if row.get("enabled")
        ]

    @Slot()
    def refresh(self):
        for provider in self._providers.values():
            provider.refreshPlans()

    @Slot(str, str, bool)
    def setPlanEnabled(self, provider_id, plan_id, enabled):
        provider = self._providers.get(str(provider_id))
        if provider is not None:
            provider.setPlanEnabled(str(plan_id), bool(enabled))

    @Slot(str, str)
    def openPlan(self, provider_id, plan_id):
        identity = (str(provider_id), str(plan_id))
        row = next(
            (
                row for row in self.rows
                if (row.get("provider"), row.get("planId")) == identity
            ),
            None,
        )
        if row is not None:
            self.toolOpenRequested.emit(str(row["targetToolId"]))


__all__ = ["ScheduleBridge"]
