# Web Projects 与 Confluence 页面合并设计

## 目标

Web 端只保留一个项目入口。删除静态演示性质的 Confluence 独立页面，将现有项目筛选、缓存刷新、详情同步、责任信息和 Weekly Review 迁移到 `Projects`，并将 Apply 后的项目详情改为按产品线折叠的瀑布卡片。

## 页面与导航

- 唯一项目入口为 `/projects.html`，导航名称为 `Projects`。
- 删除 `web/frontend/confluence.html`，不保留跳转页或兼容入口。
- 所有桌面端与移动端导航删除独立 `Confluence` 项。
- `projects.html` 删除 New Project、静态计数、硬编码 Kanban 列和示例项目，改为真实项目业务挂载点。
- Jira 保持独立入口和现有业务，不与 Projects 合并。

## 数据与刷新边界

- 后端继续由 `/api/confluence/project-facts` 提供项目事实，不重命名 API，不增加第二套项目模型。
- 页面进入时先读取 SQLite 当前账户的本地快照，立即展示可用缓存。
- 页面偏好恢复后仅发起一次 `catalog=1` 目录刷新，后续轮询只读取本地状态。
- Apply 只对当前筛选查询快照启动详情刷新，不信任前端项目 ID，不扩大到全量数据。
- Jira/Confluence 业务使用 Web Server 已保存的账户凭据，不调用 LDAP；LDAP 只保留在首次登录验证链路。
- 页面状态只保存展示和未提交控件值，资源 ID、筛选结果和业务选择集继续由 SQLite 负责。

## 页面结构

Projects 页面保留并整合以下区域：

1. 项目筛选、搜索、Apply、Reset。
2. Weekly Review 日期与审查、取消、下载操作。
3. 项目与 QA 责任汇总、工作量图。
4. Apply 后的产品线折叠瀑布卡片。

页面在无快照、加载、失败、凭据失效和就绪状态下继续复用现有状态反馈，不建立新的并行状态流。

## 产品线折叠瀑布

- 始终渲染四个产品线折叠组件，即使某个产品线当前没有项目也不得移除该组件。
- 产品线显示顺序不承担业务排名含义；组件内部不做项目排序，严格保留接口返回顺序，后续排序规则另行设计。
- 每个产品线折叠组件内部使用响应式多列瀑布卡片；窄屏降为单列。
- 不按 `Current Stage` 分组或分列；`Current Stage` 只作为项目卡片信息展示。
- 每个项目按稳定 identity 只渲染一张卡，不因多个角色或负责人重复出现。
- 前端所有可见位置只显示产品线完整业务名称：`China Operator Business`、`Smart Device Business`、`TV Business`、`Global Operator & STB Business`。`DOPL`、`SDPL`、`TV`、`OOPL` 仅作为 API、筛选和数据库内部 key，不得直接展示。
- 显示层复用接口 `Product Space` facet 返回的 value/label 权威映射，不建立第二套业务名称 owner；缺少 label 时不得回退显示内部 key。

项目卡片第一版展示：

- 项目名称与 Project ID；
- Product Space；
- Project Status、Current Stage、Support Mode；
- Customer Summary；
- 角色与负责人；
- 其余非空详情字段。

空字段不占位；数组按可读列表展示。第一版不增加卡片编辑、拖拽、阶段修改或新的详情接口。

## 代码所有权与清理

- 将现有 Confluence 项目组件收敛为 Projects 唯一业务组件，保留现有 API owner 与缓存/刷新 owner。
- Projects 和 Jira 使用各自单一入口脚本，移除 `report-main.js` 中按 pathname 选择两套页面的条件分支。
- 删除静态假项目 DOM、旧横向 `.owner-project-row` 项目详情渲染，以及仅服务于被删除结构的 CSS。
- 复用现有项目卡片的标题、描述、badge、footer 等视觉原子；只新增产品线折叠和响应式瀑布所需样式。
- 删除或迁移 Confluence 页面入口测试，保留缓存优先、目录刷新、Apply、轮询、会话变化、Weekly Review 等行为测试。
- 不保留重定向页面、兼容组件、重复入口或废弃实现。

## 验收标准

