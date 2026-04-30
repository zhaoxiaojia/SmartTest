from __future__ import annotations

from datetime import datetime
import json
import re
from typing import Any

from AI.mcp.client import McpClient, McpServerConfig, McpTool


_SERVER_URLS = {
    "jira": "http://10.28.11.88:8111/mcp",
    "confluence": "http://10.28.11.88:8112/sse",
    "opengrok": "http://10.28.11.88:8114/mcp",
    "gerrit_scgit": "http://10.28.11.88:8115/mcp",
    "jenkins": "http://10.28.11.88:8117/mcp",
    "soc_spec_search": "http://10.28.11.88:8122/mcp",
}

_CONTEXT_SERVER_NAMES = {"soc_spec_search", "confluence", "jira"}


class McpContextService:
    def __init__(self, clients: list[McpClient], *, max_terms: int = 4, max_calls_per_server: int = 2):
        self._clients = clients
        self._max_terms = max_terms
        self._max_calls_per_server = max_calls_per_server
        self._tool_cache: dict[str, list[McpTool]] = {}

    def enrich(self, prompt: str) -> list[dict[str, Any]]:
        terms = _extract_terms(prompt)[: self._max_terms]
        if not terms:
            return []
        contexts: list[dict[str, Any]] = []
        for client in self._clients:
            if not client.context_enabled:
                continue
            try:
                tools = self._tools_for_client(client)
                search_tools = _select_search_tools(tools)
                if not search_tools:
                    contexts.append({"server": client.name, "status": "no_search_tool"})
                    continue
                calls = 0
                for tool in search_tools:
                    for term in terms:
                        if calls >= self._max_calls_per_server:
                            break
                        arguments = _build_tool_arguments(tool.input_schema, term, prompt)
                        result = client.call_tool(tool.name, arguments)
                        contexts.append(
                            {
                                "server": client.name,
                                "tool": tool.name,
                                "query": term,
                                "arguments": arguments,
                                "result": _compact_result(result),
                            }
                        )
                        calls += 1
                    if calls >= self._max_calls_per_server:
                        break
            except Exception as exc:  # noqa: BLE001
                contexts.append({"server": client.name, "status": "error", "message": str(exc)})
        return contexts

    def _tools_for_client(self, client: McpClient) -> list[McpTool]:
        if client.name not in self._tool_cache:
            self._tool_cache[client.name] = client.list_tools()
            _trace_mcp_context(
                "tools_cached",
                server=client.name,
                count=len(self._tool_cache[client.name]),
                names=",".join(tool.name for tool in self._tool_cache[client.name][:12]),
            )
        return self._tool_cache[client.name]

    def search_jira_issues(
        self,
        *,
        jql: str,
        max_results: int = 50,
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        jira_client = next((client for client in self._clients if client.name == "jira"), None)
        if jira_client is None or not jira_client.context_enabled:
            _trace_mcp_context("jira_search_skip", reason="jira_client_unavailable")
            return []
        tools = self._tools_for_client(jira_client)
        tool = _select_jira_issue_search_tool(tools)
        if tool is None:
            _trace_mcp_context("jira_search_skip", reason="search_tool_not_found")
            return []
        arguments = _build_jira_search_arguments(
            tool.input_schema,
            jql=str(jql or "").strip(),
            max_results=int(max_results),
            fields=list(fields or ["summary", "status", "assignee", "priority", "updated"]),
        )
        _trace_mcp_context(
            "jira_search_call",
            tool=tool.name,
            args=_truncate(json.dumps(arguments, ensure_ascii=False), limit=300),
        )
        payload = jira_client.call_tool(tool.name, arguments)
        issues = _extract_jira_issues(payload)
        _trace_mcp_context(
            "jira_search_result",
            tool=tool.name,
            issues=len(issues),
            payload_type=type(payload).__name__,
            payload_keys=",".join(list(payload.keys())[:10]) if isinstance(payload, dict) else "",
        )
        return issues


def create_default_mcp_context_service(*, username: str, password: str) -> McpContextService:
    clean_username = _account_name(username)
    clients = []
    for name, url in _SERVER_URLS.items():
        clients.append(
            McpClient(
                McpServerConfig(
                    name=name,
                    url=url,
                    timeout_seconds=10.0,
                    headers_factory=_headers_factory(name, username=clean_username, password=password),
                    context_enabled=name in _CONTEXT_SERVER_NAMES,
                )
            )
        )
    return McpContextService(clients)


def _headers_factory(server_name: str, *, username: str, password: str):
    def build_headers() -> dict[str, str]:
        if server_name in {"jira", "confluence"}:
            return {"Authorization": json.dumps({"username": username, "password": password}, ensure_ascii=False)}
        if server_name == "opengrok":
            return {"Authorization": json.dumps({"server_url": "http://opengrok.amlogic.com:8080/source"})}
        if server_name == "gerrit_scgit":
            return {
                "Authorization": json.dumps(
                    {
                        "server_url": "https://scgit.amlogic.com",
                        "username": username,
                        "http_password": password,
                    },
                    ensure_ascii=False,
                )
            }
        if server_name == "jenkins":
            return {"Authorization": json.dumps({"username": username, "api_token": password}, ensure_ascii=False)}
        return {}

    return build_headers


def _account_name(username: str) -> str:
    clean = str(username or "").strip()
    if "\\" in clean:
        return clean.rsplit("\\", 1)[-1]
    if "@" in clean:
        return clean.split("@", 1)[0]
    return clean


def _extract_terms(prompt: str) -> list[str]:
    text = str(prompt or "")
    terms: list[str] = []
    for match in re.finditer(r"\b[A-Za-z][A-Za-z0-9_.-]{1,}\b", text):
        value = match.group(0)
        if value.lower() in {
            "analyze",
            "analysis",
            "jira",
            "bug",
            "bugs",
            "issue",
            "issues",
            "the",
            "and",
            "or",
        }:
            continue
        if value not in terms:
            terms.append(value)
    return terms


def _select_search_tools(tools: list[McpTool]) -> list[McpTool]:
    candidates: list[McpTool] = []
    for tool in tools:
        text = f"{tool.name} {tool.description}".lower()
        if any(marker in text for marker in ("search", "query", "find", "lookup", "spec")):
            candidates.append(tool)
    return candidates[:3]


def _select_jira_issue_search_tool(tools: list[McpTool]) -> McpTool | None:
    prioritized: list[McpTool] = []
    for tool in tools:
        text = f"{tool.name} {tool.description}".lower()
        if "jira" not in text and "issue" not in text:
            continue
        if "search" in text and "issue" in text:
            prioritized.append(tool)
    if prioritized:
        prioritized.sort(key=lambda item: len(item.name))
        return prioritized[0]
    for tool in tools:
        text = f"{tool.name} {tool.description}".lower()
        if "search" in text and "jira" in text:
            return tool
    return None


def _build_jira_search_arguments(
    input_schema: dict[str, Any],
    *,
    jql: str,
    max_results: int,
    fields: list[str],
) -> dict[str, Any]:
    properties = input_schema.get("properties") if isinstance(input_schema, dict) else None
    if not isinstance(properties, dict):
        return {"jql": jql, "max_results": max_results, "fields": fields}
    args: dict[str, Any] = {}
    for name in properties.keys():
        lower = str(name).lower()
        if lower in {"jql", "query", "q"}:
            args[name] = jql
        elif lower in {"max_results", "maxresults", "limit", "size", "topk", "top_k"}:
            args[name] = max_results
        elif lower in {"fields", "field_list"}:
            args[name] = fields
        elif lower in {"startat", "start_at", "offset"}:
            args[name] = 0
    if not any(str(k).lower() in {"jql", "query", "q"} for k in args.keys()):
        args["jql"] = jql
    return args


def _build_tool_arguments(input_schema: dict[str, Any], term: str, prompt: str) -> dict[str, Any]:
    properties = input_schema.get("properties") if isinstance(input_schema, dict) else None
    if not isinstance(properties, dict):
        return {"query": term}
    args: dict[str, Any] = {}
    for name, spec in properties.items():
        lower = str(name).lower()
        if any(marker in lower for marker in ("query", "keyword", "search", "term", "text", "q")):
            args[name] = term
        elif lower in {"limit", "max", "max_results", "maxresults", "top_k", "topk"}:
            args[name] = 5
        elif lower in {"prompt", "question"}:
            args[name] = prompt
        elif isinstance(spec, dict) and "default" in spec:
            args[name] = spec["default"]
    if not any(isinstance(value, str) and value == term for value in args.values()):
        args["query"] = term
    return args


def _compact_result(result: Any) -> Any:
    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, list):
            return [_compact_result(item) for item in content[:5]]
        compact = {}
        for key, value in result.items():
            if key in {"content", "structuredContent", "isError", "text", "data", "result", "results"}:
                compact[key] = _compact_result(value)
        return compact or _truncate(str(result))
    if isinstance(result, list):
        return [_compact_result(item) for item in result[:5]]
    if isinstance(result, str):
        return _truncate(result)
    return result


