from __future__ import annotations

import pytest

from testing.runner.android_client import build_case_params, trigger_android_client_case
from testing.runtime import request_case_param


pytestmark = pytest.mark.case_type("system")


@pytest.mark.requires_params(
    "auto_reboot:cycle_count",
    "auto_reboot:interval_sec",
)
def test_auto_reboot_via_android_client(request):
    trigger_android_client_case(
        case_id="auto_reboot",
        params=build_case_params(
            "auto_reboot",
            cycle_count=request_case_param(request, "auto_reboot:cycle_count", 20, cast=int),
            interval_sec=request_case_param(request, "auto_reboot:interval_sec", 100, cast=int),
        ),
        trigger=request.node.nodeid,
    )
