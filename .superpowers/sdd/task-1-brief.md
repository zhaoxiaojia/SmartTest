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
