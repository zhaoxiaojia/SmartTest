from AI.core.models import AIChatMessage
from AI.transport.client import AIChatClient, AIClientConfig


def test_chat_client_builds_openai_compatible_payload(monkeypatch):
    client = AIChatClient(
        AIClientConfig(base_url="https://example.com/base"),
        api_key_provider=lambda: "stub-key",
    )
    captured = {}

    def fake_request_json(payload):
        captured["payload"] = payload
        return {
            "id": "resp-1",
            "model": "DeepSeek-V3-2",
            "created": 123,
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": "hello",
                    },
                }
            ],
        }

    monkeypatch.setattr(client, "_request_json", fake_request_json)

    response = client.chat_completion(
        [
            AIChatMessage(role="system", content="You are a helpful assistant."),
            AIChatMessage(role="user", content="hello"),
        ],
        model="DeepSeek-V3-2",
        max_tokens=64,
        temperature=0.2,
        tools=[{"type": "function", "function": {"name": "ping"}}],
    )

    assert captured["payload"]["model"] == "DeepSeek-V3-2"
    assert captured["payload"]["messages"][0]["role"] == "system"
    assert captured["payload"]["messages"][1]["content"] == "hello"
    assert captured["payload"]["max_tokens"] == 64
    assert captured["payload"]["temperature"] == 0.2
    assert captured["payload"]["tools"][0]["function"]["name"] == "ping"
    assert response.text == "hello"
