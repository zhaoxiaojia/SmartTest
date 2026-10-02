# A9 Yocto 工作台日报设计与执行清单

## 目标

提供一份可直接粘贴到工作台运行的独立 Python 工作流脚本。脚本复用工作台的 `jira_search_issues` 与 `email_send_html` 接口，迁移 SmartTest 当前 A9 Yocto 的 Jira 过滤、14 天趋势、确定性分析和 HTML 日报格式，并由当前工作台用户自己的邮箱发送。

## 范围

- 仅实现首个试点项目 A9 Yocto；其他三个项目待真实工作台验证通过后再生成。
- 工作流配置界面提供 `project_name`、`project_label`、`jql`、`recipients`、`cc`、`subject`、`detail_priorities`、`trend_days`、`stale_days` 和 `send_email`。
- 默认值分别为 `A9 Yocto`、`Linux-A9_Yocto`、`status not in (Closed, Done, Verified) AND labels = Linux-A9_Yocto`、`chao.li@amlogic.com`、空、`[A9 Yocto] 公版状态日报`、`P0,P1`、`14`、`7` 和 `false`；所有值均可在工作流配置界面覆盖。
- 不生成或发送 Excel，不使用 SMTP，不包含邮箱/Jira密码或 Token，不依赖 SmartTest 本地模块或第三方 Python 包。
- 生成的单文件 HTML 作为工作流产物保留；仅当 `send_email=true` 时调用 `email_send_html`。

## 结构与数据流

生产代码放在 `tool/common/daily_report/workflows/a9_yocto_workbench.py`，保持一个可复制的自包含工作流文件；测试放在 `testing/self_tests/tool/test_a9_yocto_workbench.py`，通过 fake `wf` 运行真实 `main(wf)`。

工作流读取并校验参数，先用配置的 JQL 查询当前 Issue，再用 `status WAS NOT IN (Closed, Done, Verified) ON "YYYY-MM-DD" AND labels = <project_label>` 查询前 N-1 天历史数据。当前查询失败时终止；单日历史查询失败时记录缺失点并继续。脚本规范化 Jira 返回结构，计算今日创建/更新、P0/P1、停滞、状态构成、模块 Top 5、趋势与 P0/P1 明细，使用邮件兼容的内联 HTML/CSS 输出，不引用本地图片。

## 异常与安全

- 必填字符串、邮箱列表、优先级列表和数值范围在调用外部工具前校验。
- 当前 Jira 查询失败不生成或发送不完整日报。
- 邮件发送失败时保留已经发布的 HTML 产物并向工作台抛出失败。
- 日志只记录数量和阶段，不输出完整收件人列表、完整 Jira 数据或敏感凭据。
- `send_email=false` 是安全默认值。

## 验收标准

- 默认配置查询 A9 Yocto，产物包含 SmartTest 当前主要指标、分布、14 天趋势和 P0/P1 明细。
- 所有业务输入来自 `wf.input`，默认收件人仅为 `chao.li@amlogic.com`，无默认抄送。
- `send_email=false` 时不调用邮件工具；为 true 时只调用 `email_send_html`，参数包含 recipients、subject、file_path、add_footer=False，以及有值时的 cc_addresses。
- 代码可在无 SmartTest 模块和无第三方包的 Python 环境导入和执行。
- 当前查询失败、历史部分失败、空数据、字段变体和参数非法均有行为测试。

## TDD 执行清单

- [ ] 先建立 fake `wf` 行为测试，覆盖参数读取、当前/历史 JQL、HTML 产物以及默认不发信；运行并确认因生产脚本不存在而失败。
- [ ] 实现最小自包含工作流，使基础路径测试通过。
- [ ] 增加字段规范化、指标、P0/P1 明细和历史缺失测试；逐项确认 RED 后实现 GREEN。
- [ ] 增加输入校验和邮件开关/抄送参数测试；逐项确认 RED 后实现 GREEN。
- [ ] 清理重复逻辑和临时诊断，运行聚焦 pytest、`compileall`、脚本无本地依赖检查与 `git diff --check`。
- [ ] Atlas 按 scoped diff、测试证据和代码增长审查功能与质量。
