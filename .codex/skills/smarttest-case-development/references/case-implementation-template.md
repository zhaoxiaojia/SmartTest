# SmartTest 单条测试用例实现模板

实现任何测试用例前完整填写本合同。字段不适用时写明“不适用”及理由；不得留空。源需求和 Coco 已确认的实现思路优先，本模板不能增加业务判断、回退或兜底。

## 1. 实现前合同

```text
源用例身份：文件 / sheet / 行 / 原始 id
标题 / 模块 / 优先级 / milestone：
目标：
完整预期：
客观自动化边界：
人工/设备边界：

执行模式：Python / APK（二选一）
选择理由：
前置状态：
人工准备动作：
用户参数：
动态参数：
环境/设备参数：

pytest 文件 / case_id / case_type / 测试函数：
SMARTTEST_CASE_PLAN：
Python 业务 owner：
APK executor：
DUT driver / feature / PC 或设备工具：

现有可复用能力：
需要通用扩展的能力：
缺失且阻塞的能力：
复用决定与预计净新增生产代码：

steps / checkpoints / evidence：
cleanup / timeout / cancel：
报告字段 / 敏感字段排除 / 边界说明：
自测 / discovery / 真机验证 / 最高验收等级：
```

没有客观检测方法和通过规则、执行 owner 未确定、参数或能力合同缺失时，状态为 `BLOCKED`，停止实现并报告最小待确认项。

## 2. 执行 owner 决策

业务执行必须二选一，默认 Python。

| 选择 | 判定条件 | 业务位置 |
|---|---|---|
| Python | ADB/shell、节点、property、dumpsys、PC 库或现有 DUT driver 可完成；运行期间 ADB 可用；不依赖 Android 特权或设备端生命周期 | `testing/tests/**/test_*.py`、`testing/tool/dut_tool/features/`、`testing/tool/dut_tool/duts/android.py` |
| APK | 需要 system/priv-app、Framework callback/Service/Receiver/Activity；重启、深度休眠或 ADB 失联期间继续；设备端连续低延迟采样 | `mobile/android/app/src/main/java/com/smarttest/mobile/runner/cases/` |

APK 模式仍必须有 `testing/tests/android/**/test_*.py`。它只使用 `testing.runner.apk_client.apk_case_plan` / `run_apk_case` 完成参数下发、触发、进度/超时/取消监管、结果收集和报告；不得再实现 ADB 业务动作、checkpoint 或 cleanup。APK executor 负责动作、检测、证据和设备端恢复。

## 3. 前端和参数

普通用例不新增专用 QML。参数由以下通用 owner 渲染和持久化：

```text
client/app/ui/example/imports/example/qml/page/T_TestConfig.qml
client/app/ui/example/bridge/TestPageBridge.py
client/app/ui/jsonTool.py
%LOCALAPPDATA%\Amlogic\SmartTest\test_page_state.json
```

只有新增公共参数类型/交互时才修改 QML/bridge。固定文字同时更新 `client/app/ui/example/example_en_US.ts` 和 `example_zh_CN.ts`。

参数业务合同写在 `testing/params/contracts.py`，key 使用 `<case_id>:<param_id>`。每个参数记录：

```text
key, value_type, category, scope, default, required_at_start,
source_kind, enum_values, options_source, refreshes_options_sources,
refresh_on_dut_refresh, unit/limits, consumer, report exposure, sensitivity
```

代码只使用现有 `ParamContract` 字段；未承载的 unit/limits/sensitivity 先留在合同和断言中，扩展公共 schema 需另行批准。动态选项复用 `testing/tool/dut_tool/parameter_helper.py`、`testing/params/options.py`，开始校验由 `testing/params/validation.py` 负责。

| `ParamValueType` | 默认控件 |
|---|---|
| `STRING` | `FluTextBox` |
| `INT` / `FLOAT` | 数字文本输入 |
| `BOOL` | `FluToggleSwitch` |
| `ENUM` | `FluComboBox` |
| `MULTI_ENUM` | 多选列表 |
| `PATH` | 路径输入/动态选项 |
| `MULTILINE` | `FluMultilineTextBox` |

Python 从 `smarttest_context().params.case_values(request.node.nodeid)` 读取；APK 由 `apk_params(case_id, trigger)` 生成 case-scoped `caseId:paramId=value`。密码、Token、临时凭据不进日志和报告。

## 4. pytest 入口

文件位于 `testing/tests/<platform>/<case_type>/<domain>/test_<case_name>.py`，声明：

```python
pytestmark = pytest.mark.case_type("<case_type>")
SMARTTEST_CASE_PLAN = {"case_id": "<case_id>", "steps": [...]}

@pytest.mark.requires_params("<case_id>:<param_id>")
def test_<case_name>(request):
    ...
```

