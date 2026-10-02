# Redmine 批量 Clone 到 Jira 创建页面设计

## 目标

用户可以在 Redmine Issue 列表中选择多个尚未 Clone 的问题，集中查看、填写和修改对应的 Jira 创建草稿，并且只有在用户最后点击一次“批量创建”后才真正创建 Jira Issue。

本设计复用现有 Redmine Issue 列表、Clone 状态检测、Jira 登录客户端和创建服务。新增一个由字段 Schema 驱动的 Jira Create QML，不嵌入 Jira 网页，也不通过浏览器自动操作 Jira 创建弹窗。

## 职责边界

### Redmine 选择流程

Redmine Issue 列表只负责选择问题和提供能够可靠映射的源数据：

- 进入和退出 Clone 选择模式。
- 选择模式下，每条 Issue 显示复选框。
- `cloneStatus` 已经是 `cloned` 的条目仍然显示，但复选框不可用。
- 非选择模式下保持原有 Issue 选择和详情展示行为。
- 打开创建草稿前，将用户选择的 Redmine Issue 补全为完整详情。
- 只有映射关系明确时才提供初始值。

Redmine 不负责定义 Jira 控件、必填字段、候选选项，也不为无法映射的字段猜测默认值。

### Jira 创建 Schema 与草稿

Jira 创建业务负责获取固定项目 `SH` 和对应 Issue Type 的创建元数据，并向前端提供与界面无关的字段 Schema。Schema 包含字段标识、名称、必填状态、控件类型、当前值、候选项、加载状态和校验错误。

新 Jira Create QML 根据 Schema 还原 Jira 原生控件：

- Jira 文本框对应 QML 文本框。
- Jira 单选下拉对应 QML 单选下拉。
- Jira 多选下拉对应 QML 多选下拉。
- Jira 级联选择对应两个联动的 QML 下拉框。
- Jira 人员选择器对应由 Jira API 支持的可搜索人员选择器。
- Jira 多行字段对应 QML 多行编辑器。

QML 只负责布局和临时编辑交互。Bridge 负责草稿身份、字段 Schema、选项加载、校验、请求转换和提交状态。

## 人员配置调整

Amlogic 标准部门统一为：

- `FAE-QA`
- `FAE-SW`
- `FAE-HW`

现有 `FAE` 部门改名为 `FAE-SW`，已有人员和产品线分配保持不变。

新增 Fred Chen：

- LDAP/Jira 账号：`fred.chen`
- 显示名称：`Fred Chen`
- 部门：`FAE-SW`
- 职级：`M5`
- 职责：SmartHome 产品线负责人

只有当前登录用户的标准部门严格等于 `FAE-SW` 时，才自动将本人填入 FAE Coworker。`FAE-QA`、`FAE-HW`、未知人员和其他部门都保持为空，由用户手动选择。

## 草稿创建流程

1. 用户点击 Redmine Issue 列表工具栏中的 Clone。
2. 当前列表中所有 Issue 显示复选框。
3. 已 Clone 的 Issue 保持可见，但复选框不可用。
4. 用户选择一个或多个 Issue，并确认选择。
5. Bridge 加载完整 Redmine 详情和 Jira 创建字段/选项，此时不创建 Jira Issue。
6. 打开一个批量创建弹窗，按照 Redmine 列表顺序完整展开所有草稿。
7. 用户集中浏览，并修改任意预填或空白字段。
8. 用户点击一次“批量创建”，系统先在本地校验全部草稿。
9. 如果校验失败，不发送任何 Jira 创建请求；界面滚动到第一个错误草稿/字段，并显示全部错误。
10. 全部校验通过后，Bridge 按顺序提交草稿。开始提交后不再允许取消。

打开弹窗、加载选项和编辑草稿均不会产生 Jira 创建副作用。

## 已确认的初始值

工具填入的所有初始值都允许用户后续修改。

| Jira 字段 | 初始值 |
|---|---|
| Project | 固定为 `Smart Home Projects (SH)`，key 为 `SH` |
| Issue Type | Redmine `Bug -> Bug`；`Support -> Feature` |
| Channel of Reporter | `Customer-Feedback`，子级为 `None` |
| Summary | Redmine Subject |
| Priority | `P2` |
| Severity | `Major` |
| Product | `BDS Reference` |
| Component/s | `Customization` |
| Project ID | Redmine 子项目中的 `[Project ID]` |
| Software Release | 除非后续确认映射，否则保持为空 |
| Reporter | 当前登录 Jira 用户 |
| Manager | Jira 用户 `fred.chen` |
| FAE Coworker | 当前 LDAP 用户属于 `FAE-SW` 时填当前用户，否则为空 |
| FAE Manager | Jira 用户 `fred.chen` |
| Description | Redmine Description 加来源身份和链接；仅在原 Description 为空时生成非空来源摘要 |

