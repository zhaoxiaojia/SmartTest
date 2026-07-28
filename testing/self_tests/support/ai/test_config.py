import base64
import json

import pytest

from support.ai import (
    AIConfigurationError,
    AIKeyResolver,
    available_models,
    model_by_id,
    select_model,
    selected_model_id,
)


@pytest.fixture(autouse=True)
def clear_compatibility_environment(monkeypatch):
    for name in (
        "SMARTTEST_AI_API_KEY",
        "SMARTTEST_KIMI_API_KEY",
        "DEEPSEEK_API_KEY",
        "SMARTTEST_DEEPSEEK_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def _resolver_at(monkeypatch, path):
    import support.ai.config as config

    monkeypatch.setattr(config, "_default_store_path", lambda: path)
    return AIKeyResolver()


def test_builtin_models_are_resolvable_and_unknown_model_is_rejected():
    models = available_models()

    assert [model.id for model in models] == [
        "company-kimi",
        "public-deepseek",
    ]
    assert [model.display_name for model in models] == [
        "Company Intranet Kimi",
        "Public DeepSeek",
    ]
    assert model_by_id("company-kimi").credential_id != model_by_id(
        "public-deepseek"
    ).credential_id
    with pytest.raises(AIConfigurationError):
        model_by_id("unknown-model")


def test_builtin_model_parameters_are_fixed_and_request_options_are_immutable():
    kimi = model_by_id("company-kimi")
    deepseek = model_by_id("public-deepseek")

    assert (
        kimi.base_url,
        kimi.model_id,
        kimi.timeout,
        kimi.max_tokens,
        dict(kimi.request_options),
    ) == (
        "https://llm.amlogic.com/8d1b5b4c",
        "Amlogic_Local/Kimi-K2.7-Code",
        120.0,
        2048,
        {"chat_template_kwargs": {"enable_thinking": False}},
    )
    assert (
        deepseek.base_url,
        deepseek.model_id,
        deepseek.timeout,
        deepseek.max_tokens,
        dict(deepseek.request_options),
    ) == (
        "https://api.deepseek.com",
        "deepseek-v4-flash",
        120.0,
        2048,
        {"thinking": {"type": "disabled"}},
    )
    with pytest.raises(TypeError):
        kimi.request_options["model"] = "replaced"
    with pytest.raises(TypeError):
        kimi.request_options["chat_template_kwargs"]["enable_thinking"] = True


def test_chat_client_model_selection_is_optional_and_can_be_explicit(monkeypatch):
    import support.ai.config as config

    credentials = []
    monkeypatch.setattr(
        config,
        "AIKeyResolver",
        lambda: type(
            "Resolver",
            (),
            {
                "resolve": lambda _self, credential_id: (
                    credentials.append(credential_id) or "key"
                )
            },
        )(),
    )

    explicit = config.create_chat_client("public-deepseek")
    default = config.create_chat_client()

    assert explicit._config.model == "deepseek-v4-flash"
    assert default._config.model == model_by_id(selected_model_id()).model_id
    assert credentials == [
        "public-deepseek",
        model_by_id(selected_model_id()).credential_id,
    ]


def test_selected_model_is_persisted_and_unknown_selection_is_rejected(monkeypatch, tmp_path):
    import support.ai.config as config

    monkeypatch.setattr(config, "_default_settings_path", lambda: tmp_path / "settings.json")

    assert selected_model_id() == "company-kimi"
    select_model("public-deepseek")
    assert selected_model_id() == "public-deepseek"
    assert json.loads((tmp_path / "settings.json").read_text(encoding="utf-8")) == {
        "selected_model_id": "public-deepseek"
    }
    with pytest.raises(AIConfigurationError):
        select_model("unknown-model")


def test_credentials_are_isolated_and_clear_only_removes_requested_credential(
    monkeypatch, tmp_path
):
    import support.ai.config as config

    monkeypatch.setattr(config, "_dpapi_protect", lambda value, *, entropy=None: b"p:" + value)
    monkeypatch.setattr(config, "_dpapi_unprotect", lambda value, *, entropy=None: value[2:])
    resolver = _resolver_at(monkeypatch, tmp_path / "secrets.json")

    resolver.store("company-kimi", "kimi-key")
    resolver.store("public-deepseek", "deepseek-key")
    resolver.clear("company-kimi")

    assert not resolver.is_configured("company-kimi")
    assert resolver.resolve("public-deepseek") == "deepseek-key"
    assert resolver.is_configured("public-deepseek")


def test_environment_key_is_a_fallback_not_an_override(monkeypatch, tmp_path):
    import support.ai.config as config

    monkeypatch.setattr(config, "_dpapi_protect", lambda value, *, entropy=None: b"p:" + value)
    monkeypatch.setattr(config, "_dpapi_unprotect", lambda value, *, entropy=None: value[2:])
    monkeypatch.setenv("DEEPSEEK_API_KEY", "environment-key")
    resolver = _resolver_at(monkeypatch, tmp_path / "secrets.json")

    resolver.store("public-deepseek", "saved-key")

    assert resolver.resolve("public-deepseek") == "saved-key"
    empty = _resolver_at(monkeypatch, tmp_path / "empty.json")
    assert empty.resolve("public-deepseek") == "environment-key"


@pytest.mark.parametrize(
    ("field", "entropy"),
    [
        ("api_key_dpapi", None),
        ("encrypted_api_key", b"SmartTest.AI.SecretStore.v1"),
    ],
)
def test_legacy_kimi_key_migrates_only_when_kimi_credential_is_resolved(
    monkeypatch, tmp_path, field, entropy
):
    import support.ai.config as config

    store_path = tmp_path / "secrets.json"
    store_path.write_text(
        json.dumps({field: base64.b64encode(b"legacy-cipher").decode()}),
        encoding="utf-8",
    )
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    calls = []
    monkeypatch.setattr(
        config,
        "_dpapi_unprotect",
        lambda value, *, entropy=None: calls.append(entropy) or b"legacy-key",
    )
    monkeypatch.setattr(config, "_dpapi_protect", lambda value, *, entropy=None: b"new-cipher")
    resolver = _resolver_at(monkeypatch, store_path)

    with pytest.raises(AIConfigurationError):
        resolver.resolve("public-deepseek")
    assert resolver.resolve("company-kimi") == "legacy-key"
    payload = json.loads(store_path.read_text(encoding="utf-8"))
    assert "api_key_dpapi" not in payload
    assert "legacy-key" not in store_path.read_text(encoding="utf-8")
    assert set(payload["credentials"]) == {"company-kimi"}
    assert calls == [entropy]
