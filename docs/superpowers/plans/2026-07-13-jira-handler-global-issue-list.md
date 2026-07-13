# Jira 全局问题列表实施计划

## 修改文件

- `jira_handler.py`
- `testing/self_tests/jira/test_jira_handler.py`

## 实施步骤

### 1. 增加脚本配置

在 `jira_handler.py` 顶部增加 `JIRA_CONFIG`，用于填写账户、密码、JQL、网页链接、Issue Key 列表和报告路径。

### 2. 统一解析查询来源

支持以下输入：

- Issue Key 列表
- 单个 `/browse/KEY-123` 链接
- 带 JQL 的搜索链接
- 带 `filter` 的过滤器链接
- 直接填写 JQL

### 3. 建立全局 Issue 列表

增加全局 `ISSUE_LIST`。查询完成后原地更新该列表，格式审计和后续业务都使用它，不再各自请求 Jira。

### 4. 改为直接运行

执行：

```powershell
python .\jira_handler.py
```

脚本读取顶部配置，查询 Jira，执行格式审计并生成 Excel 报告。

### 5. 自测

验证以下内容：

- 各类查询来源解析正确。
- Jira 只查询一次。
- 全局列表被所有业务共用。
- 密码不会输出。
- 原有格式校验和 Excel 报告功能正常。
- Python 编译和代码格式检查通过。
