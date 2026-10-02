# Confluence 多 Project Space 项目发现机制设计

## 1. 目标

Common Tools 的 Project Weekly Audit 同时发现以下两个 Confluence 项目空间中的项目：

- `DOPL`：`https://confluence.amlogic.com/display/DOPL/Project+Space`
- `SDPL`：`https://confluence.amlogic.com/display/SDPL/Project+Space`

用户仍只通过年份、`Support Mode` 和 `Project Status` 筛选项目。当前不提供 Project Space 过滤器，也不要求用户理解或区分 DOPL 与 SDPL。

## 2. 项目资格

项目是否进入候选列表只由以下条件决定：

1. 项目直属年份页属于用户选择的年份；
2. 项目入口页的 `Support Mode` 属于用户选择值；
3. 项目入口页的 `Project Status` 属于用户选择值。

`Current Stage`、Project Owner、ODM、OEM/Operator、Key Part Number、Launch OS、日期及其他属性不参与资格判断。字段缺失、为空或格式异常不得因此排除项目。

## 3. 权威层级

两个空间使用同一发现约定：

```text
Project Space
└─ YYYY Projects
   └─ 项目总入口
      ├─ Project Target
      │  ├─ Project ID
      │  ├─ Support Mode
      │  └─ Project Status
      └─ 项目审查子页面
```

- `Project Space` 的直属年份页是年份 owner。
- `YYYY Projects` 的直属子页面是项目总入口。
- 项目总入口的标题和 URL 是候选列表、报告及打开项目链接的权威值。
- Basic Information、Project Status Report 及更深子孙页面不是项目入口，只能作为属性或审查页面。

## 4. 发现与过滤流程

1. 依次读取 DOPL、SDPL 的 Project Space。
2. 从每个 Project Space 的直属子页面识别 `YYYY Projects`。
3. 仅遍历用户所选年份；刷新过滤选项时遍历两个空间可见年份的并集。
4. 获取每个年份页的直属子页面，按 `space_key + project_root_page_id` 建立项目身份。
5. 获取项目入口页，从 Project Target 表读取：
   - `Support Mode`：资格判断必需；
   - `Project Status`：资格判断必需；
   - `Project ID`：存在时作为业务元数据，不作为发现前提。
6. 在本地应用年份、Mode、Status 三项过滤。
7. 合并两个空间的结果并按现有候选列表规则排序。
8. 仅对用户最终选择的项目继续发现审查子页面。

不得使用年份汇总表中的 Project Link、Project ID 或其他列作为项目发现入口，也不得从任意深层子页面反向猜测项目根。

## 5. 内部模型与未来扩展

每个项目内部保留 `space_key` 和项目根 `pageId`，形成跨空间稳定身份。当前 UI 不展示也不过滤 `space_key`。

如果未来需要按 Project Space 筛选，只在现有集合过滤器和 UI 上增加 `space_key` 条件；项目发现、身份和审查流程无需拆分或重写。

## 6. 异常处理

- 单个项目入口无法读取：记录该项目的结构/访问错误，继续同年份其他项目。
- 单个年份页无法读取：记录空间和年份级错误，继续其他年份。
- 单个 Project Space 无权限或不可用：继续另一个空间，同时在集合状态中明确结果不完整。
- 项目缺少 `Support Mode` 或 `Project Status`：不能判断是否匹配筛选器，记录为不可判定，不静默纳入或排除。
- 不记录页面正文、项目名称、Project ID、人员或凭据到诊断日志；只记录空间、年份和聚合计数。

## 7. 删除与复用

复用：

- 现有 Confluence 只读 client；
- `get_page_children`、页面读取和 Project Target 表解析能力；
- 现有年份、Mode、Status 过滤 owner；
- 现有项目页面审查和报告流程。

删除：

- 年份汇总表 HTML 行解析；
- 年份表必填列校验；
- Project Link 到项目根的 parent-chain 反向解析；
- 因错误入口产生的根目录距离选择和去重补救；
- 仅为旧发现机制存在的测试、兼容路径和诊断字段。

不增加第三套项目发现流程，不保留新旧机制开关。

## 8. 验收标准

- DOPL 与 SDPL 的所选年份项目均进入统一候选集合。
- 候选资格只由 Year、Support Mode、Project Status 决定。
- 同名或相同 Project ID 的跨空间项目不会互相覆盖。
- 项目名称和项目链接始终指向年份页直属项目总入口。
- Basic Information、Status Report 和错误嵌套页面不会成为独立项目。
- 其他项目属性缺失或异常不影响候选资格。
- 一个空间失败时另一个空间仍可用，且结果明确标记为不完整。
- 删除旧年份表发现机制，无平行兼容流和冗余代码。
- 聚焦项目发现、集合过滤、bridge、报告测试以及全部 support self-tests 通过。
- 不执行 Confluence 写操作，不输出敏感页面内容。
