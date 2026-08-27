# SmartTest Web 长期开发设计

## 1. 文档定位

本文档是 SmartTest Web 长期开发的产品与架构基线，记录已经由 Coco 确认的目标、数据权威、权限原则、模块边界、交付顺序和验收标准。后续采用“单模块设计、单模块实现、单模块验收，最后整合”的方式推进，不反复重新整理已经确认的共同背景。

本文档不授权一次性实现全部模块。每个模块开始前仍需形成该模块的具体设计与验收标准并由 Coco 确认；模块设计不得改变本文档已经确定的产品边界。

## 2. 产品定位

SmartTest Web 的长期定位是面向测试团队的完整管理平台，而不只是数据看板。平台最终覆盖：

- Home 管理工作台；
- Confluence 项目聚合与项目进度；
- 项目阶段审查与历史回溯；
- 人员、组织和数据权限；
- 人员工作量分析；
- 管理岗客观参考指标；
- Jira、Redmine 等第三方缺陷/任务数据；
- 后续接入 SmartTest 测试任务、执行和报告数据；
- 现有 Wi-Fi Database。

当前阶段以访问、聚合、分析和 Web 自有历史记录为主，尽量不修改 Confluence、Jira、Redmine 等第三方平台数据。

## 3. 已有基础

### 3.1 Web 产品边界

现有 `web/` 已采用以下依赖方向：

```text
web/frontend -> web/backend -> core
```

- 前端使用 Vite、SmartTest 主题样式、Chart.js、ExcelJS 和 jsPDF；
- 后端使用 FastAPI；
- 浏览器只调用 Web API，不直接访问 `core/`；
- Web 后端负责认证、权限、请求编排、传输模型和 Web 自有持久化；
- 核心业务继续由 `core/` 中的既有 owner 负责；
- 现有 Wi-Fi Database 保持只读查询边界。

### 3.2 可复用能力

后续开发必须先复用仓库已有能力，除非 Coco 明确要求独立封装：

- `core/config/personnel.json`：人员、职级、汇报关系、产品线分配、专业领域、系统角色和第三方账号映射；
- 现有 SmartTest 认证体系：账号身份和登录逻辑；
- `core/tools/common/project_weekly_audit/`：Confluence 跨 Space 项目发现、稳定项目身份、项目过滤、页面历史、周更新审查、手动/定时审查、审查结果和报告；
- 既有 Jira、Redmine 集成；
- 既有公共调度、日志和配置能力；
- 后续既有 SmartTest 测试任务、运行、步骤和报告 owner；
- 现有 Wi-Fi Database 查询和图表能力。

Web 不建立平行的人员清单、项目清单、账号体系、Confluence 采集器、审查器、调度器或测试执行模型。

## 4. 总体架构

采用模块化单体，保持一套 Web 前端、一套 Web 后端和统一部署边界。模块内部独立，跨模块只通过明确接口协作。

```text
Web Frontend
  -> Web Backend
       -> 身份与权限模块
       -> Home 聚合模块
       -> 项目模块
       -> 审查与历史模块
       -> 人员模块
       -> 工作量模块
       -> 参考指标模块
       -> Wi-Fi Database 模块
       -> core 既有业务 owner
       -> Web 自有数据库
```

### 4.1 Web 后端职责

- 复用现有认证并识别当前账号；
- 将账号映射到 `personnel.json` 人员；
- 计算页面和数据范围权限；
- 编排 Confluence、Jira、Redmine、SmartTest 等数据；
- 将核心模型转换为稳定的 Web API 契约；
- 保存 Web 自有的项目快照、阶段审查、指标结果和审计记录；
- 对外部依赖失败、超时、权限不足和部分数据缺失提供明确状态；
- 禁止浏览器绕过后端直接访问第三方平台或 `core/`。

### 4.2 Web 前端职责

- 路由、布局、交互和展示状态；
- 通过 API 获取已经过权限过滤的数据；
- 显示加载、空数据、部分可用、失败和无权限状态；
- 不推导管理范围，不自行拼接第三方业务关系，不保存权威业务结果；
- 使用接近 Fluent UI 的统一视觉体系。

## 5. 数据权威与读写边界

### 5.1 项目数据

- Confluence 是项目主数据源；
- 项目档案、阶段、计划、进度、负责人、里程碑和审查材料以 Confluence 为主；
- Jira、Redmine 等第三方缺陷/任务平台为辅助数据源；
- SmartTest 后续提供测试任务、执行量、结果和报告数据；
- 多来源发生冲突时不静默覆盖，页面应展示来源和更新时间；
- 当前阶段不通过 Web 修改第三方平台数据。

项目范围直接复用现有 Confluence 跨 Space 发现、稳定身份和过滤规则，不维护 Web 专用项目清单。

### 5.2 人员数据

`core/config/personnel.json` 是人员身份、组织关系、职级、产品线分配和系统角色的唯一来源。Web 不复制人员档案。当前人员模块以读取和展示为主，人员配置编辑不在当前范围。

### 5.3 Web 自有数据

