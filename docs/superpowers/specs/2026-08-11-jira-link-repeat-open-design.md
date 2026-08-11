# Jira 链接重复打开修复设计

## 目标

Redmine 详情中的 Jira 号每被用户点击一次，都向系统浏览器发起一次对应 URL 的打开请求。用户关闭浏览器页面后，再次点击仍可正常跳转。

## 根因

`RedmineBridge.openWebUrl()` 使用 `_opened_urls` 永久缓存已打开 URL。SmartTest 无法接收外部浏览器标签页关闭事件，因此缓存不会失效，后续点击同一 Jira URL 会被直接拦截。

## 设计

- 保留现有 QML 点击链路与 `RedmineBridge.openWebUrl(url)` 接口。
- 删除 Bridge 中 `_opened_urls` 状态及相同 URL 的提前返回逻辑。
- 保留空 URL 校验；每次有效用户请求都调用 `QDesktopServices.openUrl(QUrl(clean_url))`。
- 外部浏览器页面生命周期由系统浏览器管理，SmartTest 不维护不可校准的镜像状态。
- 不增加防双击冷却时间，不修改 Clone 单滚动条、项目列表或 Redmine 标题回写逻辑。

## 验收与执行清单

- [x] 先将现有“一次性打开”测试改为：同一 URL 连续请求两次，`QDesktopServices.openUrl` 收到两次调用。
- [x] 在旧实现上运行该测试并确认因第二次调用被拦截而失败。
- [x] 删除永久 URL 缓存与提前返回分支。
- [x] 运行聚焦 Bridge 测试、UI owner 测试及 Python 编译检查。
- [x] 检查 scoped diff、冗余代码、临时诊断和 `git diff --check`。

## 验收标准

1. 同一个 Jira 号连续点击任意次数，均产生相同次数的系统打开请求。
2. 空 URL 仍不会触发系统打开请求。
3. QML 路由和其他 Redmine Clone 行为保持不变。
