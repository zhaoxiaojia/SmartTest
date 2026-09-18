# 人员名单与产品线人工维护规则

## 当前有效方案

Coco 已确认改为人工维护 `core/config/personnel.json`，撤销原 Confluence 组织架构自动解析、账号搜索复核及登录/会话恢复调度。现有 Confluence 项目事实、角色解析、详情刷新及授权功能保持不变。本次不实现来源脚本或定时同步机制。

FAE-QA 的五线归属使用 Core canonical 常量：China Operator Business、Smart Device Business、TV Business、Global Operator & STB Business、Wireless Connection。本轮确认名单分别为6、5、34、12、12人，共69个归属。未列入五线的已有 QA 只移除五线旧归属，不推断离职，不删除其他人员字段。其他部门和 technical centers 保持原值。

确认的身份修正仅为 Lingguo Bu/`lingguo.bu` → Linguo Bu/`linguo.bu`，Tianwei Xie/`tianwei.xie` → Tianxiang Xie/`tianxiang.xie`；替换原记录及同配置内部引用，不创建双记录。Xiaoshuang Ni 原空账号补为 `xiaoshuang.ni`。新增明确 Zonghao Ma/`zonghao.ma`，归属为空；不能据此替换身份未确认的 Zongwu Ma。Meiling Zhu 仅保留 TV。数字后缀原样保留。

离职人员仅在精确身份命中时标记 active=false，保留其他字段；未知账号不猜测。未明确新增的 `jiajia.mu` 不录入。

## Self-Test 数据边界

Self-Test 页面与 Dashboard 复用同一 Core 固定 JQL 声明：issuetype=Bug、Channel of Reporter=Self-Test、本年创建范围、reporter IN(有效 FAE-QA account)。没有旧 assignee、项目或 labels 排除。用户条件与固定声明仅通过 Core compose_jql 求交集，校验、执行和 SQLite 保存使用同一 effective_jql。未选条件不能取消固定边界。空名单明确失败，不发送 reporter IN() 或全量兜底。

统计按 reporter 分组，而不是 assignee；先按 personnel 判断 Wireless 归属，命中则直接计入，不限制 Jira 项目；其他人员按既有 project 映射。已应用集合是统计总数权威，非 Wireless 的未知项目保留在总数和既有诊断计数，不捏造归属。WIRELESS_CONNECTION 的 jira_project_keys 为空，不绑定其他四线项目。

SQLite 旧卡片快照只有 effective JQL 与当前名单/年度固定边界一致才有效；不匹配返回既有 no_snapshot，不自动发远端请求。新任务运行期间保持轮询，但不把过期范围当作有效图。Dashboard 与 Jira 统一读取账号+Self-Test 卡片的 analytics 快照，使用同一 roster fingerprint 失效边界，普通重新登录恢复最后有效条件和结果，不保留独立 Dashboard 数据路径。

共享过滤器、独立卡片查询、快照与任务隔离、展示缓存规则统一遵循 [全局异步任务规则](2026-08-31-global-async-task-manager-design.md)，此处不再保留已撤销的同步实现描述。

## 本轮执行清单

- [x] 人工五线归属与两组账号替换、空账号补充、Zonghao 空归属。
- [x] 移除组织架构同步 owner、自动 scheduler、专用账号查询与相关测试。
- [x] Self-Test 固定 QA reporter 边界、reporter 统计、空名单拒绝及旧快照失效。
- [x] 完整后端262、前端199、相关 Core/边界检测器单元测试56通过；lint/build 与 diff check 通过。
- [ ] 仓库产品边界扫描：既有 `.superpowers` 根目录触发 retired owner 错误，未擅自删除范围外目录。
