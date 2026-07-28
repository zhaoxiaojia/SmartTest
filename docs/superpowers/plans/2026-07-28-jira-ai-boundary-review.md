# Jira AI 模糊边界复核实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `jira_handler.py` 中先用确定性规则筛选全部 Jira，再以最多 4 个线程并发调用 AI 裁决模糊边界，并向终端持续输出总体进度。

**Architecture:** 保留 `validate_issue` 作为字符规则唯一所有者，为违规增加内部可复核分类；新增 AI 请求封装和批量并发协调器，只接收模糊项并返回现有 violation 字典。`run` 先完成全部硬规则审查，再调用协调器合并 AI 结果，最后沿用现有 Excel 导出。

**Tech Stack:** Python 标准库、`concurrent.futures.ThreadPoolExecutor`、现有 `openai` SDK、`unittest`、现有 XLSX 导出实现。

## Global Constraints

- 生产代码只修改根目录 `jira_handler.py`。
- 不修改 `coco.py`、Jira 查询条件、创建人白名单、Excel 列结构或纵向合并格式。
- AI 只裁决配置为模糊边界的现有违规，不独立审查全部 Jira，不新增规则范围。
- 明确缺失、空值、冒号缺失和明确拼写错误不发送 AI。
- 默认最多 4 个线程；并发单位是一个 Jira 的全部模糊项。
- AI 请求失败时保留原字符规则结果，报告生成不得中断。
- 离线测试不得访问 Jira 或 AI 内网接口，不输出 API Key。

---

### Task 1: 违规分流

**Files:**
- Modify: `jira_handler.py`
- Create: `test_jira_handler_ai.py`

**Interfaces:**
- Produces: `AI_REVIEWABLE_RULES: frozenset[str]`
- Produces: `_partition_ai_review_candidates(results: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]`
- Candidate item keeps the original result and only its reviewable violations.

- [ ] **Step 1: Write the failing tests**

Create `test_jira_handler_ai.py` with `unittest` cases that hand-build validation results:

```python
import unittest

import jira_handler


class AiBoundaryPartitionTests(unittest.TestCase):
    def test_only_fuzzy_rate_format_is_sent_to_ai(self):
        result = {
            "issue_key": "IPTV-42126",
            "violations": [
                {"rule_id": "DESCRIPTION.RATE_FORMAT", "current_value": "12 小时，1/1 Fail"},
                {"rule_id": "DESCRIPTION.STEPS_TO_REPRODUCE", "current_value": ""},
            ],
        }

        candidates, untouched = jira_handler._partition_ai_review_candidates([result])

        self.assertEqual(
            [item["rule_id"] for item in candidates[0]["violations"]],
            ["DESCRIPTION.RATE_FORMAT"],
        )
        self.assertEqual(
            [item["rule_id"] for item in untouched[0]["violations"]],
            ["DESCRIPTION.STEPS_TO_REPRODUCE"],
        )

    def test_jira_without_fuzzy_violations_is_not_a_candidate(self):
        result = {
            "issue_key": "DEMO-1",
            "violations": [
                {"rule_id": "DESCRIPTION.STEPS_TO_REPRODUCE", "current_value": ""}
            ],
        }
        candidates, untouched = jira_handler._partition_ai_review_candidates([result])
        self.assertEqual(candidates, [])
        self.assertEqual(untouched[0]["issue_key"], "DEMO-1")
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m unittest test_jira_handler_ai.AiBoundaryPartitionTests -v
```

Expected: FAIL because `_partition_ai_review_candidates` does not exist.

- [ ] **Step 3: Implement minimal centralized classification**

Add `AI_REVIEWABLE_RULES` beside the rule configuration. Initially include only semantic or extraction-boundary rules already observed in reports:

```python
AI_REVIEWABLE_RULES = frozenset(
    {
        "DESCRIPTION.RATE_FORMAT",
        "DESCRIPTION.COMPARISON",
        "DESCRIPTION.NOTES_HW",
        "DESCRIPTION.NOTES_SW",
    }
)
```

