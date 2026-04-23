from __future__ import annotations

import pytest

from testing.runner.android_client import trigger_android_client_case


pytestmark = pytest.mark.case_type("system")


def test_cpu_freq_switch_via_android_client(request):
    trigger_android_client_case(case_id="cpu_freq_switch", trigger=request.node.nodeid)
