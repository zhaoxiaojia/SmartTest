# Redmine 批量 Clone 到 Jira 创建页面实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Redmine Issue 列表中批量选择未 Clone 问题，通过 Jira API Schema 渲染可统一编辑、校验和提交的 Jira Create QML。

**Architecture:** Redmine 只拥有选择和可靠初始值；新增 `JiraCreateSchemaService` 将 Jira create metadata 转为稳定字段 Schema；`RedmineCloneDraftService` 组合 Redmine 详情、人员配置和 Schema；`RedmineBridge` 管理批次状态与异步提交；新 QML 只渲染 Schema 和编辑草稿。现有 `CreateIssueService` 继续唯一负责重复检查与 Jira 创建 payload。

**Tech Stack:** Python 3、PySide6/QML、FluentUI、现有 `JiraClient`/`CreateIssueService`、pytest、Qt resource/TS。

## 全局约束

- Jira Project 固定为 `SH`，Redmine 不定义 Jira 控件和候选项。
- 所有 Jira 控件类型、必填状态和候选项来自 `SH + Issue Type` 的 Jira API 元数据。
- 工具预填值全部允许用户修改；无法可靠映射的字段保持空值。
- 只有用户完成全部草稿审阅并点击一次“批量创建”后才允许发送创建请求。
- 部门只使用 `FAE-QA`、`FAE-SW`、`FAE-HW`；只有 `FAE-SW` 自动填写当前用户为 FAE Coworker。
- 固定人员 Fred Chen 使用 Jira/LDAP 账号 `fred.chen`，职级 `M5`，为 SmartHome 产品线负责人。
- QML 不拼装 Jira JSON，不写死下拉候选项，不直接访问 Jira/Redmine 服务。
- 固定前端文本同步维护中英文 TS，并重建 QRC。

---

### Task 1: 人员部门与 Fred Chen 配置

**Files:**
- Modify: `config/personnel.json`
- Modify: `ui/example/bridge/ToolBridge.py`
- Modify: `testing/self_tests/ui/test_tool_page.py`
- Modify: `testing/self_tests/ui/test_auth_bridge_profile.py`

**Interfaces:**
- Produces: `employee_department(personnel: dict, account: str) -> str` 返回标准部门；配置中 `fred.chen` 可由 LDAP/Jira 账号唯一定位。

- [ ] **Step 1: 写失败测试**

```python
def test_personnel_uses_three_explicit_fae_departments_and_fred_owns_smarthome():
    personnel = load_tool_access(PERSONNEL_PATH)
    assert set(personnel["amlogic"]["departments"]) == {"FAE-QA", "FAE-SW", "FAE-HW"}
    fred = next(item for item in amlogic_employees(personnel) if item["account"] == "fred.chen")
    assert fred["grade"] == "M5"
    assert fred["organization"]["department"] == "FAE-SW"
    assert any(item["product_line_id"] == "SmartHome" and item["primary"] for item in fred["assignments"])
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/ui/test_tool_page.py -q -k "three_explicit_fae_departments"`

Expected: FAIL，现有部门仍包含 `FAE`，且没有 `fred.chen`。

- [ ] **Step 3: 最小实现**

将 `config/personnel.json` 的 `FAE` 节点改名为 `FAE-SW`，保留原人员和 assignments；新增 `fred.chen`，并让所有部门读取逻辑只依赖配置节点名，不维护旧名称 fallback。

- [ ] **Step 4: 运行人员与权限回归**

