# SmartTest Web 可定制 Dashboard 网格设计

## 1. 背景与目标

Dashboard 当前只保留统一 Web Shell，主内容为空。本次建立一个按账号隔离的组件式 Dashboard：用户登录后看到自己的布局；没有个人布局时看到系统默认布局；进入编辑模式后可以添加、移除、拖动和缩放卡片，并通过明确的“保存 / 取消”提交或放弃本轮编辑。

首版必须使用真实业务组件验证机制，不使用无业务占位卡。首个组件为现有 `Role workload`。它先从 Projects 页面实现中抽取为独立组件，再由 Projects 与 Dashboard 共同复用。

## 2. 范围

### 2.1 首版范围

- 引入 `gridstack` 13.3.x，使用其 Vanilla JavaScript API、CSS、拖拽、缩放、碰撞、响应式布局与序列化能力。
- Dashboard 使用 24 列逻辑网格；高度按逻辑行向下无限扩展。
- 建立统一的组件注册、实例生命周期、卡片外壳、布局编辑和账户偏好持久化机制。
- 抽取并注册真实的 `Role workload` 组件，保持现有数据来源、Product Line/Role 切换、排序、Chart.js 图表和 Projects 页面行为。
- 提供普通模式、编辑模式、添加组件、移除组件、拖动、缩放、保存、取消和恢复默认布局。
- 桌面与窄屏均可展示；布局保存时始终保存 GridStack 能恢复的最大列布局，不用当前窄屏列数覆盖 24 列布局。

### 2.2 不在首版范围

- 不新增第二个业务组件。
- 不改变 `Role workload` 的统计口径、排序、角色定义、产品线范围或数据刷新行为。
- 不保存项目事实、人员列表、统计结果、HTML 或权威资源 ID 到 Dashboard 布局。
- 不允许用户创建组件类型、脚本、查询或任意 HTML。
- 不新增共享布局、管理员发布布局或查看他人布局。
- 不修改系统默认布局的管理方式；首版默认布局随前端版本发布。

## 3. 依赖选择

