from __future__ import annotations

from testing.params.bt_devices import parse_paired_bluetooth_devices_output


def test_parse_paired_bluetooth_devices_output_supports_inline_name_and_mac() -> None:
    output = """
    Name = 小米小钢炮蓝牙音箱   [74:a3:4a:13:3e:da]
    Name = HUAWEI Sound Joy-09524  [78:04:e3:54:3e:91]
    Name = JBL Charge 3   [04:21:44:ab:d6:63]
    """.strip()

    assert parse_paired_bluetooth_devices_output(output) == [
        "小米小钢炮蓝牙音箱 [74:A3:4A:13:3E:DA]",
        "HUAWEI Sound Joy-09524 [78:04:E3:54:3E:91]",
        "JBL Charge 3 [04:21:44:AB:D6:63]",
    ]


def test_parse_paired_bluetooth_devices_output_supports_multiline_name_and_address() -> None:
    output = """
    Bonded devices:
    Name: EDIFIER M380
    Address: f4:4e:fd:44:a5:89
    Name: SRS-XB10
    Peer: f8:df:15:22:4a:cc
    """.strip()

    assert parse_paired_bluetooth_devices_output(output) == [
        "EDIFIER M380 [F4:4E:FD:44:A5:89]",
        "SRS-XB10 [F8:DF:15:22:4A:CC]",
    ]


def test_parse_paired_bluetooth_devices_output_ignores_local_adapter_properties() -> None:
    output = """
    AdapterProperties
      Name: CMCC_STB
      Address: 90:7A:DA:FB:45:66
      Bonded devices:
    """.strip()

    assert parse_paired_bluetooth_devices_output(output) == []
