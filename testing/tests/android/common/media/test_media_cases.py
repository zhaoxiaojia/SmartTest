from __future__ import annotations

import pytest

from testing.runner.android_client import trigger_android_client_case


pytestmark = pytest.mark.case_type("media")


def test_local_video_loop_via_android_client(request):
    trigger_android_client_case(case_id="av_codec_loop", trigger=request.node.nodeid)


def test_live_channel_switch_via_android_client(request):
    trigger_android_client_case(case_id="live_channel_switch", trigger=request.node.nodeid)


def test_camera_codec_via_android_client(request):
    trigger_android_client_case(case_id="camera_codec", trigger=request.node.nodeid)


def test_audio_loop_via_android_client(request):
    trigger_android_client_case(case_id="audio_loop", trigger=request.node.nodeid)
