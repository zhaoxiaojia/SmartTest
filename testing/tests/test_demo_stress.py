import pytest


@pytest.mark.case_type("stress")
@pytest.mark.wifi
@pytest.mark.requires_param_groups("dut_identity", "stress_runtime")
@pytest.mark.parametrize("concurrency", [1, 4])
def test_stress_throughput_placeholder(concurrency: int):
    """
    Demo "stress" case.

    Case type is taken from `@pytest.mark.case_type("stress")` (preferred path).
    """
    assert concurrency > 0


@pytest.mark.case_type("stress")
@pytest.mark.regression
@pytest.mark.requires_params("operator")
def test_stress_regression_placeholder():
    assert "stress" in "smarttest-stress"
