# 产品线全局视觉机制与现有代码收敛

状态：已实现，Atlas 已完成差异验收。本文同时包含设计与执行清单，不另建实施计划。

## 1. 目标与范围

为 China Operator、Smart Device、TV、Global Operator & STB、Wireless Connection 五个前端分类建立统一视觉入口。元素声明“产品线 + 控件类型”，同一产品线跨页面复用同一套定义。

本阶段实现机制并收敛已有代码，不选择或填充五套新配色、纹理、动画。沿用现有主题与有效交互表现。后续专属视觉只修改集中定义及必要的控件适配规则。

不改变后端产品线定义、查询、权限、缓存、筛选值、排序或持久化。Projects 仍按既有 catalog 显示四个产品线容器；支持第五类视觉不代表向 Projects 添加没有数据定义的容器。保留已完成的 Top3 效果及 Project 标题下进度。

## 2. 现状与复用决定

- `core/product_lines.py` 已定义五个分类的完整名称，是业务分类事实来源。
- `project-semantics.js` 通过 data 属性绑定 Project Status／Current Stage，`smarttest-theme.css` 集中提供语义样式。产品线沿用此模式，但保持独立 owner。
- Projects 的 `productSpaces` 使用 `{ value, label }`，`value` 是 Confluence 标识，`label` 是展示名称；Jira 的产品线选项使用 `{ id, label }`。
- `ranking-card.js` 是多张排名卡片的共享展示 owner，统一接入一次。
- `ranking-card.css` 的产品线按钮存在重复的 `::before`、`::after`、active 与动画声明；迁移时按当前实际生效结果合并，不把被覆盖的历史尝试复制到新入口。
- `smarttest-theme.css` 的 `.product-space-group` 和 `.product-space-summary` 混合了布局与外观，迁移其产品线外观，保留页面布局职责。

复用原生 data 属性、CSS 自定义属性及现有主题，不引入样式库、主题运行时、动画计时器或新的组件框架。

## 3. 身份与展示契约

| 产品线完整名称／视觉身份 | Confluence 内部值 |
| --- | --- |
| China Operator | DOPL |
| Smart Device | SDPL |
| TV | TV |
| Global Operator & STB | OOPL |
| Wireless Connection | WIRELESS |

内部值继续参与请求、筛选、数据匹配和既有持久化，不转换请求值。用户可见的标题、按钮文字、标签及无障碍名称使用完整名称，不显示内部缩写。

共享排名选项保留 `value`、`label`，补充 `productLine` 字段，表示完整名称形式的视觉身份。Projects／Jira 适配器从当前响应的完整名称字段填入，不从 DOM 文本反推，不建立另一份 Confluence 缩写映射表。`label` 在本范围内继续显示同一个完整名称。

例如 Projects 选项为 `{ value: 'DOPL', label: 'China Operator', productLine: 'China Operator' }`。点击后仍用 `DOPL` 查数据，视觉绑定使用 `China Operator`。

前端只声明这五个视觉分类的样式，不新增业务产品线目录。缺少视觉身份时清除旧产品线属性；没有对应样式的身份保持基础控件外观，不猜测归属、不显示内部值作为名称。数据定义错误如实报告，不增加标签推断或业务兜底。

## 4. 元素契约与最小接口

新增 `web/frontend/src/product-line-semantics.js`，只提供：

```js
bindProductLine(element, productLine, surface)
```

该函数设置或更新 `data-product-line` 和 `data-product-surface`，返回原元素；清空身份时移除旧绑定。它不请求数据、不改文字、不维护选中状态，也不修改控件的其他属性。

```html
<section data-product-line="China Operator" data-product-surface="card">
<button data-product-line="China Operator" data-product-surface="button">
<span data-product-line="China Operator" data-product-surface="badge">
```

第一阶段仅支持 `card / button / badge`，不提前抽象更多控件类型。实际页面没有产品线 badge 的地方不新增标签；用测试样例验证 badge 接入能力。

## 5. 全局样式 owner

新增 `web/frontend/src/product-line-theme.css`，由现有全局主题入口加载一次，分三部分：

1. 五个产品线选择器：集中定义外观变量。本阶段使用现有主题值，未启用的纹理与装饰动画取 `none`，不编造五套临时设计。
2. 三种 surface 规则：消费产品线变量，管理卡片、按钮、标签的外观与交互状态。
3. 浅暗主题、焦点、选中、禁用、减少动态效果规则。

变量限于本次消费者需要的色彩与装饰入口：前景、底色、边框、强调色、纹理及装饰动画。使用 `--product-line-*` 前缀，不覆盖全局 `--accent`，避免嵌套状态徽章及普通控件被一起染色。具体复杂动画以后按批准样式实现，不预建通用动画引擎。

页面 CSS 继续管理尺寸、间距、布局、图表滚动、按钮组排列；产品线 CSS 管理产品线外观。原有基础 card/button 样式继续复用，新规则不重写所有控件基础样式。

必须同时声明产品线和 surface 才应用产品线装饰；不会通过宽泛后代选择器自动装饰所有子元素。不同产品线子元素显式绑定自己的身份，混合分类父容器保持中性。产品线身份不从父级隐式推断。

状态沿用现有 `aria-pressed`、`aria-expanded`、`disabled`、`:focus-visible` 等，不增加第二份选中状态。产品线按钮原有有效选中/悬停表现迁入公共规则；同一伪元素只保留一个明确职责及一套生效声明。专属新纹理和动画在下一阶段填充。