Python 模式按顺序：解析 DUT/参数、记录源身份、调用 feature/driver、用 runtime step 包围动作、断言客观结果、记录结构化证据、恢复状态。

APK 模式的 pytest 只允许：

```python
SMARTTEST_CASE_PLAN = apk_case_plan("<case_id>", ["<runtime_definition_id>"])

def test_<case_name>_via_android_client(request):
    run_apk_case(case_id="<case_id>", trigger=request.node.nodeid)
```

## 5. 驱动复用和扩展

依次搜索并记录 owner：

1. `testing/tool/dut_tool/duts/android.py` / `linux.py` 的公共 DUT 能力。
2. `testing/tool/dut_tool/features/` 的可复用业务能力。
3. `testing/tool/pc_tool/`、`testing/tool/equipment.py`、`testing/tool/relay_tool/`；串口只能由 `serial_tool.py` 实现。
4. APK 的 `mobile/android/app/src/main/java/com/smarttest/mobile/runner/device/`。

对每个动作/checkpoint 填写：已有 owner、支持状态、输入/输出、缺口、处理。选择顺序是直接复用、通用扩展当前 owner、合并重复、扩展现有 feature、最后新增公共 owner。禁止在 case 中建立私有 ADB/串口/安装/文件转换机制，禁止 Python/APK 双实现。

## 6. Step 与 checkpoint

公共 step 定义位于 `testing/steps/definitions.py`，计划由 `SMARTTEST_CASE_PLAN` 预声明，运行时由 `testing/runtime/steps.py` 更新。

每个 step 必须包含 `id/title/kind/definition_id/expected`，按需包含 `parent_id` 和 loop/cycle 身份。`kind` 使用 `setup`、`action`/`step`、`check`、`cleanup`、`external`。

Python 使用 `with step(...)` 更新同一计划行。APK 由 `apk_case_plan()` 预声明，并通过 `SmartTestRunStore.updateProgress(...)` / `finishStep(...)` 更新匹配的 step id；不得创建 APK 替代行或第二套 UI/report 模型。

每个 checkpoint 必须填写：

```text
id, owning step, object, method, expected, actual, tolerance/threshold,
timeout, evidence type, pass/skip/fail rule, dependency, cleanup
```

合法检测包括精确值/范围、节点 token、进程/连接状态、有效 IP、持续 `PLAYING` 或经批准算法阈值。“看起来正常”“声音/画质正常”“没有明显卡顿”只能记录为人工边界。证据使用 `step_log(..., extra={...})` 或 step evidence 事件，不使用 `print()`。

## 7. 异常和恢复

明确参数缺失、DUT 离线、超时、用户取消、APK snapshot 丢失、失败后 cleanup 的处理。被修改的频率、网络、音量、显示和应用状态必须恢复。恢复属于业务 owner 或测试函数 `finally`，不得建立旁路。

## 8. 报告合同

报告 owner：`testing/test_context.py`、`support/report/`、`support/report/json/store.py`、`client/app/ui/example/bridge/ReportBridge.py`。

必须呈现：

- 身份：run/case/node/source/DUT/build/APK。
- 输入：实际非敏感参数、来源、默认/用户值、循环和人工前置。
- 结果：状态、时间/耗时、step `definition_id/expected/actual/status/evidence`、cycle、cleanup。
- 失败：checkpoint、expected/actual、错误、结构化日志、命令结果和截图/录屏/文件/快照路径。
- 边界：skip、人工项、缺失设备限制，以及局部软件检查不代表完整业务通过的说明。

## 9. 验收检查表

Python：编译/导入、pytest discovery、参数暴露/开始校验、计划与运行 step、聚焦 self-tests、可用时真机、报告 JSON/HTML、`git diff --check`。

APK 额外：case-scoped am-start、`SmartTestCatalog` / `TestCaseRegistry`、APK planned/runtime step、checkpoint `None` skip、Gradle assemble、平台签名 `dist` APK、DUT refresh/provisioning、真机执行。

最终记录 L1 静态、L2 框架、L3 PC+DUT 或 L4 检测设备验收；不得越级声称。

## 10. 停止条件

- Coco 已给出实现思路但现有 owner 无法按原思路完成。
- checkpoint 没有检测方法、阈值或证据。
- Python/APK 业务 owner 未二选一。
- 需要新增公共参数/驱动/report contract 而边界未批准。
- 自动化结果超出批准边界或需要未提供的外设。

命中时报告证据、受影响用例和最小待确认项，不自行增加 fallback、弱断言或人工结果冒充自动通过。
