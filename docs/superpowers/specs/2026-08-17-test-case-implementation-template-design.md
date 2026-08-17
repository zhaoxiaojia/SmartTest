# SmartTest 单条测试用例实现模板设计

## 1. 目标

把单条测试用例从源需求、执行模式、前端参数、测试入口、驱动复用、step/checkpoint、报告到验收的完整开发合同固化到 `smarttest-case-development` 技能中。模板必须细化到代码 owner，使实现者在修改代码前能够回答：需求是什么、谁执行、参数从哪里来、调用哪个能力、如何检测、证据进入哪里、报告如何呈现、完成到哪个验收等级。

本设计只修改开发规则，不修改业务代码、公共接口或现有用例行为。

## 2. 文件组织

采用“主规则强制入口 + 详细 reference”结构：

- `.codex/skills/smarttest-case-development/SKILL.md`：增加强制入口、执行模式原则和交付门。
- `.codex/skills/smarttest-case-development/references/case-implementation-template.md`：保存完整的单条用例实现模板、代码位置、字段和检查表。

开始实现任何测试用例前，执行者必须完整读取 reference、填写单条用例实现合同并完成能力映射。用例提取、纯评估等不进入实现阶段的工作无需加载详细 reference。

## 3. 标准开发流程

### 3.1 建立源用例需求卡

每条用例先记录：

- 源文件、sheet、行号、原始用例编号、标题、模块和优先级。
- 前置状态、人工准备动作、SmartTest 执行动作、原始预期结果。
- 可客观检测部分、人工边界、外部设备依赖。
- 参数、超时、循环次数、失败策略、恢复动作。
- DUT、PC、账号、网络、片源、普通外设和检测设备。

没有明确检测对象、检测方法和通过规则时，停止实现并请求确认，不得根据描述自行补充产品判断。

单条普通用例可直接在 `testing/tests/**/test_*.py` 中保留身份；从 Excel、Word 或计划批量提取的同类用例可在测试模块旁建立数据清单，例如 `testing/tests/android/common/iptv/middle_screen_cases.py`。

### 3.2 选择唯一业务执行 owner

业务执行模式为 Python 或 APK，二者选其一。默认使用 Python。

#### Python 模式

满足以下条件时选择 Python：

- ADB shell、节点、property、dumpsys、PC 库或已有 DUT driver 能完成动作和检测。
- 测试期间 ADB 可用。
- 不依赖 Android 系统权限、Framework 回调或设备端长期服务。
- 不需要在 PC 失联、DUT 重启或深度休眠期间继续执行。

业务代码 owner：

```text
testing/tests/**/test_*.py
testing/tool/dut_tool/features/*.py
testing/tool/dut_tool/duts/android.py
```

#### APK 模式

只有满足以下条件之一时选择 APK：

- 需要 `android.uid.system`、priv-app 或 Android Framework API。
- 需要 BroadcastReceiver、Service、Activity、MediaSession 等设备端生命周期能力。
- DUT 重启、深度休眠或 ADB 暂时失联时仍需继续执行。
- 需要设备端低延迟、连续状态采样。

业务执行 owner：

```text
android_client/app/src/main/java/com/smarttest/mobile/runner/cases/
```

APK 模式仍必须提供 Python pytest 外壳：

```text
testing/tests/android/**/test_*.py
```

职责固定为：

```text
Python pytest：参数解析、触发 APK、监管进度/超时/取消、接收结果、汇总统一报告
APK executor：执行设备动作、完成设备端检测、产生实际结果和证据
```

Python 外壳复用 `testing.runner.apk_client.apk_case_plan` 和 `run_apk_case`。禁止 Python 与 APK 各实现一套相同业务动作、检测点或恢复逻辑。

### 3.3 前端布局与参数呈现

正常新增用例不新增专用 QML 页面。通用 owner 为：

```text
ui/example/imports/example/qml/page/T_TestConfig.qml
ui/example/bridge/TestPageBridge.py
```

QML 根据参数契约自动渲染：

| 参数类型 | 默认控件 |
|---|---|
| `STRING` | `FluTextBox` |
| `INT` / `FLOAT` | 数字文本输入 |
| `BOOL` | `FluToggleSwitch` |
| `ENUM` | `FluComboBox` |
| `MULTI_ENUM` | 多选列表 |
| `PATH` | 路径输入或动态选项 |
| `MULTILINE` | `FluMultilineTextBox` |

