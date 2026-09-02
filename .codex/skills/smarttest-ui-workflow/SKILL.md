---
name: smarttest-ui-workflow
description: Use when changing SmartTest client/app/ui/, QML/FluentUI pages, Python bridge view models, frontend text, UI persistence, QRC resources, Test/Run/Report presentation, or diagnosing source/package UI behavior.
---

# SmartTest UI Workflow

## Ownership

- QML under `client/app/ui/example/imports/example/qml/` owns layout, interaction, and presentational state only.
- Bridges under `client/app/ui/example/bridge/`, registered from `client/app/ui/example/main.py`, own narrow signals/slots and business-facing view models: ordering, grouping, selection mappings, parameter applicability, and Test-page relationships.
- QML never imports `core/testing/`; bridges are the boundary. Do not move pytest/runner logic into bridges.
- Prefer existing FluentUI controls, styles, effects, and nearby patterns. Inspect them before introducing a visible pattern; alternative UI libraries require Coco's approval.

## State And Dynamic Options

- Persist user-visible selections unless explicitly transient. Frontend display preferences use `FrontendStateStore`; bridge-owned business state keeps its existing owner.
- User-configured test parameters have one source of truth: `%LOCALAPPDATA%\Amlogic\SmartTest\test_page_state.json` through `core/config/jsonTool.py`. Bridges may keep short render/edit mirrors; cross-layer calls pass identities such as nodeid/source/DUT, not parameter values.
- Render cached selectable data first, then refresh external data asynchronously.
- DUT refresh uses contracts in `core/testing/params/contracts.py` and `core/testing/tool/dut_tool/parameter_helper.py`. The bridge derives needed parameter/env sources from selected cases; do not hard-code case/field refresh paths.
- Declare dependencies between dynamic sources in schema. Refresh a dependent source for its nodeid only after upstream state is persisted; include nodeid in parameter-dependent cache identity.
- Refreshed scalar/path facts may replace stale persisted values. Multi-select refresh updates candidates only; user selection owns the persisted run value.
- Render normal numeric/equipment inputs as text boxes unless incremental controls are requested. Use compact bounded inputs for short values and full width for paths/long/multiline values.

### SmartTest 登录与凭据生命周期

- 首次验证账户时才访问 LDAP。验证成功后，凭据由运行机器的平台安全存储按账户持久化：Windows 使用 Windows Credential Manager，Linux/Ubuntu 使用项目既有加密存储；不得按 Web session、Cookie 或页面复制凭据。
- 后续 Client/Web 启动、Web 服务重启或 session 过期时，直接用已保存的账户凭据恢复或新建 session，不重复 LDAP。Client 与 Web 遵循同一业务规则，但各自的平台凭据 owner 独立。
- logout、session expiry、revoke 和普通 HTTP 401 只结束 session，不删除账户凭据。网络、超时、服务不可用或 LDAP 不可达也不得推断凭据失效。
- 只有 Jira、Confluence 等下游明确返回 `invalid_credentials` 时，唯一凭据失效入口才可删除该账户凭据、使该账户所有 session 失效，并要求重新 LDAP；没有明确分类时必须保留凭据并如实报告错误。
- 密码不得暴露给 QML，也不得进入日志、SQLite 明文、报告或前端状态；Python 业务统一从认证 owner 获取进程内凭据。

### 前端显示状态持久化

- 新增普通用户可编辑控件时，页面使用 `PersistentPage`，控件默认使用对应的 `Persist*` 包装并声明稳定 `objectName`；明确不需要恢复的临时输入必须声明 `persistEnabled: false`。
- 同一组紧密关联的页面筛选使用一个 `PersistGroup` schema 和一个稳定 `stateKey`，不要为每个字段复制注册、恢复、保存或 ready 生命周期。
- 只保存前端显示偏好。测试参数、认证、密码、API Key、Token、临时凭据、运行进度、服务端结果、日志和报告继续由原业务 owner 管理；禁止建立第二套状态。
- 敏感值不得进入 `FrontendStateStore`。密码式输入必须保持敏感标记，聚合 object 中也不得包含敏感字段。
- 页面不得重新引入 `SettingsHelper.save/get`、`persistReady/persistValue` 或同类手写兼容流；登录账号切换、类型回退、恢复零回写和缺少稳定身份由公共组件处理。

## Text, Theme, And Resources

- Fixed frontend text lives only in `client/app/ui/example/example_en_US.ts` and `client/app/ui/example/example_zh_CN.ts`; both languages change together. QML uses `qsTr(...)`; QObject bridges use `self.tr(...)`.
- `core/testing/` exposes machine keys/types/defaults/scopes/options/results, never frontend labels, descriptions, hints, titles, locale strings, bilingual dictionaries, or fallback maps.
- Bridge display fields mark sources explicitly (`label_source`, `description_source`, `title_source`, `value_source`, or `enum_values_source`) as fixed or dynamic. QML renders bridge text as already localized.
- Keep external/system/user text raw: pytest/adb logs, paths, serials, Jira content, package/case ids, versions, user input, and fetched option values.
- Fixed text has no fallback. Treat missing entries, `unfinished`, mojibake, `?`, `??`, and `???` as failures; do not assemble sentences from translated fragments.
- Prefer `FluTheme` semantic colors. Every custom theme-sensitive color must define and select explicit light/dark values.
- Rebuild the applicable `resource_rc.py` after QRC-backed changes and validate the runtime resource/translation chain.

```powershell
.\.venv\Scripts\pyside6-rcc.exe client\app\ui\example\imports\resource.qrc -o client\app\ui\example\imports\resource_rc.py
```

Rebuild the FluentUI QRC too when `client/app/ui/FluentUI/imports/resource.qrc` changes.

## Test, Run, And Report Presentation

- Test tree, selected rows, selected parameters, and case-type rows come from bridge/controller models. QML retains only filter, expansion, focus, and drag visuals.
- Run and Report consume one bridge-owned `list[dict]` step model. QML renders rows/status only; runtime updates update declared rows and never remove planned rows or create APK-derived replacements.
- Repeated cases show one visible cycle window. At a new cycle, refresh the entire group title to current `x/x` immediately while preserving per-row `planned/running/passed` state.
- `ReportBridge.py` owns report rows, URLs, folder opening, and PDF export. QML never parses report JSON, infers case/step relations, rebuilds summaries, scrapes HTML/PDF, or creates report-only step/log models.
- Run Logs, Report Logs, and step logs reuse one log-list component. Rows use text color plus a narrow left accent; default row background stays transparent.

## Validation

1. Run focused bridge/QML/translation tests; for owned text use `core/testing/self_tests/ui/test_owned_ui_translations.py`.
2. Confirm generated resources are newer than changed QML/resources.
3. Validate source startup from repository root with `.\.venv\Scripts\python.exe client\app\main.py` or a bounded startup/log check.
4. State whether validation used source or package. Never imply `SmartTest.exe` contains source edits without rebuilding it.

Source validation is normal during development. Rebuild desktop packages only when requested, preparing a release, or targeting packaged-runtime behavior; packaged behavior remains the product target.

`core/release/version.json` is the only product-version owner. Package builds consume its `MAJOR.MINOR.PATCH` value through `core/devtools/scripts/build_manifest.py` without changing it. Keep `build/generated/build_manifest.json` and `build/generated/installer_version.iss` consistent through that manifest/include chain; never bypass it.

## Quality Check

Move grouping/sorting/business relationships out of QML; move pytest details out of bridges; replace page-local stores with existing owners; replace blocking external page-load calls with cache-first async refresh; reject duplicate step/log models.
