# SmartTest 多端目录重构设计

## 1. 背景与目标

SmartTest 将在保留 Windows 桌面客户端的基础上逐步增加 Web 端，并继续维护 Android/移动端。代码仍使用当前单一 GitHub 仓库，不拆分为多个仓库。

本次重构的目标是建立清晰的多端目录和单一核心业务边界，使桌面端、Web 端和移动端能够共享 SmartTest 核心能力，同时保持各端界面、平台集成和发布流程相互独立。

旧 Web 仓库后续逐步迁入当前仓库。迁移采用“迁入一个业务模块、适配一个业务模块”的方式，不进行一次性覆盖或整体替换。

## 2. 已确认的架构决策

仓库根目录设置四个一级产品目录：

```text
SmartTest/
├── client/                 # Windows QML 桌面客户端
├── core/                   # SmartTest 唯一业务核心
├── web/                    # Web 前端与 Web 后端
├── mobile/                 # Android/移动端
├── docs/                   # 架构、协议和开发文档
├── support/                # 开发、迁移、构建和 CI 脚本
├── pyproject.toml
├── README.md
└── AGENTS.md
```

`core/` 是中立的共享业务所有者，不归属于 `client/`、`web/` 或 `mobile/`。即使未来 Web 成为主要入口，Web 仍调用 `core/`，不把核心实现复制或移动到 Web 内部。

## 3. 目标目录

```text
SmartTest/
├── client/
│   ├── app/
│   │   ├── main.py
│   │   ├── ui/
│   │   └── bridge/
│   ├── packaging/
│   └── tests/
│
├── core/
│   ├── testing/
│   ├── tools/
│   ├── jira/
│   ├── config/
│   ├── contracts/
│   └── tests/
│
├── web/
│   ├── frontend/
│   ├── backend/
│   │   ├── app/
│   │   ├── api/
│   │   ├── services/
│   │   ├── events/
│   │   └── tests/
│   ├── legacy/
│   └── README.md
│
├── mobile/
│   ├── android/
│   ├── generated/
│   └── tests/
│
├── docs/
│   ├── architecture/
│   ├── api/
│   └── migration/
│
└── support/
    ├── dev/
    ├── migration/
    ├── packaging/
    └── ci/
```

目录中的子目录按实际迁移需求创建，不为尚未落地的机制预先创建空实现。

## 4. 所有权与依赖方向

依赖方向固定为：

```text
client ---------------------> core
web/frontend -> web/backend -> core
mobile ------> web/backend -> core
```

### 4.1 `client/`

`client/` 负责 Windows 桌面端的 QML 页面、Qt Bridge、窗口与本地交互、客户端显示状态以及桌面打包。桌面端继续支持本机独立运行，并直接使用 `core/` 的 Python 能力，不以 Web 后端可用作为运行前提。

### 4.2 `core/`

`core/` 负责 pytest 执行、参数、DUT、串口与实验室设备、步骤、结构化事件、日志、报告、Jira 业务能力及跨端业务契约。核心业务只有这一份实现。

`core/` 不得导入 `client/`、`web/` 或 `mobile/`。其中的模型、事件和接口保持与具体 UI 技术无关。

### 4.3 `web/`

`web/frontend/` 负责 CoreUI 页面和浏览器交互，只调用 Web API，不直接访问 `core/`。

`web/backend/` 负责 HTTP API、实时事件传输、认证、请求编排以及 Web 运行边界。凡是涉及测试执行、参数、设备、日志和报告的业务行为，必须调用 `core/`，不得在 Web 后端复制实现。

`web/legacy/` 仅作为旧 Web 仓库迁移期间的临时隔离区。每个旧模块完成适配后，应删除对应旧实现，禁止形成长期并行的新旧业务路径。

### 4.4 `mobile/`

`mobile/` 负责 Android/移动端界面和平台专属行为。远程业务能力通过 Web API 使用 `core/`；Android 本机专属 APK runner、系统权限和平台集成继续由移动端拥有。

## 5. 当前目录映射

| 当前路径 | 目标路径 |
|---|---|
| `ui/` | `client/app/ui/` |
| 根目录 `main.py` | `client/app/main.py` |
| `testing/` | `core/testing/` |
| `tools/`、`tool/` | 按现有业务 owner 整理至 `core/tools/` 或保留为明确的仓库级工具 |
| `jira/` | `core/jira/` |
| `config/` | `core/config/` |
| `android_client/` | `mobile/android/` |
| 旧 Web 仓库 `src/` | `web/frontend/` |
| 旧 Web 仓库 `server/` | 先进入 `web/legacy/`，再逐项适配至 `web/backend/` |
| 旧 Web 构建产物 | 不迁入，由新环境重新生成 |
| 旧 Web 数据文件或 SQL | 先放迁移区审查，不直接作为新数据模型 |

