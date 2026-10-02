# Redmine Clone 单滚动条设计

## 目标

Clone Redmine issues to Jira 编辑器打开时只保留表单内部纵向滚动条，避免与 Tool 页的 Redmine 外层滚动条形成嵌套滚动。

## 根因

Clone 编辑器原本加载在 `redmineWorkspaceScroll` 的滚动内容中，其内部 `draftScroll` 与外层滚动条同时可见。

## 设计

- 在 `T_Tool.qml` 增加与 Redmine 工作区视口等大的宿主，外层 Flickable 与 Clone Loader 成为同级子项。
- 将 Clone Loader、Bindings 和 Connections 从 `RedmineWorkspace.qml` 移至视口级覆盖层；覆盖层 `anchors.fill: parent` 且 `z: 1000`。
- 覆盖层激活时禁止底层 Flickable 交互并隐藏其滚动条；关闭后恢复。
- `JiraCreateBatchDialog.qml` 的 `draftScroll` 保持为长表单唯一滚动 owner。

## 验收

- Clone 编辑器打开时只显示一条表单纵向滚动条。
- 标题和底部操作区固定，关闭后 Redmine 工作区滚动恢复。
