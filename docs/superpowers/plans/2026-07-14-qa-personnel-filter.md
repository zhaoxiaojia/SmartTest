# QA 人员名单与 Jira 过滤实施计划

## 修改内容

1. 新增 `config/personnel.json`，写入 QA 名单和预留人员字段。
2. 在 `jira_handler.py` 内置相同 QA 用户名集合。
3. 保留 Reporter 的账户名和显示名。
4. 查询完成后先按 QA Reporter 过滤，再执行格式审核。
5. 增加测试，检查两份名单一致、QA Reporter 被审核、非 QA Reporter 被忽略。
6. 使用真实 Jira 配置验证过滤后的 Issue 数量和报告内容。