以下信息由 Web 自有数据库持久化：

- 定期项目快照；
- 管理岗执行阶段审查时形成的正式节点快照；
- 审查人、审查时间、审查结论、意见和证据引用；
- 快照对应的数据来源、采集时间和统计口径版本；
- 工作量与客观参考指标的周期性计算结果；
- 与敏感操作相关的审计记录。

Web 自有数据库与 Wi-Fi Database 分离。Wi-Fi Database 继续只接受参数化只读查询，不承担项目历史或审查数据写入。

## 6. 身份与权限

### 6.1 身份来源

- 复用现有 SmartTest 账号登录和身份体系；
- 登录账号匹配 `personnel.json` 的 `account`；
- 未匹配到有效人员配置的账号不得默认获得业务数据权限；
- 认证、会话和人员身份由后端确认，前端不得声明身份。

### 6.2 I 岗权限

I 岗默认只能查看：

- 自己的工作量和客观参考指标；
- 自己参与或负责的项目；
- 与自己业务范围相关的审查和历史信息；
- 角色授权的公共业务数据。

### 6.3 M 岗权限

M 岗可见范围由以下关系取并集并去重：

1. 根据 `reports_to` 递归得到直接和间接下属；
2. 若本人是产品线负责人，加入该产品线分配的全部人员。

高级 M 岗通过汇报树自然覆盖下级管理岗及其团队。M 岗只能查看其负责范围内人员、项目、工作量和参考指标。权限结果应保留命中原因，如“汇报关系”或“产品线负责人”。

### 6.4 强制约束

- 数据范围必须在后端执行；
- 页面、API、统计和导出复用同一权限结果；
- 不信任前端传入的人员账号、产品线或管理范围；
- 不允许通过直接请求 API 或导出绕过权限；
- 权限不足返回明确但不泄露目标数据的结果。

## 7. 业务模块

### 7.1 身份与权限模块

目标：建立所有后续模块共同使用的当前用户和数据范围基础。

主要能力：

- 复用现有登录；
- 当前用户资料；
- I/M 岗识别；
- 汇报树和产品线管理范围；
- 页面、API 和导出权限；
- 权限原因与诊断信息；
- 无匹配、停用人员和配置异常处理。

### 7.2 人员模块

主要能力：

- 人员目录和搜索；
- 部门、团队、Division、职级、岗位筛选；
- 汇报关系和组织树；
- 产品线负责人及成员；
- 人员详情、参与项目、工作量和参考指标入口；
- 只展示当前用户有权查看的人员。

当前不通过 Web 编辑 `personnel.json`。

### 7.3 项目模块

主要能力：

- 复用 Confluence 跨 Space 项目发现；
- 按产品线、年份、项目状态、支持模式、阶段、负责人筛选；
- 项目列表、状态、阶段、进度、负责人、更新时间和风险摘要；
- 项目详情，包括档案、阶段、里程碑、更新情况、成员、缺陷/任务和测试数据；
- 保留来源链接，允许回到 Confluence、Jira 或 Redmine 核查；
- 当前不修改第三方项目数据。

### 7.4 审查与历史模块

采用自动快照与人工阶段节点相结合：

- 定期任务采集项目快照，形成连续趋势；
- 管理岗执行项目审查时保存正式阶段节点；
- 人工节点不可覆盖，后续变化形成新记录；
- 支持项目、阶段和时间维度回溯；
- 记录审查人、结论、意见、证据、来源、采集时间和口径版本；
- 复用现有 Confluence 审查规则、调度和项目模型；
- 外部数据读取失败时记录失败事实，不以旧数据冒充新快照。

### 7.5 工作量模块

当前综合以下数据：

- Confluence：项目投入、更新、计划推进和周报活动；
- Jira：任务/缺陷创建、跟进、处理和完成情况。

后续加入：

- SmartTest 测试任务量；
- 用例执行量；
- 自动化执行量；
- 结果、报告和其他已确认的测试事实。

计算原则：

- 通过 `personnel.json` 的账号及第三方映射统一人员身份；
- 不将不同来源条目简单相加；
- 先保存和展示分来源原始指标，再根据未来确认的规则形成综合工作量；
- 每项指标带统计周期、来源、更新时间和口径版本；
- 缺少可靠数据时显示缺失，不估算、不生成模拟值。

### 7.6 客观参考指标模块

当前只为管理岗提供客观参考，不构成正式绩效考核：

- 不生成综合绩效分数；
- 不设置绩效等级；
- 不公开人员排名；
- 不直接关联奖金、奖惩或人事结论；
- 分来源展示工作量、及时性、完成情况、缺陷跟进和后续测试量等客观事实；
- 支持按周期、人员、团队和产品线查看趋势；
- 明确标注“参考指标”、统计口径、来源和更新时间。

未来只有在领导意图和业务规则明确后，才单独设计权重、评分、确认、申诉和归档机制。

### 7.7 Home 管理工作台

Home 是上述模块的权限化聚合视图，不独立拥有业务数据。

建议区域：