def _truncate(value: str, limit: int = 1200) -> str:
    return value if len(value) <= limit else value[:limit] + "...[truncated]"


def _extract_jira_issues(payload: Any) -> list[dict[str, Any]]:
    queue: list[Any] = [payload]
    visited = 0
    while queue:
        visited += 1
        current = queue.pop(0)
        if isinstance(current, dict):
            issues = current.get("issues")
            if isinstance(issues, list):
                _trace_mcp_context("jira_extract_hit", path="issues", visited=visited, count=len(issues))
                return [item for item in issues if isinstance(item, dict)]
            item_type = str(current.get("type", "")).strip().lower()
            if item_type == "text" and isinstance(current.get("text"), str):
                queue.append(current.get("text"))
            for key in ("result", "data", "structuredContent", "content"):
                if key in current:
                    queue.append(current.get(key))
        elif isinstance(current, list):
            for item in current:
                queue.append(item)
        elif isinstance(current, str):
            text = current.strip()
            if not text:
                continue
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                continue
            queue.append(parsed)
    _trace_mcp_context("jira_extract_miss", visited=visited, payload_preview=_truncate(str(payload), limit=500))
    return []


def _trace_mcp_context(stage: str, **values: Any) -> None:
    details = " ".join(f"{key}={values[key]}" for key in sorted(values))
    print(f"{_trace_timestamp()} [MCP_CTX] {stage} {details}".rstrip())


def _trace_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
