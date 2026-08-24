from pathlib import Path


def test_mcp_transport_and_jira_context_have_canonical_owners():
    from support.mcp.client import McpClient, _parse_mcp_response
    from core.jira.mcp_context import McpContextService

    assert McpClient.__module__ == "support.mcp.client"
    assert McpContextService.__module__ == "core.jira.mcp_context"
    assert _parse_mcp_response('data: {"result": {"ok": true}}')["result"] == {"ok": True}


def test_desktop_kpi_owner_preserves_interval_calculation():
    from client.app.debug.kpi.analysis import calculate_kpi_interval

    assert calculate_kpi_interval(fps=25, start_frame=10, end_frame=35) == {
        "sequence": 1,
        "start_frame": 10,
        "end_frame": 35,
        "elapsed_frames": 25,
        "elapsed_seconds": 1.0,
        "elapsed_ms": 1000.0,
        "start_time": 0.4,
        "end_time": 1.4,
    }


def test_bt_capture_uses_serial_tool_seam_and_explicit_output_owner(tmp_path):
    from core.testing.tool.bt_analysis import capture_serial_log

    class FakeSerialTool:
        def __init__(self, port, baudrate, timeout):
            self.arguments = (port, baudrate, timeout)
            self.reads = [b"\x01\x02", b""]
            self.closed = False

        def read(self, size):
            return self.reads.pop(0)

        def close(self):
            self.closed = True

    created = []

    def factory(*args, **kwargs):
        instance = FakeSerialTool(*args, **kwargs)
        created.append(instance)
        return instance

    checks = iter((False, False, True))
    paths = capture_serial_log(
        "COM7", 115200, add_timestamp=False, output_dir=tmp_path,
        stop_flag=lambda: next(checks), serial_factory=factory,
    )

    assert created[0].arguments == ("COM7", 115200, 0.2)
    assert created[0].closed is True
    assert len(paths) == 1
    assert paths[0].parent == tmp_path
    assert paths[0].read_text(encoding="utf-8") == "01 02\n"


def test_bt_15p4_parser_preserves_decoded_output(capsys):
    from core.testing.tool.bt_analysis.parse_15p4_log import parse_15p4_log

    parse_15p4_log(0x55, "0x04", 6)

    assert capsys.readouterr().out == "[15p4 key]channel: 0x6 "


def test_root_legacy_owners_are_absent():
    root = Path(__file__).resolve().parents[2]
    forbidden = ("AI", "debug", "tools", "demo_outlook.py", "dist_installer", "dist_tool", ".superpowers")
    assert [name for name in forbidden if (root / name).exists()] == []
