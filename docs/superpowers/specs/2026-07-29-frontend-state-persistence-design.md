# SmartTest 前端状态自动持久化设计

## 目标

建立统一的前端显示状态缓存机制。新增用户可编辑控件时，控件默认把用户值写入静态 JSON，并在下次进入页面时恢复；页面不再分别调用 `SettingsHelper.save*`、`get*` 或维护 `persistReady/persistValue`。

本设计只管理前端显示偏好。测试参数、认证信息、API Key、运行进度、服务端结果、日志和报告仍由原业务 owner 管理。

## 当前问题

- `SettingsHelper` 把通用设置和页面业务 key 混在 `example.ini`。
- `T_Jira.qml` 等页面手写成组 `save/get`。
- 部分页面重复实现初始化保护和保存时机。
- `jsonTool` 只有底层读写能力，没有用户、页面、控件、类型和敏感性约束。
- 新增控件是否缓存依赖开发者记忆。

## 方案

### 单一数据 owner

新增 `FrontendStateStore`，静态文件固定为：

`%LOCALAPPDATA%\Amlogic\SmartTest\frontend_state.json`

数据按版本、登录用户、页面 scope、控件 key 分层。语言、主题等登录前设置使用 `global` scope；普通页面状态使用规范化后的 SmartTest 登录账号。

Store 负责原子读写、类型校验、损坏回退、版本迁移、用户隔离和敏感字段拒绝。它复用 `ui/jsonTool.py`，不重复实现 JSON 序列化。

### QML 控件契约

新增 `PersistentPage` 和常用持久化控件：

- `PersistTextBox`
- `PersistMultilineTextBox`
- `PersistComboBox`
- `PersistCheckBox`
- `PersistSwitch`
- `PersistSpinBox`

`PersistentPage.stateScope` 提供页面命名空间。持久化控件以稳定 `objectName` 作为 key，创建时自动恢复，用户修改后自动保存。文本输入防抖写入；选择、布尔值和数值立即写入。

可编辑控件默认 `persistEnabled: true`。临时输入显式设置 `persistEnabled: false`。密码、Token、API Key 和 LDAP 凭据类型在 Store 边界拒绝持久化，不能依赖页面自律。

QML 层级和布局位置不参与 key 生成，避免调整布局后缓存失效。

### 数据边界

默认保存：

- 文本与多行文本
- 下拉选择
- 复选、开关
- 数值输入
- 用户选择的页签、筛选和折叠偏好

默认不保存：

- 标签、按钮、进度和错误提示
- 查询结果、审查结果、日志和报告
- 测试运行参数及设备状态
- 密码、密钥、Token 和临时凭据

### 生命周期

1. 应用创建 `FrontendStateBridge`，加载并校验 JSON。
2. 登录状态变化时，Bridge 切换当前用户命名空间并通知页面恢复。
3. `PersistentPage` 注册 scope。
4. 持久化控件注册 `objectName`、值类型和默认值。
5. Bridge 返回兼容缓存值；无缓存或类型不兼容时使用控件默认值。
6. 用户修改触发合并写入；恢复过程不反向写入。

### 迁移与瘦身

第一阶段迁移通用全局设置和普通页面筛选状态。`SettingsHelper` 中被新 Store 接管的通用 getter/setter 与 `T_Jira.qml` 手写持久化代码随迁移删除。

`T_TestConfig.qml` 的参数持久化属于测试参数业务契约，继续使用 `test_page_state.json`，不机械迁移。

Jira 审查只在通用机制完成后接入持久化控件；本次不修改其审查业务。

## 错误处理

- JSON 不存在：使用默认值并在首次修改时创建。
- JSON 损坏：记录脱敏警告、使用默认值，不阻止 UI 启动。
- 值类型不兼容：忽略旧值，保留文件中其他有效状态。
- 写入失败：记录固定错误，不在日志输出用户输入。
- 重复 scope/key：开发测试失败，运行时拒绝后注册项。

## 验收

- 两个不同登录用户不能读取彼此的页面状态。
- 页面重新创建后恢复文本、选择、布尔和数值。
- 恢复值不会触发重复写入。
- 敏感类型不能写入 JSON。
- JSON 损坏或旧类型不影响应用启动。
- 新持久化控件缺少 `objectName` 时测试失败。
- 迁移页面不再包含手写 `SettingsHelper.save/get` 或 `persistReady/persistValue`。
- `test_page_state.json`、认证存储和 Jira 审查结果不受影响。