具体移动前必须检查实际导入、资源、打包、pytest discovery、Gradle 和 CI 路径。本表只定义所有权目标，不授权机械地合并语义不同的目录。

## 6. 迁移策略

迁移必须保持每个阶段均可验证、可回退，并将“目录移动”和“业务行为修改”分开交付。

### 阶段一：建立目录与导入边界

建立四个一级产品目录和必要的包入口，明确依赖规则。此阶段不修改业务行为，也不提前迁入旧 Web 业务。

### 阶段二：迁移移动端

将 `android_client/` 迁至 `mobile/android/`，修复 Gradle、构建、签名、安装和桌面到 APK 集成路径，并验证现有 Android 行为不变。

### 阶段三：迁移桌面客户端

将桌面入口和 `ui/` 迁至 `client/`。该阶段保持当前 QML、Bridge 和测试核心调用关系，不同时重构业务流程。

### 阶段四：迁移共享核心

将 `testing/` 及其明确依赖逐步迁至 `core/`，修复 Python 导入、pytest discovery、运行参数、资源、报告和打包路径。旧路径兼容入口只能作为有删除期限的迁移手段，最终不得保留两套 owner 或传输路径。

### 阶段五：迁入旧 Web 仓库

将旧 Web 前端迁至 `web/frontend/`，将旧服务端先隔离到 `web/legacy/`。逐个识别可复用 UI、旧 Wi-Fi 专属逻辑、通用能力和废弃实现。

每适配一个业务模块：先定义该模块与 `core/` 的契约，再实现 `web/backend/` 调用，然后接入 `web/frontend/`，验证完成后删除对应 legacy 实现。

### 阶段六：统一开发与持续集成

建立桌面端、Web 端、移动端的独立启动与验证入口，以及需要时的一键联调入口。CI 按受影响目录执行对应检查，同时保留跨层契约和端到端验证。

## 7. 开发运行模式

计划提供以下仓库级入口：

```powershell
.\support\dev\start-client.ps1
.\support\dev\start-web.ps1
.\support\dev\start-mobile.ps1
.\support\dev\start-all.ps1
```

SmartTest 的 ADB、串口、USB 和实验室设备依赖 Windows 主机环境，因此核心执行服务开发期默认直接运行在主机，不强制容器化。Web 前端和通用数据库可按实际需要使用容器，但不能改变核心硬件访问边界。

## 8. 验收标准

每个迁移阶段至少满足：

1. 只移动该阶段已批准范围内的目录和引用。
2. 不改变现有客户端、测试执行或 Android 业务行为。
3. 原有针对性测试在新路径下通过，pytest discovery 和运行入口有效。
4. 涉及 QML/QRC 时资源与翻译链有效；涉及 Android 时 Gradle 构建和集成路径有效。
5. 桌面源代码启动通过；包行为只有实际重建并验证后才能声称通过。
6. `core/` 不反向依赖任何端，Web 后端不复制核心测试逻辑。
7. 不保留无期限的兼容层、重复 owner、临时诊断或废弃迁移代码。
8. scoped diff 无无关修改，`git diff --check` 通过。

## 9. 非目标

本目录重构不自动授权以下事项：

- 重写现有测试业务行为；
- 将桌面客户端改为依赖 Web 后端运行；
- 一次性合并整个旧 Web 仓库；
- 新增认证、权限、调度、数据库或微服务机制；
- 为目录统一而手写已有依赖可覆盖的底层实现；
- 在未验证硬件环境时宣称 DUT、串口或实验室设备验收通过。

这些能力如需实施，应在对应迁移阶段另行明确范围和验收。

## 10. 分阶段执行清单

本清单是该重构的唯一执行计划。每一阶段单独形成原子交付；前一阶段通过功能验收和代码质量验收后，才进入下一阶段。不得把后续阶段的业务改造提前混入当前阶段。

### 10.1 阶段一：建立目录骨架与仓库约束

范围：

- 创建实际需要的 `client/`、`core/`、`web/`、`mobile/` 目录入口；
- 更新仓库说明、开发入口和静态路径检查，使四个产品目录的 owner 与依赖方向可验证；
- 保持当前 `main.py`、QML、pytest 和 Android 工程从原路径运行；
- 不移动业务源码，不添加 Web 业务实现，不改变导入路径。

验收：

- 当前桌面源码启动检查、pytest discovery 和 Android 基线检查保持不变；
- 新目录不包含重复业务实现或无用途的空模块；
- 仓库文档明确 `core` 不得依赖三端，以及 Web 必须通过后端调用 `core`。

### 10.2 阶段二：迁移 Android 工程

范围：

- 将 `android_client/` 迁至 `mobile/android/`；
- 更新 Gradle、签名、`dist/` 产物、priv-app 安装、桌面触发和相关 CI/脚本路径；
- 保持 package id、case id、参数键、`am start` 协议、步骤身份和安装入口不变。

验收：

