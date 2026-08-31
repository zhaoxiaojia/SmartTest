from __future__ import annotations

from PySide6.QtCore import QDateTime, QObject, Property, Signal, Slot, Qt


class ScheduleBridge(QObject):
    rowsChanged = Signal()

    def __init__(self, providers: dict[str, QObject]):
        super().__init__()
        self._providers = dict(providers)
        for provider in self._providers.values():
            provider.scheduleRowsChanged.connect(self.rowsChanged)

    @Property("QVariantList", notify=rowsChanged)
    def rows(self):
        return [
            self._display_row(row)
            for provider in self._providers.values()
            for row in provider.scheduleRows
        ]

    @Slot()
    def refresh(self):
        for provider in self._providers.values():
            provider.refreshPlans()

    @Slot(str, str, bool)
    def setPlanEnabled(self, provider_id, plan_id, enabled):
        provider = self._providers.get(str(provider_id))
        if provider is not None and hasattr(provider, "setPlanEnabled"):
            provider.setPlanEnabled(str(plan_id), bool(enabled))

    @Slot(str, str)
    def runNow(self, provider_id, plan_id):
        provider = self._providers.get(str(provider_id))
        if provider is not None and hasattr(provider, "runPlanNow"):
            provider.runPlanNow(str(plan_id))

    @Slot(str, str)
    def deletePlan(self, provider_id, plan_id):
        provider = self._providers.get(str(provider_id))
        if provider is not None and hasattr(provider, "deletePlan"):
            provider.deletePlan(str(plan_id))

    def _display_row(self, source):
        row = dict(source)
        row.setdefault("manageable", False)
        row.setdefault("operationRunning", False)
        row.setdefault("operationText", "")
        row.setdefault("taskTypeText", "")
        row.setdefault("contentText", "")
        row.setdefault("planText", "")
        if not row.get("enabled"):
            status = self.tr("Disabled")
        elif not row.get("registered"):
            status = self.tr("Not registered")
        elif row.get("reconciliation") == "ok":
            status = self.tr("Ready")
        else:
            status = self.tr("Needs attention")
        row["statusText"] = status
        row["nextRunText"] = self._next_run_text(row.get("nextRunAt"))
        return row

    def _next_run_text(self, value):
        if not value:
            return self.tr("Next run unavailable")
        parsed = QDateTime.fromString(str(value), Qt.DateFormat.ISODate)
        if not parsed.isValid():
            return self.tr("Next run unavailable")
        return self.tr("Next run: {time}").format(
            time=parsed.toString("yyyy-MM-dd HH:mm")
        )


__all__ = ["ScheduleBridge"]
