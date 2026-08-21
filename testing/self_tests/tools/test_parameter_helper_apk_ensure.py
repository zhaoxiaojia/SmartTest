from testing.tool.dut_tool.parameter_helper import ParameterHelper


def test_refresh_duts_returns_single_device_before_explicit_apk_prepare():
    calls = []
    helper = ParameterHelper(
        device_lister=lambda: ["192.168.1.220:5555"],
        apk_ensurer=lambda **kwargs: calls.append(kwargs) or True,
    )

    assert helper.refresh_duts() == ["192.168.1.220:5555"]
    assert calls == []


def test_refresh_duts_does_not_ensure_apk_for_multiple_devices_without_selection():
    calls = []
    helper = ParameterHelper(
        device_lister=lambda: ["device-a", "device-b"],
        apk_ensurer=lambda **kwargs: calls.append(kwargs) or True,
    )

    assert helper.refresh_duts() == ["device-a", "device-b"]

    assert calls == []