Implement `_partition_ai_review_candidates` without changing violation dictionaries or mutating input. Preserve the original result metadata in both outputs.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```powershell
python -m unittest test_jira_handler_ai.AiBoundaryPartitionTests -v
```

Expected: PASS.

### Task 2: 单 Jira AI 结构化裁决

**Files:**
- Modify: `jira_handler.py`
- Modify: `test_jira_handler_ai.py`

**Interfaces:**
- Produces: `_review_issue_with_ai(candidate, *, client, model) -> dict[str, Any]`
- Returned mapping: `{"issue_key": str, "decisions": list[dict], "error": str | None, "tokens": int}`
- Decision mapping: `{"rule_id": str, "result": "PASS" | "FAIL", "reason": str, "guidance": str}`

- [ ] **Step 1: Write failing response-contract tests**

Add a small fake client that mirrors the OpenAI response shape and tests:

```python
def test_ai_review_accepts_structured_decisions(self):
    candidate = {
        "issue_key": "IPTV-42126",
        "violations": [
            {
                "rule_id": "DESCRIPTION.RATE_FORMAT",
                "requirement": "复现概率必须是百分比或分数",
                "current_value": "[Reproducibility rate]: 12 小时，1/1 Fail",
                "reason": "Description 中的复现概率格式无效。",
            }
        ],
    }
    client = FakeClient(
        '{"issue_key":"IPTV-42126","decisions":['
        '{"rule_id":"DESCRIPTION.RATE_FORMAT","result":"PASS",'
        '"reason":"内容包含合法分数 1/1。","guidance":""}]}'
    )

    reviewed = jira_handler._review_issue_with_ai(
        candidate, client=client, model="test-model"
    )

    self.assertIsNone(reviewed["error"])
    self.assertEqual(reviewed["decisions"][0]["result"], "PASS")
```

Add separate cases for malformed JSON and a returned unknown rule ID. The malformed response must set `error`; unknown rule IDs must be discarded so AI cannot expand scope.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m unittest test_jira_handler_ai.AiReviewContractTests -v
```

Expected: FAIL because `_review_issue_with_ai` does not exist.

- [ ] **Step 3: Implement the request boundary**

Reuse `OpenAI` through a local import inside the client factory so importing `jira_handler.py` does not require network access. Build one compact JSON request per Jira containing only original fields and candidate violations. Require JSON-only output, extract one JSON object, validate:

- returned Issue Key equals requested key;
- each decision rule is in the candidate rule set;
- each candidate rule receives exactly one `PASS` or `FAIL`;
- reasons are non-empty for `FAIL`;
- malformed or incomplete output returns `error` instead of raising.

Do not include credentials in exceptions or returned error strings.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```powershell
python -m unittest test_jira_handler_ai.AiReviewContractTests -v
```

Expected: PASS.

### Task 3: 并发协调、进度和失败降级

**Files:**
- Modify: `jira_handler.py`
- Modify: `test_jira_handler_ai.py`

**Interfaces:**
- Produces: `review_fuzzy_violations_with_ai(results, *, client, model, max_workers=4, progress_stream=sys.stdout) -> list[dict[str, Any]]`
- The returned list has the same result order and schema accepted by `export_xlsx`.

- [ ] **Step 1: Write failing orchestration tests**

Add tests with a deterministic reviewer injection or fake client:

```python
def test_parallel_review_removes_pass_and_rewrites_fail(self):
    results = make_results_with_two_fuzzy_issues()
    client = FakeClientByIssue(
        {
            "A-1": pass_decision("A-1", "DESCRIPTION.RATE_FORMAT"),
            "A-2": fail_decision(
                "A-2",
                "DESCRIPTION.COMPARISON",
                "只写了章节标题，没有实际对比内容。",
                "补充对比结果或明确写无需对比。",
            ),
        }
    )
    progress = io.StringIO()

    merged = jira_handler.review_fuzzy_violations_with_ai(
        results,
        client=client,
        model="test-model",
        max_workers=2,
        progress_stream=progress,
    )

    self.assertEqual(merged[0]["violations"], [])
    self.assertEqual(
        merged[1]["violations"][0]["reason"],
        "只写了章节标题，没有实际对比内容。",
    )
    self.assertIn("2/2", progress.getvalue())
