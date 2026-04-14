import pytest


@pytest.mark.smoke
@pytest.mark.wifi
def test_smoke_app_bootstrap():
    """
    Demo "smoke" case.

    Case type is inferred from marker name (fallback path in `testing/conftest.py`).
    """
    assert True


@pytest.mark.smoke
def test_smoke_basic_math():
    assert 1 + 1 == 2

