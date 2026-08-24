from __future__ import annotations

import re
from datetime import datetime, time, timezone
from typing import Any

from .filters import WifiFilters


_WRITE_TOKEN = re.compile(r"\b(?:INSERT|UPDATE|DELETE|REPLACE|ALTER|CREATE|DROP|TRUNCATE|CALL|GRANT|REVOKE|LOAD|LOCK|UNLOCK)\b", re.I)


def ensure_readonly_sql(sql: str) -> None:
    normalized = sql.strip()
    if not re.match(r"^(?:SELECT|WITH)\b", normalized, re.I) or ";" in normalized or _WRITE_TOKEN.search(normalized):
        raise ValueError("Only one read-only SELECT/WITH statement is allowed")


def _add_values(conditions: list[str], params: list[Any], column: str, values: list[Any]) -> None:
    if not values:
        return
    if len(values) == 1:
        conditions.append(f"{column} = %s")
    else:
        conditions.append(f"{column} IN ({', '.join('%s' for _ in values)})")
    params.extend(values)


def _add_report_names(conditions: list[str], params: list[Any], values: list[str]) -> None:
    if not values:
        return
    pieces = []
    for value in values:
        pieces.append("(tr.report_name = %s OR tr.csv_name = %s OR COALESCE(tr.report_name, tr.csv_name, '') = %s)")
        params.extend((value, value, value))
    conditions.append(f"({' OR '.join(pieces)})")


def build_conditions(filters: WifiFilters, *, include_base: bool = True) -> tuple[list[str], list[Any]]:
    conditions: list[str] = []
    params: list[Any] = []
    if include_base:
        conditions.append("COALESCE(p.throughput_avg_mbps, p.throughput_peak_mbps, kv.throughput_mbps) IS NOT NULL")
        if filters.data_type == "RVR":
            conditions.insert(0, "p.attenuation IS NOT NULL")
        elif filters.data_type == "RVO":
            conditions.append("p.angle IS NOT NULL")
    _add_values(conditions, params, "pr.project_type", filters.product_lines)
    _add_values(conditions, params, "pr.project_name", filters.projects)
    _add_values(conditions, params, "p.wifi_mode", filters.standards)
    if filters.data_type == "PEAK_THROUGHPUT":
        conditions.append("(UPPER(COALESCE(tr.report_name, tr.csv_name, '')) LIKE 'PERFORMANCE%' OR UPPER(COALESCE(tr.report_type, '')) LIKE 'PEAK%')")
    elif filters.data_type in {"RVR", "RVO"}:
        conditions.append(f"UPPER(COALESCE(tr.report_name, tr.csv_name, '')) LIKE '{filters.data_type}%'")
    _add_report_names(conditions, params, filters.report_names)
    if filters.start_date:
        conditions.append("p.created_at >= %s")
        params.append(datetime.combine(filters.start_date, time.min))
    if filters.end_date:
        conditions.append("p.created_at <= %s")
        params.append(datetime.combine(filters.end_date, time.max))
    return conditions, params


_PERFORMANCE_SELECT = """
SELECT p.attenuation,
  COALESCE(p.throughput_avg_mbps, p.throughput_peak_mbps, kv.throughput_mbps) AS throughput_value_mbps,
  p.throughput_avg_mbps, p.throughput_peak_mbps, p.created_at, p.test_report_id,
  p.scenario_group_key, p.band, p.bandwidth_mhz, p.wifi_mode, p.direction, p.channel, p.angle,
  p.test_category, p.protocol, tr.csv_name, tr.report_type, tr.report_name, tr.case_path,
  tr.project_id, pr.customer, pr.nickname AS project_nickname, pr.project_type, pr.project_name,
  d.adb_device, d.ip
FROM performance p
INNER JOIN test_report tr ON tr.id = p.test_report_id
INNER JOIN project pr ON pr.id = tr.project_id
LEFT JOIN dut d ON d.test_report_id = tr.id
LEFT JOIN (SELECT test_report_id, AVG(metric_value) AS throughput_mbps FROM perf_metric_kv
  WHERE metric_name = 'throughput' GROUP BY test_report_id) kv ON kv.test_report_id = p.test_report_id
"""


def build_performance_query(filters: WifiFilters, *, default_limit: int = 1000, max_limit: int = 5000):
    conditions, params = build_conditions(filters)
    applied_limit = min(filters.limit or default_limit, max_limit)
    sql = _PERFORMANCE_SELECT
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY p.attenuation ASC, p.created_at ASC, p.id ASC LIMIT %s"
    params.append(applied_limit + 1)
    return sql, params, applied_limit


def _number(value):
    return float(value) if value is not None else None


def _iso(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat().replace("+00:00", "Z")
    return str(value)


def transform_performance_row(row: dict[str, Any]) -> dict[str, Any]:
    source = "throughput_avg_mbps" if row.get("throughput_avg_mbps") is not None else (
        "throughput_peak_mbps" if row.get("throughput_peak_mbps") is not None else "perf_metric_kv"
    )
    mapping = {
        "pathLossDb": _number(row.get("attenuation")), "throughputAvgMbps": _number(row.get("throughput_value_mbps")),
        "throughputSource": source, "createdAt": _iso(row.get("created_at")),
        "executionId": row.get("test_report_id"), "testReportId": row.get("test_report_id"),
        "scenarioGroupKey": row.get("scenario_group_key"), "band": row.get("band"),
        "bandwidthMhz": _number(row.get("bandwidth_mhz")), "standard": row.get("wifi_mode"),
        "direction": row.get("direction"), "centerFreqMhz": _number(row.get("channel")),
        "angleDeg": _number(row.get("angle")), "testCategory": row.get("test_category"),
        "protocol": row.get("protocol"), "csvName": row.get("csv_name"), "dataType": row.get("report_type"),
        "reportName": row.get("report_name"), "casePath": row.get("case_path"), "projectId": row.get("project_id"),
        "brand": row.get("customer"), "productLine": row.get("project_type"),
        "projectNickname": row.get("project_nickname"), "project": row.get("project_name"),
        "adbDevice": row.get("adb_device"), "telnetIp": row.get("ip"),
    }
    return mapping
