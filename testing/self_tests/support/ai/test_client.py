import io, json
import urllib.error
import pytest
from support.ai import AIChatClient, AIChatMessage, AIClientConfig, AIResponseError, AITransportError

class Response:
    def __init__(self, body): self.body=body
    def __enter__(self): return self
    def __exit__(self, *_args): pass
    def read(self): return self.body

def test_client_uses_openai_compatible_payload_and_structured_format():
    seen={}
    def opener(request, timeout):
        seen["payload"] = json.loads(request.data); seen["timeout"] = timeout
        return Response(b'{"choices":[{"message":{"content":"{}"}}],"model":"m"}')
    response=AIChatClient(AIClientConfig("https://ai/v1","m","secret",2), opener=opener).chat_completion([AIChatMessage("user","body")], response_format={"type":"json_object"})
    assert seen["payload"]["response_format"] == {"type":"json_object"}
    assert seen["payload"]["max_tokens"] == 2048
    assert response.content == "{}"

def test_transport_and_invalid_json_errors_do_not_expose_secret_or_body():
    client=AIChatClient(AIClientConfig("https://ai/v1","m","secret"), opener=lambda *_a, **_k: (_ for _ in ()).throw(TimeoutError()))
    with pytest.raises(AITransportError) as error: client.chat_completion([])
    assert "secret" not in str(error.value)
    client=AIChatClient(AIClientConfig("https://ai/v1","m","secret"), opener=lambda *_a, **_k: Response(b'sensitive invalid'))
    with pytest.raises(AIResponseError) as error: client.chat_completion([])
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
