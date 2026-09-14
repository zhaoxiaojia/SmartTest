"""Semantic second review for every deterministic Jira violation."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
import json

from core.ai import (
    AIChatMessage, AIConfigurationError, AIResponseError, AITransportError,
    create_chat_client,
)

from .models import AIReviewStatus, AuditViolation, IssueAuditResult
from .rules import active_rules


_MAX_REVIEW_WORKERS = 6


def _public_deepseek_client():
    return create_chat_client("public-deepseek")


def review_failed_issues(results, *, client_factory=None, cancellation, progress):
    failed_indexes = [index for index, result in enumerate(results) if result.violations]
    if not failed_indexes:
        progress("ai_reviewing", 0, 0)
        return results
    factory = client_factory or _public_deepseek_client
    try:
        client = factory()
    except AIConfigurationError:
        return _mark_all(results, failed_indexes, AIReviewStatus.UNCONFIGURED, "configuration", progress)
    except Exception:
        return _mark_all(results, failed_indexes, AIReviewStatus.FAILED, "unexpected", progress)
    with ThreadPoolExecutor(
        max_workers=min(_MAX_REVIEW_WORKERS, len(failed_indexes)),
        thread_name_prefix="jira-ai-review",
    ) as executor:
        futures = {
            executor.submit(review_issue, results[index], client): index
            for index in failed_indexes
        }
        for completed, future in enumerate(as_completed(futures), 1):
            cancellation.raise_if_cancelled()
            results[futures[future]] = future.result()
            progress("ai_reviewing", completed, len(failed_indexes))
    return results


def review_issue(result: IssueAuditResult, client) -> IssueAuditResult:
    try:
        response = client.chat_completion(
            [
                AIChatMessage("system", "只输出 Jira 规范复审 JSON，不展示推理过程，不新增规则。"),
                AIChatMessage("user", _prompt(result)),
            ],
            response_format={"type": "json_object"}, temperature=0, max_tokens=2400,
        )
        decisions = _parse_response(
            response.content, issue_key=result.key,
            requested_rule_ids={item.rule_id for item in result.violations},
        )
    except AIConfigurationError:
        return _review_failure(result, AIReviewStatus.UNCONFIGURED, "configuration")
    except TimeoutError:
        return _review_failure(result, AIReviewStatus.FAILED, "timeout")
    except AITransportError as error:
        category = "timeout" if error.category == "timeout" else "transport"
        return _review_failure(result, AIReviewStatus.FAILED, category)
    except AIResponseError:
        return _review_failure(result, AIReviewStatus.FAILED, "invalid_response")
    except (TypeError, ValueError):
        return _review_failure(result, AIReviewStatus.FAILED, "invalid_response")
    except Exception:
        return _review_failure(result, AIReviewStatus.FAILED, "unexpected")
    return _merge(result, decisions)


def _prompt(result):
    rules = {rule.rule_id: rule for rule in active_rules()}
    payload = {
        "issue_key": result.key,
        "summary": result.summary,
        "description": result.description,
        "violations": [
            {
                "rule_id": item.rule_id,
                "field": item.field,
                "requirement": rules[item.rule_id].requirement,
                "initial_reason": item.reason,
                **({"observed": item.observed} if item.observed != result.description else {}),
            }
            for item in result.violations
        ],
    }
    return (
        "复核脚本判定的全部 Jira 违规。只根据完整原文判断对应规则是否实际满足；"
        "不得新增规则。decisions 必须为每条输入违规各返回一次，result 只能是 PASS 或 FAIL；"
        "FAIL 必须给出非空 reason，guidance 可为空。\n"
        + json.dumps(payload, ensure_ascii=False)
    )


def _parse_response(content, *, issue_key, requested_rule_ids):
    try:
        payload = json.loads(str(content or "").strip())
    except (json.JSONDecodeError, TypeError):
        raise ValueError("invalid AI JSON") from None
    if not isinstance(payload, dict) or payload.get("issue_key") != issue_key:
        raise ValueError("invalid AI issue key")
    decisions = payload.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("invalid AI decisions")
    normalized = {}
    for decision in decisions:
        if not isinstance(decision, dict):
            raise ValueError("invalid AI decision")
        rule_id = decision.get("rule_id")
        if rule_id not in requested_rule_ids or rule_id in normalized:
            raise ValueError("invalid AI rule decision")
        outcome = decision.get("result")
        reason, guidance = decision.get("reason", ""), decision.get("guidance", "")
        if outcome not in {"PASS", "FAIL"} or not isinstance(reason, str) or not isinstance(guidance, str):
            raise ValueError("invalid AI decision")
        if outcome == "FAIL" and not reason.strip():
            raise ValueError("AI failure reason is required")
        normalized[rule_id] = (outcome, reason.strip(), guidance.strip())
    if set(normalized) != requested_rule_ids:
        raise ValueError("incomplete AI decisions")
    return normalized


def _merge(result, decisions):
    final: list[AuditViolation] = []
    passed_count = failed_count = 0
    for violation in result.violations:
        outcome, reason, guidance = decisions[violation.rule_id]
        if outcome == "PASS":
            passed_count += 1
        else:
            failed_count += 1
            final.append(replace(violation, reason=reason, guidance=guidance or violation.guidance))
    return replace(
        result, passed=not final, violations=tuple(final),
        ai_review_status=AIReviewStatus.COMPLETED, ai_failure_category=None,
        ai_passed_count=passed_count, ai_failed_count=failed_count,
    )


def _review_failure(result, status, category):
    return replace(result, ai_review_status=status, ai_failure_category=category)


def _mark_all(results, indexes, status, category, progress):
    for completed, index in enumerate(indexes, 1):
        results[index] = _review_failure(results[index], status, category)
        progress("ai_reviewing", completed, len(indexes))
    return results
