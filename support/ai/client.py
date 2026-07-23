from __future__ import annotations

import json
import urllib.error
import urllib.request

from .core import AIChatMessage, AIChatResponse, AIClientConfig, AIResponseError, AITransportError


class AIChatClient:
    def __init__(self, config: AIClientConfig, *, opener=None):
        self._config = config
        self._opener = opener or urllib.request.urlopen

    def chat_completion(
        self,
        messages,
        *,
        response_format=None,
        temperature=0,
        max_tokens=None,
    ) -> AIChatResponse:
        payload = {
            "model": self._config.model,
            "messages": [
                {"role": message.role, "content": message.content}
                if isinstance(message, AIChatMessage)
                else dict(message)
                for message in messages
            ],
            "temperature": temperature,
            "max_tokens": (
                self._config.max_tokens if max_tokens is None else int(max_tokens)
            ),
        }
        if response_format is not None: payload["response_format"] = response_format
        request = urllib.request.Request(self._config.base_url.rstrip("/") + "/chat/completions", data=json.dumps(payload).encode("utf-8"), headers={"Authorization": "Bearer " + self._config.api_key, "Content-Type": "application/json"}, method="POST")
        try:
            with self._opener(request, timeout=self._config.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise AITransportError(
                f"AI request failed: HTTP {exc.code}",
                category="http",
                status_code=exc.code,
                timeout=self._config.timeout,
            ) from None
        except urllib.error.URLError as exc:
            reason = exc.reason
            category = (
                "timeout"
                if isinstance(reason, TimeoutError)
                else type(reason).__name__.lower() or "url"
            )
            raise AITransportError(
                "AI request failed",
                category=category,
                timeout=self._config.timeout,
            ) from None
        except TimeoutError:
            raise AITransportError(
                "AI request failed",
                category="timeout",
                timeout=self._config.timeout,
            ) from None
        except Exception as exc:
            raise AITransportError(
                "AI request failed",
                category=type(exc).__name__.lower(),
                timeout=self._config.timeout,
            ) from None
        try:
            body = json.loads(raw.decode("utf-8"))
            content = str(body["choices"][0]["message"]["content"])
            return AIChatResponse(content=content, model=str(body.get("model") or ""), usage=body.get("usage"))
        except Exception:
            raise AIResponseError("AI response is invalid") from None
