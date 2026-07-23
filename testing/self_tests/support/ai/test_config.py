import pytest
from support.ai import AIConfigurationError, AIKeyResolver, load_ai_client_config
import base64
import json

def test_key_resolver_prefers_environment(monkeypatch):
    monkeypatch.setenv("SMARTTEST_AI_API_KEY", "env-key")
    assert AIKeyResolver().resolve() == "env-key"

def test_missing_key_is_explicit(monkeypatch, tmp_path):
    monkeypatch.delenv("SMARTTEST_AI_API_KEY", raising=False)
    with pytest.raises(AIConfigurationError): AIKeyResolver(tmp_path / "missing.json").resolve()


def test_runtime_config_defaults_to_company_provider_and_allows_environment_override(monkeypatch):
    class Resolver:
        def resolve(self): return "key"
    for name in (
        "SMARTTEST_AI_BASE_URL",
        "SMARTTEST_AI_MODEL",
        "SMARTTEST_AI_TIMEOUT",
        "SMARTTEST_AI_MAX_TOKENS",
    ):
        monkeypatch.delenv(name, raising=False)
    default = load_ai_client_config(Resolver())
    assert default.base_url == "https://llm.amlogic.com/8d1b5b4c"
    assert default.model == "Amlogic_Local/Kimi-K2.7-Code"
    assert default.timeout == 120.0
    assert default.max_tokens == 2048
    monkeypatch.setenv("SMARTTEST_AI_BASE_URL", "https://internal.example/v1/")
    monkeypatch.setenv("SMARTTEST_AI_MODEL", "internal-model")
    monkeypatch.setenv("SMARTTEST_AI_TIMEOUT", "7.5")
    monkeypatch.setenv("SMARTTEST_AI_MAX_TOKENS", "512")
    overridden = load_ai_client_config(Resolver())
    assert (
        overridden.base_url,
        overridden.model,
        overridden.timeout,
        overridden.max_tokens,
    ) == ("https://internal.example/v1", "internal-model", 7.5, 512)

def test_config_module_has_no_qt_dependency():
    import support.ai.config as config
    assert "PySide6" not in config.__loader__.get_source(config.__name__)

def test_legacy_dpapi_field_uses_historical_entropy_and_migrates(monkeypatch, tmp_path):
    import support.ai.config as config
    path = tmp_path / "secret_store.json"
    path.write_text(json.dumps({"encrypted_api_key": base64.b64encode(b"cipher").decode()}), encoding="utf-8")
    calls = []
    monkeypatch.delenv("SMARTTEST_AI_API_KEY", raising=False)
    monkeypatch.setattr(config, "_dpapi_unprotect", lambda value, *, entropy=None: calls.append((value, entropy)) or b"legacy-key")
    monkeypatch.setattr(AIKeyResolver, "store", lambda self, key: calls.append(("store", key)) or path)
    assert AIKeyResolver(path).resolve() == "legacy-key"
    assert calls == [(b"cipher", config.LEGACY_DPAPI_ENTROPY), ("store", "legacy-key")]

@pytest.mark.parametrize("name,value", [("SMARTTEST_AI_TIMEOUT", "0"), ("SMARTTEST_AI_TIMEOUT", "-1")])
def test_invalid_runtime_config_is_explicit(monkeypatch, name, value):
    class Resolver:
        def resolve(self): return "key"
    monkeypatch.setenv(name, value)
    with pytest.raises(AIConfigurationError): load_ai_client_config(Resolver())
