# Web Projects 与 Confluence 页面合并设计

## 目标

Web 端只保留一个项目入口。删除静态演示性质的 Confluence 独立页面，将现有项目筛选、缓存刷新、详情同步、责任信息和 Weekly Review 迁移到 `Projects`，并将 Apply 后的项目详情改为按 `Current Stage` 分组的卡片看板。

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
4. Apply 后的 Current Stage 分组项目看板。

页面在无快照、加载、失败、凭据失效和就绪状态下继续复用现有状态反馈，不建立新的并行状态流。

## Current Stage 看板

- 看板按 `Current Stage` 分组，每个阶段为一列。
- 阶段顺序采用接口返回的 `Current Stage` facet 选项顺序，不在前端硬编码业务阶段。
- 当前结果中存在但 facet 未声明的阶段追加在已知阶段之后。
- 空阶段统一归入最后一列 `Unspecified`。
- 桌面端为横向多列看板并允许水平滚动；窄屏降为单列。
- 每个项目按稳定 identity 只渲染一张卡，不因多个角色或负责人重复出现。

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
- 复用现有项目卡片的标题、描述、badge、footer 等视觉原子；只新增看板分组和响应式布局所需样式。
- 删除或迁移 Confluence 页面入口测试，保留缓存优先、目录刷新、Apply、轮询、会话变化、Weekly Review 等行为测试。
- 不保留重定向页面、兼容组件、重复入口或废弃实现。

## 验收标准

- 桌面端和移动端导航只出现一个 `Projects`，访问 `/projects.html` 可使用完整项目业务。
- 仓库中不存在运行时 `confluence.html` 入口，Vite 不再构建该入口。
- 首屏缓存读取不触发远端；页面进入只启动一次目录刷新；Apply 只刷新当前查询快照详情。
- Apply 后项目按 Current Stage 分组，每项目一卡，未分组项目进入 `Unspecified`。
- 无负责人项目仍显示；多角色、多负责人不会复制项目卡片。
- 会话切换、缓存空/加载/失败、审查轮询和下载行为保持有效。
- 桌面端横向多列、窄屏单列、明暗主题均可读。
- 前端完整测试、Web 后端相关测试、产品边界检查和 `git diff --check` 通过。
- 最终差异无静态假数据、旧横向项目行、重复入口、临时诊断和废弃 CSS。
