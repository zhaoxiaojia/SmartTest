# SmartTest 可复用 Issue 详情布局设计

## 目标

在 SmartTest 中新增一组可复用 QML 组件，尽可能复刻用户提供的 Jira Issue 详情视觉布局。首阶段只实现布局、展示状态、拖放确认和信号合同，不连接 Jira/Redmine REST、LDAP、评论提交或附件上传业务。

组件供 Jira 页面、SmartHome Redmine 页面及未来其他 Tool 页面复用。数据源差异必须在 Bridge/业务适配层转换，QML 不解析 Jira 或 Redmine 原始响应。

## 范围

首阶段包含：

- Issue 头部、项目路径、可点击 Issue Key 和标题；
- Details、People、Dates 等字段分区；
- 只读 Description；
- 单一 Comments 区域，不提供 Activity/All/Work Log/History 页签；
- 评论列表、评论编辑器及提交信号；
- Attachments 区域、附件卡片、文件选择信号；
- 文件/图片拖入详情页后的上传确认弹窗与确认信号；
- 加载、提交、上传、空数据及错误展示状态；
- 明暗主题与中英文固定文案。

首阶段不包含：

- Jira/Redmine 网络请求或字段解析；
- LDAP 或浏览器登录；
- 真正提交评论、上传附件或下载附件；
- 编辑标题、描述、状态、优先级、Assignee、版本、自定义字段；
- 顶部 Edit、Assign、More、Set Due Date、Resolve、Export 等 Jira 操作栏；
- Issue 过滤器和左侧 Issue 列表，它们属于下一阶段 `IssueBrowserView`。

## 组件结构

```text
IssueDetailView.qml
├─ IssueHeader.qml
├─ IssueFieldSection.qml
├─ IssueDescription.qml
├─ IssueComments.qml
└─ IssueAttachments.qml
   └─ IssueAttachmentCard.qml
```

建议放置在：

```text
ui/example/imports/example/qml/component/issue/
```

`IssueDetailView` 是对外入口和滚动容器。子组件不依赖具体页面、Bridge、Jira 包或 Redmine 包。

## 视觉布局

### 整体

- 使用白色/主题背景、细分隔线、紧凑字段间距和 Jira 风格蓝色链接；
- 主内容纵向滚动；
- 宽度变化时保持截图布局比例，不把右侧栏移动到下方；
- 主字段栏约占可用宽度 68%，People/Dates 侧栏约占 32%；
- 文字保持最低可读字号，长标题、字段值和链接允许换行；
- 不使用横向滚动条。

### 头部

- 展示 Issue 类型图标、项目路径、Issue Key 和标题；
- Issue Key 与标题均为可点击链接；
- 点击只发出打开信号，不直接调用浏览器；
- 不显示 Jira 编辑/分配/解决/导出操作栏。

### 字段区

- 左侧 Details 使用标签/值双列布局；
- 右侧 People、Dates 及可选扩展分区使用相同比例与折叠标题；
- 支持标量、链接、标签列表、人员、状态徽标和多行文本展示；
- 外部字段和值保持原文，QML 不翻译动态内容。

### Description

- 只读展示；
- 保留换行、URL 和长路径的换行能力；
- 不提供编辑入口。

### Comments

- 只保留 Comments 标题，不显示 Activity 页签；
- 展示评论人、时间、头像占位和原始评论正文；
- 提供 Comment 按钮及可展开输入区；
- 提交时发出信号；提交中禁用重复提交；失败时保留输入；成功后的清空与新列表由外部状态更新驱动。

### Attachments

- 使用 Jira 风格虚线拖放区域和卡片网格；
- 卡片展示缩略图/文件占位图、文件名、时间和大小；
- 支持点击附件和选择文件信号；
- 文件/图片拖入详情页时，仅收集本地文件 URL 并弹出确认框；
- 用户确认后发出上传确认信号，取消不发出上传信号；
- 不在 QML 内读取文件内容或调用上传接口。

## 数据合同

`IssueDetailView` 接受稳定展示模型：

```qml
property var issue
property var comments: []
property var attachments: []
property bool commentsLoading: false
property bool commentSubmitting: false
property bool attachmentsLoading: false
property bool attachmentUploading: false
property string commentError: ""
property string attachmentError: ""
```

`issue` 至少允许包含：

```text
key, title, webUrl, projectName, projectUrl, typeIcon,
detailsFields, peopleFields, dateFields, extraSections,
description
```

字段数组元素使用稳定展示结构：

```text
label, value, kind, url, values
```

`kind` 只描述展示方式，例如 `text`、`link`、`status`、`tags`、`person`；它不携带 Jira/Redmine 字段 ID 或业务决策。

## 信号合同

```qml
signal openIssueRequested(string issueKey, string webUrl)
signal externalLinkRequested(string url)
signal commentSubmitRequested(string issueKey, string content)
signal attachmentFilesSelected(string issueKey, var fileUrls)
signal attachmentUploadConfirmed(string issueKey, var fileUrls)
signal attachmentOpenRequested(string issueKey, var attachment)
```

打开系统默认浏览器及“同一 SmartTest 运行期间，同一 Issue 只打开一次”的去重策略属于后续 Web 打开服务，不属于详情 QML。

评论与附件业务后续通过 `support/jira_integration` 对接 LDAP/Jira。布局组件不得导入该包。

## 文本规则

- SmartTest 固定文案同时写入 `example_en_US.ts` 和 `example_zh_CN.ts`；
- QML 固定文案使用 `qsTr(...)`；
- Jira/Redmine 评论、字段、人员、错误和附件名等动态外部文本原样显示；
- 不拼接需要翻译的固定句子片段。

## 验收标准

- `IssueDetailView` 可在独立 QML 测试宿主中加载，不需要 Jira/Redmine Bridge；
- 视觉结构与参考截图一致：头部、68/32 字段双栏、Description、Attachments、Comments；
- 不存在 Jira 顶部编辑操作栏和 Activity 页签；
- 点击 Key/标题、评论提交、文件选择、拖放确认、附件点击均发出正确且唯一的信号；
- 拖入文件在确认前不发出上传信号，取消后不发出上传信号；
- 提交/上传状态阻止重复操作；
- 动态外部文本保持原样；固定文案双语完整；
- 明暗主题可读，窄宽度保持双栏比例且无横向滚动；
- 聚焦 QML、资源和翻译测试通过，源码模式可加载组件；
- `git diff --check` 通过，无业务请求、页面特例或无关修改。

## 后续阶段

第二阶段新增：

```text
IssueBrowserView.qml
├─ IssueFilterBar.qml
├─ IssueListView.qml
└─ IssueDetailView.qml
```

第三阶段再把评论、附件、系统浏览器去重和 Jira/Redmine 映射接入业务层。
