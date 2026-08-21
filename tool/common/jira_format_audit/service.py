from __future__ import annotations

import json
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime
from typing import Protocol
from urllib.parse import parse_qs, urlsplit

from support.ai import (
    AIChatClient,
    AIChatMessage,
    AIConfigurationError,
    AIResponseError,
    AITransportError,
    create_chat_client,
)

from .models import (
    AIReviewStatus,
    AuditReport,
    AuditViolation,
    IssueAuditResult,
    ResolvedAuditInput,
)
from .rules import (
    active_rules,
    ai_reviewable_violations,
    audit_issue,
    is_audit_eligible,
    issue_description,
)


_URL = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
_ISSUE_KEY = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")
_FIELDS = (
    "creator",
    "summary",
    "description",
    "components",
)
_AI_MAX_WORKERS = 6


class _AuditClient(Protocol):
    def fetch_filter(self, filter_id: str) -> dict: ...
    def search_page(self, jql: str, **kwargs): ...


def resolve_audit_input(
    text: str, *, base_url: str, client: _AuditClient
) -> ResolvedAuditInput:
    original = str(text or "").strip()
    if not original:
        raise ValueError("请输入 JQL 或 Jira URL。")
    resolved = (
        _resolve_url(original, base_url, client)
        if _URL.match(original)
        else ResolvedAuditInput("jql", original, original)
    )
    try:
        client.search_page(
            resolved.jql,
            start_at=0,
            max_results=1,
            fields=_FIELDS,
            validate_query="strict",
        )
    except Exception as exc:
        raise ValueError(
            "JQL validation failed. Check the query and Jira permissions."
        ) from exc
    return resolved


def _resolve_url(
    original: str, base_url: str, client: _AuditClient
) -> ResolvedAuditInput:
    parsed, base = urlsplit(original), urlsplit(str(base_url or "").strip())
    if parsed.scheme.casefold() not in {"http", "https"}:
        raise ValueError("Jira URLs must use HTTP or HTTPS.")
    if not parsed.hostname or not base.hostname:
        raise ValueError("The Jira URL is malformed.")
    if parsed.hostname.casefold() != base.hostname.casefold():
        raise ValueError("The Jira URL host must match the configured Jira host.")

    query = parse_qs(parsed.query, keep_blank_values=True)
    jql = str((query.get("jql") or [""])[0] or "").strip()
    if jql:
        return ResolvedAuditInput("jql_url", original, jql)

    browse = re.fullmatch(r"/browse/([^/]+)/?", parsed.path)
    if browse:
        key = browse.group(1).strip()
        if not _ISSUE_KEY.fullmatch(key):
            raise ValueError("The Jira issue URL contains an invalid issue key.")
        return ResolvedAuditInput("issue_url", original, f'key = "{key}"')

    filter_id = str((query.get("filter") or [""])[0] or "").strip()
    path_filter = re.fullmatch(r"/filter/(\d+)/?", parsed.path)
    filter_id = filter_id or (path_filter.group(1) if path_filter else "")
    if filter_id.isdigit():
        try:
            payload = client.fetch_filter(filter_id)
        except Exception as exc:
            raise ValueError(
                "The Jira filter could not be loaded. Check its permissions."
            ) from exc
        jql = str((payload or {}).get("jql", "") or "").strip()
        if not jql:
            raise ValueError("The Jira filter does not contain JQL.")
        return ResolvedAuditInput("filter_url", original, jql)
    raise ValueError("Use a Jira issue, filter, or search URL.")


