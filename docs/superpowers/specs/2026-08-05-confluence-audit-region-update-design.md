# Confluence 项目审查区域更新判定设计

## 目标

修正 Project Audit 目前按整页更新时间判断多个审查点的问题。审查应先识别目标审查区域，再判断该区域本周是否真正更新，避免用户只修改页面其他内容就让所有审查点同时显示“已更新”。

本次保持现有 Project 收集、筛选、12 列 Excel 报告及页面展示格式不变。

## 范围

本次只处理现有 12 个审查点：

1. `Project Status Report.Highlights`
2. `Project Status Report.Impact Issue`
3. `Test Information.每周信息`
4. `Test Information.测试结果 Summary`
5. `Test Information.Task 完成情况`
6. `Test Information.Block QA 问题状态`
7. `Test Plan.测试计划`
8. `Test Environment Setup and Precautions.环境搭建方式`
9. `Test Environment Setup and Precautions.常用 Log 信息`
10. `Summary of Experience and Typical Cases.经验总结`
11. `Summary of Experience and Typical Cases.典型案例`
12. `Test Report Store.测试报告`

邮件中提到但不在当前 12 列内的内容不新增为审查列，也不改变既有 Excel 格式。

## 审查时间窗口

- 时区固定为 `Asia/Shanghai`。
- 每周一 `00:00` 重置本周审查时间窗口。
- 手动执行时，窗口为本周一 `00:00` 至实际执行时间。
- 审查结果只回答目标审查区域在该时间窗口内是否发生有效内容更新。

## 审查区域识别

每个审查点由一个标准名称和一组明确别名定位。识别顺序为：

1. 标题区域；
2. 表格字段名及其对应单元格或后续表格；
3. Confluence 宏标题；
4. 明确配置的别名。

首批别名如下：

| 审查点 | 明确别名 |
|---|---|
| Highlights | `Highlights`、`Highlight`、`项目亮点` |
| Impact Issue | `Impact Issue(s)`、`Impact`、`影响问题` |
| 每周信息 | `Weekly Information`、`Weekly Update`、`每周信息`、`本周更新` |
| 测试结果 Summary | `Test Result Summary`、`Testing Result Summary`、`测试结果汇总` |
| Task 完成情况 | `Task Arrangement`、`Task Arrangement of Important Test`、`测试任务安排` |
| Block QA 问题状态 | `Blocking QA Issues`、`Blocking QA Testing Items`、`阻塞问题` |
| 测试计划 | `Test Plan`、`Weekly Test Plan`、`测试计划` |
| 环境搭建方式 | `Environment Setup`、`Setup Method`、`环境搭建` |
| 常用 Log 信息 | `Common Log Information`、`Log Collection`、`常用日志` |
| 经验总结 | `Experience Summary`、`Summary of Experience`、`经验总结` |
| 典型案例 | `Typical Cases`、`Typical Case`、`典型案例` |
| 测试报告 | `Test Report`、`Report Store`、`测试报告` |

别名只用于将不同模板写法识别为同一个审查点。不得使用宽泛关键词猜测，不得在定位失败时退化为比较整个页面。后续出现新的合法模板写法时，只扩充此处对应审查点的别名或区域规则。

## 更新判定

1. 定位当前审查点的目标区域。
2. 定位失败时，结果为 `格式有误`，PS 写入 `格式有误：查询不到<标准名称>`；不再判断更新时间。
3. 定位成功后，仅检查该目标区域在本周时间窗口内是否发生有效内容变化。
4. 空格、制表符、换行及纯展示样式变化不算有效更新。
5. 页面其他区域发生变化，不影响当前审查点。
6. 目标区域本周发生有效内容变化时为 `已更新`，否则为 `未更新`。
7. 同一页面上的多个审查点独立识别、独立判断，不共享整页更新时间结论。

状态优先级保持为：

`格式有误 > 未更新 > 已更新`

本次不判断文字描述是否正确、有价值或符合业务语义。

## 所有权与数据流

- 现有 Project Audit 服务继续作为审查流程的唯一业务入口。
- 审查点标准名称、页面归属和别名由一份集中规则配置维护。
- 区域提取和内容标准化只为审查服务提供“区域是否存在”和“本周是否更新”的结果。
- 报告层只消费审查结果，不重复解析 Confluence 页面，也不自行推断状态。
- UI Bridge 和 QML 继续使用现有审查结果契约，不增加并行状态或额外传递链路。

## 报告行为

- Excel 保持现有 12 个审查列、项目分组、颜色、链接、审查周期和 PS 布局。
- `格式有误` 的具体原因写入 PS，例如：`格式有误：查询不到Task Arrangement`。
- `已更新` 和 `未更新` 沿用现有单元格显示方式。
- 不增加新列、新状态或新页面。

## 验收与持久测试

- 目标区域本周有内容变化时，仅对应审查点为 `已更新`。
- 只修改同页其他区域时，对应审查点仍为 `未更新`。
- 只改变空格、换行或纯样式时，对应审查点仍为 `未更新`。
- 同一页面的两个审查区域可以分别得到 `已更新` 和 `未更新`。
- 标准名称及已确认别名均能识别为同一个审查点。
- 找不到区域时为 `格式有误`，并在 PS 写出 `格式有误：查询不到<标准名称>`。
- 一旦格式有误，不再用整页更新时间覆盖该结果。
- 每周一 `00:00` 正确重置时间窗口，周一之前的更新不计入本周。
- 现有 12 列 Excel 结构和 Project 收集、过滤行为的回归测试继续通过。

## 执行清单

1. 收拢 12 个审查点的标准名称、页面归属与别名配置。
2. 以测试先行方式覆盖区域识别、内容标准化、本周窗口和状态优先级。
3. 将审查服务从整页更新时间判断改为目标区域本周更新判断。
4. 保持报告和 UI 的既有契约，仅传递正确的审查结果与 PS 原因。
5. 删除被替代的整页时间判断、重复规则、临时诊断和冗余传递。
6. 完成 Project Audit 定向测试、相关回归测试和 `git diff --check`。

## 明确不做

- 不新增或删减审查点。
- 不改变 Excel 报告格式。
- 不做文字语义或内容质量判断。
- 不添加附件、恢复版本、异常状态等未提出的特殊规则。
- 不改 Project 收集、DOPL/SDPL 合并、筛选或计划业务。
- 不新增并行业务流程、缓存或 UI 功能。