参数按 `DEVICE`、`ENVIRONMENT`、`NETWORK`、`EXECUTION`、`REPORT`、`GENERAL` 分类呈现。只有新增通用参数类型或公共交互时才修改 QML/bridge；固定前端文字同时写入 `ui/example/example_en_US.ts` 和 `ui/example/example_zh_CN.ts`。

### 3.4 参数合同

参数业务契约统一定义在 `testing/params/contracts.py`。每个参数在实现合同中记录：

```text
key, value_type, category, scope, default, required_at_start,
source_kind, enum_values, options_source, refreshes_options_sources,
refresh_on_dut_refresh, 单位, 合法范围, 使用者, 是否进入报告, 是否敏感
```

代码只使用现有 `ParamContract` 已支持的字段。单位、范围、敏感性等现有结构未承载的信息先留在实现合同和测试断言中；是否扩展公共 schema 需单独设计批准。

参数 key 使用 `<case_id>:<param_id>`。来源只能明确选择 `user_input`、`dut_dynamic`、`env_dynamic`、固定枚举或系统默认值。动态选项复用 `testing/tool/dut_tool/parameter_helper.py` 和 `testing/params/options.py`；运行前校验由 `testing/params/validation.py` 负责。

参数持久化继续由 `TestPageBridge.py`、`ui/jsonTool.py` 和 `%LOCALAPPDATA%\Amlogic\SmartTest\test_page_state.json` 负责。Python 测试使用 `smarttest_context().params.case_values(request.node.nodeid)` 读取；APK 请求使用 `smarttest_context().params.apk_params(case_id, trigger)` 生成 case-scoped 参数。

### 3.5 pytest 测试入口

代码位置：

```text
testing/tests/<platform>/<case_type>/<domain>/test_<case_name>.py
```

每条用例声明 `pytest.mark.case_type(...)`、`SMARTTEST_CASE_PLAN`、`pytest.mark.requires_params(...)` 和测试函数。

Python 模式测试函数负责：获取 DUT 和参数、记录源身份、调用 feature/driver、以运行时 step 包围动作、断言客观结果、记录结构化证据并执行恢复。

APK 模式测试函数只构建 `apk_case_plan(...)` 并调用 `run_apk_case(...)`，不得再编写 ADB 业务动作或设备检测。

### 3.6 驱动与业务能力复用

实现前按顺序查找：

1. DUT 公共能力：`testing/tool/dut_tool/duts/android.py`、`linux.py`。
2. 业务 feature：`testing/tool/dut_tool/features/`。
3. PC 和设备适配器：`testing/tool/pc_tool/`、`testing/tool/equipment.py`、`testing/tool/relay_tool/`。
4. APK device owner：`android_client/**/runner/device/`。

串口只能通过 `testing/tool/pc_tool/serial_tool.py`。测试函数不直接复制复杂 ADB、串口、文件转换或安装机制；APK executor 不复制共享 shell、日志、状态存储或安装流程。

每个动作/checkpoint 填写能力矩阵：动作或检测点、已有 owner、支持状态、缺口、处理方式。处理顺序为：直接复用、通用扩展现有 owner、合并重复机制、扩展现有 feature、新增公共 feature/owner。外设依赖或信息不足必须报告，不能用弱判断掩盖。

### 3.7 step 计划

公共定义 owner：`testing/steps/definitions.py`；计划入口：`SMARTTEST_CASE_PLAN`；运行时 owner：`testing/runtime/steps.py`。

每个 step 声明 `id`、`title`、`kind`、`definition_id`、`expected`、必要的 `parent_id` 和循环身份。`kind` 使用 `setup`、`action`/`step`、`check`、`cleanup` 或 `external`。

Python 模式使用 `with step(...)` 更新计划行。APK 模式由 Python `apk_case_plan()` 预声明，APK 使用 `SmartTestRunStore.updateProgress(...)` 和 `finishStep(...)` 更新同一身份。运行时只更新已计划行，不建立第二套 UI/report step。

### 3.8 checkpoint 合同

每个 checkpoint 记录：

