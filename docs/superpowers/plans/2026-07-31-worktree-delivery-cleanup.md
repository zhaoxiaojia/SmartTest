# SmartTest 未提交功能剥离与交付清理实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development and superpowers:verification-before-completion. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 剥离当前混合工作区，只交付有设计依据的 Jira 文字概率、Redmine Clone 补漏、交付规则和 durable 文档，移除未授权行为与临时产物，并让 `main` push 后工作区 clean。

**Architecture:** 以 `HEAD=37989e5` 和已批准设计为双基线，逐 hunk 保留合法功能，不整文件覆盖包含混合改动的 Redmine/Jira 文件。Mason 负责代码选择性清理和完整验证；Atlas 负责最终 staged diff、四个原子提交、push 和工作区清理验收。

**Tech Stack:** Python、PySide6/QML、pytest、Git、PowerShell

## Global Constraints

- 当前所有修改和未跟踪文件在处置前均视为用户数据；不得使用 `git reset --hard`、`git checkout --`、`git clean` 或工作区级覆盖。
- 生产文件通过 `apply_patch` 做精确 hunk 编辑；只删除设计明确列出的临时文件和延后 report 文件。
- 保留行为必须可追溯到 `docs/superpowers/specs/2026-07-22-redmine-batch-clone-jira-create-design.md` 或 `docs/superpowers/specs/2026-07-29-jira-text-rate-design.md`。
- 未授权行为必须从生产、测试、QML 和翻译中一致移除，不保留兼容路径、空 wrapper、废弃测试或临时诊断。
- Mason 不得提交、push、merge 或委派；Atlas 在验收后按原子范围提交并 push `main`。
- report 封装完全撤出本轮，工作区 clean 后由 Coco 重新启动。

---

### Task 1: 撤出未完成 report 封装

**Files:**
- Restore approved baseline behavior: `support/report/__init__.py`
- Restore approved baseline behavior: `support/report/xlsx.py`
- Restore approved baseline behavior: `support/jira_integration/audit/exporter.py`
- Restore approved baseline behavior: `testing/self_tests/support/test_report.py`
- Delete: `docs/superpowers/specs/2026-07-31-jira-xlsx-report-consolidation-design.md`
- Delete: `docs/superpowers/plans/2026-07-31-jira-xlsx-report-consolidation.md`

**Interfaces:**
- Produces: 上述四个 tracked 文件与 `HEAD` 内容一致，且不影响 `support/jira_integration/audit/rules.py` 等其他 Jira 修改。

- [ ] 使用 scoped `git diff` 识别仅由本轮 report 工作产生的 hunks。
- [ ] 通过 `apply_patch` 精确恢复四个 tracked 文件；不得用整工作区 checkout。
- [ ] 删除两个 report 设计/计划文件。
- [ ] 运行 `git diff --exit-code --` 核对四个 tracked 文件相对 `HEAD` 无差异。

### Task 2: 剥离未授权 Redmine/Jira 行为

**Files:**
- Modify: `support/jira_integration/core/create_schema.py`
- Modify: `support/jira_integration/services/create_issue_service.py`
- Modify: `support/jira_integration/services/create_schema_service.py`
- Modify: `tool/SmartHome/redmine/clone_controller.py`
- Modify: `tool/SmartHome/redmine/clone_draft.py`
- Modify: `tool/SmartHome/redmine/collector.py`
- Modify: `tool/SmartHome/redmine/issue_controller.py`
- Modify: `ui/example/bridge/RedmineBridge.py`
- Modify affected QML, FluentUI controls, translations and direct tests already present in `git status`.

**Interfaces:**
- Retain: async user search/generation、field-level patch、cascade true IDs/child validation、account identity、first-invalid focus、single controller/Bridge owner。
- Remove: Redmine Assignee auto-map/fallback、Software Release auto-map、Redmine Subject writeback/warning、Compare Status special case。

- [ ] **Step 1: 建立当前测试基线**

运行当前 Redmine/Jira focused suites，记录既有通过/失败，不把清理前失败伪装成本轮回归。

- [ ] **Step 2: 删除 Assignee 自动映射**

移除 Redmine assignee 收集、Jira user resolution、`assignee_accounts` 跨层传输、默认回退当前账户、专属 payload 排序和只为该映射存在的辅助函数/测试。保留通用 Jira 用户字段异步搜索与 account identity 编辑能力。

- [ ] **Step 3: 删除 Software Release 与 Compare Status 特例**

