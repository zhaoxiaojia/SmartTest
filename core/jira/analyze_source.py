"""Jira_Analytics_Web `/api/analyze` 接口的数据源。

一次 `fetch()` 返回一个 JQL 的完整数据：`(服务端实际执行的 jql, issue 字典列表)`。
issue 字段与服务端返回保持一致，不在本模块加工。
"""

from __future__ import annotations

import json
from typing import Any, Callable

import requests


ANALYZE_PATH = "/api/analyze"

# (phase, current, total)，phase 取值 issues / verify / comments
ProgressCallback = Callable[[str, int, int], None]


class JiraAnalyzeError(RuntimeError):
    """analyze 接口不可用、解析失败或数据不完整。"""


class JiraAnalyzeSource:
    """调用 Jira_Analytics_Web 的 `/api/analyze` 取回完整分析数据。

    服务端 NDJSON 流依次输出 total、progress、issue、done；issue 行在 verify 与
    comments 全部解析完成后才输出，因此 `fetch()` 以读到 done 为返回条件。流提前
    结束或出现 error 行都视为失败，不返回半成品数据。
    """

    def __init__(self, base_url: str, username: str, password: str, connect_timeout: float = 10):
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._connect_timeout = connect_timeout

    def fetch(
        self,
        jql: str,
        include_verify: bool = True,
        include_comments: bool = True,
        date_from: str = "",
        date_to: str = "",
        jira_url: str | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> tuple[str, list[dict[str, Any]]]:
        """按 jql 取回完整数据，返回 `(服务端实际执行的 jql, issue 列表)`。

        读取不设超时，问题量大时需等待服务端逐条解析完成；`on_progress` 用于接收
        三阶段进度。`date_from` / `date_to` 透传服务端，仅影响 verify。
        """
        payload: dict[str, Any] = {
            "jql": jql,
            "username": self._username,
            "password": self._password,
            "include_verify": include_verify,
            "include_comments": include_comments,
            "date_from": date_from,
            "date_to": date_to,
        }
        if jira_url:
            payload["jira_url"] = jira_url
        url = self._base_url + ANALYZE_PATH

        try:
            response = requests.post(
                url, json=payload, stream=True, timeout=(self._connect_timeout, None)
            )
        except requests.RequestException as error:
            raise JiraAnalyzeError(f"无法访问 analyze 服务 {url}: {error}") from error

        with response:
            if response.status_code != 200:
                raise JiraAnalyzeError(_failure_detail(response))
            if "ndjson" not in (response.headers.get("Content-Type") or ""):
                raise JiraAnalyzeError(_failure_detail(response))

            issues: list[dict[str, Any]] = []
            effective_jql = jql
            done = False
            try:
                for raw_line in response.iter_lines():
                    if not raw_line:
                        continue
                    line = raw_line.decode("utf-8")
                    try:
                        message = json.loads(line)
                    except ValueError as error:
                        raise JiraAnalyzeError(f"analyze 数据流包含非 JSON 行: {line[:200]}") from error
                    kind = message.get("type")
                    if kind == "issue":
                        issues.append(message["data"])
                    elif kind == "progress":
                        if on_progress is not None:
                            on_progress(
                                message.get("phase", ""),
                                message.get("current", 0),
                                message.get("total", 0),
                            )
                    elif kind == "done":
                        effective_jql = message.get("jql") or jql
                        done = True
                        break
                    elif kind == "error":
                        raise JiraAnalyzeError(f"analyze 服务解析失败: {message.get('message')}")
                    # total 行等其它类型不参与取数
            except requests.RequestException as error:
                raise JiraAnalyzeError(f"analyze 数据流中断: {error}") from error

            if not done:
                raise JiraAnalyzeError("analyze 数据流未返回 done，数据不完整")
            return effective_jql, issues


def _failure_detail(response: requests.Response) -> str:
    """把服务端的失败响应转成可读报错文本。"""
    try:
        payload = response.json()
    except ValueError:
        return f"HTTP {response.status_code}: {response.text[:200]}"
    if isinstance(payload, dict) and payload.get("message"):
        return str(payload["message"])
    return f"HTTP {response.status_code}: {str(payload)[:200]}"
