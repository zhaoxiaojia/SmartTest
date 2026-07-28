from __future__ import annotations

from dataclasses import dataclass

from support.ai import AIConfigurationError
from ui.example.bridge.AISettingsBridge import AISettingsBridge


@dataclass(frozen=True)
class Model:
    id: str
    display_name: str
    credential_id: str


class Resolver:
    def __init__(self):
        self.keys: dict[str, str] = {}

    def is_configured(self, credential_id: str) -> bool:
        return credential_id in self.keys

    def store(self, credential_id: str, key: str) -> None:
        self.keys[credential_id] = key

    def clear(self, credential_id: str) -> None:
        self.keys.pop(credential_id, None)


def build_bridge():
    models = (
        Model("company-kimi", "Company Kimi", "company-kimi"),
        Model("public-deepseek", "Public DeepSeek", "public-deepseek"),
    )
    selected = {"id": "company-kimi"}
    resolver = Resolver()
    bridge = AISettingsBridge(
        available_models_function=lambda: models,
        model_by_id_function=lambda model_id: next(
            model for model in models if model.id == model_id
        ),
        selected_model_id_function=lambda: selected["id"],
        select_model_function=lambda model_id: selected.__setitem__("id", model_id),
        key_resolver=resolver,
    )
    return bridge, resolver, selected


def test_state_exposes_only_safe_model_configuration_fields():
    bridge, resolver, _selected = build_bridge()
    resolver.store("company-kimi", "stored-secret")

    state = bridge.state()

    assert state["selected_model_id"] == "company-kimi"
    assert state["models"] == [
        {"id": "company-kimi", "display_name": "Company Intranet Kimi", "configured": True},
        {"id": "public-deepseek", "display_name": "Public DeepSeek", "configured": False},
    ]
    assert set(state) == {"selected_model_id", "models"}
    assert all(set(model) == {"id", "display_name", "configured"} for model in state["models"])
    assert not ({"api_key", "key", "secret", "credential"} & set(state))
    assert all(
        not ({"api_key", "key", "secret", "credential"} & set(model))
        for model in state["models"]
    )
    assert "stored-secret" not in str(state)


def test_select_model_uses_the_unified_ai_owner_and_refreshes_state():
    bridge, _resolver, selected = build_bridge()

    assert bridge.selectModel("public-deepseek") is True

    assert selected["id"] == "public-deepseek"
    assert bridge.state()["selected_model_id"] == "public-deepseek"


def test_failed_model_selection_refreshes_the_real_state():
    bridge, _resolver, selected = build_bridge()
    refreshes: list[bool] = []
    bridge.stateChanged.connect(lambda: refreshes.append(True))

    def fail_selection(_model_id: str) -> None:
        raise AIConfigurationError("selection failed")

    bridge._select_model = fail_selection

    assert bridge.selectModel("public-deepseek") is False

    assert selected["id"] == "company-kimi"
    assert bridge.state()["selected_model_id"] == "company-kimi"
    assert refreshes == [True]


def test_save_rejects_empty_key_and_never_returns_it():
    bridge, resolver, _selected = build_bridge()
    errors: list[str] = []
    bridge.errorOccurred.connect(errors.append)

    assert bridge.saveApiKey("company-kimi", "   ") is False
    assert resolver.keys == {}
    assert errors

    assert bridge.saveApiKey("company-kimi", "stored-secret") is True
    assert bridge.state()["models"][0]["configured"] is True
    assert "stored-secret" not in str(bridge.state())


def test_clear_only_affects_the_selected_model_credential():
    bridge, resolver, _selected = build_bridge()
    resolver.store("company-kimi", "first-secret")
    resolver.store("public-deepseek", "second-secret")

    assert bridge.clearApiKey("company-kimi") is True

    assert resolver.keys == {"public-deepseek": "second-secret"}
    assert bridge.state()["models"] == [
        {"id": "company-kimi", "display_name": "Company Intranet Kimi", "configured": False},
        {"id": "public-deepseek", "display_name": "Public DeepSeek", "configured": True},
    ]


def test_save_errors_are_redacted():
    class FailingResolver(Resolver):
        def store(self, _credential_id: str, _key: str) -> None:
            raise AIConfigurationError("stored-secret was rejected")

    bridge, _resolver, _selected = build_bridge()
    bridge._key_resolver = FailingResolver()
    errors: list[str] = []
    bridge.errorOccurred.connect(errors.append)

    assert bridge.saveApiKey("company-kimi", "stored-secret") is False

    assert errors
    assert "stored-secret" not in errors[-1]
