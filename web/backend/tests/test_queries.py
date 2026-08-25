from datetime import date, datetime, time

import pytest

from smarttest_web.config import ConfigurationError, DatabaseSettings
from smarttest_web.filters import WifiFilters
from smarttest_web.queries import build_performance_query, ensure_readonly_sql, transform_performance_row
from smarttest_web.service import WifiDatabaseQueries


def test_performance_sql_preserves_condition_and_parameter_order():
    filters = WifiFilters(
        product_lines=["Consumer", "Enterprise"], projects=["Apollo"],
        report_names=["Performance-1"], standards=["802.11be"],
        data_type="PEAK_THROUGHPUT", start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 24), limit=25,
    )
    sql, params, applied_limit = build_performance_query(filters, max_limit=5000)
    assert "pr.project_type IN (%s, %s)" in sql
    assert "pr.project_name = %s" in sql
    assert "p.wifi_mode = %s" in sql
    assert "UPPER(COALESCE(tr.report_name, tr.csv_name, '')) LIKE 'PERFORMANCE%'" in sql
    assert params == ["Consumer", "Enterprise", "Apollo", "802.11be",
                      "Performance-1", "Performance-1", "Performance-1",
                      datetime.combine(date(2026, 8, 1), time.min),
                      datetime.combine(date(2026, 8, 24), time.max), 26]
    assert applied_limit == 25


@pytest.mark.parametrize("sql", [
    "UPDATE performance SET attenuation=0", "DELETE FROM performance",
    "SELECT 1; SELECT 2", "WITH changed AS (DELETE FROM performance RETURNING *) SELECT * FROM changed",
])
def test_readonly_guard_rejects_writes_and_multiple_statements(sql):
    with pytest.raises(ValueError, match="read-only"):
        ensure_readonly_sql(sql)


def test_readonly_guard_allows_select_and_readonly_cte():
    ensure_readonly_sql("SELECT id FROM performance WHERE id = %s")
    ensure_readonly_sql("WITH recent AS (SELECT id FROM performance) SELECT * FROM recent")


def test_missing_password_has_explicit_configuration_boundary():
    with pytest.raises(ConfigurationError, match="WIFI_DB_PASSWORD"):
        DatabaseSettings.from_environment({"WIFI_DB_HOST": "db", "WIFI_DB_USER": "reader", "WIFI_DB_NAME": "wifi_test"})


def test_row_conversion_keeps_legacy_camel_case_contract():
    row = {"attenuation": "10.5", "throughput_value_mbps": "900.25", "throughput_avg_mbps": None,
           "throughput_peak_mbps": "900.25", "created_at": None, "test_report_id": 7,
           "scenario_group_key": "BAND=5G", "band": "5G", "bandwidth_mhz": 80,
           "wifi_mode": "802.11be", "direction": "tx", "channel": 5210, "angle": None,
           "report_name": "Performance-1", "project_name": "Apollo"}
    converted = transform_performance_row(row)
    assert converted["pathLossDb"] == 10.5
    assert converted["throughputAvgMbps"] == 900.25
    assert converted["throughputSource"] == "throughput_peak_mbps"
    assert converted["scenarioGroupKey"] == "BAND=5G"
    assert converted["reportName"] == "Performance-1"


def test_advanced_performance_conditions_keep_whitelisted_columns_and_parameter_order():
    filters = WifiFilters(
        project_ids=[9], wifi_modules=["W2"], interfaces=["SDIO"], bands=["5G"],
        bandwidths_mhz=[80.0], test_report_csv_names=["RVR-a.csv"],
        device_column="ip", device_values=["192.0.2.1"], data_type="RVR",
        path_loss_min=5.0, path_loss_max=80.0, rssi_min=-90.0, rssi_max=-20.0,
    )
    sql, params, _ = build_performance_query(filters)
    assert "pr.id = %s" in sql
    assert "pr.wifi_module = %s" in sql
    assert "pr.interface = %s" in sql
    assert "d.ip = %s" in sql
    assert "p.band = %s" in sql
    assert "p.bandwidth_mhz = %s" in sql
    assert "p.attenuation >= %s" in sql and "p.rssi <= %s" in sql
    assert "LIKE 'RVR%'" in sql
    assert params[:-1] == [9, "W2", "SDIO", "192.0.2.1", "5G", 80.0,
                           5.0, 80.0, -90.0, -20.0,
                           "RVR-a.csv", "RVR-a.csv", "RVR-a.csv"]


class RecordingDatabase:
    def __init__(self):
        self.calls = []

    def select(self, sql, params=()):
        self.calls.append((sql, list(params)))
        if "project_type FROM project" in sql:
            return [{"project_type": "Consumer"}]
        if "wifi_module AS value" in sql:
            return [{"value": "W2"}]
        if "project_name AS value" in sql:
            return [{"value": "Apollo"}]
        if "wifi_mode AS value" in sql:
            return [{"value": "802.11be"}]
        if "csv_name AS value" in sql:
            return [{"value": "raw.csv"}]
        if "report_name AS value" in sql:
            return [{"value": "Performance-1"}]
        return []


def test_filter_facets_exclude_their_own_selection_and_return_full_contract():
    database = RecordingDatabase()
    payload = WifiDatabaseQueries(database).get_filters(WifiFilters(
        projects=["Apollo"], standards=["802.11be"], report_names=["Performance-1"],
        data_type="PEAK_THROUGHPUT",
    ))
    project_sql = next(sql for sql, _ in database.calls if "project_name AS value" in sql)
    standard_sql = next(sql for sql, _ in database.calls if "wifi_mode AS value" in sql)
    report_sql = next(sql for sql, _ in database.calls if "report_name AS value" in sql)
    assert "pr.project_name = %s" not in project_sql
    assert "p.wifi_mode = %s" not in standard_sql
    assert "tr.report_name = %s" not in report_sql
    assert payload["wifiModules"] == ["W2"]
    assert payload["testReports"] == ["raw.csv"]
    assert payload["reportNames"] == ["Performance-1"]
