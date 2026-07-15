# QA 人员名单与 Jira 过滤设计

## 目标

- SmartTest 保存一份可扩展的全局人员资料。
- 独立 `jira_handler.py` 内置同一份 QA 名单，不依赖外部文件。
- Jira 审核只处理 Reporter 属于 QA 名单的 Issue。

## 数据位置

全局资料放在 `config/personnel.json`。每个人包含：

- `username`：Jira 账户名
- `role`：当前统一为 `QA`
- `title`：职位，当前留空
- `product_lines`：产品线，当前为空列表
- `active`：是否启用

`jira_handler.py` 内置 QA 用户名集合。两处名单必须保持一致。

## 过滤规则

查询 Jira 后，根据 Reporter 的 `name`、`key` 或 `accountId` 识别账户名。只有启用的 QA 人员创建的 Jira 才进入格式审核、汇总和违规明细。无法识别或不在名单中的 Reporter 直接忽略。