class JiraAuditService:
    def __init__(
        self,
        client: _AuditClient,
        *,
        base_url: str,
    ):
        self._client = client
        self._base_url = str(base_url or "").rstrip("/")

    def run(
        self, resolved: ResolvedAuditInput, progress: Callable[[str, int, int], None]
    ) -> AuditReport:
        seen_issue_keys = set()
        results = []
        candidate_indexes = []
        candidate_descriptions = {}
        eligible_count = 0
        start_at = 0
        while True:
            page = self._client.search_page(
                resolved.jql,
                start_at=start_at,
                fields=_FIELDS,
                validate_query="strict",
            )
            page_issues = page.issues
            page_total = page.total
            page_size = len(page_issues)
            page_is_last = page.is_last
            del page
            for offset in range(page_size):
                issue = page_issues[offset]
                page_issues[offset] = None
                issue_key = str(issue.get("key", "") or "").strip().casefold()
                if issue_key and issue_key in seen_issue_keys:
                    del issue
                    continue
                if issue_key:
                    seen_issue_keys.add(issue_key)
                if not is_audit_eligible(issue):
                    del issue
                    continue
                eligible_count += 1
                description = issue_description(issue)
                result = audit_issue(issue, base_url=self._base_url)
                result_index = len(results)
                results.append(result)
                if ai_reviewable_violations(result, description=description):
                    candidate_indexes.append(result_index)
                    candidate_descriptions[result_index] = description
                del description, issue, result
            del page_issues
            next_start = start_at + page_size
            progress("fetching", min(next_start, page_total), page_total)
            if page_is_last or not page_size or next_start >= page_total:
                break
            start_at = next_start

        if eligible_count:
            progress("rule_auditing", eligible_count, eligible_count)
        else:
            progress("rule_auditing", 0, 0)

        if not candidate_indexes:
            progress("ai_reviewing", 0, 0)
        else:
            try:
                ai_client = create_chat_client()
            except AIConfigurationError:
                failure_status = AIReviewStatus.UNCONFIGURED
            except Exception:
                failure_status = AIReviewStatus.FAILED
            else:
                failure_status = None
            if failure_status:
                candidate_descriptions.clear()
                for completed, index in enumerate(candidate_indexes, 1):
                    results[index] = _review_failure(
                        results[index],
                        failure_status,
                    )
                    progress(
                        "ai_reviewing",
                        completed,
                        len(candidate_indexes),
                    )
            else:
                worker_count = min(_AI_MAX_WORKERS, len(candidate_indexes))
                with ThreadPoolExecutor(max_workers=worker_count) as executor:
                    futures = {
                        executor.submit(
                            _review_issue,
                            results[index],
                            ai_client,
                            candidate_descriptions[index],
                        ): index
                        for index in candidate_indexes
                    }
                    for completed, future in enumerate(
                        as_completed(futures),
                        1,
                    ):
                        index = futures[future]
                        try:
                            results[index] = future.result()
                        except Exception:
                            results[index] = _review_failure(
                                results[index],
                                AIReviewStatus.FAILED,
                            )
                        progress(
                            "ai_reviewing",
                            completed,
                            len(candidate_indexes),
                        )
                candidate_descriptions.clear()
        progress("finalizing", len(results), len(results))
        return AuditReport(
            resolved,
            datetime.now(),
            active_rules(),
            tuple(results),
        )


