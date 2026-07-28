import io
import json
import urllib.error

import pytest

from support.ai import (
    AIChatClient,
    AIChatMessage,
    AIClientConfig,
    AIConfigurationError,
    AIResponseError,
    AITransportError,
    create_chat_client,
)


class Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass

    def read(self):
        return self.body


def test_model_request_options_are_merged_into_openai_compatible_payload():
    seen = {}

    def opener(request, timeout):
        seen["payload"] = json.loads(request.data)
        return Response(b'{"choices":[{"message":{"content":"{}"}}],"model":"m"}')

    config = AIClientConfig(
        "https://ai/v1",
        "m",
        "secret",
        request_options={"thinking": {"type": "disabled"}},
    )
    AIChatClient(config, opener=opener).chat_completion(
        [AIChatMessage("user", "body")], response_format={"type": "json_object"}
    )

    assert seen["payload"]["thinking"] == {"type": "disabled"}
    assert seen["payload"]["response_format"] == {"type": "json_object"}


def test_request_options_are_defensively_copied_before_payload_construction():
    options = {"thinking": {"type": "disabled"}}
    seen = {}

    def opener(request, timeout):
        seen["payload"] = json.loads(request.data)
        return Response(b'{"choices":[{"message":{"content":"{}"}}]}')

    client = AIChatClient(
        AIClientConfig("https://ai/v1", "m", "secret", request_options=options),
        opener=opener,
    )
    options["thinking"]["type"] = "enabled"
    options["model"] = "replaced"

    client.chat_completion([AIChatMessage("user", "body")])

    assert seen["payload"]["model"] == "m"
    assert seen["payload"]["thinking"] == {"type": "disabled"}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("model", "replaced"),
        ("messages", []),
        ("temperature", 1),
        ("max_tokens", 1),
        ("response_format", {"type": "text"}),
    ],
)
def test_request_options_cannot_override_client_owned_payload_fields(field, value):
    client = AIChatClient(
        AIClientConfig("https://ai/v1", "m", "secret", request_options={field: value}),
        opener=lambda *_args, **_kwargs: Response(
            b'{"choices":[{"message":{"content":"{}"}}]}'
        ),
    )

    with pytest.raises(AIConfigurationError):
        client.chat_completion([AIChatMessage("user", "body")])


def test_create_chat_client_uses_selected_template_and_credential(monkeypatch, tmp_path):
    import support.ai.config as config_module

    class Resolver:
        def resolve(self, credential_id):
            assert credential_id == "public-deepseek"
            return "stored-key"

    monkeypatch.setattr(config_module, "AIKeyResolver", Resolver)
    monkeypatch.setattr(config_module, "_default_settings_path", lambda: tmp_path / "settings.json")
    select_model = config_module.select_model
    select_model("public-deepseek")
    client = create_chat_client()
    seen = {}
    client._opener = lambda request, timeout: seen.update(
        payload=json.loads(request.data), url=request.full_url
    ) or Response(b'{"choices":[{"message":{"content":"ok"}}]}')

    assert client.chat_completion([AIChatMessage("user", "body")]).content == "ok"
    assert seen["url"] == "https://api.deepseek.com/chat/completions"
    assert seen["payload"]["model"] == "deepseek-v4-flash"
    assert seen["payload"]["thinking"] == {"type": "disabled"}


def test_transport_and_response_errors_do_not_expose_secret_or_body():
    client = AIChatClient(
        AIClientConfig("https://ai/v1", "m", "secret"),
        opener=lambda *_a, **_k: (_ for _ in ()).throw(TimeoutError()),
    )
    with pytest.raises(AITransportError) as error:
        client.chat_completion([])
    assert "secret" not in str(error.value)
    client = AIChatClient(
        AIClientConfig("https://ai/v1", "m", "secret"),
        opener=lambda *_a, **_k: Response(b"sensitive invalid"),
    )
    with pytest.raises(AIResponseError) as error:
        client.chat_completion([])
    assert "sensitive" not in str(error.value)


def test_http_error_reports_only_status_without_secret_or_response_body():
    error = urllib.error.HTTPError(
        "https://ai/v1/chat/completions",
        401,
        "Unauthorized",
        {},
        io.BytesIO(b'{"error":{"message":"sensitive server detail"}}'),
    )
    client = AIChatClient(
        AIClientConfig("https://ai/v1", "m", "secret"),
        opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
    )

    with pytest.raises(AITransportError) as captured:
        client.chat_completion([])

    assert str(captured.value) == "AI request failed: HTTP 401"
    assert captured.value.category == "http"
    assert captured.value.status_code == 401
    assert captured.value.timeout == 120.0
    assert "secret" not in str(captured.value)
    assert "sensitive" not in str(captured.value)


def test_url_error_exposes_only_safe_reason_category_and_timeout():
    error = urllib.error.URLError(ConnectionRefusedError("sensitive host detail"))
    client = AIChatClient(
        AIClientConfig("https://ai/v1", "m", "secret", timeout=9),
        opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
    )

    with pytest.raises(AITransportError) as captured:
        client.chat_completion([])

    assert captured.value.category == "connectionrefusederror"
    assert captured.value.timeout == 9
    assert "sensitive" not in str(captured.value)
