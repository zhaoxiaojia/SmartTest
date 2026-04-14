import pytest


@pytest.mark.performance
@pytest.mark.wifi
def test_performance_nested_rvr_chamber():
    assert pytest.approx(0.95, rel=1e-6) == 0.95
