import pytest


@pytest.mark.case_type("stress")
@pytest.mark.wifi
@pytest.mark.requires_param_groups("stress_runtime")
@pytest.mark.parametrize("clients", [8, 16])
def test_stress_nested_wifi_throughput(clients: int):
    assert clients > 0