```text
checkpoint id, 所属 step, 检测对象, 检测方法, expected, actual,
容差/阈值, 超时, 证据类型, pass/skip/fail 条件, 设备依赖, 恢复动作
```

合法检测是可重复的客观判断，例如值相等、节点包含 token、进程处于状态、地址/连接有效、MediaSession 在观察窗口持续 `PLAYING`，或已批准算法达到阈值。“看起来正常”“画质正常”“声音正常”“没有明显卡顿”只能作为人工边界，不能直接判为自动通过。

证据通过 `step_log(..., extra={...})` 或 step evidence 事件进入统一模型，禁止临时 `print()` 作为验收证据。

### 3.9 异常、取消与恢复

每条用例定义参数缺失、DUT 离线、超时、用户取消、APK snapshot 丢失、失败后 cleanup 和状态恢复策略。频率、网络、音量、显示、应用等被修改状态必须恢复；恢复逻辑放在业务 owner 或测试函数 `finally`，不建立旁路。

### 3.10 报告合同

报告 owner：

```text
testing/test_context.py
support/report/
support/report/json/store.py
ui/example/bridge/ReportBridge.py
```

报告必须呈现：

- 身份：`run_id`、`case_nodeid`、`case_id`、标题、case type、源文件/sheet/编号/行、DUT serial、软件/APK 构建身份。
- 输入：实际参数、来源、默认/用户值、非敏感环境配置、循环次数、人工前置动作。
- 结果：最终状态、起止时间、总耗时、step 状态/耗时/`definition_id`/`expected`/`actual`、checkpoint 证据、循环身份、cleanup 结果。
- 失败：失败 step/checkpoint、expected/actual、错误、结构化日志、命令结果、截图/录屏/文件/设备快照路径、失败域。
- 边界：跳过项、人工检测项、缺少设备造成的限制、局部软件检查不代表完整业务通过的说明。

密码、Token、敏感账号或凭据不得进入报告。

### 3.11 验证与交付

Python 用例至少验证：模块编译/导入、pytest discovery、参数暴露和 `required_at_start`、`SMARTTEST_CASE_PLAN`、聚焦 self-tests、可用时的真实 DUT 执行、报告 JSON/HTML 和 `git diff --check`。

APK 用例额外验证：case-scoped am-start 参数、`SmartTestCatalog` / `TestCaseRegistry`、计划与运行 step 身份、checkpoint `None` 跳过语义、Gradle 构建、平台签名 `dist` APK、DUT refresh/provisioning 和真实 APK 执行。

验收等级保持 L1 编译/静态契约、L2 发现/参数/计划/框架、L3 PC+DUT、L4 检测设备执行。不得越级声称验收。

## 4. 单条用例实现合同字段

详细 reference 必须提供以下可填写结构：

```text
源用例身份：
目标：
完整预期：
自动化边界：
执行模式：Python / APK
选择理由：

前置状态：
人工准备：
用户参数：
动态参数：
环境参数：

pytest 文件：
case_id：
case_type：
测试函数：
SMARTTEST_CASE_PLAN：

Python 业务 owner：
APK executor：
DUT driver：
业务 feature：
设备/PC 工具：

现有可复用能力：
需要扩展的能力：
缺失且阻塞的能力：
复用决定：
预计净新增生产代码：

steps：
checkpoints：
evidence：
cleanup：
timeout/cancel：

报告字段：
敏感字段排除：
人工边界说明：

自测：
发现验证：
真机验证：
最高验收等级：
```

所有不适用字段必须明确填写“不适用”及理由，不能留空。

## 5. 规则更新验收

规则更新完成需满足：

1. 主 `SKILL.md` 能明确触发详细模板，且不复制 reference 全文。
2. reference 覆盖本设计所有阶段、代码 owner 和实现合同字段。
3. Python 优先、业务执行 owner 二选一、APK Python 外壳职责边界无歧义。
4. 模板不会要求为普通用例新增专用 QML，也不会绕过参数、step、报告或 driver owner。
5. 使用一个 Python 用例场景和一个 APK 用例场景验证模板可执行性；使用缺少检测阈值的场景验证模板会停止实现。
6. 文档不存在未决占位标记、未解释空字段、重复 owner 或与 SmartTest 现有工作流冲突的要求；代码格式中的参数占位符属于模板语法。
