from __future__ import annotations

import pytest

from testing.tests.android.common.iptv.middle_screen_cases import case_by_source_id
from testing.tests.android.common.iptv.middle_screen_runner import build_middle_screen_plan, run_middle_screen_case


pytestmark = pytest.mark.case_type("iptv_middle_screen")
CASE = case_by_source_id(66)
SMARTTEST_CASE_PLAN = build_middle_screen_plan(CASE)


@pytest.mark.requires_params(*CASE.parameters)
def test_middle_screen_066_mjpeg_4k30(request):
    run_middle_screen_case(request, CASE)