恢复为 Jira metadata 驱动的通用 schema/control/transport；Software Release 草稿初值保持设计规定的空值，Compare Status 不做名称特判。保留 Channel of Reporter 的 cascade 父子真实 ID 和子项必填合同。

- [ ] **Step 4: 删除 Redmine Subject 回写**

移除 `jira_prefixed_subject()`、浏览器 edit-form Subject 更新、controller finalize writeback、Bridge callback、warning 状态、UI warning 和专属测试/翻译。Jira 创建结果仍更新 SmartTest clone 状态、key 和链接。

- [ ] **Step 5: 保留并精简合法补漏**

逐项验证异步迟到结果保护、窄字段 patch、非法字段聚焦、cascade、用户 identity 和 controller ownership；删除重复投影、薄 helper、临时日志及仅保护实现形状的测试。

- [ ] **Step 6: 翻译和 QML 一致性**

去除只服务于 Subject warning 或未授权字段行为的翻译；保留合法 UI 固定文本。若 TS location 因删除文本改变，使用仓库既有翻译更新方式，避免全文件无关 churn。

### Task 3: 验证 Jira 文字概率独立范围

**Files:**
- Keep: `support/jira_integration/audit/rules.py`
- Keep durable tests: `testing/self_tests/support/test_jira_format_audit_rules.py`
- Keep docs: `docs/superpowers/specs/2026-07-29-jira-text-rate-design.md`
- Keep docs: `docs/superpowers/plans/2026-07-29-jira-text-rate.md`

- [ ] 核对代码仅实现 Summary/Description 明确文字次数概率识别和 owner 收敛。
- [ ] 移除与文字概率无关的规则行为或探索性测试。
- [ ] 运行 Jira audit rules/service focused tests并记录 exit code。

### Task 4: 全量相关验证和差异质量

- [ ] 运行 Jira create schema/service、Jira audit、Redmine clone controller/draft/context、Redmine Bridge、Auth profile、Redmine QML、FluentUI 控件和 owned translations 测试。
- [ ] 对变更 Python owner 运行 `compileall -q`。
- [ ] 按 UI skill 验证 QML/翻译资源链；普通调试不构建安装包。
- [ ] `git diff --check`。
- [ ] 扫描未授权符号与行为：`jira_prefixed_subject`、`update_issue_subject`、`assignee_accounts`、Redmine `Software Release` 初值、`compare_status` 特判和 Subject warning 均不存在。
- [ ] 输出保留/移除矩阵、变更文件、测试命令/exit code、限制、生产代码净增长和 relevant `git status`。

### Task 5: Atlas 原子提交与 clean

**Owner:** Atlas only

- [ ] **Commit 1: Jira 文字概率**

只 stage Jira audit rules、durable tests、Jira text-rate spec/plan。检查 staged diff 后提交业务结果。

- [ ] **Commit 2: Redmine Clone 设计补漏**

只 stage Redmine/Jira create schema/controller/Bridge/QML/translation 及其 durable tests。检查 staged diff 不含未授权行为和 report 文件后提交。

- [ ] **Commit 3: 双 Codex 交付规则**

只 stage `AGENTS.md` 和 `.codex/skills/smarttest-dual-codex-delivery/SKILL.md`。

- [ ] **Commit 4: Durable 文档**

只 stage与已提交 Confluence 审查直接对应的 `docs/superpowers/specs`、`docs/superpowers/plans`，以及本次 cleanup spec/plan。不得 stage `.superpowers` worker 报告、浏览器状态或生成物。

- [ ] **精确清理临时文件**

验证以下绝对路径均位于 `D:\SmartTest` 后，用 PowerShell `Remove-Item -LiteralPath` 对精确文件/目录逐项清理：

- `.superpowers/brainstorm`
- `.superpowers/mason-confluence-audit-guidance-round2-report.md`
- `.superpowers/mason-confluence-audit-live-business-fix-report.md`
- `.superpowers/mason-confluence-audit-report.md`
- `.superpowers/mason-confluence-audit-round4-report.md`
- `.superpowers/mason-confluence-audit-single-seed-report.md`
- `jira_format_audit.xlsx`
- `output`
- `tmp`

- [ ] 重新运行最终测试和 `git diff --check`，确认 `git status --short` 为空。
- [ ] 确认当前分支为 `main`，push 到其配置远端。
- [ ] push 后再次确认 `git status --short` 为空并报告提交哈希。
