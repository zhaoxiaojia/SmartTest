# Confluence 项目集合与定期审查设计

## 1. 背景与目标

Project Weekly Audit 当前仅以 Muffin314 作为固定种子，并同时执行页面更新时间和页面内容审查。本次调整将项目来源切换为 Confluence `Project Space`，通过统一的项目集合过滤器选择审查对象；审查阶段仅判断既定 QA 页面是否在本周更新，不再判断页面内部内容。

同一套集合及审查逻辑同时服务于：

- 用户在 SmartTest 中主动发起的自定义集合审查；
- 每周五 `00:05` 自动执行的静默审查；
- 前端对本机已注册审查计划的查看、启用、停止和编辑。

Project Weekly Audit 的输出格式为 PDF，Jira Format Audit 继续使用 Excel。

## 2. 已确认业务规则

### 2.1 默认审查集合

项目来源为：

`https://confluence.amlogic.com/display/DOPL/Project+Space`

默认过滤条件：

- 年份为当前年和上一年；在 2026 年运行时即为 2025、2026；
- `Support Mode = A`；
- `Current Stage = IN DEVELOPMENT`；
- 排除 POC、pending 和已结案项目。

年份按执行日期动态计算，不将 2025、2026 永久写死在代码中。

### 2.2 审查周期

- 审查窗口起点：本周周一 `00:00`；
- 审查窗口终点：本周周五 `00:00`，终点不包含；
- 自动执行时间：每周五 `00:05`；
- 周五 `00:00` 以后发生的更新计入下一审查周期。

### 2.3 页面范围

沿用邮件《Confluence 自动检查工具开发需求》及现有实现中的 QA 页面范围，不重新定义页面责任：

- Project Status Report；
- Test Information；
- Test Plan；
- Test Environment Setup and Precautions；
- Test Report Store；
- Summary of Experience and Typical Cases 仍仅在项目结束场景适用，不纳入当前开发中项目的每周更新失败判定。

### 2.4 当前启用的规则

每个应审页面仅检查：

1. 页面是否存在；
2. 页面是否可读取；
3. 页面是否在本次审查窗口内更新。

页面存在但没有本周版本更新时判定为 `failed`。无法获得版本或更新时间、无法可靠判断时判定为 `unknown`，不得伪判为未更新。

### 2.5 停用的内容规则

以下规则保留实现但不进入当前执行规则集：

- summary 内容；
- QA task、到期状态；
- Highlights、Impact issue 链接；
- 测试指标、总数和通过率；
- failure summary 与 Jira 链接；
- Test Plan 内容、模板和周粒度；
- 环境搭建内容完整度；
- 测试报告附件、链接及 N/A 原因；
- DeepSeek 文本或图片内容审查。

不通过大段源码注释控制功能。规则 owner 提供明确的 `content_review` 能力开关或规则集选择，默认及计划执行均关闭该能力。这样停用状态可测试、可观察，也能在后续需求确认后安全恢复。

## 3. 统一领域模型

### 3.1 `ConfluenceProject`

表示从项目年份页面解析出的单个项目：

- `year`；
- `project_id`；
- `name`；
- `status_page_id`；
- `status_url`；
- `home_url`；
- `project_status`；
- `current_stage`；
- `support_mode`；
- `project_owner`；
- Project Space 表格中后续过滤或展示所需的其他原始字段。

字段缺失时保留空值和解析诊断，不以猜测值填充。

### 3.2 `ProjectCollectionFilter`

表示可持久化、可复用的集合条件：

- `source_url`；
- `years`；
- `support_modes`；
- `project_statuses`；
- `current_stages`；
- `included_project_ids`。

`included_project_ids` 为空表示选取其他条件过滤后的全部项目；非空表示在过滤结果上进一步限定用户勾选的项目。过滤值使用 Confluence 原始机器文本的规范化形式，前端显示文案与机器值分离。

### 3.3 `ProjectCollection`

表示某次发现及过滤结果：

- 稳定集合 ID；
- 用户可见名称；
- `ProjectCollectionFilter`；
- 发现时间；
- 项目列表；
- 被排除项目及原因的可选诊断摘要。

