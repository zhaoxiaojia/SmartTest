from AI.config.api_key_resolver import AIApiKeyResolver
from AI.config.secret_store import AISecretStore
from AI.providers.amlogic_defaults import decode_default_amlogic_api_key


def test_secret_store_bootstraps_default_key(tmp_path, monkeypatch):
    monkeypatch.delenv("SMARTTEST_AI_API_KEY", raising=False)
    store = AISecretStore(tmp_path / "secret_store.json")

    resolved = AIApiKeyResolver(store, default_api_key_factory=decode_default_amlogic_api_key).resolve()

    assert resolved == decode_default_amlogic_api_key()
    assert store.store_path.exists()
    assert resolved not in store.store_path.read_text(encoding="utf-8")
    assert store.read_api_key() == decode_default_amlogic_api_key()


def test_secret_store_prefers_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("SMARTTEST_AI_API_KEY", "env-token")
    store = AISecretStore(tmp_path / "secret_store.json")

    resolved = AIApiKeyResolver(store, default_api_key_factory=decode_default_amlogic_api_key).resolve()

    assert resolved == "env-token"
    assert not store.store_path.exists()
