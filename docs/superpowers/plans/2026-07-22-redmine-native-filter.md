# Redmine Native Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 SmartTest 的 Redmine 列表过滤重构为 Redmine 原生查询，并增加 Subject、全文搜索、“我关注的”和 Jira Channel 二级默认 None。

**Architecture:** 新增纯 Python 原生查询契约作为唯一参数构造者；collector 执行查询分支、分页和按 Issue ID 合并，Bridge 只管理查询意图与异步视图。view model 不再重复业务过滤，账号 context JSON 继续作为缓存和关注 ID 的唯一持久化载体。

**Tech Stack:** Python 3、PySide6、Playwright、QML/FluentUI、pytest、Redmine 原生 Issue Query。

## Global Constraints

- 查询开始时继续展示缓存，只有匹配代次的成功结果可原子替换可见视图。
- 项目、状态、类型、Subject 和全文语义由 Redmine 原生查询负责。
- `60371 播放失败` 的结果是精确 Issue ID 分支与全文任一关键词分支的并集。
- “我关注的”按 LDAP 账号隔离，存入现有 context JSON，不创建独立静态文件。
- 未更新和 Clone 检测只对 Redmine 返回的候选 Issue 执行。
- 不提交、不打包，直到 Coco 完成功能验收。

---

### Task 1: Redmine 原生查询契约

**Files:**
- Create: `tool/SmartHome/redmine/query.py`
- Create: `testing/self_tests/tool/smarthome/redmine/test_query.py`

**Interfaces:**
- Produces: `parse_terms(text: str) -> tuple[str, ...]`
- Produces: `RedmineQuery(project: str, status: str, tracker: str, subject: str, text: str, issue_ids: tuple[str, ...])`
- Produces: `RedmineQuery.branches() -> tuple[RedmineQueryBranch, ...]`
- Produces: `RedmineQueryBranch.params(page: int, per_page: int) -> list[tuple[str, str]]`

- [ ] **Step 1: Write failing parsing and parameter tests**

```python
def test_text_query_builds_native_fulltext_and_numeric_id_union():
    query = RedmineQuery(status="open", subject="Highlight", text="60371 播放失败")
    branches = query.branches()
    assert [branch.kind for branch in branches] == ["fulltext", "issue_ids"]
    assert ("op[any_searchable]", "*~") in branches[0].params(1, 100)
    assert ("v[issue_id][]", "60371") in branches[1].params(1, 100)

def test_empty_subject_is_not_sent():
    params = RedmineQuery(subject="").branches()[0].params(1, 100)
    assert not any(key == "v[subject][]" for key, _ in params)
```

- [ ] **Step 2: Run `python -m pytest testing/self_tests/tool/smarthome/redmine/test_query.py -q` and verify RED because the module is absent.**
- [ ] **Step 3: Implement immutable query/branch types with native mappings `status_id`, `tracker_id`, `subject/~`, `any_searchable/*~`, `issue_id/=`. Preserve duplicate keys as an ordered tuple/list, and append `f[]`, `set_filter=1`, `sort=id:desc`, `page`, `per_page`.**
- [ ] **Step 4: Run the same command and verify PASS.**

### Task 2: Collector 原生执行、分页和结果合并

**Files:**
- Modify: `tool/SmartHome/redmine/collector.py`
- Modify: `testing/self_tests/tool/smarthome/redmine/test_context_collector.py`

**Interfaces:**
- Consumes: `RedmineQuery.branches()` and `RedmineQueryBranch.params()`
- Produces: `RedmineContextCollector.collect_query(query: RedmineQuery) -> RedmineContext`

- [ ] **Step 1: Write failing tests proving all branches execute, each branch paginates, and duplicate Issue IDs merge once in descending ID order.**
- [ ] **Step 2: Run `python -m pytest testing/self_tests/tool/smarthome/redmine/test_context_collector.py -q`; expect failure because `collect_query` is absent.**
- [ ] **Step 3: Implement one URL builder and page parser. Project scope uses `/projects/{identifier}/issues`; all-project scope uses `/issues`. Execute branches, follow pagination, merge by Issue ID, and retain row project identity.**
- [ ] **Step 4: Route ordinary and watched-ID searches through `collect_query`; delete duplicate `set_filter`, status and pagination string construction after callers migrate.**
- [ ] **Step 5: Run query and collector tests; expect PASS.**