- 项目总数、进行中、待审查、延期和风险项目；
- 项目阶段分布和进度趋势；
- 当前用户有权查看的人员负载；
- Confluence 与 Jira 分来源工作量摘要；
- 管理岗客观参考指标趋势；
- 待审项目、即将到期、逾期和数据异常；
- 最近审查、项目状态变化和数据同步状态。

所有卡片和图表支持跳转到对应模块，不能在 Home 重复实现计算逻辑。

### 7.8 Wi-Fi Database 模块

保留现有 Peak Throughput、RVR、RVO、筛选、图表和导出能力。后续只做统一导航、认证、权限、视觉和运行环境整合，不改变其只读数据库 owner。

## 8. 快照与历史模型原则

正式字段在模块设计时确定，但必须满足以下原则：

- 项目使用现有稳定 Confluence 项目身份；
- 快照拥有唯一身份、采集时间和业务周期；
- 区分 `scheduled` 自动快照与 `manual_review` 人工审查节点；
- 保存规范化结果和必要的来源引用，不无界复制第三方完整页面；
- 人工审查节点不可原地修改历史事实，修订形成新版本并关联前一版本；
- 指标必须保存口径版本，以便未来规则变化后仍能解释历史结果；
- 定义保留、归档、备份和恢复策略后才能进入服务器正式运行；
- 敏感数据按最小化原则保存。

## 9. API 原则

- 按业务模块组织路由，不继续把所有页面逻辑集中在单个 `app.js` 或单个 FastAPI 文件；
- API 使用稳定传输模型，不直接暴露内部 Python 对象；
- 列表接口支持服务端分页、筛选和排序；
- 所有业务接口先完成认证与数据范围过滤；
- 聚合结果返回来源状态、数据时间和部分失败信息；
- 写入 Web 自有历史时支持幂等或明确的重复检测；
- 第三方异常不转换成成功空数据；
- 日志不记录密码、Token、Cookie 或第三方敏感响应。

## 10. 前端设计体系

- 整体视觉接近 Fluent UI：中性背景、清晰层级、轻边框、低阴影和语义色；
- 当前视觉基础采用已确认的 TemplateMo 608 布局与样式，并在运行代码中统一使用 SmartTest 命名；
- 复用 SmartTest 主题样式和语义 token，避免同时存在两套组件语言；
- 建立统一的导航、页面标题、筛选栏、统计卡、表格、状态标记、图表、空状态、错误状态和详情布局；
- 支持明暗主题时使用统一语义色；
- 桌面优先并保留合理响应式布局；
- 关键操作支持键盘和清晰焦点；
- 不用颜色作为状态的唯一表达。

## 11. 非功能需求

### 11.1 安全

- 后端强制认证和数据范围；
- 第三方凭据沿用现有安全 owner，不进入前端存储；
- 防止查询参数越权、导出越权和对象直接引用越权；
- Web 自有写操作保留审计记录；
- 错误响应不泄露连接串、凭据或内部堆栈。

### 11.2 稳定性

- 区分加载、无数据、无权限、配置缺失、外部系统失败和部分成功；
- 外部调用采用有界超时；
- 缓存和历史数据必须显示时间，不冒充实时数据；
- 定时任务可观察、可重试且避免重复写入；
- 服务器部署前完成数据库迁移、备份和恢复验证。

### 11.3 可维护性

- 每个业务行为只有一个 owner；
- 复用决策优先于新增代码；
- 模块之间使用明确接口，不读取对方内部存储；
- 保留能够保护权限、历史、数据口径和关键业务契约的测试；
- 不保留探索性测试、源码形状断言或重复等价用例。

## 12. Web 持久会话与账号级前端偏好

### 12.1 目标与边界

Web 登录会话与用户偏好由 Web 后端统一持久化，支持单台 Server 重启恢复、同一账号多设备同时登录，以及跨设备同步网页配置。继续复用现有 `LdapAuthenticator`，不引入 Redis、Keycloak 或第二套账号体系。

- 登录会话采用最后活动时间起 90 天滑动过期；主动退出、账号禁用或会话撤销立即失效。
- 每台设备持有独立会话；退出当前设备不影响其他设备，并提供撤销账号全部会话的后端能力。
- Cookie 只保存高强度随机 token；SQLite 只保存 token 哈希、账号身份、会话时间和撤销状态。
- 浏览器缓存、响应、日志和 SQLite session 表不得保存 LDAP 明文密码、Token 或 Cookie；LDAP 密码仅交给统一服务端 credential owner：Windows Credential Manager 持久化，Linux 以外部主密钥进行 AEAD 加密后将密文存入 Web SQLite。
- Server 重启后由持久 session 的 credential reference 恢复 Confluence/Jira 服务端凭据；仅在凭据缺失、主密钥不可用或解密失败时要求用户重新验证。
- Web 自有 SQLite 数据库位于既有 app-data 目录，启用 WAL、外键、busy timeout 和受控 schema 迁移；不写入源码目录或网络共享盘。

### 12.2 持久会话模型

