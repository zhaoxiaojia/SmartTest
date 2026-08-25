from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol


class QueryValues(Protocol):
    def get(self, key: str, default: str | None = None) -> str | None: ...
    def getlist(self, key: str) -> list[str]: ...


def _unique(values):
    return list(dict.fromkeys(value for value in values if value is not None))


def _strings(query: QueryValues, *keys: str) -> list[str]:
    for key in keys:
        values = [str(value).strip() for value in query.getlist(key)]
        values = [value for value in values if value]
        if values:
            return _unique(values)
    return []


def _numbers(query: QueryValues, *keys: str) -> list[float]:
    values = []
    for value in _strings(query, *keys):
        try:
            values.append(float(value))
        except ValueError:
            continue
    return _unique(values)


def _integers(query: QueryValues, *keys: str) -> list[int]:
    return _unique([int(value) for value in _numbers(query, *keys) if value.is_integer() and value > 0])


def _number(query: QueryValues, *keys: str) -> float | None:
    values = _numbers(query, *keys)
    return values[0] if values else None


def _canonical_data_type(value: str | None) -> str | None:
    normalized = (value or "").strip().upper()
    if normalized in {"PERFORMANCE", "THROUGHPUT", "PEAK THROUGHPUT", "PEAK_THROUGHPUT"}:
        return "PEAK_THROUGHPUT"
    return normalized or None


@dataclass
class WifiFilters:
    product_lines: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    project_ids: list[int] = field(default_factory=list)
    hardware_versions: list[str] = field(default_factory=list)
    wifi_modules: list[str] = field(default_factory=list)
    interfaces: list[str] = field(default_factory=list)
    standards: list[str] = field(default_factory=list)
    bands: list[str] = field(default_factory=list)
    bandwidths_mhz: list[float] = field(default_factory=list)
    data_type: str | None = None
    test_report_csv_names: list[str] = field(default_factory=list)
    report_names: list[str] = field(default_factory=list)
    device_type_raw: str | None = None
    device_column: str | None = None
    device_values: list[str] = field(default_factory=list)
    path_loss_min: float | None = None
    path_loss_max: float | None = None
    rssi_min: float | None = None
    rssi_max: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    limit: int | None = None
    test_report_limit: int = 200

    @classmethod
    def from_query(cls, query: QueryValues) -> "WifiFilters":
        def first(*keys):
            values = _strings(query, *keys)
            return values[0] if values else None

        def parsed_date(*keys):
            value = first(*keys)
            return date.fromisoformat(value) if value else None

        data_type = first("data_type", "dataType")
        device_type = first("device_type", "deviceType")
        device_values = _strings(query, "device_value", "deviceValue")
        if device_type and device_type not in {"adb_device", "ip"}:
            raise ValueError("Unsupported device type")
        if device_values and not device_type:
            raise ValueError("device_type is required with device_value")
        raw_limit = _integers(query, "limit", "max_points", "maxPoints")
        raw_report_limit = _integers(query, "test_report_limit", "testReportLimit")
        report_limit = min(max(raw_report_limit[0] if raw_report_limit else 200, 10), 1000)
        return cls(
            product_lines=_strings(query, "product_line", "productLine"),
            projects=_strings(query, "project", "project_name", "projectName"),
            project_ids=_integers(query, "project_id", "projectId"),
            hardware_versions=_strings(query, "hardware_version", "hardwareVersion"),
            wifi_modules=_strings(query, "wifi_module", "wifiModule"),
            interfaces=_strings(query, "interface"),
            standards=_strings(query, "standard"), bands=_strings(query, "band"),
            bandwidths_mhz=_numbers(query, "bandwidth_mhz", "bandwidthMhz"),
            data_type=_canonical_data_type(data_type),
            test_report_csv_names=_strings(
                query, "test_report_csv_name", "testReportCsvName", "test_report",
                "testReport", "csv_name", "csvName",
            ),
            report_names=_strings(query, "report_name", "reportName"),
            device_type_raw=device_type, device_column=device_type, device_values=device_values,
            path_loss_min=_number(query, "path_loss_min", "pathLossMin"),
            path_loss_max=_number(query, "path_loss_max", "pathLossMax"),
            rssi_min=_number(query, "rssi_min", "rssiMin"),
            rssi_max=_number(query, "rssi_max", "rssiMax"),
            start_date=parsed_date("start", "start_date", "startDate"),
            end_date=parsed_date("end", "end_date", "endDate"),
            limit=raw_limit[0] if raw_limit else None, test_report_limit=report_limit,
        )
