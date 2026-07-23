# Task 5：Redmine 批量 Clone 的 QML 交互

## 目标

在现有 Redmine 工作区接入 Task 4 的批量 Clone Bridge，并新增复用 Jira 原生字段类型的批量创建对话框。用户先选择，再一次看到全部已填草稿，统一检查、修改并一次确认创建。

## 文件范围

- 新增 `ui/example/imports/example/qml/component/issue/JiraCreateField.qml`
- 新增 `ui/example/imports/example/qml/component/issue/JiraCreateDraftCard.qml`
- 新增 `ui/example/imports/example/qml/component/issue/JiraCreateBatchDialog.qml`
- 修改 `ui/example/imports/example/qml/component/issue/JiraIssueBrowserLayout.qml`
- 修改 `ui/example/imports/example/qml/page/Tool/RedmineWorkspace.qml`
- 修改相关 QRC、英文/中文 TS 和 UI 自测
- 新增 `testing/self_tests/ui/test_redmine_clone_create_ui.py`

## 必须复用

- Task 4 的 `cloneSelectionMode`、`cloneSelectedIds`、`cloneDrafts`、`cloneBatchState`、进度/错误/首个非法字段属性及所有 Clone slots。
- 现有 issue list、dialog、FluentUI 控件与翻译机制。
- QML 只负责呈现和用户输入，不得复制字段映射、校验、Jira payload 或创建逻辑。

## 验收标准

1. Redmine issue list 提供 Clone 入口；进入后每条显示多选框，已 Clone 条目禁选，取消/确认清晰可用。
2. 选择确认只生成草稿，不调用 Jira 创建；loading 显示进度且可关闭/取消（提交阶段不可关闭）。
3. 所有草稿在同一对话框内同时、默认展开呈现；不是逐条确认。
4. 字段严格按 Bridge schema 顺序，支持 text、multiline、single、multi、cascade、user；预填值均可修改，空值由用户填写。
5. 底部固定操作区提供整批创建；校验失败定位首个非法 issue/字段；提交期间禁止重复操作。
6. partial_failed 清楚展示每条成功/重复/失败结果，并只提供“重试失败项”；completed 可关闭。
7. issue ID 原有跳转、条目选择详情、clone 状态与其他 Jira/Redmine 列表功能不回归。
8. 新 QML 已加入 QRC，英文和中文文案完整，UI 自测覆盖状态/控件/QRC/翻译契约。

## 测试与提交

- 先写失败测试，再实现。
- 运行新 UI 测试、现有 Redmine/QML/ToolPage 相关测试、QML 静态检查（仓库已有方式）、`git diff --check`。
- 只提交本任务文件，提交信息：`feat: add Redmine batch clone editor`。
- 报告写入 `.superpowers/sdd/task-5-report.md`，包含文件、RED/GREEN 命令与退出码、限制和 commit。