`web_sessions` 保存会话唯一标识、`token_hash`、规范化账号、显示名、可选头像缓存、创建时间、最后访问时间、过期时间和撤销时间。原始 token 只存在于 `HttpOnly`、`Secure`、`SameSite=Lax` Cookie。

登录成功创建新的设备会话；普通请求验证 token 哈希并按有限频率更新最后访问与过期时间，避免每个请求都写库。退出当前设备撤销当前记录；退出全部设备按当前认证账号撤销全部有效记录。过期记录由有界清理机制删除。

### 12.3 账号级偏好模型

`user_preferences` 以当前认证账号、页面 `scope` 和配置 `key` 唯一定位，保存 JSON 值、schema 版本和更新时间。后端只从认证会话取得账号，不信任前端提交的用户名；写入使用原子 upsert，多设备修改采用最后一次写入生效。

保存主题、筛选勾选、搜索条件、排序、分页、页签、列显示、折叠状态及其他非敏感表单偏好。密码、Token、Cookie、临时凭据、文件上传、查询结果、报告、日志、运行进度和业务提交结果禁止进入偏好存储。

### 12.4 前端自动持久化机制

公共 `PreferenceStore` 只作用于页面配置区域和筛选区域，不盲扫所有表单。公共页面或组件在容器级声明偏好区域；区域内新增标准 `input`、`textarea`、`select`、checkbox、radio、switch、tab、折叠和排序控件后，由事件委托自动保存和恢复，不允许页面再编写独立缓存调用。

- 页面 `scope` 默认取稳定路由；控件 `key` 优先取 `name`，其次取 `id`，公共自定义组件使用自身稳定语义标识。
- 标准控件默认持久化，无需逐控件增加缓存代码；明确的临时控件可退出自动持久化。
- 密码、敏感命名字段、隐藏字段、文件、按钮及禁止类型由公共边界强制排除。
- 动态新增控件同样自动恢复与监听；自定义控件只允许在公共组件层增加一次适配，不逐实例接入。
- 选择、布尔、页签和排序立即保存；文本、搜索和日期输入防抖保存；成组筛选合并写入。
- 服务端偏好是跨设备权威数据；浏览器只允许使用内存或有界本地副本加速，写入失败必须显示未同步状态并保留重试能力。
- 自动化测试扫描偏好区域内可编辑控件；缺少稳定 `name`/`id`、未被公共组件适配且未明确排除时测试失败。

### 12.5 迁移与验收清单

- [ ] 以失败测试固定 SQLite schema、迁移、WAL/并发、原子 upsert、损坏/不可用错误边界。
- [ ] 用持久 `SessionStore` 替换 `InMemorySessionStore`，覆盖重启恢复、90 天滑动过期、有限续期、当前设备退出、全部设备撤销和过期清理。
- [ ] 通过统一 credential owner 持久化服务端凭据，验证重启恢复；凭据缺失、主密钥不可用或解密失败时返回明确的重新验证状态。
- [ ] 新增认证账号下的偏好读取、批量 upsert、scope reset API，覆盖越权、类型、大小、敏感字段和并发边界。
- [ ] 实现公共前端 `PreferenceStore`、偏好区域自动发现、动态控件恢复、事件委托、防抖、合并保存、失败重试和未同步提示。
- [ ] 迁移主题、Confluence 更多筛选及 Wi-Fi 三个页面筛选，删除被替代的 `localStorage`/`sessionStorage` 页面缓存逻辑。
- [ ] Settings 只接入已有真实业务含义的配置；不得为模板中的账号资料、2FA、删除账号等占位控件伪造业务能力。
- [ ] 验证同账号跨浏览器/设备恢复、不同账号隔离、最后写入生效、Server 重启恢复及敏感数据不落盘。
- [ ] 运行前端聚焦测试、完整前端测试/lint/build、后端聚焦测试、完整 Web 后端测试和 `git diff --check`。

### 12.6 Confluence 账号权限、页面发现与筛选修复

Confluence 项目事实继续复用搬移前的页面发现 owner，不维护只从 `Project Status Report` 向下搜索的平行逻辑。目录入口为 Status 页面时，必须先上溯项目根，再从兄弟分支定位 `Basic Information`；缓存解析后的 entry/root page ID，不依赖目录 URL 是否直接携带 `pageId`。

- 全文搜索范围保持项目、人员、Space key、全部 Project Space 字段值和 Confluence identity，页面文案使用 `Project / Person / Field Search`。
- Product Space 过滤值继续使用 DOPL、SDPL、TV、OOPL；下拉分别显示 `China Operator Business`、`Smart Device Business`、`TV Business`、`Global Operator & STB Business`。空的旧快照显示名不得覆盖 Core 已有显示名。
- 未选择 Product Space 时，Current Stage 下拉显示四个产品线源数据 Stage 的并集；选择一个或多个 Product Space 时，显示所选产品线 Stage 的并集。Stage 域不随年份、状态等其他筛选条件收缩，选择当前项目不存在的 Stage 只返回零匹配，不报错；名称保留源数据原文。
- 不实现 `personnel.json` 的 I/M 范围过滤。使用当前登录账号访问 Confluence，项目事实快照按规范化账号隔离；无权访问的 Space、项目或页面直接排除，不向页面返回权限错误，也不得向其他账号泄露已有快照。
- Server 重启只读取当前账号自己的历史快照；需要刷新时从该 session 的服务端 credential owner 恢复凭据，仅在恢复不可用或解密失败时返回重新验证状态。
- API 已命中但责任人员采集失败时，页面仍展示项目基础结果并标记责任信息不可用，不得因 owner hierarchy 为空而显示成零项目。

