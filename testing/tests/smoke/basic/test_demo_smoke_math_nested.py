import pytest


@pytest.mark.smoke
def test_smoke_nested_basic_math():
    assert 2 * 3 == 6

