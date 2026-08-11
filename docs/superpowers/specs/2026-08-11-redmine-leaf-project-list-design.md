# Redmine 叶子项目列表设计

## 目标

Redmine Project 页包含父子项目层级时，SmartTest 项目筛选列表只展示没有子项目的叶子项目，避免同时展示父项目和其下项目造成冗余。

## 已确认规则

- 顶层项目存在子项目时，不展示该顶层项目，继续遍历其子项目。
- 任意层级项目仍存在子项目时，不展示该中间项目，继续向下遍历。
- 没有子项目的项目必须展示，包括没有子项目的顶层项目。
- 展示项使用自身的名称、identifier 和 Project ID，不继承父项目信息。
- 保持 Redmine 查询、缓存、排序和项目筛选接口不变。

## 设计

`tool/SmartHome/redmine/collector.py` 继续作为 Redmine Project 页结构的唯一解析 owner。页面脚本在采集每个 `a.project` 时判断其所属项目节点是否包含直接子项目，并输出 `hasChildren`；`parse_project_nodes()` 过滤 `hasChildren=true` 的节点，因此 Bridge、缓存和 QML 只接收叶子项目，不新增第二套前端过滤逻辑。

## 复用与代码规模

复用现有 `_PROJECTS_SCRIPT`、`parse_project_nodes()` 和 `project_options()` 链路，不引入依赖、不新增业务模块。删除要求“保留所有项目”的旧测试和仅检查脚本文本形状的冗余断言，改为保护最终解析行为的持久回归测试。

## 执行清单

- [x] 修改 `testing/self_tests/tool/smarthome/redmine/test_context_collector.py`，覆盖“有子项目的父节点被过滤、叶子节点保留、无子项目顶层节点保留”。
- [x] 运行新增测试并确认因旧实现保留父项目而失败。
- [x] 修改 `tool/SmartHome/redmine/collector.py`，让 DOM 采集结果携带 `hasChildren` 并在解析边界过滤父节点。
- [x] 运行 Redmine collector 聚焦测试和相关 Redmine 测试。
- [x] 运行 `git diff --check`，检查无无关改动、临时诊断或重复机制。
- [x] 以源码模式执行最高可行的启动验证，不重建安装包。

## 验收标准

- `BDS.KTC` 等存在子项目的项目不出现在 SmartTest 项目列表。
- 其下没有子项目的项目全部保留，顺序与 Redmine 页面一致。
- 没有子项目的顶层项目正常显示。
- 多层项目树只展示最终叶子项目。
- Project ID 显示与现有格式保持一致。
