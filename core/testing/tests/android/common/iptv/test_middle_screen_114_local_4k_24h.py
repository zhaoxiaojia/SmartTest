from __future__ import annotations

import pytest

from core.testing.tests.android.common.iptv.middle_screen_cases import case_by_source_id
from core.testing.tests.android.common.iptv.middle_screen_runner import build_middle_screen_plan, run_middle_screen_case


pytestmark = pytest.mark.case_type("iptv_middle_screen")
CASE = case_by_source_id(114)
SMARTTEST_CASE_PLAN = build_middle_screen_plan(CASE)


@pytest.mark.requires_params(*CASE.parameters)
def test_middle_screen_114_local_4k_24h(request):
    run_middle_screen_case(request, CASE)