- 桌面端和移动端导航只出现一个 `Projects`，访问 `/projects.html` 可使用完整项目业务。
- 仓库中不存在运行时 `confluence.html` 入口，Vite 不再构建该入口。
- 首屏缓存读取不触发远端；页面进入只启动一次目录刷新；Apply 只刷新当前查询快照详情。
- Apply 后始终存在四个产品线折叠组件，每组内部为响应式瀑布，每项目一卡且保持接口顺序。
- 前端所有产品线位置只显示完整业务名称，不显示 `DOPL`、`SDPL`、`TV`、`OOPL` 内部 key。
- 无负责人项目仍显示；多角色、多负责人不会复制项目卡片。
- 会话切换、缓存空/加载/失败、审查轮询和下载行为保持有效。
- 桌面端产品线内多列瀑布、窄屏单列、明暗主题均可读。
- 前端完整测试、Web 后端相关测试、产品边界检查和 `git diff --check` 通过。
- 最终差异无静态假数据、旧横向项目行、重复入口、临时诊断和废弃 CSS。

## 实施检查表

### 任务一：锁定唯一入口与导航

- [x] 先修改 `web/frontend/tests/shell-html.test.js`、`web/frontend/tests/vite-config.test.js` 和入口集成测试，断言只有 `/projects.html` 项目入口、导航没有 Confluence、Vite 不再构建 `confluence.html`，并运行测试确认按预期失败。
- [x] 将 `confluence.html` 的真实业务挂载结构迁入 `projects.html`，删除全部静态假项目和 New Project 操作。
- [x] 删除所有运行时 HTML 的 Confluence 导航项，更新桌面端与移动端 Projects 激活状态。
- [x] 删除 `web/frontend/confluence.html` 及 Vite 的 Confluence input，运行入口测试确认通过。

### 任务二：收敛入口脚本与项目组件 owner

- [x] 先调整入口测试，要求 Projects 入口直接创建项目工作区、Jira 入口直接创建 Jira 工作区，且不存在 pathname 二选一分支；运行测试确认按预期失败。
- [x] 将 `report-main.js` 拆分并收敛为 Projects 与 Jira 各自唯一入口，复用现有 API、会话和偏好生命周期，不复制业务初始化代码。
- [x] 将 Confluence 项目组件及测试重命名为 Projects 业务 owner；API 路径 `/api/confluence/project-facts` 保持不变。
- [x] 删除不再使用的双入口条件、旧文件和对应废弃断言，运行入口与会话测试确认通过。

### 任务三：按产品线渲染唯一项目卡片

- [x] 先在项目组件测试中加入真实行为断言：始终显示四个完整名称的产品线折叠组件、空组保留、组内保持接口顺序、多角色项目只出现一张卡、无负责人项目仍显示，且可见文本没有内部产品线 key；运行测试确认按预期失败。
- [x] 让 `payload.projects` 成为项目卡片唯一数据源，按稳定 identity 去重并按 Product Space 放入固定折叠组件；`ownerHierarchy` 只继续负责汇总和工作量呈现。
- [x] 卡片复用现有标题、描述、badge、footer 视觉原子，展示设计中约定的核心字段、角色负责人和其他非空详情字段；数组按列表展示，空字段不渲染。
- [x] 删除旧 `.owner-project-list`、`.owner-project-row` DOM 与渲染逻辑，运行项目组件测试确认通过。

### 任务四：折叠瀑布布局与冗余清理

- [x] 先增加 DOM 行为测试，约束四个折叠组件、每组项目计数、空组和组内响应式瀑布所需结构；运行测试确认按预期失败。
- [x] 在 `smarttest-theme.css` 中复用现有卡片视觉，增加最小的产品线折叠与组内瀑布布局规则，并删除阶段列样式。
- [x] 删除仅供旧静态 Projects 和横向详情使用的 DOM、CSS、入口引用与重复测试，不保留兼容层或弃用注释。
- [x] 搜索确认不存在运行时 `confluence.html` 引用、静态假项目、旧横向项目行和双入口条件分支。

### 任务五：完整验收

- [x] 运行项目组件、入口、导航、Vite、登录 next、偏好和会话相关前端测试。
- [x] 运行完整前端测试，并运行 Web 后端相关测试，确认缓存、catalog、Apply 查询快照、审查和凭据边界没有回归。
- [x] 运行产品边界检查和 `git diff --check`。
- [x] 检查最终 diff，确认仅包含本设计范围，无临时诊断、静态假数据、重复 owner、废弃 CSS 或无关改动。