执行清单：

- [ ] 以失败测试复现 Status 与 Basic Information 为兄弟页、目录 URL 缺少 pageId 和旧快照空显示名覆盖问题。
- [ ] 复用既有 `discover_project_pages()` 上溯与遍历语义，删除或收敛平行页面发现逻辑，并缓存解析后的稳定页面 ID。
- [ ] 将 ProjectFactStore/Web owner/API 查询切换为认证账号命名空间，验证账号隔离、重启恢复与无权项目静默排除。
- [ ] 建立按 Product Space 独立保存的 Stage 域及选中 Space 并集契约，验证全集、子集和无匹配不报错。
- [ ] 修复四个 Product Space 显示名、全文搜索文案及无责任人员项目的可见降级展示。
- [ ] 用真实四个 Product Space 刷新验证页面发现、权限和 Stage 域；完成后移除或降级临时诊断，不保留重复日志。
- [ ] 运行 Core 项目事实/旧发现/logging 边界测试、Web 后端、前端测试/lint/build、产品边界检查和 `git diff --check`。

### 12.7 Confluence 首次缓存与目录优先加载

Confluence 筛选器只依赖四个 Project Space 目录页，不得等待所有项目的 `Basic Information` 与责任人员详情采集完成。首次账号缓存采用目录优先的两阶段流程：

1. 当前账号成功 LDAP 登录后，若其账号命名空间没有项目事实快照，立即启动后台初始化，不等待用户进入 Confluence 页面。
2. 后台任务以四个相互独立的有界请求并行读取当前账号可访问的四个 Project Space 目录；目录阶段完成后立即原子保存账号级快照，提供全部目录字段、四空间显示名、各空间 Stage 域和基础项目结果。
3. Web 查询在目录快照可用后立即开放筛选器。页面加载、筛选勾选、Reset 和普通轮询不得读取 `Basic Information`、责任人员或项目页面图。
4. 用户点击 `Apply Filters` 后，先在账号目录缓存中完成过滤；只有匹配项目才进入既有页面发现 owner 并读取 `Basic Information` 与责任人员详情。零匹配不得发起详情请求；已有有效详情缓存直接复用。
5. 单个 Space 或项目无权限时静默排除；单个命中项目详情慢、失败或无权限不得阻塞其他匹配结果。详情不可用的项目保持基础结果可见并标记责任信息不可用。
6. Server 重启后直接读取当前账号已有目录与详情缓存，不访问 Confluence。目录缓存不存在时从持久 session 的服务端 credential owner 恢复凭据并初始化；凭据不可用或解密失败时返回明确的 `reauthentication_required`，前端显示重新验证提示，不保持无限 Loading。
7. 账号重新登录或验证后自动启动缺失目录缓存初始化；前端有界轮询目录阶段，目录快照可用后停止禁用筛选器。Apply 详情请求使用独立状态，不得把筛选器重新置为 Loading。
8. Preference scope 去除路由开头 `/`，例如 `confluence.html`，不得请求 `/api/preferences//confluence.html`。

执行清单：

- [ ] 以慢详情 fake client 复现四目录已完成但筛选器仍等待全部项目详情的问题，固定目录阶段先返回的时序契约。
- [ ] 将项目事实收敛为并行目录快照与 Apply 按需详情两个独立入口，保留账号隔离、Stage 域、权限静默排除和失败事实。
- [ ] 验证页面加载只发起四个目录请求，目录完成即保存；Apply 只读取过滤命中的项目详情，零匹配和缓存命中不访问详情。
- [ ] 登录成功时只为缺失账号快照启动 single-flight 初始化；已有快照不访问 Confluence。
- [ ] 修复无缓存且持久凭据不可用或解密失败时的前端重新验证提示，避免无限 Loading。
- [ ] 规范化 Preference scope，并验证既有账号偏好读写不产生双斜杠。
- [ ] 记录目录阶段与详情阶段的安全耗时和数量，不输出账号、凭据、页面正文、人员或项目明细。
- [ ] 运行慢详情时序、账号隔离、Core/Web/前端、logging/产品边界和 `git diff --check` 验收。

### 12.8 服务端持久凭据

