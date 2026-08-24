from __future__ import annotations

from .filters import WifiFilters
from .queries import build_conditions, build_performance_query, transform_performance_row


class WifiDatabaseQueries:
    def __init__(self, database):
        self._database = database

    def get_filters(self, filters: WifiFilters) -> dict:
        product_lines = self._database.select(
            "SELECT DISTINCT project_type FROM project WHERE project_type IS NOT NULL ORDER BY project_type"
        )
        conditions, params = build_conditions(filters, include_base=False)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        joins = " INNER JOIN test_report tr ON tr.project_id = pr.id INNER JOIN performance p ON p.test_report_id = tr.id LEFT JOIN dut d ON d.test_report_id = tr.id"
        projects = self._database.select(
            f"SELECT DISTINCT pr.project_name AS value FROM project pr{joins}{where} ORDER BY pr.project_name", params
        )
        standards = self._database.select(
            f"SELECT DISTINCT p.wifi_mode AS value FROM project pr{joins}{where} AND p.wifi_mode IS NOT NULL ORDER BY p.wifi_mode" if where
            else f"SELECT DISTINCT p.wifi_mode AS value FROM project pr{joins} WHERE p.wifi_mode IS NOT NULL ORDER BY p.wifi_mode", params
        )
        reports = self._database.select(
            f"SELECT DISTINCT tr.report_name AS value FROM project pr{joins}{where} ORDER BY tr.report_name", params
        )
        project_values = [row["value"] for row in projects if row.get("value")]
        report_values = [row["value"] for row in reports if row.get("value")]
        return {
            "productLines": [row["project_type"] for row in product_lines],
            "brands": [], "mainChips": [], "ecosystems": [], "massProductionStatuses": [],
            "dutConnectTypes": [], "wifiModules": [], "interfaces": [],
            "projects": project_values,
            "projectOptions": [{"value": value, "label": value} for value in project_values],
            "standards": [row["value"] for row in standards if row.get("value")],
            "testReports": report_values, "reportNames": report_values,
        }

    def get_performance(self, filters: WifiFilters) -> dict:
        sql, params, applied_limit = build_performance_query(filters)
        rows = self._database.select(sql, params)
        truncated = len(rows) > applied_limit
        data = [transform_performance_row(row) for row in rows[:applied_limit]]
        throughput = [row["throughputAvgMbps"] for row in data if row["throughputAvgMbps"] is not None]
        losses = [row["pathLossDb"] for row in data if row["pathLossDb"] is not None]
        dates = [row["createdAt"] for row in data if row["createdAt"]]
        summary = {
            "count": len(data),
            "throughput": {
                "average": sum(throughput) / len(throughput) if throughput else None,
                "max": max(throughput) if throughput else None,
                "min": min(throughput) if throughput else None,
            },
            "pathLoss": {"min": min(losses) if losses else None, "max": max(losses) if losses else None},
            "lastUpdatedAt": max(dates) if dates else None,
        }
        return {
            "data": data, "summary": summary,
            "filters": {
                "productLine": filters.product_lines[0] if filters.product_lines else None,
                "productLines": filters.product_lines,
                "project": filters.projects[0] if filters.projects else None,
                "projects": filters.projects,
                "testReportCsvName": None, "testReportCsvNames": [],
                "standard": filters.standards[0] if filters.standards else None,
                "standards": filters.standards,
                "band": None, "bands": [], "bandwidthMhz": None, "bandwidthsMhz": [],
                "deviceType": None, "deviceValue": None, "deviceValues": [],
                "start": filters.start_date.isoformat() if filters.start_date else None,
                "end": filters.end_date.isoformat() if filters.end_date else None,
            },
            "metadata": {"requestedLimit": filters.limit, "appliedLimit": applied_limit,
                         "totalReturned": len(data), "truncated": truncated},
        }
