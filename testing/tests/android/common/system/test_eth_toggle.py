from __future__ import annotations

import pytest

from testing.runner.android_client import trigger_android_client_case


pytestmark = pytest.mark.case_type("system")


def test_eth_toggle_via_android_client(request):
    trigger_android_client_case(case_id="eth_toggle", trigger=request.node.nodeid)
