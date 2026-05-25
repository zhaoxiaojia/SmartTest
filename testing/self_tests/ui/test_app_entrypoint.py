from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "ui"))

from ui.example.main import _exit_code_from_event_result


def test_normal_app_close_returns_zero_exit_code() -> None:
    assert _exit_code_from_event_result(True) == 0


def test_integer_restart_exit_code_is_preserved() -> None:
    assert _exit_code_from_event_result(931) == 931
