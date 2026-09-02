import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = ROOT / "client" / "scripts"


def _dev_module():
    sys.path.insert(0, str(SCRIPTS))
    try:
        return importlib.import_module("dev")
    finally:
        sys.path.remove(str(SCRIPTS))


def test_client_dev_environment_defaults_local_web_base_url(monkeypatch):
    monkeypatch.delenv("SMARTTEST_WEB_BASE_URL", raising=False)

    child_environment = _dev_module().client_environment()

    assert child_environment["SMARTTEST_WEB_BASE_URL"] == "http://127.0.0.1:8000"


def test_client_dev_environment_preserves_external_web_base_url(monkeypatch):
    monkeypatch.setenv("SMARTTEST_WEB_BASE_URL", "https://smarttest.example")

    child_environment = _dev_module().client_environment()

    assert child_environment["SMARTTEST_WEB_BASE_URL"] == "https://smarttest.example"


def test_startup_web_base_url_log_uses_core_logging_without_secrets(monkeypatch):
    main = importlib.import_module("client.app.ui.example.main")
    records = []
    monkeypatch.setattr(main, "smart_log", lambda *args, **kwargs: records.append((args, kwargs)))

    main._log_web_base_url("http://127.0.0.1:8000")

    assert records
    assert "http://127.0.0.1:8000" in repr(records)
    assert "password" not in repr(records).casefold()
    assert "token" not in repr(records).casefold()


def test_startup_web_base_url_log_redacts_userinfo_and_query(monkeypatch):
    main = importlib.import_module("client.app.ui.example.main")
    records = []
    monkeypatch.setattr(main, "smart_log", lambda *args, **kwargs: records.append((args, kwargs)))

    main._log_web_base_url("https://alice:secret@example.test/api?token=private#fragment")

    rendered = repr(records)
    assert "https://example.test/api" in rendered
    assert "alice" not in rendered
    assert "secret" not in rendered
    assert "private" not in rendered