### Task 3: Bridge、缓存和 Redmine QML

**Files:**
- Modify: `ui/example/bridge/RedmineBridge.py`
- Modify: `tool/SmartHome/redmine/context_store.py`
- Modify: `tool/SmartHome/redmine/view_model.py`
- Modify: `ui/example/imports/example/qml/component/issue/JiraIssueBrowserLayout.qml`
- Modify: `ui/example/imports/example/qml/component/redmine/RedmineWorkspace.qml`
- Modify: `ui/example/example_en_US.ts`
- Modify: `ui/example/example_zh_CN.ts`
- Modify: `testing/self_tests/ui/test_redmine_bridge.py`
- Modify: `testing/self_tests/ui/test_redmine_context_store.py`
- Modify: `testing/self_tests/ui/test_tool_page.py`

**Interfaces:**
- Consumes: `RedmineContextCollector.collect_query(RedmineQuery)`
- Produces filter keys: `project`, `status`, `type`, `subject`, `text`
- Produces quick view id: `watched`
- Produces slots/properties: `saveWatchedIssueIds(str)`, `watchedIssueText`, `watchedIssueError`

- [ ] **Step 1: Write failing tests for optional visible Subject, native query creation, watched ID account isolation, valid/invalid feedback, clearing, and cache-first refresh.**
- [ ] **Step 2: Run Bridge/context/QML tests and verify RED on missing contracts.**
- [ ] **Step 3: Translate QML values once in `applyFilters`; never construct URLs in Bridge. Keep cached `_view` during loading/cancel/failure and apply returned context once in `_apply_data`.**
- [ ] **Step 4: Persist `watchedIssueIds: list[str]` through the atomic context-store update owner. Query submitted IDs through the same collector, save valid IDs, report invalid IDs together, and preserve the old list if all submitted IDs are invalid.**
- [ ] **Step 5: Add always-visible optional Subject and a Watched-only ID editor with the agreed separators and explicit confirmation. Do not add row-level actions.**
- [ ] **Step 6: Delete project/status/type/text/subject business matching from `view_model._match()` and its callers; retain monitoring eligibility and display projection only.**
- [ ] **Step 7: Rebuild QRC, run Bridge/context/QML/translation tests, and verify PASS without warnings.**

### Task 4: Jira Channel None 与最终清理

**Files:**
- Modify: `support/jira_integration/services/create_schema_service.py`
- Modify: `ui/example/imports/example/qml/component/issue/JiraCreateField.qml`
- Modify: `testing/self_tests/support/test_jira_create_schema_service.py`
- Modify: `testing/self_tests/ui/test_redmine_clone_create_ui.py`

**Interfaces:**
- Produces Channel child empty option: `{value: "", label: "None"}`

- [ ] **Step 1: Write failing test asserting Customer-Feedback defaults to `[parent_id, ""]`, the empty child label is `None`, and payload never serializes the label.**
- [ ] **Step 2: Run schema/QML tests and verify RED.**
- [ ] **Step 3: Expose and select the empty child option while preserving an empty submitted value.**
- [ ] **Step 4: Scan for legacy `_match`, duplicated URL fragments, diagnostics and unused query helpers; remove only owners replaced by this plan.**
- [ ] **Step 5: Run complete directed Redmine/QML/Jira schema tests, `py_compile`, QRC rebuild, and `git diff --check`; expect all exit 0.**

## Validation Commands

```powershell
python -m pytest testing/self_tests/tool/smarthome/redmine testing/self_tests/ui/test_redmine_bridge.py testing/self_tests/ui/test_redmine_context_store.py testing/self_tests/ui/test_redmine_clone_create_ui.py testing/self_tests/ui/test_tool_page.py testing/self_tests/support/test_jira_create_schema_service.py -q
python -m py_compile tool/SmartHome/redmine/query.py tool/SmartHome/redmine/collector.py tool/SmartHome/redmine/context_store.py ui/example/bridge/RedmineBridge.py
.\.venv\Scripts\pyside6-rcc.exe ui\example\imports\resource.qrc -o ui\example\imports\resource_rc.py
git diff --check
```
