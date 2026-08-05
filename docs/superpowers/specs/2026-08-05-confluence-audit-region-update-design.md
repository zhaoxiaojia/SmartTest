# Confluence 项目审查区域更新判定设计

## 目标

修正 Project Audit 目前按整页更新时间判断多个审查点的问题。审查应先识别目标审查区域，再判断该区域本周是否真正更新，避免用户只修改页面其他内容就让所有审查点同时显示“已更新”。

本次保持现有 Project 收集、筛选及页面展示格式不变，并将报告审查列收敛为 10 个经确认的 Confluence 真实路径。

## 范围

本次只处理以下 10 个审查点。列名中的每一级只能来自 Confluence 页面树、页面标题或页面内真实字段；项目名、序号和星标等动态前缀不进入列名。邮件文字只描述审查要求，不用于命名列。

| Confluence 审查列名 | 邮件中的对应描述 |
|---|---|
| `Project Status Report.Highlights` | 检查 highlights 是否有链接 |
| `Project Status Report.Impact issues` | 检查 impact issue 是否有链接 |
| `Basic Information.Test Information.Phase Status（当前阶段测试状态）` | 检查信息是否每周更新 |
| `Basic Information.Test Information.项目整体状态Summary` | 检查测试结果是否进行了 summary |
| `Basic Information.Test Information.Task Arrangement of Important Test（Must give ETA）` | 检查 task 到期是否完成 |
| `Basic Information.Test Information.Blocking QA Testing Items` | 检查 block QA 测试问题状态是否更新 |
| `Basic Information.Test Information.Test Plan.Category` | 检查 QA test plan 是否更新、不是默认模板并细化到每周 |
| `Basic Information.Test Information.Test Environment Setup and Precautions.测试环境搭建以及注意事项` | 检查是否记录项目环境搭建方式 |
| `Basic Information.Test Information.Summary of Experience and Typical Cases` | 检查项目结束后是否记录经验总结和典型案例 |
| `Basic Information.Test Information.Test Report Store` | 检查项目是否定期上传测试报告进行备份 |

`Test Environment Setup and Precautions.常用Log信息` 整项取消，不保留规则、定位逻辑、报告列或测试。`经验总结` 和 `典型案例` 不再拆分，统一审查 `Summary of Experience and Typical Cases` 页面。邮件描述只建立对应关系，不在本次新增链接存在性、到期完成质量、模板质量或内容语义判断。

## 审查时间窗口

- 时区固定为 `Asia/Shanghai`。
- 每周一 `00:00` 重置本周审查时间窗口。
- 手动执行时，窗口为本周一 `00:00` 至实际执行时间。
- 审查结果只回答目标审查区域在该时间窗口内是否发生有效内容更新。

## 审查区域识别

每个审查点由 Confluence 真实路径、页面归属和一组真实字段定位。识别顺序为：

1. 标题区域；
2. 表格字段名及其对应单元格或后续表格；
3. Confluence 宏标题；
4. 经 Coco 确认的同一 Confluence 字段写法。

列名始终使用上表中的真实标准路径。不得用邮件描述、自创英文标准名或宽泛关键词替代 Confluence 字段，不得在定位失败时退化为比较整个页面。后续出现新的合法模板写法时，必须先确认它对应同一 Confluence 字段，再扩充该审查点的定位规则。

`Summary of Experience and Typical Cases` 和 `Test Report Store` 以页面本身作为审查点，不强行追加页面中不存在的字段。找不到 `Test Report Store` 页面或页面没有可审查内容时，输出 `格式有误：查询不到Test Report Store`；定位成功后再判断本周是否更新。

## 更新判定

1. 定位当前审查点的目标区域。
2. 定位失败时，结果单元格写入 `格式有误：查询不到<标准名称>`；不再判断更新时间。
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

- Excel 保持现有项目分组、颜色、链接、审查周期和 PS 布局，审查列按上表调整为 10 列。
- `格式有误` 的具体原因直接写入对应审查单元格，例如：`格式有误：查询不到Task Arrangement of Important Test（Must give ETA）`。
- PS 不重复审查单元格中的格式错误；没有其他信息时留空。
- `已更新` 和 `未更新` 沿用现有单元格显示方式。
- 不增加新列、新状态或新页面。

## 验收与持久测试

- 目标区域本周有内容变化时，仅对应审查点为 `已更新`。
- 只修改同页其他区域时，对应审查点仍为 `未更新`。
- 只改变空格、换行或纯样式时，对应审查点仍为 `未更新`。
- 同一页面的两个审查区域可以分别得到 `已更新` 和 `未更新`。
- 上表中的 Confluence 真实字段及经确认的同字段写法均能识别为同一个审查点。
- 找不到区域时，对应单元格写出 `格式有误：查询不到<标准名称>`，PS 不重复显示。
- 一旦格式有误，不再用整页更新时间覆盖该结果。
- 每周一 `00:00` 正确重置时间窗口，周一之前的更新不计入本周。
- Excel 准确输出 10 个真实路径列名，Project 收集和过滤行为的回归测试继续通过。
- 报告和规则中不再出现 `Weekly Information`、`Test Result Summary`、`Task Arrangement`、`Blocking QA Issues` 等自创列名。
- `常用Log信息` 规则及其定位代码、报告列和测试全部移除。
- `Summary of Experience and Typical Cases` 只产生一个审查结果和一个报告列。

## 执行清单

1. 将审查配置收敛为上表 10 个 Confluence 真实路径及字段定位。
2. 以测试先行方式覆盖区域识别、内容标准化、本周窗口和状态优先级。
3. 将审查服务从整页更新时间判断改为目标区域本周更新判断。
4. 保持报告和 UI 的既有契约，仅传递正确的审查结果与单元格错误原因。
5. 删除常用 Log 审查、经验/案例拆分、自创列名、被替代的整页时间判断、临时诊断和冗余传递。
6. 完成 Project Audit 定向测试、相关回归测试和 `git diff --check`。

## 明确不做

- 除明确取消常用 Log、合并经验与案例外，不新增或删减审查点。
- 除审查列由 12 列调整为 10 列及列名改为真实路径外，不改变 Excel 报告格式。
- 不做文字语义或内容质量判断。
- 不添加附件、恢复版本、异常状态等未提出的特殊规则。
- 不改 Project 收集、DOPL/SDPL 合并、筛选或计划业务。
- 不新增并行业务流程、缓存或 UI 功能。
