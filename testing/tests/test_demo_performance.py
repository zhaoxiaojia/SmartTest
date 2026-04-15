import pytest


@pytest.mark.performance
@pytest.mark.wifi
@pytest.mark.requires_param_groups("dut_identity")
def test_performance_rvr_placeholder():
    """
    Demo "performance" case.

    Case type is inferred from marker name (fallback path in `testing/conftest.py`).
    """
    assert 0.1 + 0.2 == pytest.approx(0.3)