```

Add tests proving:

- one Jira with multiple fuzzy violations produces one client request;
- a client exception preserves the original fuzzy violation and changes its reason to include `AI 复核失败，保留规则初筛结果`;
- a hard violation remains unchanged and is never submitted;
- result order remains identical to input order.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m unittest test_jira_handler_ai.AiReviewOrchestrationTests -v
```

Expected: FAIL because the coordinator does not exist.

- [ ] **Step 3: Implement minimal concurrent coordinator**

Use `ThreadPoolExecutor(max_workers=min(max_workers, candidate_count))` and `as_completed`. Update a single-line progress bar after every completed future:

```text
\rAI 复核进度 [████████████░░░░] 75%  30/40
```

Write a final newline and summary. Merge decisions by Issue Key and rule ID:

- `PASS`: remove only that fuzzy violation;
- `FAIL`: preserve rule metadata and replace `reason`/`guidance` with AI text;
- error/missing decision: preserve original violation and add the failure marker.

Recalculate each result’s `overall_result` from the final violations.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```powershell
python -m unittest test_jira_handler_ai.AiReviewOrchestrationTests -v
```

Expected: PASS.

### Task 4: 运行入口集成和完整验证

**Files:**
- Modify: `jira_handler.py`
- Modify: `test_jira_handler_ai.py`

**Interfaces:**
- Consumes: `review_fuzzy_violations_with_ai`
- Preserves: `run(config: dict[str, Any]) -> int`

- [ ] **Step 1: Write failing run-flow tests**

Patch only external boundaries (`fetch_jira_issues`, client creation, and `export_xlsx`) and call real `run`. Assert:

- validation occurs before AI review;
- AI-disabled or missing configuration still exports hard-rule results;
- AI-enabled configuration passes model and `max_workers=4`;
- no candidates prints `无需 AI 复核` and never creates a client.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m unittest test_jira_handler_ai.JiraRunAiIntegrationTests -v
```

Expected: FAIL because `run` does not invoke AI review.

- [ ] **Step 3: Integrate configuration and flow**

Extend existing root configuration with:

```python
"ai_review": {
    "enabled": True,
    "base_url": os.getenv("JIRA_AUDIT_AI_BASE_URL", ""),
    "api_key": os.getenv("JIRA_AUDIT_AI_API_KEY", ""),
    "model": os.getenv("JIRA_AUDIT_AI_MODEL", "Amlogic_Local/Kimi-K2.7-Code"),
    "max_workers": 4,
}
```

Do not hard-code new credentials. In `run`, after `validate_issues` and before `export_xlsx`, invoke AI only when enabled, candidates exist, and configuration is complete. Missing configuration prints a concise degradation message and exports original results.

- [ ] **Step 4: Run focused and regression tests**

Run:

```powershell
python -m unittest test_jira_handler_ai -v
python -m py_compile jira_handler.py
git diff --check -- jira_handler.py test_jira_handler_ai.py
```

Expected: all commands exit 0.

- [ ] **Step 5: Clean delivery residue**

Review the scoped diff and remove temporary debug prints, source-shape assertions, repeated fixtures and abandoned compatibility paths. Keep only progress/status output required by the design and durable behavior tests.

- [ ] **Step 6: Report without running intranet calls**

Report changed files, exact commands and exit codes, the fact that AI/Jira integration was not executed locally, relevant `git status`, reuse decision (`ThreadPoolExecutor` and existing `openai` SDK), and net production-code growth.