Run: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/ui/test_tool_page.py testing/self_tests/ui/test_auth_bridge_profile.py -q`

Expected: PASS，且未知 LDAP 用户仍只有 common 权限。

- [ ] **Step 5: 提交**

```powershell
git add config/personnel.json ui/example/bridge/ToolBridge.py testing/self_tests/ui/test_tool_page.py testing/self_tests/ui/test_auth_bridge_profile.py
git commit -m "feat: define SmartHome FAE software ownership"
```

### Task 2: Jira Create Metadata 与字段 Schema

**Files:**
- Modify: `support/jira_integration/transport/client.py`
- Create: `support/jira_integration/core/create_schema.py`
- Create: `support/jira_integration/services/create_schema_service.py`
- Modify: `support/jira_integration/services/__init__.py`
- Create: `testing/self_tests/support/test_jira_create_schema_service.py`

**Interfaces:**
- Produces: `JiraClient.fetch_create_metadata(project_key: str, issue_type: str) -> dict[str, Any]`。
- Produces: `JiraClient.search_users(query: str) -> list[dict[str, Any]]`。
- Produces: `CreateFieldSchema(field_id, name, required, control, options, value, children)` 和 `JiraCreateSchemaService.schema(project_key, issue_type)`。
- Control 枚举固定为 `text`、`multiline`、`single`、`multi`、`cascade`、`user`。

- [ ] **Step 1: 写 transport 失败测试**

```python
def test_fetch_create_metadata_scopes_project_and_issue_type(fake_client):
    payload = fake_client.fetch_create_metadata("SH", "Bug")
    assert fake_client.last_path.endswith("issue/createmeta")
    assert fake_client.last_params == {"projectKeys": "SH", "issuetypeNames": "Bug", "expand": "projects.issuetypes.fields"}
    assert payload["projects"][0]["key"] == "SH"
```

- [ ] **Step 2: 写 Schema 转换失败测试**

```python
def test_schema_maps_jira_native_controls_and_required_state():
    service = JiraCreateSchemaService(FakeClient(CREATE_META))
    fields = {item.field_id: item for item in service.schema("SH", "Bug")}
    assert fields["summary"].control == "text" and fields["summary"].required
    assert fields["description"].control == "multiline"
    assert fields["customfield_12200"].control == "cascade"
    assert fields["components"].control == "multi"
    assert fields["customfield_10700"].control == "user"
```

- [ ] **Step 3: 运行并确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_jira_create_schema_service.py -q`

Expected: FAIL，接口和 Schema 类型尚不存在。

- [ ] **Step 4: 实现 API 与转换**

`fetch_create_metadata` 请求 `/rest/api/2/issue/createmeta`，传入 `projectKeys`、`issuetypeNames` 和 `expand=projects.issuetypes.fields`；Schema Service 从 `fields` 的 `required`、`schema.type/items/custom`、`allowedValues` 和字段名称生成稳定 Schema。人员字段通过字段 schema custom 或确认名称识别为 `user`，不能在 QML 判断 custom field ID。

- [ ] **Step 5: 实现人员搜索**

`search_users(query)` 请求 `/rest/api/2/user/assignable/search?project=SH&username=<query>`，返回 `{account, display_name, avatar_url}`；调用方必须校验 `fred.chen` 唯一匹配。

- [ ] **Step 6: 运行 Schema 和 Jira transport 回归**

Run: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_jira_create_schema_service.py testing/self_tests/support/test_browser_automation.py -q`

Expected: PASS。

- [ ] **Step 7: 提交**

```powershell
git add support/jira_integration testing/self_tests/support/test_jira_create_schema_service.py
git commit -m "feat: expose Jira create field schema"
```

### Task 3: Redmine Clone 草稿映射与创建请求

**Files:**
- Create: `tool/SmartHome/redmine/clone_draft.py`
- Modify: `tool/SmartHome/redmine/create.py`
- Modify: `support/jira_integration/core/models.py`
- Modify: `support/jira_integration/services/create_issue_service.py`
- Create: `testing/self_tests/tool/smarthome/redmine/test_clone_draft.py`
- Modify: `testing/self_tests/tool/smarthome/redmine/test_auth.py`

**Interfaces:**
- Produces: `RedmineCloneDraftService.build(issue, project, schema, account, department) -> CloneDraft`。
- Produces: `CloneDraft.to_request() -> CreateIssueRequest`，其中 `extra_fields` 只包含用户确认后的 Jira 字段值。
- Consumes: Task 2 的 `CreateFieldSchema`。

- [ ] **Step 1: 写初始值失败测试**

```python
def test_clone_draft_prefills_only_confirmed_mappings():
    draft = service.build(issue=REDMINE_BUG, project=PROJECT, schema=SCHEMA, account="defeng.zhai", department="FAE-SW")
    assert draft.value("project") == "SH"
    assert draft.value("issuetype") == "Bug"
    assert draft.value("priority") == "P2"
    assert draft.value("customfield_12200") == {"parent": "Customer-Feedback", "child": "None"}
    assert draft.value("customfield_10109") == "Major"
    assert draft.value("customfield_10107") == ["BDS Reference"]
    assert draft.value("components") == ["Customization"]
    assert draft.value("customfield_10407") == ["AN40BF-A311D2"]
    assert draft.value("customfield_10300") == []
    assert draft.value("customfield_10700") == "fred.chen"
    assert draft.value("customfield_10409") == "defeng.zhai"
    assert draft.value("customfield_11002") == "fred.chen"
