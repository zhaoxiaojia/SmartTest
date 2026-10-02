# Jira Client 与 MCP 链瘦身

## 已确认范围

Coco 已批准删除独立 Client `T_Jira` 入口、QML、专属 JiraBridge，以及只有该页面使用的 workspace、browse、analysis、conversation、presenter、payload/request/query/factory 链；删除 Jira MCP 和其独占的 `core/mcp`、旧 fields registry/spec/extractors、字段 metadata cache/model/API。按实际消费者删除，不按 Jira 名称批量删除。

保留 Redmine Clone 的共享 Jira 创建/浏览 QML、RedmineBridge、创建/查重/附件/创建元数据；保留 Web Jira/Confluence 当前缓存、账号映射、审查和报告；保留日报基础封装及其他消费者的账号能力。Issue 继续属于 Jira。不新增功能、回退或校验，不为调整目录移动代码。

## Owner 与收敛决定

- 删除独立页面入口及专属服务；`core.jira` 不保留兼容导出。菜单、主页直达入口、QRC、翻译提取和专属测试同步清理。
- 复用现有 `JiraGateway`、Mapper、Repository、IssueCommandService、JiraCreateSchemaService；Clone 使用的 `current_user`、创建元数据、用户搜索、附件和查重不动。
- 日报是 IssueService 唯一剩余业务消费者；保留分页全量查询，删除无作用的 specs/include_heavy/max_workers 和只服务页面的 hydration/page/filter 转发。日报直接使用正式 Issue 字段，不重新建立字段注册层。
- 删除 MCP transport/context 所有独占链及临时 trace；不碰其他 AI 或公共认证功能。配置、文档、测试只按已删除 owner 的实际引用收敛。
- 不创建新 abstraction/transport/cache/report owner，不修改报告格式或时间戳。

## 执行清单

- [x] 记录起点与实际消费者：起始 `git status` 为空，HEAD `3b620a9`。
- [x] TDD 验证简化后的日报轻量查询保持 components/resolution 和无详情请求；删除只保护被移除功能的测试，保留 Gateway 原分页查询。
- [x] 删除独立 Client Jira 与 MCP/字段注册链，清理无消费者转发/配置/调试残留。
- [x] 保留 Clone 创建表单、查重、附件与创建元数据的真实边界测试；保留 Web cache/audit/report 与日报回归。
- [x] 菜单/主页、桥注册、资源和中英文翻译闭环；重建适用 QM/QRC。
- [x] 全 backend/frontend、相关 Core/Client、边界、compile/import、source 有界启动与 `git diff --check`。
- [x] 审查净代码、遗留引用和调试残留，向 Atlas 交付，由 Atlas 独立验收及 Git 操作。

## 约束与交付

Mason 不委派、不 stage/commit/push、不访问真实远端、不清用户数据。保留任何并行用户修改。周额度基线剩余92%，89%报告、87%暂停；无实时读数不声称观察到额度变化。只做 source/resource 验证，不构建桌面包。

## 自测交付

- 轻量日报接口先 RED 两项（旧 specs 强制参数），简化后 GREEN；保留正式字段与单次轻量查询断言。日报真实 service→gateway→mapper→报告流程覆盖当前及13个日期查询。
- 相关 Core/Clone/日报/边界组合239项、backend121项、frontend88项通过；翻译验证2项、lint/build、compile/import、产品边界和 diff-check 通过。
- 共享 Clone 表单使用实际 QML 验证草稿文本编辑及提交信号；账号窗口、共享浏览组件保留。测试按可视树定位 Repeater 中的编辑器，不改变生产实现。
- main/tool source 在隔离本地状态、关闭无关在线壁纸请求的验证环境中各运行6秒，未见QML/Traceback错误；未构建包、未做真实远端业务验证。
- 两份TS只删除退休上下文/条目，没有新增 unfinished；既有非本轮条目保持。仅保护退休Client/MCP的正式测试删除，ignored本地旧测试不批量纳入/重写。
