# SmartTest 未提交功能剥离与交付清理设计

## 目标

在继续全局 report 封装前，审计并剥离当前工作区中混合存在的 Jira 文字概率、Redmine 批量 Clone 补漏、交付规则、Confluence durable 文档、未完成 report 封装和临时生成物。只保留有已批准设计依据的行为，删除未授权或与设计冲突的扩展，形成原子提交并最终使工作区 clean。

## 基线

当前 `main` 的 `HEAD` 为 `37989e5 feat: add streamlined Confluence project audit`。Redmine 批量 Clone 的主体设计已通过历史提交进入 `main`，当前相关修改属于主体功能之上的补漏与额外扩展。Jira 文字概率存在独立设计和实施计划，Confluence 交付记录明确将其列为并发且未包含的改动。

所有当前修改和未跟踪文件在清理前均视为需要逐项处置的数据，不使用 broad reset、checkout 或工作区级清理命令。

## 保留并交付

### Jira 文字概率

保留 `support/jira_integration/audit/rules.py`、对应 durable 测试以及 `2026-07-29-jira-text-rate` 设计/计划。行为限于 Summary 与 Description 对明确文字次数的概率识别，以及现有审查 owner 的收敛，不混入 XLSX 或 Redmine 改动。

### Redmine 批量 Clone 设计补漏

保留原 `2026-07-22-redmine-batch-clone-jira-create` 设计已经要求但当前主体实现不完整的行为：

- Jira 用户选项异步加载和 generation 迟到结果保护；
- 单字段更新只 patch 对应草稿字段，不重建无关列表和编辑器；
- Cascade 父子选项、真实 ID 和子项必填传输；
- 用户字段保存 Jira account identity，显示名称只用于展示；
- 校验失败定位第一个非法字段；
- Bridge/controller 维持单一业务状态 owner；
- 为这些契约必要的 QML、控件、翻译和 durable 测试。

### 交付规则

保留 `AGENTS.md` 和 `.codex/skills/smarttest-dual-codex-delivery/SKILL.md` 中一致的资源保护规则：唯一 Mason、并发限制、同 worker 返工、等待次数、配额门禁和证据约束。作为独立非产品提交交付。

### Confluence durable 文档

保留 `docs/superpowers/specs` 和 `docs/superpowers/plans` 中与已提交 Confluence 项目审查直接对应的设计与实施计划。它们作为历史功能的 durable 设计记录单独提交，不包含 `.superpowers` worker 报告、浏览器状态或验证产物。

## 移除或撤出

### 未授权 Redmine/Jira 行为

从生产代码、测试和翻译中一致移除：

- Redmine Assignee 自动搜索并映射 Jira account；
- Assignee 无匹配时回退当前 Jira 用户；
- Software Release 从 Redmine 自动填入 Jira；
- Jira 创建成功或重复后把 `[JIRA-KEY]` 写回 Redmine Subject；
- Redmine Subject 回写失败 warning；
- Compare Status 未经设计确认的特殊控件和选项规则。

移除时保留与已批准通用行为共享的代码，不以整文件回退覆盖合法补漏。

### report 封装

当前未完成的 report 收敛不进入本轮提交。恢复 `support/report/__init__.py`、`support/report/xlsx.py`、`support/jira_integration/audit/exporter.py` 和 `testing/self_tests/support/test_report.py` 到 `HEAD` 行为，并移除本轮 `jira-xlsx-report-consolidation` 设计/计划。工作区 clean 后重新设计和实施。

### 临时生成物

删除可重建且不属于产品源的 `.superpowers/mason-confluence-*.md`、`.superpowers/brainstorm/`、`jira_format_audit.xlsx`、`output/` 和 `tmp/`。删除前必须按精确绝对路径验证目标位于 `D:\SmartTest`，不得使用宽泛 glob 递归删除工作区根目录。

## 原子提交顺序

1. Jira 文字概率审查。
2. Redmine 批量 Clone 设计补漏。
3. 双 Codex 交付资源规则。
4. Confluence 与本次清理的 durable 设计/计划文档。

每个提交只包含对应范围。完成全部测试和代码质量审查后，按 SmartTest 交付合同将提交保留在 `main` 并 push 到配置远端。

## 验证

- Jira 文字概率规则和审查服务测试通过。
- Redmine clone controller/draft/context、Jira create schema/service、Redmine Bridge/QML、Auth profile、FluentUI 控件和翻译相关测试通过。
- 变更 Python 模块 compileall 通过；QML/资源采用仓库既有验证方式。
- 保留行为可从已批准设计逐项追溯；未授权行为的生产路径和专属测试均不存在。
- 每个 staged diff 原子、无 report 封装混入、`git diff --check` 通过。
- 最终 `git status --short` 为空，当前分支为 `main`，push 成功。

## 边界

- 不继续设计或实现 report 封装。
- 不新增 Redmine/Jira 产品行为。
- 不改写已提交历史，不使用 `git reset --hard`、`git checkout --` 或 broad clean。
- 不删除不在本设计精确列表中的用户文件。