```

- [ ] **Step 2: 写部门反例和空描述测试**

```python
@pytest.mark.parametrize("department", ["FAE-QA", "FAE-HW", ""])
def test_only_fae_sw_prefills_coworker(department):
    draft = build_draft(service, issue=REDMINE_BUG, project=PROJECT, schema=SCHEMA, account="hardware.user", department=department)
    assert draft.value("customfield_10409") == ""

def test_empty_redmine_description_generates_nonempty_source_description():
    draft = build_draft(service, issue=replace(REDMINE_BUG, description=""), project=PROJECT, schema=SCHEMA, account="qa.user", department="FAE-QA")
    assert "Redmine #61043" in draft.value("description")
    assert REDMINE_BUG.url in draft.value("description")
```

- [ ] **Step 3: 运行并确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/tool/smarthome/redmine/test_clone_draft.py -q`

Expected: FAIL，草稿服务尚不存在。

- [ ] **Step 4: 实现草稿和 request 转换**

映射服务按字段 name/ID 从 Schema 找到目标字段，只有目标选项在 `allowedValues` 中存在时才预填；否则保留空值并记录字段错误。`CreateIssueService._payload()` 继续唯一组装 Jira JSON，并接受单选、多选、级联和人员字段已经标准化的 `extra_fields`。

- [ ] **Step 5: 运行映射与 create service 回归**

Run: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/tool/smarthome/redmine/test_clone_draft.py testing/self_tests/tool/smarthome/redmine/test_auth.py -q`

Expected: PASS。

- [ ] **Step 6: 提交**

```powershell
git add tool/SmartHome/redmine/clone_draft.py tool/SmartHome/redmine/create.py support/jira_integration/core/models.py support/jira_integration/services/create_issue_service.py testing/self_tests/tool/smarthome/redmine
git commit -m "feat: map Redmine issues to editable Jira drafts"
```

### Task 4: RedmineBridge 批次状态与提交编排

**Files:**
- Modify: `ui/example/bridge/RedmineBridge.py`
- Modify: `testing/self_tests/ui/test_redmine_bridge.py`

**Interfaces:**
- Produces QML properties: `cloneSelectionMode: bool`、`cloneSelectedIds: list[str]`、`cloneDrafts: list[dict]`、`cloneBatchState: str`、`cloneBatchLoaded/Total: int`、`cloneBatchError: str`。
- Produces slots: `beginCloneSelection()`、`toggleCloneSelection(issue_id, selected)`、`cancelCloneSelection()`、`prepareCloneDrafts()`、`updateCloneDraft(issue_id, field_id, value)`、`submitCloneBatch()`、`retryFailedClones()`、`closeCloneBatch()`、`searchCloneUsers(issue_id, field_id, query)`。

- [ ] **Step 1: 写选择状态失败测试**

```python
def test_clone_selection_rejects_already_cloned_rows():
    bridge._view = {"issueRows": [{"id": "1", "cloneStatus": "cloned"}, {"id": "2", "cloneStatus": "not_cloned"}]}
    bridge.beginCloneSelection()
    bridge.toggleCloneSelection("1", True)
    bridge.toggleCloneSelection("2", True)
    assert bridge.cloneSelectedIds == ["2"]
