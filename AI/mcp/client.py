from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener


HeadersFactory = Callable[[], dict[str, str]]


@dataclass(frozen=True)
class McpServerConfig:
    name: str
    url: str
    server_type: str = "streamableHttp"
    timeout_seconds: float = 10.0
    disabled: bool = False
    headers_factory: HeadersFactory | None = None
    context_enabled: bool = False


@dataclass
class McpTool:
    server_name: str
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)


class McpClient:
    def __init__(self, config: McpServerConfig):
        self._config = config
        self._request_id = 0
        self._session_id = ""
        self._initialized = False

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def context_enabled(self) -> bool:
        return self._config.context_enabled and not self._config.disabled

    def list_tools(self) -> list[McpTool]:
        if self._config.disabled:
            return []
        self._ensure_initialized()
        payload = self._rpc("tools/list", {})
        tools = payload.get("tools") if isinstance(payload, dict) else None
        if not isinstance(tools, list):
            return []
        result: list[McpTool] = []
        for item in tools:
            if not isinstance(item, dict):
                continue
            result.append(
                McpTool(
                    server_name=self._config.name,
                    name=str(item.get("name", "") or ""),
                    description=str(item.get("description", "") or ""),
                    input_schema=dict(item.get("inputSchema") or {}),
                )
            )
        return [tool for tool in result if tool.name]

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        if self._config.disabled:
            return None
        self._ensure_initialized()
        return self._rpc("tools/call", {"name": tool_name, "arguments": arguments})

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        self._rpc(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "SmartTest", "version": "0.1"},
            },
        )
        try:
            self._notify("notifications/initialized", {})
        except Exception as exc:  # noqa: BLE001
            _trace_mcp("initialized_notify_failed", server=self._config.name, error=str(exc))
        self._initialized = True

    def _rpc(self, method: str, params: dict[str, Any]) -> Any:
        self._request_id += 1
        response = self._post_json(
            {
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": method,
                "params": params,
            }
        )
        if "error" in response:
            raise RuntimeError(f"MCP {self._config.name} {method} failed: {response['error']}")
        return response.get("result")

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        self._post_json({"jsonrpc": "2.0", "method": method, "params": params})

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        started_at = time.monotonic()
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        if self._config.headers_factory is not None:
            headers.update(self._config.headers_factory())
        request = Request(
            url=self._config.url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers=headers,
        )
        _trace_mcp("request_start", server=self._config.name, method=payload.get("method", ""))
        try:
            with build_opener().open(request, timeout=self._config.timeout_seconds) as response:
                session_id = response.headers.get("Mcp-Session-Id") or response.headers.get("mcp-session-id")
                if session_id:
                    self._session_id = session_id
                raw_text = response.read().decode("utf-8", errors="replace")
                _trace_mcp(
                    "request_done",
                    server=self._config.name,
                    method=payload.get("method", ""),
                    status=int(response.status),
                    elapsed_ms=int((time.monotonic() - started_at) * 1000),
                )
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            _trace_mcp(
                "request_http_error",
                server=self._config.name,
                method=payload.get("method", ""),
                status=exc.code,
                elapsed_ms=int((time.monotonic() - started_at) * 1000),
            )
            raise RuntimeError(f"MCP request failed: {self._config.name} -> {exc.code} {body[:300]}") from exc
        except URLError as exc:
            _trace_mcp(
                "request_url_error",
                server=self._config.name,
                method=payload.get("method", ""),
                elapsed_ms=int((time.monotonic() - started_at) * 1000),
            )
            raise RuntimeError(f"MCP request failed: {self._config.name} -> {exc.reason}") from exc
        return _parse_mcp_response(raw_text)


def _parse_mcp_response(text: str) -> dict[str, Any]:
    clean = text.strip()
    if not clean:
        return {}
    if clean.startswith("event:") or clean.startswith("data:"):
        data_lines = []
        for line in clean.splitlines():
            if line.startswith("data:"):
                data_lines.append(line[5:].strip())
        clean = "\n".join(data_lines).strip()
    payload = json.loads(clean)
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict) and ("result" in item or "error" in item):
                return item
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _trace_mcp(stage: str, **values: Any) -> None:
    details = " ".join(f"{key}={values[key]}" for key in sorted(values))
    print(f"{_trace_timestamp()} [MCP] {stage} {details}".rstrip())


def _trace_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
