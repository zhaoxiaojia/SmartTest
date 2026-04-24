from __future__ import annotations

import pytest

from testing.runner.android_client import build_case_params, trigger_android_client_case
from testing.runtime import request_case_param


pytestmark = pytest.mark.case_type("system")


@pytest.mark.requires_params(
    "auto_suspend:cycle_count",
    "auto_suspend:interval_sec",
    "auto_suspend:ping_target",
    "auto_suspend:bt_target",
)
def test_auto_suspend_via_android_client(request):
    trigger_android_client_case(
        case_id="auto_suspend",
        params=build_case_params(
            "auto_suspend",
            cycle_count=request_case_param(request, "auto_suspend:cycle_count", 20, cast=int),
            interval_sec=request_case_param(request, "auto_suspend:interval_sec", 100, cast=int),
            ping_target=request_case_param(request, "auto_suspend:ping_target", ""),
            bt_target=request_case_param(request, "auto_suspend:bt_target", ""),
        ),
        trigger=request.node.nodeid,
    )