```

- [ ] **Step 2: 写统一校验与无提前创建测试**

```python
def test_prepare_only_builds_drafts_and_submit_validates_all_before_create():
    bridge.prepareCloneDrafts()
    assert create_service.calls == []
    bridge.submitCloneBatch()
    assert create_service.calls == []
    assert bridge.cloneDrafts[0]["errors"]["customfield_10300"]
```

- [ ] **Step 3: 写部分失败与重试测试**

```python
def test_batch_continues_after_failure_and_retry_only_sends_failed():
    bridge.submitCloneBatch()
    assert [draft["state"] for draft in bridge.cloneDrafts] == ["created", "failed", "duplicate"]
    bridge.retryFailedClones()
    assert create_service.submitted_ids[-1:] == ["2"]
```

- [ ] **Step 4: 运行并确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/ui/test_redmine_bridge.py -q -k "clone_selection or prepare_only or batch_continues"`

Expected: FAIL，批次属性和 slots 尚不存在。

- [ ] **Step 5: 实现批次状态机**

状态只允许 `idle -> selecting -> loading -> editing -> validating -> submitting -> completed/partial_failed`。准备阶段复用当前已登录 Browser/Jira 服务加载 Redmine 详情和 Schema；提交前重新执行 clone check；账号 generation 改变时清空批次并忽略迟到结果。

- [ ] **Step 6: 运行 Bridge 全回归**

Run: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/ui/test_redmine_bridge.py -q`

Expected: PASS。

- [ ] **Step 7: 提交**

```powershell
git add ui/example/bridge/RedmineBridge.py testing/self_tests/ui/test_redmine_bridge.py
git commit -m "feat: orchestrate Redmine clone batches"
```

### Task 5: Clone 选择 UI 与 Jira Create 批量 QML

**Files:**
- Create: `ui/example/imports/example/qml/component/issue/JiraCreateField.qml`
- Create: `ui/example/imports/example/qml/component/issue/JiraCreateDraftCard.qml`
- Create: `ui/example/imports/example/qml/component/issue/JiraCreateBatchDialog.qml`
- Modify: `ui/example/imports/example/qml/component/issue/JiraIssueBrowserLayout.qml`
- Modify: `ui/example/imports/example/qml/component/redmine/RedmineWorkspace.qml`
- Modify: `ui/example/imports/resource.qrc`
- Modify: `ui/example/example_en_US.ts`
- Modify: `ui/example/example_zh_CN.ts`
- Create: `testing/self_tests/ui/test_redmine_clone_create_ui.py`
- Modify: `testing/self_tests/ui/test_tool_page.py`

**Interfaces:**
- Consumes: Task 4 的 properties 和 slots。
- Produces: 一个选择模式和一个集中批量编辑弹窗；不包含业务 mapping 或 Jira JSON。

- [ ] **Step 1: 写 QML 契约失败测试**

```python
def test_issue_list_clone_mode_and_batch_dialog_contract():
    browser = BROWSER_QML.read_text(encoding="utf-8")
    dialog = BATCH_QML.read_text(encoding="utf-8")
    assert "cloneSelectionMode" in browser and "cloneSelectable" in browser
    assert "modelData.cloneStatus !== \"cloned\"" in browser
    assert "Repeater" in dialog and "cloneDrafts" in dialog
    assert "submitCloneBatch" in dialog and "updateCloneDraft" in dialog
```

- [ ] **Step 2: 写 QML runtime 失败测试**

构造两个草稿（text、single、multi、cascade、user、multiline），加载 `JiraCreateBatchDialog.qml`，断言两张卡片都展开、预填文本可修改、一个 Batch Create 按钮存在、必填错误会聚焦首个字段。

- [ ] **Step 3: 运行并确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/ui/test_redmine_clone_create_ui.py -q`