## 6. 接入与收敛边界

| 位置 | 接入与保留职责 |
| --- | --- |
| `widgets/role-workload.js` | 传递完整产品线视觉身份；内部 `value` 与 `space_key` 匹配保持原样 |
| `widgets/jira-statistics-card.js` | 从响应选项传递相同视觉身份；保留用户已有 Jira 改动 |
| `widgets/ranking-card.js` | 每个产品线按钮绑定自身身份；内容区绑定当前选中身份，切换／恢复／空选项时同步更新或清除 |
| `widgets/ranking-card.css` | 保留排名布局、角色控件、Top3、进度样式；移出产品线外观并清理被覆盖的重复规则 |
| `projects.js` | 产品线分组容器及展开按钮分别绑定 card/button；标题继续使用完整名称 |
| `smarttest-theme.css` | 引入全局产品线主题；移出本次接入元素的产品线外观，保留布局及 Status／Stage 体系 |

排名卡片的混合产品线切换栏不随当前选择整体换产品线背景；各选项有自己的身份，单产品线内容区随选择变化。避免一个父卡片的选中产品线装饰覆盖其他产品线按钮。

Project Status、Current Stage、Top3 金银铜、Jira 当前／上期条形颜色保持各自语义 owner。产品线装饰作用于专属容器和明确接入的按钮／标签，不用产品线色覆盖这些语义元素。

原生 select 的 option 保留完整名称及原有样式，本阶段不替换控件，也不承诺原生选项支持纹理动画。其他页面后续可通过同一绑定入口接入，本次不扩大到无关页面重构。

## 7. 执行清单

- [x] Mason 记录开始时 git status 和相关 baseline diff，保护全部已有改动。
- [x] 建立产品线绑定入口、全局 CSS 入口与三种 surface；不新增依赖。
- [x] 在 Projects／Jira 适配器传递完整视觉身份，保留业务值。
- [x] 接入共享排名组件及 Projects 分组，覆盖选择变化和缓存恢复的既有渲染路径。
- [x] 从原样式文件迁移外观规则，删除重叠旧声明，核对迁移前后有效交互。
- [x] 添加关键回归测试及浏览器验证，清理临时样例和诊断。
- [x] Atlas 按 scoped diff 验收，报告复用决定、净生产代码增长与双 PASS 结果。不自动提交或推送。

## 8. 验收标准

1. 相同产品线在 Projects 与 Jira 上得到相同 `data-product-line`；请求、匹配和持久化仍使用原内部值。
2. 五个分类完整名称正确；本次接入的可见标题、按钮、标签及无障碍文案不出现 DOPL／SDPL／OOPL／WIRELESS 代号。
3. 切换产品线、选项更新及空选项不会留下上一条产品线身份；多个卡片独立切换互不污染。
4. card/button/badge 都能通过同一契约使用样式；更换某分类定义无需逐页修改业务代码。
5. 浅暗主题、选中、悬停、键盘焦点、禁用、减少动态效果可用；长名称不截成缩写，不以静默换行掩盖现有单行布局要求，窄屏超出既有布局能力时明确报告。
6. Status／Stage／Top3／Jira 期间配色与 Project 进度无回归；分类目录、查询范围、后端接口不变。
7. 聚焦测试、完整前端测试、lint 和 `git diff --check` 通过；浏览器以本地样例验证五类、三种控件和状态切换，不需要远端业务请求。
8. 不保留新旧两套产品线外观 owner，不保留临时诊断、失效动画规则或无消费者的抽象；报告迁移删除量及净代码增长。

## 9. 后续阶段

机制验收后，再选择五套专属颜色、纹理及动画。后续设计明确每类的视觉特征和各 surface 表现，本阶段不预先做产品决定。

## 10. 实施验收记录

- Mason /root/mason 实现，Atlas 按本轮 baseline diff 验收；Functional Acceptance PASS，Code Quality PASS。
- 生产代码 +170/-204，净减少 34 行；保留原有未提交修改。
- 完整前端 258/258、lint、git diff --check 均 exit 0。
- 本地浏览器验证五类及三种 surface、浅暗主题、焦点、禁用、身份切换；减少动态通过样例激活实际 CSS 媒体规则验证，未切换系统设置。
- 640px 样例内工具栏 clientWidth 542px / scrollWidth 619px，保留已记录的单行窄屏溢出边界。
- 专属新颜色、背景、动画尚未填充；未提交或推送。

## 10. 已批准扩展：项目行 disclosure（2026-09-30）

Coco 确认将 Projects 白色项目行纳入产品线机制，新增 `data-product-surface="disclosure"`。实际 owner 是 `article.project-card`，沿用鼠标悬停显示附加字段、移出收起的既有交互，不改成点击或 `details/open`。

- 从当前 `productSpaces` 的完整名称向阶段分组渲染及项目行传递身份；请求/匹配值不变。
- 同一项目行容器覆盖摘要和附加字段的产品线外观；Smart Device 使用弱化静态纹理与青色边线，其他产品线保留基础外观。
- Stage 与 TV launch-OS 的原生折叠、Status/Stage 颜色、项目链接、字段和排序保持原 owner；不新增展开状态、持久化或动画计时器。
- 验证真实 Projects 组件中的悬停展开/移出收起、跨产品线隔离、浅暗主题及键盘焦点；减少动态规则延用全局入口。
