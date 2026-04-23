from __future__ import annotations

from testing.params.adb_devices import parse_adb_devices_output, resolve_adb_serial_for_command


def test_parse_adb_devices_output_keeps_only_ready_devices():
    output = """
List of devices attached
emulator-5554\tdevice
ZY223JQW7\toffline
R58N123ABC\tunauthorized
ABCDEF012345\tdevice product:test model:test_device device:test transport_id:2

"""

    assert parse_adb_devices_output(output) == [
        "emulator-5554",
        "ABCDEF012345",
    ]


def test_parse_adb_devices_output_keeps_raw_single_device_serial():
    output = b"List of devices attached\r\n0099360090052090260214801F41D0F\xb6\tdevice\r\n\r\n".decode(
        "latin-1"
    )

    assert parse_adb_devices_output(output) == ["0099360090052090260214801F41D0F\xb6"]


def test_resolve_adb_serial_for_command_omits_serial_when_single_device(monkeypatch) -> None:
    monkeypatch.setattr("testing.params.adb_devices.list_adb_devices", lambda: ["ABC123"])

    assert resolve_adb_serial_for_command("ABC123") is None


def test_resolve_adb_serial_for_command_keeps_selected_serial_when_multiple_devices(monkeypatch) -> None:
    monkeypatch.setattr("testing.params.adb_devices.list_adb_devices", lambda: ["ABC123", "XYZ789"])

    assert resolve_adb_serial_for_command("ABC123") == "ABC123"