- 浏览器仍只保存随机 session Cookie；LDAP 密码仅由服务端凭据 owner 持久化，并以每个 session 独立的 credential reference 关联现有 SQLite session。
- Windows 复用 `core/credentials/windows.py` 的 Windows Credential Manager owner；Ubuntu/Linux 使用 `cryptography` AEAD，加密后的 ciphertext、nonce 与 key version 存入现有 Web SQLite，主密钥只从 `SMARTTEST_WEB_CREDENTIAL_KEY` 外部配置读取，禁止写入数据库或日志。
- server 重启后，持久 session 通过 credential reference 恢复 Jira/Confluence 共用凭据；多设备 session 相互独立。单设备 logout 只删除自己的凭据；logout-all、过期清理删除对应全部凭据。
- 主密钥缺失、格式错误、版本不匹配或解密失败时安全失败，不回退到明文、浏览器存储或第二套账号体系，也不记录密码、token、ciphertext 或主密钥。

## 13. 模块开发顺序

### 13.1 Jira 报告工作台

本模块已由 Coco 通过 `web/design/reference/jira-confluence-report-workspace.html` 确认视觉布局，开发与验收均以该本地 HTML 为桌面端视觉基准。

范围与边界：

- 顶部导航保留 `Jira` 和 `Confluence` 两个独立入口，现有页面、主题切换和 Wi-Fi Data 行为不变；
- Jira 使用“左侧报告目录 + 右侧完整报告预览”及 Client 同口径 JQL 输入；
- Jira 复用 Client 现有 Jira 审查、报告和导出业务 owner；
- 浏览器只访问 Web API，第三方认证、访问、审查和报告生成逻辑不得复制到前端或 Web 后端；
- 当前只读展示，不通过 Web 修改 Jira 或 Confluence；
- 报告正文在页面中直接展示，报告工具栏提供来源跳转和 `Download`；下载必须复用后端权限范围与既有导出结果；
- 不生成模拟业务数据；加载、无报告、无权限、配置缺失、外部失败和部分成功必须有明确页面状态；
- 桌面端尽可能复现已确认 HTML，窄屏维持现有 SmartTest 响应式视觉语言。

执行清单：

- [x] 通过失败测试确定 Jira Web API 契约、只读边界、错误状态和下载行为；
- [x] 复用 Client 对应报告导出 owner，Web 后端仅增加本地只读报告目录与传输适配，不复制第三方访问、审查或导出逻辑；
- [x] 浏览器登录复用下沉到 Core 的 Client LDAP owner；Web 使用 HTTP-only/Secure cookie 标识持久 session，密码不进入前端或 SQLite session 表，仅由 Windows Credential Manager 或 Linux AEAD credential owner 持久化；
- [ ] 后续接入 `personnel.json` 人员映射及 I/M 岗数据范围，并让列表、正文和下载共用同一权限结果；
- [x] 通过失败测试确定 Jira 报告工作台、筛选、报告选择、正文展示和下载交互；
- [x] 实现 Jira 页面并与本地视觉基准比对；
- [x] 验证加载、空数据、无权限、配置缺失、外部失败和部分成功；
- [x] 验证现有 Dashboard 页面、主题切换、移动导航和 Wi-Fi Data 无回归；
- [x] 运行前端测试、lint、build，后端聚焦测试和 `git diff --check`；
- [x] 用实际浏览器截图与本地 HTML 对照，矫正导航、间距、尺寸、颜色、卡片、工具栏和响应式差异。

当前限制：Web 已具备复用 Client LDAP 规则的持久浏览器会话及服务端 credential owner，但尚未接入 `personnel.json` 与 I/M 岗权限范围。Jira 模块仍只读取 Client 已导出的本地 XLSX，不使用会话凭据执行 Jira 查询或审查；API 保留明确的 `unauthorized` 状态，正式人员范围过滤由后续权限阶段接入。

Jira 执行限制：Client 的新审查链路依赖 `JiraAuditBridge` 持有的运行时临时凭据，并经过 `resolve_audit_input`、`JiraAuditService.run`、人工确认后才允许 `export_audit_xlsx`。Web 当前不能安全复用该临时凭据会话，因此 Jira 页面的 JQL 动作只按导出文件中保存的“JQL 查询条件”精确定位 Client 已生成报告，不执行新查询或审查；新审查继续由 Client 发起。

### 13.2 Confluence 全项目 QA 责任事实（Core 阶段）

本阶段先建立 Core 唯一 owner，不接入或修改 Web 前端。该 owner 从全部已配置 Product Space 读取项目目录，不套用现有周审查的 A/B、年份、项目状态或 Stage1/2/3 资格过滤；现有 Client 周审查入口与规则保持不变。

执行清单：

- [x] 保留 Product Space 每个实际表头、原始值与标准化字段，并单列未知表头差异；
- [x] 从 `Basic Information` 精确提取 `Major FAE QA`、`FAE QA`、`QA Reviewer`，保留多人及源数据提供的 Confluence 稳定身份；
- [x] 使用现有 app-data JSON owner 原子保存版本化快照，与 Client 的有界内存缓存分离；
- [x] 增量刷新复用未变化项目；失败时保留旧事实并标记 stale，目录缺失项目标记 inactive 而不删除；
- [x] 提供只读本地查询与全字段 facets，不在查询时访问 Confluence；
- [x] 通过全目录、未知列、角色多人、首次快照、零变化、单项目变化、局部失败、inactive、本地过滤与损坏/schema 拒绝测试；
- [ ] 待 Coco 根据真实 Confluence 页面确认未知表头差异清单后，决定是否增加新的标准字段映射；
- [ ] 待项目只读 Web 模块开发时，通过 Web 权限适配公开该 Core 查询契约。

