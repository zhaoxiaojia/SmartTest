# Jira 标题文字次数规则实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Summary 和 Description 中明确的文字次数通过概率审查，并移除根目录旧 Jira 审查实现。

**Architecture:** 扩展 `support/jira_integration/audit/rules.py` 现有 Summary 末尾概率提取，并由 Summary 与 Description 复用同一个文字次数校验函数。删除 `jira_handler.py`，不增加兼容层。

**Tech Stack:** Python 3.10、正则表达式、pytest。

## Global Constraints

- 仅接受“出现/复现 + 中文或阿拉伯数字 + 次”的 Summary 末尾文字次数。
- `50%`、`1/2` 等现有格式保持有效。
- Description 的 `Reproducibility rate` 同时接受百分比、分数和文字次数；文字次数后允许一组括号说明。
- 不提交 `jira_format_audit.xlsx`。

---

### Task 1: Summary 文字次数规则

**Files:**
- Modify: `support/jira_integration/audit/rules.py`
- Test: `testing/self_tests/support/test_jira_format_audit_rules.py`

**Interfaces:**
- Consumes: `audit_issue(issue, base_url=...)`
- Produces: Summary 末尾概率提取结果与 `_valid_rate(value)`

- [ ] **Step 1: 写失败测试**

增加参数化用例，验证 `出现一次`、`复现2次`、`出现三次`不产生 `SUMMARY.PROBABILITY`；验证正文中的“次”、`偶现`和缺少“次”的数字仍失败；验证 Description 接受相同文字次数及其后一组中英文括号说明。

- [ ] **Step 2: 运行测试确认 RED**

Run: `.\.venv\Scripts\python.exe -m pytest -q testing/self_tests/support/test_jira_format_audit_rules.py`

Expected: 新增的有效文字次数用例因 `SUMMARY.PROBABILITY` 失败。

- [ ] **Step 3: 最小实现**

在现有 Summary 末尾提取表达式中加入文字次数分支；将百分比、分数和文字次数收敛到一个概率校验函数，供 Summary 与 Description 复用。Description 仅在调用前允许剥离文字次数后的一组中英文括号说明。

- [ ] **Step 4: 运行测试确认 GREEN**

Run: `.\.venv\Scripts\python.exe -m pytest -q testing/self_tests/support/test_jira_format_audit_rules.py testing/self_tests/support/test_jira_format_audit_service.py`

Expected: PASS。

### Task 2: 删除旧实现并交付

**Files:**
- Delete: `jira_handler.py`

**Interfaces:**
- Produces: `support/jira_integration/audit` 成为唯一 Jira 审查 owner。

- [ ] **Step 1: 删除旧脚本**

删除根目录 `jira_handler.py`；检索仓库，确认无生产代码依赖该文件。

- [ ] **Step 2: 完整验证**

Run: `.\.venv\Scripts\python.exe -m compileall -q support/jira_integration/audit`

Run: `git diff --check`

Expected: 两条命令均 exit 0，且无调试打印、兼容包装或重复规则实现。

- [ ] **Step 3: 提交**

仅暂存设计、计划、规则、长期回归测试和 `jira_handler.py` 删除；排除用户 XLSX。
