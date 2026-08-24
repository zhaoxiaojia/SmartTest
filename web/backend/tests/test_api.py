from fastapi.testclient import TestClient

from smarttest_web.app import create_app


class RecordingOwner:
    def __init__(self):
        self.filters_arg = None
        self.performance_arg = None

    def get_filters(self, filters):
        self.filters_arg = filters
        return {
            "productLines": ["Consumer"], "projects": ["Apollo"],
            "projectOptions": [{"value": "Apollo", "label": "Apollo"}],
            "standards": ["802.11be"], "testReports": ["raw.csv"],
            "reportNames": ["Performance-1"], "brands": [], "mainChips": [],
            "ecosystems": [], "massProductionStatuses": [], "dutConnectTypes": [],
            "wifiModules": [], "interfaces": [],
        }

    def get_performance(self, filters):
        self.performance_arg = filters
        return {
            "data": [{"pathLossDb": 10.0, "throughputAvgMbps": 900.0, "reportName": "Performance-1"}],
            "summary": {"count": 1},
            "filters": {"productLines": filters.product_lines},
            "metadata": {"requestedLimit": filters.limit, "appliedLimit": filters.limit, "totalReturned": 1, "truncated": False},
        }


def test_health_does_not_resolve_database_owner():
    app = create_app(query_owner=lambda: (_ for _ in ()).throw(AssertionError("DB resolved")))
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_repeated_snake_case_filters_reach_owner_and_response_keeps_camel_case():
    owner = RecordingOwner()
    client = TestClient(create_app(query_owner=lambda: owner))
    response = client.get(
        "/api/filters",
        params=[("product_line", "Consumer"), ("product_line", "Enterprise"),
                ("project", "Apollo"), ("report_name", "Performance-1"),
                ("standard", "802.11be"), ("data_type", "performance")],
    )
    assert response.status_code == 200
    assert owner.filters_arg.product_lines == ["Consumer", "Enterprise"]
    assert owner.filters_arg.data_type == "PEAK_THROUGHPUT"
    assert response.json()["projectOptions"] == [{"value": "Apollo", "label": "Apollo"}]


def test_performance_contract_and_limit_are_forwarded():
    owner = RecordingOwner()
    response = TestClient(create_app(query_owner=lambda: owner)).get(
        "/api/performance?data_type=RVO&start_date=2026-08-01&end_date=2026-08-24&limit=25"
    )
    assert response.status_code == 200
    assert owner.performance_arg.data_type == "RVO"
    assert owner.performance_arg.limit == 25
    assert response.json()["data"][0]["throughputAvgMbps"] == 900.0


def test_database_failure_is_safe_503():
    class FailedOwner(RecordingOwner):
        def get_performance(self, filters):
            raise RuntimeError("password=secret SELECT * FROM private")

    response = TestClient(create_app(query_owner=lambda: FailedOwner())).get("/api/performance")
    assert response.status_code == 503
    assert response.json() == {"detail": "Wi-Fi Database is unavailable."}
    assert "secret" not in response.text
    assert "SELECT" not in response.text


def test_database_owner_configuration_failure_is_safe_503():
    def missing_configuration():
        raise RuntimeError("WIFI_DB_PASSWORD missing secret detail")

    client = TestClient(create_app(query_owner=missing_configuration), raise_server_exceptions=False)
    response = client.get("/api/filters")
    assert response.status_code == 503
    assert response.json() == {"detail": "Wi-Fi Database is unavailable."}
    assert "PASSWORD" not in response.text


def test_only_approved_routes_exist():
    client = TestClient(create_app(query_owner=lambda: RecordingOwner()))
    assert client.post("/api/performance").status_code == 405
    assert client.get("/api/users").status_code == 404
