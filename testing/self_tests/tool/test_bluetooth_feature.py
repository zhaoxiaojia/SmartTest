from __future__ import annotations

from testing.tool.dut_tool.features.bluetooth import connected_bluetooth_targets_from_dumpsys


def test_connected_bluetooth_targets_from_dumpsys_parses_connected_profiles() -> None:
    raw = """
  Bonded devices:
    A0:E9:DB:23:17:58 [ DUAL ] iChocolate Mini
Profile: A2dpService
  === A2dpStateMachine for XX:XX:XX:XX:17:58 (Active) ===
    StateMachine: name=A2dpStateMachine state=Connected
Profile: HeadsetService
    mCurrentDevice: 11:22:33:44:55:66
    StateMachine: name=HeadsetStateMachine state=Connected
shim::legacy::record 001 11:22:33:44:55:66 BR_EDR name:"Living Room Speaker"
A2DP Source State: Enabled
  Peer: AA:BB:CC:DD:EE:FF
    Connected: true
"""

    targets = connected_bluetooth_targets_from_dumpsys(raw)

    assert targets == [
        "iChocolate Mini [A0:E9:DB:23:17:58]",
        "Living Room Speaker [11:22:33:44:55:66]",
        "AA:BB:CC:DD:EE:FF",
    ]


def test_connected_bluetooth_targets_from_dumpsys_ignores_disconnected_profiles() -> None:
    raw = """
  === A2dpStateMachine for 11:22:33:44:55:66 (Active) ===
    StateMachine: name=A2dpStateMachine state=Disconnected
  Peer: AA:BB:CC:DD:EE:FF
    Connected: false
"""

    assert connected_bluetooth_targets_from_dumpsys(raw) == []
