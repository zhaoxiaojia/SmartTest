# Confluence Project Space 汇总表筛选设计

## 1. 目标

Project Weekly Audit 以 DOPL、SDPL 两个 Project Space 页面中的 Stiltsoft Table Filter 源汇总表作为唯一候选项目数据源。SmartTest 不遍历年份目录，不为刷新过滤器逐个读取项目入口，也不依赖 Table Filter 的动态浏览器 session。

## 2. 数据来源

- `https://confluence.amlogic.com/display/DOPL/Project+Space`
- `https://confluence.amlogic.com/display/SDPL/Project+Space`

每个页面只读取一次渲染后的汇总表。目标表必须包含：

- `页面`
- `Date of Commercial approval`
- `Support Mode`
- `Project Status`

`Project ID` 可作为显示或业务元数据，但不是候选资格前提。其他列不参与筛选。

## 3. SmartTest 过滤器

- Years：从 `Date of Commercial approval` 中解析有效日期并取年份集合。
- Support modes：从 `Support Mode` 列取非空规范化值集合。
- Project statuses：从 `Project Status` 列取非空规范化值集合。
- 用户应用过滤时，只在已加载的两张汇总表数据上执行 Year + Mode + Status 交集。
- 未选择某个维度表示该维度全选。

SmartTest 不展示或处理 Current Stage、Owner、ODM、OEM、OS、日期以外的其他条件。

## 4. 项目身份与审查

- 项目名称和 URL 来自汇总表 `页面` 列。
- 内部身份使用 `space_key + canonical page URL/pageId`，跨空间不合并。
- 刷新过滤选项不访问项目详情。
- 仅在用户开始审查后读取入选项目页面及其审查子页面。

## 5. 性能与状态

- 一次刷新最多读取 DOPL、SDPL 两个汇总页面及必要分页，不产生逐项目 N+1 请求。
- 同一账户同一时刻只允许一个刷新任务；重复点击不创建并行请求。
- 新刷新开始时清空旧 available/candidate 数据，避免显示误导性的 `1 available`。
- 单个空间失败时保留另一空间结果，并明确标记部分结果。
- 缓存以账户和两个汇总页面版本为边界；手动刷新强制重新读取。

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

- 刷新只读取两个 Project Space 汇总页面，不读取任何项目详情。
- 前端三个过滤器选项与汇总表中对应字段一致。
- Year 使用 Date of Commercial approval，而不是目录年份。
- 应用过滤后候选数量与同字段条件下的 Confluence 汇总表一致。
- 重复点击不会创建并行发现。
- History 前端与业务代码完全移除。
- 旧逐项目发现机制和冗余测试删除。
- scoped tests、全部 support tests、UI 契约、compileall、diff check 通过。