- 相关 Android 单元/静态检查通过；
- `mobile/android/gradlew.bat -p mobile/android :app:assembleDebug` 通过；
- 平台签名流程仍只生成一个 `dist/` 产品 APK；
- 桌面到 APK 的既有集成测试通过；没有硬件时明确记录未执行的 DUT 验证。

### 10.3 阶段三：迁移桌面客户端

范围：

- 将根入口和 `ui/` 迁入 `client/`；
- 更新 QML、QRC、翻译、Bridge 注册、资源、开发启动和桌面打包路径；
- 暂时继续调用尚未移动的 `testing/`，不在本阶段重构业务边界。

验收：

- UI/Bridge/翻译聚焦测试通过；
- QRC 生成资源与源文件一致；
- 从仓库根目录通过新入口启动客户端；
- pytest discovery、运行、报告和 Android 调用行为不变；
- 未重建桌面包时，不声称安装包包含本阶段改动。

### 10.4 阶段四：迁移共享核心

范围：

- 将 `testing/` 迁入 `core/testing/`；
- 根据实际 owner 将 `tools/`、`tool/`、`jira/` 和 `config/` 中的核心业务迁入 `core/`；
- 修复客户端、pytest 子进程、运行时环境、报告、资源、脚本和打包导入；
- 清理 `core` 对 UI 的现有反向依赖：相关持久化或配置通过明确契约访问，不复制参数状态；
- 迁移期兼容入口须在本阶段结束前删除，除非文档记录了明确的后续删除阶段并获得 Coco 批准。

验收：

- `core/` 不导入 `client/`、`web/` 或 `mobile/`；
- pytest discovery、runner、runtime、params、steps、报告和关键 UI Bridge 测试通过；
- 客户端通过唯一 `core` owner 完成选择、运行、取消、事件和报告闭环；
- 不存在重复参数存储、运行传输、步骤模型、日志或报告实现；
- 针对核心模块的 compile/import 检查和桌面源码启动检查通过。

### 10.5 阶段五：迁入旧 Web 前端

范围：

- 将旧仓库 CoreUI 前端源码迁入 `web/frontend/`；
- 保留可复用的布局、导航、组件和品牌资源；
- 隔离旧 Wi-Fi 业务页面，不把旧接口、数据库结构或服务端假设当作新 SmartTest 契约；
- 建立独立安装、开发热更新、构建和静态检查入口。

验收：

- Web 前端可以独立安装、启动和构建；
- 迁入产物许可证和第三方依赖声明完整；
- 无历史构建产物、凭据、数据库备份或无关 Wi-Fi 业务进入产品构建；
- 此阶段不直接调用 `core/`，也不伪造尚未实现的 SmartTest API。

### 10.6 阶段六：迁入旧 Web 服务端并建立新后端

范围：

- 将旧 `server/` 放入 `web/legacy/` 隔离审查；
- 在 `web/backend/` 建立新 Web 后端入口和基础健康检查；
- 选择首个已批准的 SmartTest 业务闭环，定义 API/事件契约并调用 `core/`；
- 每完成一个模块的适配，删除对应 legacy 业务实现。

验收：

- `web/frontend -> web/backend -> core` 是唯一 Web 业务调用方向；
- Web 后端不复制 pytest、参数、DUT、步骤、日志或报告逻辑；
- API 契约、错误响应和实时事件具有聚焦测试；
- 首个业务闭环的前后端联调通过；
- 未适配的 legacy 模块不会进入新运行路径或生产构建。

### 10.7 阶段七：统一开发入口与 CI

范围：

- 完成 `start-client.ps1`、`start-web.ps1`、`start-mobile.ps1` 和必要的一键联调入口；
- 根据变更目录路由客户端、核心、Web 和 Android 检查；
- 增加跨层契约和关键端到端验证，不建立第二套测试执行机制。

验收：

- 各端可独立开发和验证，联调入口能够明确报告每个进程的地址与失败原因；
- CI 能在相关目录变化时运行对应检查，并覆盖共享契约变化的消费者；
- Windows 主机上的 ADB、串口、USB 和实验室设备访问不因开发编排被强制容器化；
- 开发文档与实际命令一致。

### 10.8 每阶段交付门禁

每阶段均执行以下门禁：

1. 开始前记录相关 `git status`，保留全部用户已有修改；
2. Mason 负责目标代码调查、实现、清理和自测，Atlas 负责范围与最终 diff 验收；
3. 先报告复用决策，再引入新 owner 或依赖；
4. 执行该阶段聚焦测试和最高可行的环境验证，不削弱测试；
5. 清理兼容残留、临时诊断、废弃尝试、重复实现和无关生成物；
6. Atlas 检查 `git diff --stat`、scoped diff、测试证据和 `git diff --check`；
7. Coco 确认功能完整后，才执行代码清理、最终验证和原子提交；
8. 未经 Coco 明确批准，不进入下一阶段、不扩大产品能力、不执行合并或推送。
