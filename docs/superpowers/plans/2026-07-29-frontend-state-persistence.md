# SmartTest 前端状态自动持久化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立用户隔离、类型安全、默认启用的前端控件状态缓存，并删除被替代的页面级持久化代码。

**Architecture:** `FrontendStateStore` 是 `frontend_state.json` 的唯一 owner，`FrontendStateBridge` 提供 QML 边界，`PersistentPage` 与持久化控件封装恢复和保存生命周期。测试参数、认证和运行数据保留原 owner。

**Tech Stack:** Python 3.10、PySide6/QML、现有 `ui/jsonTool.py`、pytest。

## Global Constraints

- 中文设计、计划和交付报告。
- 不保存密码、API Key、Token、LDAP 凭据、运行结果或日志。
- 不修改 Jira 审查、Redmine 和测试参数业务逻辑。
- 保留当前工作区全部用户改动及 `jira_format_audit.xlsx`。
- 先 RED、再最小实现；最终删除探索测试和重复实现。

---

### Task 1: JSON 状态 owner

**Files:**
- Create: `ui/frontend_state.py`
- Test: `testing/self_tests/ui/test_frontend_state.py`

**Interfaces:**
- Produces: `FrontendStateStore(path: Path)`
- Produces: `load(user: str, scope: str, key: str, value_type: str, default: Any) -> Any`
- Produces: `save(user: str, scope: str, key: str, value_type: str, value: Any, *, sensitive: bool = False) -> None`

- [ ] 写失败测试，覆盖用户隔离、类型不兼容回退、损坏 JSON 回退、原子合并写入和敏感字段拒绝。
- [ ] 运行 `.\.venv\Scripts\python.exe -m pytest testing\self_tests\ui\test_frontend_state.py -q`，确认因 owner 不存在而失败。
- [ ] 最小实现 Store；复用 `jsonTool.read_json/write_json`，不新增序列化器。
- [ ] 重跑测试并确认通过。

### Task 2: QML Bridge 与控件注册契约

**Files:**
- Create: `ui/example/bridge/FrontendStateBridge.py`
- Modify: `ui/example/bridge/context_registry.py`
- Test: `testing/self_tests/ui/test_frontend_state_bridge.py`

**Interfaces:**
- Consumes: `FrontendStateStore`
- Produces QML slots: `restore(scope, key, valueType, defaultValue)`、`save(scope, key, valueType, value, sensitive)`
- Produces: 登录账号切换后的 `stateContextChanged`

- [ ] 写失败测试，验证账号规范化、scope/key 校验、重复注册拒绝和登录切换隔离。
- [ ] 运行定向测试确认 RED。
- [ ] 注册单一 Bridge；从现有 AuthBridge 读取当前账号，不复制认证状态。
- [ ] 重跑测试确认 GREEN。

### Task 3: 默认持久化 QML 控件

**Files:**
- Create: `ui/example/imports/example/qml/component/persistence/PersistentPage.qml`
- Create: `ui/example/imports/example/qml/component/persistence/PersistTextBox.qml`
- Create: `ui/example/imports/example/qml/component/persistence/PersistMultilineTextBox.qml`
- Create: `ui/example/imports/example/qml/component/persistence/PersistComboBox.qml`
- Create: `ui/example/imports/example/qml/component/persistence/PersistCheckBox.qml`
- Create: `ui/example/imports/example/qml/component/persistence/PersistSwitch.qml`
- Create: `ui/example/imports/example/qml/component/persistence/PersistSpinBox.qml`
- Modify: `ui/example/imports/resource.qrc`
- Test: `testing/self_tests/ui/test_frontend_persistent_controls.py`

**Interfaces:**
- Consumes: `FrontendStateBridge`
- Contract: `stateScope` 来自页面，`objectName` 是稳定 key，`persistEnabled` 默认 `true`

- [ ] 写运行态失败测试，验证重建页面后恢复各类型值、恢复不回写、禁用持久化和缺少 `objectName` 拒绝注册。
- [ ] 运行定向测试确认 RED。
- [ ] 用共享的非视觉注册组件消除六种控件重复生命周期代码；各包装只映射自己的值属性和变更信号。
- [ ] 重建 QRC 并运行测试确认 GREEN。

### Task 4: 迁移普通前端设置并删除旧实现

**Files:**
- Modify: `ui/example/imports/example/qml/App.qml`
- Modify: `ui/example/imports/example/qml/window/MainWindow.qml`
- Modify: `ui/example/imports/example/qml/page/T_Jira.qml`
- Modify/Delete: `ui/example/helper/SettingsHelper.py`
- Modify: `ui/example/main.py`
- Test: `testing/self_tests/ui/test_frontend_state_migration.py`
- Test: `testing/self_tests/ui/test_owned_ui_translations.py`

**Interfaces:**
- Consumes: 持久化控件和 `FrontendStateBridge`
- Preserves: 语言、主题、关闭行为和 Jira 页面筛选值

- [ ] 写迁移失败测试：预置旧 `example.ini`，首次启动迁移到 JSON；迁移后页面恢复值且不会再次依赖旧 key。
- [ ] 运行定向测试确认 RED。
- [ ] 将普通 UI 设置迁移到新机制；删除已被替代的 `save/get`、`persistFilterState` 和兼容代码。
- [ ] 保留尚未迁移且有真实 owner 的最小 SettingsHelper 能力；若引用清零则删除整个 helper 和注册。
- [ ] 重跑迁移、翻译和页面加载测试确认 GREEN。

### Task 5: 新控件默认契约与最终瘦身

**Files:**
- Modify: `.codex/skills/smarttest-ui-workflow/SKILL.md`
- Modify: `AGENTS.md` only if routing wording must reference the existing UI skill; otherwise不修改
- Test: `testing/self_tests/ui/test_frontend_persistence_contract.py`

**Interfaces:**
- Contract: 新增用户可编辑控件必须使用持久化包装，或显式声明 `persistEnabled: false`

- [ ] 写契约测试，解析 QML 组件实例并报告缺失稳定身份的新增可编辑控件；排除显示控件和已有业务 owner 控件。
- [ ] 更新中文开发约束：默认持久化、敏感值禁止、业务状态不重复保存。
- [ ] 删除重复 helper、迁移探针、临时日志、源码文本形状断言和重复等价测试。
- [ ] 运行 UI focused tests、`compileall`、QRC 重建、源启动检查和 `git diff --check`。
- [ ] 审查净生产代码增长和当前 `git status`，确认未包含 Jira、测试参数、认证或用户文件的意外变化。
