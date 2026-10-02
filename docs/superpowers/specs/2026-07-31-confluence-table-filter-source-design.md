# Confluence Project Space 汇总表筛选设计

## 1. 目标

Project Weekly Audit 以用户选中的 DOPL、SDPL、TV、OOPL Project Space 页面中的汇总表作为候选项目字段来源。SmartTest 不遍历年份目录来补充字段，也不依赖 Table Filter 的动态浏览器 session。

## 2. 数据来源

- `https://confluence.amlogic.com/display/DOPL/Project+Space`
- `https://confluence.amlogic.com/display/SDPL/Project+Space`
- `https://confluence.amlogic.com/display/TV/Project+Space`
- `https://confluence.amlogic.com/display/OOPL/Project+Space`

每个页面只读取一次渲染后的汇总表。目标表必须包含：

- `页面`
- `Date of Commercial approval`
- `Support Mode`
- `Project Status`

`Project ID` 和 `Current Stage` 同样来自汇总表；其他列不参与筛选字段推断。

候选收集只复刻 Project Space 汇总表已有字段和筛选结果。禁止在刷新过滤选项或应用过滤时读取项目页面、父页面或子页面，也禁止根据页面层级增加候选资格校验。

## 3. SmartTest 过滤器

- Years：从 `Date of Commercial approval` 中解析有效日期并取年份集合。
- Support modes：从 `Support Mode` 列取非空规范化值集合。
- Project statuses：从 `Project Status` 列取非空规范化值集合。
- 用户应用过滤时，只在所选产品线的汇总表数据上执行 Year + Mode + Status 交集。
- 未选择某个维度表示该维度全选。
- 无论 UI 条件如何，`Current Stage` 数字前缀大于等于 5 的项目统一排除，包括 `5 MP CLOSE` 以及 6、7、8、9 阶段。
- `Current Stage` 缺失或不是数字前缀时不新增产品规则，继续按其他现有条件处理。

SmartTest 不把 Current Stage 作为 UI 条件，也不处理 Owner、ODM、OEM、OS、日期以外的其他条件。

## 4. 项目身份与审查

- 项目名称和 URL 来自汇总表 `页面` 列。
- 内部身份使用 `space_key + canonical page URL/pageId`，跨空间不合并。
- 刷新过滤选项和应用过滤只读取所选产品线的 Project Space 汇总页。
- 仅在用户开始审查后读取用户勾选项目的项目页面及其审查子页面；未勾选项目不得触发项目页、父页或子页请求。

### 4.1 手工审查时间范围

- Confluence 审查页面复用 FluentUI `FluDatePicker`，提供开始日期和结束日期两个日期控件，不实现新的日期选择组件。
- 日期范围是本次手工审查的业务输入，由 `ConfluenceAuditBridge` 持有；QML 只负责显示选择并把用户确认的日期交给 bridge，不计算周一、时区或最终时间。
- 页面初始化时，开始日期默认为当前日期所在周的周一，结束日期默认为当天，时区固定使用 `Asia/Shanghai`。
- 用户可以通过日期控件把开始日期改为上周一、上上周一或任意日期，也可以修改结束日期。
- 点击开始审查时才生成最终 `AuditPeriod`：开始时间为所选开始日期 `00:00:00`；结束日期为当天时取点击开始审查时的当前时间，结束日期早于当天时取该日期次日 `00:00:00`，从而包含完整的所选结束日期。
- 开始时间必须早于最终结束时间；无效范围不启动审查并显示明确提示，不静默修改用户选择。
- 日期范围不跨应用重启持久化，每次启动重新得到“本周一到当天”的默认值。
- 该范围只用于手工审查，不改变 Project Space 候选过滤、用户勾选项目集合或现有 weekly plan 的调度时间范围。

## 5. 性能与状态

- 一次收集只读取用户选择的产品线汇总页面，不产生逐项目 N+1 请求。
- 同一账户同一时刻只允许一个刷新任务；重复点击不创建并行请求。
- 新刷新开始时清空旧 available/candidate 数据，避免显示误导性的 `1 available`。
- 任一已选产品线汇总页读取失败时整次 Apply 失败并保留旧候选结果。
- 缓存以账户和所选产品线汇总页面版本为边界；手动刷新强制重新读取。

## 6. History 删除

删除 Project Weekly Audit 的 History 前端和业务：

- QML History 下拉框；
- bridge history 状态、选择和加载方法；
- 仅用于历史批次切换的 store 查询、投影和测试；
- History 固定文本和废弃翻译。

保留当前批次结果、审查执行、Excel/PDF 输出及必要的当前批次持久化。如果 store 仅服务 History，则整体删除；如果调度或导出仍依赖当前批次保存，则只保留这些 owner 使用的最小接口。

## 7. 删除范围

删除上一版：

- Project Space -> 年份页 -> 项目根遍历；
- `get_page_children` 驱动的候选目录构建；
- 逐项目 Project Target 读取；
- 年份目录可见值计算；
- 对逐项目读取错误、root/readable/matched 的诊断；
- 为上述机制存在的缓存、兼容路径和测试。

不保留新旧发现开关。

## 8. 验收

- 只读取用户选择的产品线汇总页；候选收集不读取任何项目页、父页或子页。
- 前端三个过滤器选项与汇总表中对应字段一致。
- Year 使用 Date of Commercial approval，而不是目录年份。
- 应用过滤后候选数量与同字段条件下的 Confluence 汇总表一致。
- Current Stage 数字前缀大于等于 5 的项目在统一过滤 owner 中排除，实时 Apply 与缓存恢复结果一致。
- 重复点击不会创建并行发现。
- History 前端与业务代码完全移除。
- 旧逐项目发现机制和冗余测试删除。
- 审查阶段仅对用户勾选的项目执行既有项目页及子页发现。
- 手工审查页面提供开始、结束日期控件；默认审查范围为本周一 `00:00:00` 至点击开始审查时的当前时间。
- 用户选择更早的开始日期后，审查使用该日期 `00:00:00` 至所选结束边界；无效时间范围不得启动。
- 手工日期范围不影响 weekly plan 的既有调度窗口。
- scoped tests、全部 support tests、UI 契约、compileall、diff check 通过。

## 9. 手工审查时间范围实施清单

- [x] 在 bridge 回归测试中先覆盖默认本周一、日期更新、当天结束取运行时当前时间、历史结束日期包含整天、无效范围阻止启动，以及传给审查服务的 `AuditPeriod`。
- [x] 由 `ConfluenceAuditBridge` 增加手工审查开始/结束日期视图状态和日期更新 slot，复用现有 `AuditPeriod`，不新增平行时间模型。
- [x] 将 `startAudit()` 从固定 `current_reporting_window()` 改为使用 bridge 解析并校验后的手工审查范围；weekly plan 继续使用原有调度窗口。
- [x] 在 `ConfluenceAuditWorkspace.qml` 复用两个 `FluDatePicker` 展示开始日期与结束日期，声明稳定 `objectName`，并明确由 bridge 持有业务状态、不进入前端持久化。
- [x] 同步更新中英文固定文本、QML 资源和相关 UI 契约测试。
- [x] 运行 Confluence bridge/period/service、QML 契约、双语翻译测试，重建 QRC，执行 source 启动检查、`compileall` 和 `git diff --check`，清理临时诊断与实现残留。