def _review_issue(
    result: IssueAuditResult,
    client: AIChatClient,
    description: str,
) -> IssueAuditResult:
    candidates = ai_reviewable_violations(
        result,
        description=description,
    )
    try:
        response = client.chat_completion(
            [
                AIChatMessage(
                    "system",
                    "只输出 Jira 模糊边界复核 JSON，不展示推理过程。",
                ),
                AIChatMessage(
                    "user",
                    _review_prompt(result, candidates, description),
                ),
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=1800,
        )
        decisions = _parse_review_response(
            str(response.content or ""),
            issue_key=result.key,
            requested_rule_ids={item.rule_id for item in candidates},
        )
    except AIConfigurationError:
        return _review_failure(result, AIReviewStatus.UNCONFIGURED)
    except (TimeoutError, AITransportError, AIResponseError, TypeError, ValueError):
        return _review_failure(result, AIReviewStatus.FAILED)
    except Exception:
        return _review_failure(result, AIReviewStatus.FAILED)
    return _merge_review(result, candidates, decisions)


def _review_prompt(
    result: IssueAuditResult,
    candidates: tuple[AuditViolation, ...],
    description: str,
) -> str:
    rules_by_id = {rule.rule_id: rule for rule in active_rules()}
    payload = {
        "issue_key": result.key,
        "jira_fields": {
            "Summary": result.summary,
            "Description": description,
        },
        "violations": [
            {
                "rule_id": item.rule_id,
                "requirement": rules_by_id[item.rule_id].requirement,
                "jira_field": item.field,
                "initial_reason": item.reason,
            }
            for item in candidates
        ],
    }
    return (
        "你只复核输入中字符规则无法确定的 Jira 模糊边界，不新增任何规则。"
        "人类能够清楚理解且语义满足规范时判定 PASS；确实缺少必需信息时判定 FAIL。"
        "应结合 jira_fields 中全部自然语言判断，不要求信息必须出现在初筛指定位置；"
        "只要 Jira 整体已经明确表达所需信息就判定 PASS。"
        "返回一个 JSON 对象，issue_key 必须与输入相同；decisions 必须为每个输入规则"
        "返回且只返回一次。每项包含 rule_id、result（PASS 或 FAIL）、reason 和 guidance；"
        "FAIL 必须提供非空 reason。\n"
        + json.dumps(payload, ensure_ascii=False)
    )


def _parse_review_response(
    content: str,
    *,
    issue_key: str,
    requested_rule_ids: set[str],
) -> dict[str, dict[str, str]]:
    try:
        payload = json.loads(content.strip())
    except (json.JSONDecodeError, TypeError):
        raise ValueError("invalid AI JSON") from None
    if not isinstance(payload, dict) or payload.get("issue_key") != issue_key:
        raise ValueError("invalid AI issue key")
    decisions = payload.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("invalid AI decisions")

    normalized: dict[str, dict[str, str]] = {}
    for decision in decisions:
        if not isinstance(decision, dict):
            raise ValueError("invalid AI decision")
        rule_id = decision.get("rule_id")
        if (
            not isinstance(rule_id, str)
            or rule_id not in requested_rule_ids
            or rule_id in normalized
        ):
            raise ValueError("invalid AI rule decision")
        outcome = decision.get("result")
        if outcome not in {"PASS", "FAIL"}:
            raise ValueError("invalid AI result")
        reason = decision.get("reason", "")
        guidance = decision.get("guidance", "")
        if not isinstance(reason, str) or not isinstance(guidance, str):
            raise ValueError("invalid AI decision text")
        reason = reason.strip()
        guidance = guidance.strip()
        if outcome == "FAIL" and not reason:
            raise ValueError("AI failure reason is required")
        normalized[rule_id] = {
            "result": outcome,
            "reason": reason,
            "guidance": guidance,
        }
    if set(normalized) != requested_rule_ids:
        raise ValueError("incomplete AI decisions")
    return normalized


def _merge_review(
    result: IssueAuditResult,
    candidates: tuple[AuditViolation, ...],
    decisions: dict[str, dict[str, str]],
) -> IssueAuditResult:
    candidate_ids = {item.rule_id for item in candidates}
    final_violations = []
    for violation in result.violations:
        if violation.rule_id not in candidate_ids:
            final_violations.append(violation)
            continue
        decision = decisions[violation.rule_id]
        if decision["result"] == "PASS":
            continue
        final_violations.append(
            replace(
                violation,
                reason=decision["reason"],
                guidance=decision["guidance"] or violation.guidance,
            )
        )
    return replace(
        result,
        passed=not final_violations,
        violations=tuple(final_violations),
        ai_review_status=AIReviewStatus.COMPLETED,
    )


def _review_failure(
    result: IssueAuditResult,
    status: AIReviewStatus,
) -> IssueAuditResult:
    return replace(
        result,
        ai_review_status=status,
    )