采用 [GridStack](https://github.com/gridstack/gridstack.js) 而不是自研碰撞算法，也不采用 Muuri/Packery。GridStack 直接覆盖二维拖拽、缩放、触屏、响应式列变换以及 `save()`/`load()`；当前版本无运行时依赖并采用 MIT 许可证，适合现有 Vanilla JavaScript + Vite 前端。

`gridstack` 必须进入 `web/frontend/package.json` 的运行时依赖和 lockfile，由 Vite 打包；不使用 CDN。依赖版本固定在实现时安装得到的 13.3.x 精确锁定结果。

## 4. 布局模型

### 4.1 坐标系统

- Dashboard 的权威桌面布局固定为 24 列，`x` 和 `w` 的范围由 24 列约束。
- `y` 和 `h` 使用逻辑行，高度不设总行数上限。
- 行高采用 30px，卡片间距采用 8px；该组合参考 Grafana 的 24 列 Dashboard，同时保持 GridStack 的吸附与拖动手感。
- GridStack 负责碰撞、向上压缩、列变换和拖拽过程；SmartTest 不实现第二套位置算法。
- 普通模式关闭拖动与缩放；编辑模式才启用。

### 4.2 组件尺寸来源

Dashboard 不预设统一的 `1×1`、`2×2`、`2×4` 尺寸集合。每个真实组件完成独立封装后，根据自身内容登记：

- `defaultW/defaultH`：首次加入 Dashboard 的默认尺寸；
- `minW/minH`：保持内容可用且不发生关键内容裁切的最小尺寸；
- 可选 `maxW/maxH`：只有组件业务明确需要上限时才声明；
- `resizeHandles`：组件允许的缩放方向。

`Role workload` 首版默认宽度为 24 列，以保持当前横向占满布局。实现阶段先保持现有图表可见高度与内部滚动边界，再按 30px 行高和 8px 间距换算并记录 `defaultH/minH`；不得先凭经验指定尺寸，也不得为了缩小卡片改变现有图表内容。

### 4.3 响应式

- 宽屏使用 24 列。
- 中等宽度由 GridStack 缩放为 12 列。
- 手机宽度转为 1 列纵向顺序。
- 窄屏布局按 24 列布局的 `y`、`x` 顺序稳定排列。
- 保存调用不传当前显示列，使用 GridStack 的最大可用布局序列化语义，避免在手机保存后丢失桌面宽度与位置。

## 5. 组件架构

### 5.1 DashboardGrid

唯一的 Dashboard 布局 owner，负责：

- 初始化和销毁 GridStack；
- 加载系统默认布局或当前账户布局；
- 管理展示态与编辑态；
- 保存编辑前基线；
- 协调添加、移除、拖动、缩放、保存、取消和恢复默认；
- 将 GridStack 节点转换为持久化模型。

它不读取或解释具体组件的业务数据。

### 5.2 WidgetRegistry

统一登记可用组件类型。每个定义至少包含稳定 `type`、固定标题、布局属性和创建函数。注册表只接受代码内已登记类型；未知类型在布局加载时如实报告并跳过，不加载任意代码或 HTML。

### 5.3 Widget 实例契约

每个组件实现统一生命周期：

```text
mount(root, config)
update(config)
destroy()
```

- `mount` 创建组件自己的 DOM、订阅和第三方实例。
- `update` 只更新该组件声明的非权威显示配置。
- `destroy` 释放 Chart.js、事件监听器和其他资源。
- 卡片标题栏、编辑态拖动把手、移除按钮和 GridStack resize handle 由统一卡片外壳负责。
- 卡片内部交互不能触发拖动；拖动只能从标题栏的明确把手开始。

### 5.4 RoleWorkloadWidget

现有 `projects.js` 中 Role workload 的渲染和 Chart.js 生命周期抽成共享组件。Projects 页面继续使用该组件，Dashboard 通过注册表创建同一组件。复用范围包括：

- 四个 Product Line 切换；
- Role 切换；
- 人员名称清理、计数和既有排序；
- Chart.js 配置、空状态、动态高度和销毁。

项目事实获取仍由现有 Project Facts API 和 SQLite 查询快照 owner 提供。组件可以消费当前账户可见的本地事实，但不得触发远端同步或详情任务。

## 6. 持久化与账户隔离

复用现有 `/api/preferences/{scope}`、`user_preferences` 和认证 session：

- scope：`dashboard/layout`；
- key：`layout`；
- schema version：`1`；
- 后端只从认证 session 取得用户名，不接受前端指定账户；
- 每个账户只能读取、写入和删除自己的布局；
- 前端不在 `localStorage` 或 `sessionStorage` 保存可复用布局或组件业务数据。

持久化实例只包含：

```js
{
  id: "稳定实例 ID",
  type: "role-workload",
  x: 0,
  y: 0,
  w: 24,
  h: roleWorkload.defaultH,
  config: {}
}
```

`roleWorkload.defaultH` 是设计期符号，不进入保存数据。实现时必须按第 4.2 节的现有组件高度换算得到正整数并写入组件注册信息；序列化结果中的 `h` 只能是该正整数或用户缩放后的有效正整数。

系统默认布局是版本内只读定义，首版包含一个 `Role workload` 实例。账户无个人布局或执行“恢复默认布局”后使用该定义；恢复默认通过删除个人 preference 完成，不复制或修改系统默认。

## 7. 编辑交互

### 7.1 普通模式

- 显示“编辑 Dashboard”。
- 卡片不可拖动、缩放或移除。
- 卡片内部筛选与图表交互正常。

### 7.2 编辑模式

- 顶部显示“添加组件”“恢复默认”“取消”“保存”。
- 每张卡片显示拖动把手、移除按钮和 resize handle。
- 所有变更只作用于内存工作副本，不立即写数据库。
- 添加组件从注册表选择，按组件默认布局放入第一个可用位置。
- 移除只移除工作副本中的实例，并立即销毁组件资源。

### 7.3 保存、取消与恢复默认

- 保存：调用 GridStack `save(false)`，剔除 HTML/content，只保留允许字段；校验注册类型和正整数坐标后一次 PUT 当前账户 preference。成功后更新基线并退出编辑模式。
- 保存失败：保留当前编辑态和工作副本，显示错误，不伪装成功、不静默回退。
- 取消：销毁工作副本，按进入编辑前基线重新创建布局和组件，不访问远端。
- 恢复默认：在编辑态先把工作副本替换为系统默认；只有点击保存后才 DELETE 个人 preference。点击取消仍恢复原个人布局。

## 8. 加载、错误与生命周期

- Dashboard 先完成认证，再请求当前账户 `dashboard/layout` preference。
- 无个人记录时使用系统默认；网络或服务错误不能伪装成“无个人记录”。
- preference 无效、未知组件或越界坐标必须显示可见错误；有效组件仍可展示，但不得自动覆盖损坏记录。
- 账号切换、退出登录或页面销毁时，销毁 GridStack 和所有组件实例，清除内存布局基线。
- `Role workload` 数据不可用时复用现有空状态/错误表现，不由 Dashboard 构造替代数据。

## 9. 文件与 owner 预期

实现优先沿用现有目录，预计涉及：

- `web/frontend/package.json` 与 lockfile：GridStack 依赖；
- `web/frontend/src/dashboard-main.js`：Dashboard 页面入口；
- `web/frontend/src/dashboard/`：Grid owner、注册表、卡片外壳、布局 store；
- `web/frontend/src/widgets/role-workload.js`：共享业务组件；
- `web/frontend/src/projects.js`：改为消费共享组件；
- `web/frontend/src/api.js`：复用或暴露现有 preference API，不新增平行业务存储；
- `web/frontend/src/smarttest-theme.css`：Dashboard 与组件外壳样式；
- 对应 Vitest 测试。

若调查发现现有 owner 已提供同等能力，应复用或合并，不按本节路径机械新增文件。

## 10. 验收标准

### 10.1 功能验收

- 首次进入 Dashboard 显示系统默认的真实 `Role workload` 卡片。
- Projects 与 Dashboard 使用同一 `Role workload` 实现，原 Projects 行为不变。
- Dashboard 普通模式不可拖动、缩放或移除。
- 编辑模式可添加、移除、拖动和缩放 `Role workload`。
- 保存后刷新页面仍恢复当前账户布局。
- 取消后恢复进入编辑前的布局，未发生 preference 写入。
- 恢复默认并保存后删除个人布局，再次进入显示系统默认。
- 两个账户的布局互不可见；切换账户不闪现前一个账户布局。
- 24 列桌面布局在中等宽度和手机宽度下稳定重排，返回桌面后尺寸与位置不丢失。
- 默认尺寸下 `Role workload` 保持现有内容、切换控件、图表高度和内部滚动可用，无关键内容裁切。

### 10.2 质量验收

- 不存在自研碰撞/拖动/缩放算法。
- 不保存 HTML、项目事实、人员结果或权威资源 ID。
- 一个 WidgetRegistry、一个 DashboardGrid、一个 Role workload 实现、一个账户 preference owner。
- 组件和 GridStack 生命周期完整销毁，无重复监听器或 Chart.js 实例。
- 无临时诊断、调试输出、废弃尝试、重复测试或无业务占位组件。
- 前端全量测试、ESLint、Vite build 和 `git diff --check` 通过。

## 11. 执行检查项

1. 记录干净工作区与依赖基线，安装并锁定 GridStack。
2. 以失败测试定义组件注册、布局规范化、保存/取消、恢复默认和账号隔离。
3. 抽取 `RoleWorkloadWidget`，先保证 Projects 测试与实际表现不变。
4. 根据现有 Role workload 实际展示高度登记正整数布局属性。
5. 实现 DashboardGrid、卡片外壳、编辑工具栏和组件选择器。
6. 接入现有 preference API 与系统默认布局。
7. 验证 24/12/1 列响应式恢复、刷新恢复和账号切换。
8. 清理实现残留，完成 diff-led 验收与全量前端验证。

## 12. 复用与生产代码增长决策

- 布局引擎：引入 GridStack，不自研。
- 持久化：复用现有 preference API、SQLite `user_preferences` 和 session 账户边界。
- 图表：复用 Chart.js。
- 业务组件：从 Projects 抽取 Role workload，共享而不复制。
- 新增生产代码只覆盖 DashboardGrid、组件注册/生命周期和统一卡片外壳；如实现中出现第二套布局、偏好、图表或项目事实机制，视为质量失败。

## 13. 最终确认调整

本节记录联调后的最终产品决定，并覆盖前文中关于组件缩放和 Projects 复用的对应描述：

- Dashboard 卡片不支持用户缩放，不显示 resize handle；编辑模式只允许添加、删除和拖动位置。
- 每种组件由注册表登记固定 `defaultW/defaultH`。加载和保存布局时，尺寸始终取组件注册值，只持久化用户调整后的位置、组件增删结果与组件配置。
- `Role workload` 固定为 24×21。统一卡片外壳禁止外层滚动，只保留组件原有图表区域的一层滚动。
- `Role workload` 从 Projects 页面移除，只在 Dashboard 中作为独立组件提供。
- Dashboard 的 `Role workload` 使用空过滤条件读取当前账号授权 catalog 范围内的全部本地项目事实，不重放或修改 Projects 查询快照，也不触发远端详情任务。