当前字段证据：仓库测试夹具可确认 `Page/页面`、`Project ID`、`Date of Commercial approval`、`Support Mode`、`Project Status`、`Current Stage`。除这些已有证据外不猜测别名；其他实际表头原样保存并进入 `field_discrepancies`。

Confluence Web 接入清单：

- [x] Web API 只读取 `ProjectFactStore.load` 并调用 `query_project_facts`，查询过程不访问 Confluence；
- [x] 返回快照状态/时间、全量动态 facets、项目、字段差异及 stale/failed/inactive 数量；
- [x] 明确展示 `no_snapshot`、`schema_error` 与 `partial_success`；
- [x] Confluence 页面移除 Report Type、报告目录、报告预览、来源报告跳转和 Download；
- [x] 按本地事实动态绘制全部 Product Space 表字段筛选、独立 `Product Space` 来源维度、项目/人员搜索及基础项目结果；
- [x] 保留未知字段及原始表头标签，不在 Web 中猜测或合并别名；
- [x] `Apply Filters` 只刷新下方 `角色 → 人员 → 该人员全部项目 → 项目基本信息`，不重建顶部筛选控件；
- [x] 顶部筛选结构固定保留全部已确认字段，当前快照无字段值时显示空选项；
- [x] 常用筛选固定为 `Product Space`、`Date of Commercial approval`、`Project ID`、`Project Status`、`Current Stage`、`Project Owner`、`Support Mode`；不显示独立 `Year`；
- [x] 全部 Confluence 下拉筛选统一为多选：同字段取 OR、跨字段与项目/人员搜索取 AND；API 使用重复 `field.<key>` 参数。`Product Space` 稳定值保持 DOPL/SDPL/TV/OOPL，显示名直接来自 Core `PRODUCT_LINES.display_name`，Web 不维护映射；
- [x] 顶部 facets 在快照加载完成后保持固定；勾选、取消、全选和清空仅更新浏览器本地选择，Apply/Reset 只刷新下方责任层级，不用过滤响应收缩顶部选项；Core 与 Web 请求边界通过 `core.logging.smart_log` 记录有界筛选、命中/排除计数及返回层级汇总，不记录搜索内容、人员身份或项目明细；
- [x] `Date of Commercial approval` 复用 `ProjectCollectionFilter.years` 和现有商业批准日期年份解析，选项显示年份但字段名保持原字符；
- [x] 其他真实 Product Space 字段进入“更多筛选”，勾选后显示、取消后移除并清值；只将启用字段 key 保存到浏览器 `localStorage`，不保存业务事实；
- [x] 页面加载本地事实快照时显示 loading 并禁用 Apply；级联选项由 Core 当前过滤结果返回，失效选择清除并提示；刷新失败状态保留快照时间与 stale 信息；
- [x] 无本地 `ProjectFactStore` 快照时，登录会话从统一服务端 credential owner 取得 LDAP 账号和密码构造既有 `ConfluenceClient` 并生成缓存；缓存命中只做本地查询，显式刷新需要登录，并发刷新在 Web 编排层去重；
- [x] 无快照首次查询立即返回带完整固定 facets/空 owner 层级的 `loading`，单一进程内后台任务执行刷新；前端保持七个常用筛选与更多筛选可见但禁用，并有界轮询至 `ready`、`partial_success` 或 `failed`，页面离开/组件销毁停止轮询；
- [ ] Web 项目审查动作后续直接调用 `ConfluenceAuditService.run` 与 `export_project_audit_xlsx_by_product_line`；当前阶段仅把公共会话接入事实缓存刷新，不改变审查按钮边界；
- [ ] 后续按 Coco 确认的管理视图实现组织层级、项目卡片与详情布局。

四个 Product Space 的实测字段证据（2026-08-26，Atlas 使用 Chrome 核对）：

- 共同字段：`Page/Project Link`、`Project ID`、`ODM`、`OEM/Operator`、`Key Part Number`、`Project Status`、`Current Stage`、`Project Owner`、`Support Mode`、`Date of Kick Off`、`planned closure`、`actual closure`、`Commercial approval`；
- `DOPL` 缺少 `Launch OS`；
- `SDPL` 缺少 `MP Time`、`Launch Time`、`Next Target`、`Next Target Date`；
- `OOPL` 额外包含 `Sum`；
- `Major PM` 当前在四个 Product Space 表中均不存在，因此保留空筛选结构，不推断来源；
- 四个 Product Space 的字段顺序不同。Core 保存每个表的原始表头顺序和原始值，Web 不以某一个 Space 的顺序覆盖其他 Space。

