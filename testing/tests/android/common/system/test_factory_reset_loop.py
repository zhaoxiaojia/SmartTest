from __future__ import annotations

import pytest

from testing.runner.android_client import trigger_android_client_case


pytestmark = pytest.mark.case_type("system")


def test_factory_reset_loop_via_android_client(request):
    trigger_android_client_case(case_id="factory_reset_loop", trigger=request.node.nodeid)
