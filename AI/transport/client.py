from __future__ import annotations

from dataclasses import dataclass
import json
import ssl
import time
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import HTTPSHandler, Request, build_opener

from AI.config import AISecretStore, DEFAULT_AI_TIMEOUT_SECONDS
from AI.core.errors import AIConfigurationError, AIRequestError
from AI.core.models import AIChatMessage, AIChatResponse


@dataclass(frozen=True)
class AIClientConfig:
    base_url: str
    endpoint_path: str = "chat/completions"
    timeout_seconds: float = DEFAULT_AI_TIMEOUT_SECONDS
    verify_ssl: bool = True


class AIChatClient:
    def __init__(self, config: AIClientConfig, *, secret_store: AISecretStore):
        if not config.base_url.strip():
            raise AIConfigurationError("AI base URL cannot be empty")
        if config.timeout_seconds <= 0:
            raise AIConfigurationError("AI timeout must be positive")
        self._config = config
        self._secret_store = secret_store

    @property
    def config(self) -> AIClientConfig:
        return self._config

    def chat_completion(
        self,
        messages: Iterable[AIChatMessage | dict[str, Any]],
        *,
        model: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AIChatResponse:
        if not model.strip():
            raise AIConfigurationError("AI model cannot be empty")
        payload: dict[str, Any] = {
            "model": model,
            "messages": [_serialize_message(item) for item in messages],
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        if tools:
            payload["tools"] = tools

        response_payload = self._request_json(payload)
        if not isinstance(response_payload, dict):
            raise AIRequestError("AI endpoint returned a non-object payload")
        return AIChatResponse.from_payload(response_payload)

    def _request_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        api_key = self._secret_store.resolve_api_key()
        started_at = time.monotonic()
        request = Request(
            url=self._endpoint_url(),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        opener = self._build_opener()
        _trace_ai_request("request_start", url=self._endpoint_url())
        try:
            with opener.open(request, timeout=self._config.timeout_seconds) as response:
                raw_body = response.read()
                _trace_ai_request(
                    "request_done",
                    url=self._endpoint_url(),
                    status=int(response.status),
                    elapsed_ms=int((time.monotonic() - started_at) * 1000),
                )
        except HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            _trace_ai_request(
                "request_http_error",
                url=self._endpoint_url(),
                status=exc.code,
                elapsed_ms=int((time.monotonic() - started_at) * 1000),
            )
            raise AIRequestError(f"AI request failed: POST {self._endpoint_url()} -> {exc.code} {text[:400]}") from exc
        except URLError as exc:
            _trace_ai_request(
                "request_url_error",
                url=self._endpoint_url(),
                elapsed_ms=int((time.monotonic() - started_at) * 1000),
            )
            raise AIRequestError(f"AI request failed: POST {self._endpoint_url()} -> {exc.reason}") from exc

        text = raw_body.decode("utf-8", errors="replace")
        return _json_loads(text)

    def _endpoint_url(self) -> str:
        base = self._config.base_url.rstrip("/") + "/"
        return urljoin(base, self._config.endpoint_path.lstrip("/"))

    def _build_opener(self):
        context = None
        if not self._config.verify_ssl:
            context = ssl._create_unverified_context()
        return build_opener(HTTPSHandler(context=context))


def _serialize_message(item: AIChatMessage | dict[str, Any]) -> dict[str, Any]:
    if isinstance(item, AIChatMessage):
        return item.to_payload()
    if isinstance(item, dict):
        return dict(item)
    raise AIConfigurationError(f"Unsupported AI message type: {type(item)!r}")


def _json_loads(text: str) -> dict[str, Any]:
    if text.strip() == "":
        raise AIRequestError("AI endpoint returned an empty response")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIRequestError(f"AI endpoint returned invalid JSON: {text[:200]}") from exc
    if not isinstance(payload, dict):
        raise AIRequestError("AI endpoint returned a non-object payload")
    return payload


def _trace_ai_request(stage: str, **values: Any) -> None:
    details = " ".join(f"{key}={values[key]}" for key in sorted(values))
    print(f"[AI_HTTP] {stage} {details}".rstrip())