Expected: FAIL，新 QML 尚不存在。

- [ ] **Step 4: 实现选择模式**

在共享 Issue 行中仅由 Redmine 传入 `cloneSelectionMode` 时显示复选框；已 Clone 行禁用；工具栏 Clone/取消/确认按钮只发 signals，`RedmineWorkspace` 将 signals 连接到 Bridge slots。

- [ ] **Step 5: 实现 Schema 字段渲染**

`JiraCreateField.qml` 按 `control` 选择现有 FluentUI 文本、下拉、多选、级联和人员搜索控件；每次修改都调用 `updateCloneDraft(issueId, fieldId, value)`。所有固定文本使用 `qsTr()`。

- [ ] **Step 6: 实现批量弹窗**

弹窗完整展开所有 `cloneDrafts`，固定底栏提供取消、批量创建和失败项重试；`submitting` 状态禁用关闭和编辑；错误时滚动到 `firstInvalidIssueId/firstInvalidFieldId`。

- [ ] **Step 7: 更新翻译与资源**

Run: `.\.venv\Scripts\pyside6-rcc.exe ui\example\imports\resource.qrc -o ui\example\imports\resource_rc.py`

Expected: exit 0，生成资源时间晚于新增 QML。

- [ ] **Step 8: 运行 UI 与翻译回归**

Run: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/ui/test_redmine_clone_create_ui.py testing/self_tests/ui/test_tool_page.py testing/self_tests/ui/test_owned_ui_translations.py -q`

Expected: PASS。

- [ ] **Step 9: 提交**

```powershell
git add ui/example/imports/example/qml ui/example/imports/resource.qrc ui/example/imports/resource_rc.py ui/example/example_en_US.ts ui/example/example_zh_CN.ts testing/self_tests/ui
git commit -m "feat: add editable Jira clone batch dialog"
```

### Task 6: 集成验收与清理

**Files:**
- Review all files changed by Tasks 1-5.

**Interfaces:**
- 验证从 Redmine 选择到 Jira 创建结果回写的完整契约。

- [ ] **Step 1: 运行完整相关测试**

Run: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_jira_create_schema_service.py testing/self_tests/tool/smarthome/redmine testing/self_tests/ui/test_auth_bridge_profile.py testing/self_tests/ui/test_redmine_bridge.py testing/self_tests/ui/test_redmine_clone_create_ui.py testing/self_tests/ui/test_tool_page.py testing/self_tests/ui/test_owned_ui_translations.py -q`

Expected: 全部 PASS；仅允许已知第三方 deprecation warning。

- [ ] **Step 2: 编译与静态清理**

Run: `.\.venv\Scripts\python.exe -m compileall -q support\jira_integration tool\SmartHome\redmine ui\example\bridge`

Run: `rg -n "print\(|console\.log|TODO|FIXME|projectTree|childProject" support/jira_integration tool/SmartHome/redmine ui/example/bridge ui/example/imports/example/qml/component/issue`

Expected: compile exit 0；新增范围没有临时打印、废弃项目树或占位符。

- [ ] **Step 3: 源码启动检查**

Run: `.\.venv\Scripts\python.exe main.py`

Expected: 应用成功加载登录/主窗口和 Redmine QML，无 QML warning；检查完成后正常关闭。

- [ ] **Step 4: 差异质量检查**

Run: `git diff --check`

Expected: exit 0。确认一个 Schema owner、一个批次状态 owner、一个 Jira payload owner，没有并行创建路径。

- [ ] **Step 5: 最终提交**

如果 Step 2-4 产生了必要的清理修改，仅暂存 `git diff --name-only` 中属于本计划的文件并提交 `test: verify Redmine Jira clone workflow`；如果没有任何清理差异，不创建空提交。

安装包只在 Coco 明确要求打包验证或进入发布交付时构建。
