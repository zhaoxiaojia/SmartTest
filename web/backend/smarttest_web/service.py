from __future__ import annotations

from .filters import WifiFilters
from .queries import (
    build_conditions,
    build_performance_query,
    build_test_report_conditions,
    transform_performance_row,
)


class WifiDatabaseQueries:
    def __init__(self, database):
        self._database = database

    def get_filters(self, filters: WifiFilters) -> dict:
        product_lines = self._database.select(
            "SELECT DISTINCT project_type FROM project WHERE project_type IS NOT NULL ORDER BY project_type"
        )
        joins = " INNER JOIN test_report tr ON tr.project_id = pr.id INNER JOIN performance p ON p.test_report_id = tr.id LEFT JOIN dut d ON d.test_report_id = tr.id"
        project_conditions, project_params, project_needs_performance = build_test_report_conditions(filters, exclude={"project"})
        project_joins = " INNER JOIN test_report tr ON tr.project_id = pr.id LEFT JOIN dut d ON d.test_report_id = tr.id"
        if project_needs_performance:
            project_joins += " INNER JOIN performance p ON p.test_report_id = tr.id"
        project_conditions = ["pr.project_name IS NOT NULL", "pr.project_name <> ''", *project_conditions]
        project_where = " WHERE " + " AND ".join(project_conditions)
        projects = self._database.select(
            f"SELECT DISTINCT pr.project_name AS value FROM project pr{project_joins}{project_where} ORDER BY pr.project_name",
            project_params,
        )
        standard_conditions, standard_params = build_conditions(filters, include_base=False, exclude={"standard"})
        standard_where = " WHERE " + " AND ".join(standard_conditions) if standard_conditions else ""
        standards = self._database.select(
            f"SELECT DISTINCT p.wifi_mode AS value FROM project pr{joins}{standard_where}"
            + (" AND" if standard_where else " WHERE")
            + " p.wifi_mode IS NOT NULL ORDER BY p.wifi_mode",
            standard_params,
        )
        report_conditions, report_params, report_needs_performance = build_test_report_conditions(filters, exclude={"report"})
        report_joins = " INNER JOIN test_report tr ON tr.project_id = pr.id LEFT JOIN dut d ON d.test_report_id = tr.id"
        if report_needs_performance:
            report_joins += " INNER JOIN performance p ON p.test_report_id = tr.id"
        report_where = " WHERE " + " AND ".join(report_conditions) if report_conditions else ""
        report_limit_params = [*report_params, filters.test_report_limit]
        csv_reports = self._database.select(
            f"SELECT t.value FROM (SELECT tr.csv_name AS value, MAX(tr.id) AS max_id FROM project pr{report_joins}{report_where}"
            + (" AND" if report_where else " WHERE")
            + " tr.csv_name IS NOT NULL GROUP BY tr.csv_name ORDER BY max_id DESC LIMIT %s) t ORDER BY t.value",
            report_limit_params,
        )
        named_reports = self._database.select(
            f"SELECT t.value FROM (SELECT tr.report_name AS value, MAX(tr.id) AS max_id FROM project pr{report_joins}{report_where}"
            + (" AND" if report_where else " WHERE")
            + " tr.report_name IS NOT NULL GROUP BY tr.report_name ORDER BY max_id DESC LIMIT %s) t ORDER BY t.value",
            report_limit_params,
        )
        wifi_modules = self._database.select(
            "SELECT DISTINCT wifi_module AS value FROM project WHERE wifi_module IS NOT NULL ORDER BY wifi_module"
        )
        interfaces = self._database.select(
            "SELECT DISTINCT interface AS value FROM project WHERE interface IS NOT NULL ORDER BY interface"
        )
        brands = self._database.select(
            "SELECT DISTINCT customer AS value FROM project WHERE customer IS NOT NULL ORDER BY customer"
        )
        main_chips = self._database.select(
            "SELECT DISTINCT soc AS value FROM project WHERE soc IS NOT NULL ORDER BY soc"
        )
        ecosystems = self._database.select(
            "SELECT DISTINCT ecosystem AS value FROM project WHERE ecosystem IS NOT NULL ORDER BY ecosystem"
        )
        project_values = [row["value"] for row in projects if row.get("value")]
        csv_values = [row["value"] for row in csv_reports if row.get("value")]
        report_values = [row["value"] for row in named_reports if row.get("value")]
        return {
            "productLines": [row["project_type"] for row in product_lines],
            "brands": [row["value"] for row in brands if row.get("value")],
            "mainChips": [row["value"] for row in main_chips if row.get("value")],
            "ecosystems": [row["value"] for row in ecosystems if row.get("value")],
            "massProductionStatuses": [],
            "dutConnectTypes": [],
            "wifiModules": [row["value"] for row in wifi_modules if row.get("value")],
            "interfaces": [row["value"] for row in interfaces if row.get("value")],
            "projects": project_values,
            "projectOptions": [{"value": value, "label": value} for value in project_values],
            "standards": [row["value"] for row in standards if row.get("value")],
            "testReports": csv_values, "reportNames": report_values,
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
                "testReportCsvName": filters.test_report_csv_names[0] if filters.test_report_csv_names else None,
                "testReportCsvNames": filters.test_report_csv_names,
                "reportNames": filters.report_names,
                "standard": filters.standards[0] if filters.standards else None,
                "standards": filters.standards,
                "band": filters.bands[0] if filters.bands else None, "bands": filters.bands,
                "bandwidthMhz": filters.bandwidths_mhz[0] if filters.bandwidths_mhz else None,
                "bandwidthsMhz": filters.bandwidths_mhz,
                "deviceType": filters.device_type_raw,
                "deviceValue": filters.device_values[0] if filters.device_values else None,
                "deviceValues": filters.device_values,
                "start": filters.start_date.isoformat() if filters.start_date else None,
                "end": filters.end_date.isoformat() if filters.end_date else None,
            },
            "metadata": {"requestedLimit": filters.limit, "appliedLimit": applied_limit,
                         "totalReturned": len(data), "truncated": truncated},
        }