集合 ID 由规范化过滤条件稳定计算或在用户保存时生成，不能因项目列表顺序变化而改变。

## 4. Project Space 发现与过滤

发现流程为：

1. 读取 `Project Space`；
2. 定位过滤器中的年份页面，例如 `2025 Projects`、`2026 Projects`；
3. 读取年份页中的项目表格；
4. 按表头名称映射 `Project ID`、`Project Status`、`Current Stage`、`Support Mode` 等字段；
5. 将每行转换为 `ConfluenceProject`；
6. 使用同一个 `ProjectCollectionFilter` 完成过滤；
7. 将 `ProjectCollection` 交给审查服务。

解析依赖表头语义，不依赖固定列序号。年份页缺失、必要表头缺失或同一项目出现冲突记录时返回明确诊断，不静默跳过。

默认计划和自定义计划不得拥有各自的发现器或过滤实现。

## 5. 统一审查执行链

主动审查和计划审查共用以下执行链：

```text
ProjectCollectionFilter
  -> Project Space discovery
  -> ProjectCollection
  -> project page discovery
  -> weekly update audit
  -> failure evidence capture
  -> audit history
  -> PDF report
```

两种触发方式只提供不同的执行上下文：

- `manual`：用户从前端主动执行；
- `scheduled`：Windows 任务按计划 ID 调用后台入口。

执行上下文可以进入报告元数据，但不得改变项目发现、规则、截图或报告逻辑。

## 6. 本机审查计划

### 6.1 调度 owner

采用 Windows Task Scheduler。SmartTest 使用固定任务名前缀：

`SmartTest.ProjectWeeklyAudit.`

只有此前缀且任务定义满足 SmartTest 合约的任务才显示为本工具计划。不得把其他 Windows 任务误识别为审查计划。

### 6.2 `AuditPlan`

计划模型包含：

- `plan_id`；
- `name`；
- `collection_filter`；
- 固定调度规则：每周五 `00:05`；
- `enabled`；
- Windows 任务名；
- Credential Manager 凭据引用 ID；
- 创建和更新时间；
- 上次执行时间、状态和报告路径；
- 下次执行时间。

计划配置保存在 SmartTest 应用数据目录，采用版本化 JSON。Windows 任务只携带 `plan_id`，不携带过滤条件、用户名或密码。

### 6.3 发现与去重

前端每次进入计划区域时：

1. 读取 SmartTest 计划配置；
2. 查询带固定前缀的 Windows 任务；
3. 按 `plan_id` 合并两侧状态；
4. 显示启用、停止、缺失任务或孤立任务等真实状态；
5. 计算或读取下次执行时间和上次执行结果。

保存相同 `plan_id` 时更新原任务，不创建重复任务。计划注册应具备幂等性。

### 6.4 停止与删除

“停止”表示禁用 Windows 任务，保留：

- 计划配置；
- 集合条件；
- 历史报告；
- 上次执行状态。

删除计划属于独立的破坏性操作，不由“停止”隐式触发。本阶段前端至少提供停止和重新启用；是否暴露删除入口可在实现计划中保持最小范围。

## 7. LDAP 凭据

静默任务使用 Windows Credential Manager 保存 LDAP 凭据。

安全要求：

- JSON、命令行、Windows 任务参数、日志、历史和 PDF 中不得出现密码；
- 计划配置仅保存不可逆推出密码的凭据引用 ID；
- 后台入口按引用 ID读取凭据；
- 用户重新登录并保存计划时可以更新同一凭据条目；
- 凭据缺失或失效时不删除计划，运行记录为认证失败；
- 前端提示用户重新登录并更新计划凭据；
- 停止计划不删除凭据；删除计划时才单独处理凭据生命周期。

## 8. 后台入口

新增最小命令行入口，输入仅为 `plan_id`。入口负责：

1. 加载计划；
2. 从 Credential Manager 获取 LDAP 凭据；
3. 调用统一审查执行链；
4. 保存历史和 PDF；
5. 写入不含敏感信息的结构化运行状态；
6. 返回可供 Windows Task Scheduler 记录的退出码。

后台入口不复制 UI bridge 逻辑，也不依赖 QML。