审查调用边界：Client 的 `ConfluenceAuditBridge.startAudit` 仍通过其登录会话构造 `ConfluenceAuditService`，按 `ProjectCollectionFilter` 执行既有 Stage1/2/3 审查点并导出。Web 持久 session 与服务端 credential owner 已可供后续工具复用，但本阶段只授权 Confluence 责任事实缓存刷新；未把 Web 审查按钮接入审查与导出链路，也未改变 Jira 行为。

本地快照刷新边界：查询始终先读取 `ProjectFactStore`，缓存命中不访问 Confluence。无快照且已登录时，首个请求不等待第三方网络，立即返回完整筛选结构和 `loading`；进程内 single-flight 后台任务从服务端 credential owner 恢复会话凭据并复用 `ConfluenceClient + refresh_project_facts` 生成持久快照，同期请求继续返回 `loading`。完成后本地查询返回 `ready/partial_success`；失败返回 `failed`，显式刷新可重新启动任务。凭据不写入响应、日志、浏览器存储或 SQLite session 表；Windows Credential Manager 或 Linux AEAD 密文存储独立持久化凭据，服务退出不持久后台任务。

采用“基础模块先行、业务模块逐个交付、Home 后聚合、最后统一整合”的顺序：

1. **Web 基础壳与设计体系**：模块化路由、布局、导航、状态组件和 API 基础；
2. **身份与权限模块**：复用登录、人员映射、I/M 岗和管理范围；
3. **人员只读模块**：验证人员身份、汇报树和产品线范围；
4. **项目只读模块**：复用 Confluence 项目发现、列表和详情；
5. **审查与历史模块**：Web 自有数据库、自动快照、人工阶段节点和回溯；
6. **Jira/Redmine 辅助聚合模块**：在项目与人员范围内关联缺陷和任务；
7. **工作量模块**：先按来源展示，再形成已确认的综合视图；
8. **客观参考指标模块**：只面向管理岗，不做正式绩效结论；
9. **Home 管理工作台**：聚合已完成模块，不提前制造临时数据流；
10. **Wi-Fi Database 整合**：统一认证、导航和视觉；
11. **SmartTest 测试量接入**：复用测试任务、运行和报告 owner；
12. **服务器化与最终整合**：数据库、调度、部署、备份、监控、安全和全链路验收。

模块顺序可以由 Coco 调整，但后置模块不得通过临时复制绕过尚未完成的基础 owner。

## 14. 单模块交付方式

每个模块使用同一流程：

1. 调查现有 owner、接口、数据和测试；
2. 写入或更新本文档中的模块设计与执行清单，不另建重复计划文档；
3. Coco 审核业务边界和验收标准；
4. 按风险选择 Atlas-only 或 Atlas + Mason；
5. 实现并执行聚焦测试；
6. Coco 在实际环境确认功能完整；
7. 清理冗余、临时诊断和探索残留；
8. 完成代码质量检查并交付；
9. 下一模块复用已经交付的公共能力。

## 15. 总体验收标准

### 15.1 功能验收

- 登录身份与人员映射正确；
- I 岗只能读取本人及参与项目范围；
- M 岗范围正确覆盖汇报树和负责产品线；
- API、页面、统计和导出不存在权限差异；
- Confluence 是项目主数据，Jira/Redmine/SmartTest 作为可追溯辅助来源；
- 第三方数据保持只读；
- 自动快照和人工审查节点可分别保存与回溯；
- 历史记录不被后续采集覆盖；
- 工作量和参考指标带来源、周期、更新时间和口径；
- Home 只聚合已有模块结果；
- Wi-Fi Database 现有能力无回归。

### 15.2 代码质量验收

- 没有重复人员、项目、认证、采集、审查、调度或测试模型；
- 前端不直接访问 `core/` 或第三方平台；
- 后端不复制已有核心业务实现；
- 模块 owner 和接口清晰；
- 没有临时模拟数据、调试输出、废弃尝试或无关改动；
- 聚焦测试、最高实际环境验证和 `git diff --check` 通过。

## 16. 当前明确不做

- 通过 Web 修改 Confluence、Jira 或 Redmine；
- 通过 Web 编辑 `personnel.json`；
- 建立独立于 SmartTest 的本地账号体系；
- 建立 Web 专用项目清单；
- 正式绩效分数、绩效等级、公开排名、奖惩或人事结论；
- 未经确认的第三方双向同步；
- 为未来可能性预先拆分微服务。

## 17. 待后续模块确定

以下内容在对应模块启动时，根据实际环境和领导意图确定，不影响当前总体方向：

- 现有 SmartTest 认证在浏览器中的具体会话承载方式；
- Web 自有数据库产品及服务器部署拓扑；
- 自动快照周期、保留年限和归档策略；
- 人工审查的具体状态、角色和表单字段；
- Confluence、Jira、Redmine 指标的具体统计口径；
- SmartTest 测试量纳入工作量的时间和规则；
- 是否以及何时升级为正式绩效考核；
- 后续 Home 业务内容对现有 SmartTest 主题的扩展方式。