当前从 Jira 创建页面确认到的字段 ID 仅作为发现线索，不作为写死在 QML 中的契约：

- Channel of Reporter：`customfield_12200`
- Severity：`customfield_10109`
- Product：`customfield_10107`
- Project ID：`customfield_10407`
- Software Release：`customfield_10300`
- Manager：`customfield_10700`
- FAE Coworker：`customfield_10409`
- FAE Manager：`customfield_11002`

程序通过 Jira API 按 `SH + Issue Type` 获取字段元数据。必填字段缺失、选项不存在、人员匹配不唯一或字段 ID 发生变化时，界面必须明确显示并阻止提交，不能猜测。

## 批量弹窗布局

弹窗按照 Jira Create Issue 的纵向字段顺序和必填标记组织，同时使用现有 FluentUI 控件和主题颜色。

- 顶部：已选数量、加载/校验/提交状态，以及提交前可用的关闭操作。
- 中间滚动区：每个 Redmine Issue 对应一张完整展开的草稿卡片，以 Redmine ID 和 Summary 标识。
- 草稿卡片：按照 Jira 顺序显示 Schema 字段、必填标记、帮助/错误信息和当前值。
- 固定底栏：取消和批量创建；批量创建按钮显示草稿数量。
- 元数据加载期间显示草稿骨架或进度，禁用批量创建。
- 提交期间禁止编辑和关闭，并显示整体进度。

预期每次批量数量较少，不引入虚拟列表和折叠卡片。

## 提交与失败恢复

Jira 不支持多个 Issue 的原子事务。全部本地校验通过后，草稿按顺序创建：

- 创建成功：显示新的 Jira key 和链接，并立即更新 Redmine Clone 状态。
- 检测到重复：显示已有 Jira key 和链接，将该草稿视为已处理，不重复创建。
- 创建失败：保留全部用户编辑值并显示服务器错误。
- 单个失败不阻止后续已校验草稿提交。
- 提供“只重试失败项”，成功项和重复项不可再次提交。

已经成功创建的 Jira Issue 不做自动回滚。

## API 与缓存规则

- 复用现有已登录 Jira Client 和 `CreateIssueService`。
- 扩展现有创建请求模型以承载必填自定义字段；QML 不直接拼装 Jira JSON。
- 候选项必须来自 Jira 创建元数据或 Jira 人员/选项 API，不允许在 QML 中写死列表。`Major`、`Customization` 等已确认初始标签在提交前必须解析为 Jira 当前有效选项。
- 稳定字段元数据和选项按 Jira base URL、Project key、Issue Type、字段身份缓存，并尽量复用现有 metadata cache。
- 用户搜索和依赖字段选项异步加载，并使用 generation 防止旧结果覆盖新状态。
- 草稿只在当前会话中临时存在，并绑定当前账号。LDAP/Jira 账号改变时关闭或废弃草稿，并忽略迟到结果。

## 错误处理

- Redmine 详情无法加载：打开审阅页面前排除该 Issue，并向用户报告。
- Jira 元数据无法加载：弹窗停留在可重试错误状态，不使用猜测字段降级。
- 必填初始选项已不存在：清除无效值，要求用户重新选择。
- `fred.chen` 无法唯一匹配：阻止受影响草稿提交，并显示人员选择错误。
- 用户审阅期间 Clone 状态发生变化：提交前重新检测，将已 Clone 草稿标记为跳过/已处理。
- 账号切换：废弃整个批次，要求用户在新账号下重新选择。

## 验证范围

自动化测试至少覆盖：

- Clone 选择模式、已 Clone 禁选、取消/确认，以及退出后恢复正常 Issue 列表行为。
- Bug/Support 映射和全部已确认初始值。
- 只有 `FAE-SW` 自动填写 FAE Coworker，并覆盖 `FAE-QA`、`FAE-HW` 反例。
- Jira 元数据到文本、单选、多选、级联、人员、多行控件 Schema 的转换。
- 依赖选项加载和迟到结果保护。
- 多张完整展开草稿、预填值可编辑和一次批量确认。
- 第一个 Jira 创建请求前，必须完成全部草稿的本地校验。
- 顺序创建成功、重复、部分失败和只重试失败项。
- 账号切换导致批次失效。
- QML 运行、双语翻译、主题/资源集成和源码启动。

普通开发阶段不要求构建安装包；只有用户要求验证打包行为或进入发布交付时才执行打包验证。