## 9. 前端

Project Weekly Audit 页面包含三个区域。

### 9.1 项目集合过滤器

- Project Space 地址；
- 年份多选；
- Support Mode 多选；
- Project Status 多选；
- Current Stage 多选；
- 刷新项目；
- 过滤后的项目勾选列表；
- 项目总数及排除摘要。

默认先呈现已保存或默认过滤条件，再异步刷新 Confluence 数据。LDAP 密码不得进入前端持久化状态。

### 9.2 主动审查

- 使用当前集合立即审查；
- 只展示需要跟进的项目；
- 展示未更新、缺失或无法读取的页面；
- 展示截图并支持点击放大；
- 提供 Confluence 跳转链接；
- 导出或打开 PDF。

### 9.3 审查计划

展示当前电脑检测到的全部 SmartTest Project Weekly Audit 计划：

- 名称；
- 集合条件摘要；
- 当前状态；
- 下次执行时间；
- 上次执行时间和结果；
- 最近报告；
- 启用或停止；
- 编辑集合条件。

计划列表必须来自本机任务和配置的实际对账结果，不使用仅存在于当前进程的临时列表。

## 10. PDF 报告

Project Weekly Audit 通过全局 `support/report/` PDF 接口导出，不直接调用 Qt WebEngine 或自行维护第二套 PDF 转换器。

PDF 至少包含：

- 审查周期；
- 触发方式；
- 项目集合和过滤条件；
- 审查项目数及需要跟进项目数；
- 每个失败或 unknown 页面；
- 更新时间判定说明；
- 调整建议；
- 嵌入的截图；
- 可点击的 Confluence 链接。

Jira Format Audit 的 Excel exporter 保持不变。

## 11. 错误处理

- 年份页或项目表格无法读取：集合发现失败，报告明确错误，不退回固定项目；
- 单个项目无法读取：保留该项目并产生 `unknown`；
- 单个页面无法读取：产生页面级 `unknown`；
- 截图失败：不改变业务状态，显示证据不可用并保留链接；
- PDF 失败：审查历史仍保存，运行状态标记报告生成失败；
- Credential Manager 失败：不尝试从其他位置读取明文密码；
- Windows 任务注册失败：不把计划显示为启用成功；
- 计划配置与 Windows 任务不一致：前端显示对账状态并允许修复或重新启用。

## 12. 测试与验收

### 12.1 项目集合

- 2025、2026 年份页解析；
- 表头顺序变化；
- A 类与非 A 类过滤；
- IN DEVELOPMENT 与排除状态过滤；
- 用户勾选项目；
- 缺失年份、表头和冲突项目诊断；
- 默认年份随执行日期滚动。

### 12.2 更新时间审查

- 周一 `00:00` 更新计入本周；
- 周四 `23:59:59` 更新计入本周；
- 周五 `00:00` 更新不计入本周；
- 每个既定 QA 页面均使用同一更新时间规则；
- 内容变化不再影响结果；
- 内容审查器和 DeepSeek 不被调用。

### 12.3 计划管理

- 注册、读取、更新同一计划不重复；
- 停止后 Windows 任务禁用且历史保留；
- 重新启用恢复同一任务；
- 列出本机已存在计划；
- 配置缺失、任务缺失及孤立任务对账；
- 下次执行时间为周五 `00:05`；
- 命令行和配置中不出现密码。

### 12.4 集成验收

- 用真实 `Project Space` 获取近两年 A 类开发中项目；
- 主动审查和计划入口对同一过滤器得到相同集合及结果；
- 真实 Windows 任务可以在 SmartTest 关闭时运行；
- Credential Manager 凭据可用且无敏感数据泄漏；
- PDF 包含集合摘要、失败截图和可点击链接；
- 前端能发现、停止并重新启用当前电脑上的计划。

## 13. 范围外

- 恢复内容语义审查；
- DeepSeek 模型更换或 prompt 优化；
- 非 Windows 调度支持；
- 跨电脑同步计划；
- 服务器端集中调度；
- 自动发送邮件或消息；
- 更改 Jira Format Audit 的 Excel 输出。
