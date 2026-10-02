# Client Common 工具瘦身设计

## 目标

从桌面 client 的 `Tool > Common` 下线日报、Jira 审查和 Confluence 审查三个工具，删除它们在 client 中的页面、bridge、注册与专属资源，并清理由此失去调用者的审查专属 core 代码。对应能力后续由 web 端完善，本次不修改 web。

## 范围

### 删除

- `Tool > Common` 中日报、Jira 审查、Confluence 审查的入口和工作区。
- 三个工具专属的 QML 页面/组件、bridge、bridge 注册、翻译、资源和测试。
- 日报的定时任务功能，包括仅服务该定时功能的 client 代码及专属依赖。
- Jira 审查、Confluence 审查调用链中没有其他消费者的 core 代码、测试及专属依赖。
- 因上述删除而失效的导入、注册、QRC 条目、打包依赖和测试引用。

### 明确保留

- 独立 Jira 页面 `T_Jira.qml`、`JiraBridge` 及其完整调用链。
- 日报底层封装；即使当前没有其他调用者，也不因本次瘦身删除。
- 被 web、`T_Jira`、其他 client 功能或公共机制使用的 core 能力。
- `Tool > Common` 中未点名的其他工具及其现有行为。

### 不做

- 不增加迁移、历史数据清理、兼容入口、回退或兜底逻辑。
- 不给 client 增加 web 跳转或替代页面。
- 不重构未被本次删除直接影响的公共机制。
- 不修改 web 功能。

## 删除判定

1. 从三个 Common 工具入口沿 QML、bridge、服务和依赖方向建立实际调用链。
2. client 层属于该调用链且没有保留功能引用的代码可以删除。
3. core 层只有 Jira 审查和 Confluence 审查的专属代码在确认没有其他消费者后才能删除。
4. 日报底层封装无条件保留，只删除其 client 展示/bridge 和定时任务功能。
5. 名称包含 Jira 或 Confluence 不能作为删除依据；`T_Jira` 的引用链是明确保护边界。

## 实施检查单

- [ ] 记录起始 `git status`，确认并保护用户已有改动。
- [ ] 列出三个 Common 工具从入口到 bridge/core 的引用链，并标记保留消费者。
- [ ] 先用聚焦测试或静态断言保护剩余 Common 工具和 `T_Jira` 注册关系。
- [ ] 删除三个工具的 client 入口、页面、bridge、注册、专属翻译/资源/测试。
- [ ] 删除日报定时任务功能，保留日报底层封装。
- [ ] 删除确认仅归 Jira/Confluence 审查所有的 core 代码和专属依赖。
- [ ] 清理失效的导入、QRC、打包声明和测试引用，不增加替代逻辑。
- [ ] 运行聚焦 UI/bridge/翻译测试、相关 core 测试、导入或编译检查。
- [ ] 从仓库根目录进行有界 source 启动验证；不重建桌面安装包。
- [ ] 检查净生产代码减少量、`git diff --check` 和最终 scoped diff。

## 验收标准

- client 的 `Tool > Common` 不再展示或加载日报、Jira 审查、Confluence 审查。
- 三个工具的 client 页面与 bridge 调用链已删除，没有失效注册或资源引用。
- 日报定时任务功能已删除，日报底层封装仍存在且可导入。
- `T_Jira.qml`、`JiraBridge` 及其运行依赖保持可用。
- core 只删除经引用检查证明为 Jira/Confluence 审查专属的代码。
- 其他 Common 工具和未涉及功能行为不变。
- 聚焦测试与 source 验证通过，`git diff --check` 通过，diff 中没有临时诊断、遗留尝试或无关改动。

## 交付方式

采用 Atlas + Mason 单工作线程交付。Mason 负责目标代码调查、实现、清理和自测；Atlas 依据 scoped diff、测试证据和引用边界完成最终验收。本次预计一轮实现完成；若范围扩大到需要第二轮 Mason 工作，先按仓库规则向 Coco 询问周配额。
