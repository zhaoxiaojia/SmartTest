# Jira 创建规范

## 1. Summary 格式

### 1.1 标准格式

```text
[公版 Jira ID][客户英文名][客户 Bug ID][芯片型号][系统版本][Bug 模块]: 问题概述,概率
```

示例：

```text
[SWPL-xxxx][Skyworth][SKYAML-xxx][S905X2][9.0][Video]: Screen goes to green when play a special ts,100%.
```

### 1.2 字段说明

1. **公版 Jira ID**
   - 公版也存在该问题时，需要反馈给公版，并克隆一个公版 Jira ID，更新到 Summary 中。
   - 公版不存在该问题时，可以不填写。

2. **客户英文名**
   - 注意客户英文名称的大小写。
   - 名称较复杂时，第一个单词首字母大写，例如 `Skyworth`。
   - 简称类客户名使用全大写，例如 `TCL`、`ZTE`。
   - 特殊项目可使用客户代号表示客户英文名称。

3. **客户 Bug ID**
   - 根据实际维护的客户情况填写。
   - 客户存在 Jira ID 或 Bug ID 时填写，方便维护内外部 Bug 的对应关系。
   - 客户没有 Bug ID 时，可以不填写。

4. **芯片型号**
   - 必须全部大写。
   - 根据实际项目填写，例如 `S905L3`、`T762`、`C308`、`T963`、`S905X2`。

5. **系统版本**
   - 根据实际 Android 或系统版本填写。
   - 例如 `4.4`、`9.0`、`10.0`、`RDK`、`Linux`。

6. **Bug 所属模块**
   - 使用规定的模块名称。
   - 首单词大写。

7. **问题概述**
   - 使用英文概述问题。
   - 对英文描述较难理解的现象，例如 PQ 现象，可以在括号中增加中文备注，方便理解。

8. **概率**
   - 根据实际测试结果填写问题出现概率。
   - 例如 `100%`、`50%`。

### 1.3 标准模块名称

| 序号 | 中文模块 | Summary 模块名 |
|---:|---|---|
| 1 | 系统 | System |
| 2 | 在线单路直播或点播 | Online |
| 3 | 本地播放 | Video |
| 4 | 有线网络 | Ethernet |
| 5 | 无线网络 | Wifi |
| 6 | 蓝牙 | BT |
| 7 | APK 问题 | APK |
| 8 | HDMI 相关 | HDMI |
| 9 | 声音相关 | Audio |
| 10 | DLNA 模块 | DLNA |
| 11 | Miracast 模块 | Miracast |
| 12 | 图像质量 | PQ |
| 13 | 性能 | KPI |
| 14 | USB 模块 | USB |
| 15 | 稳定性 | Stability |
| 16 | 多实例 | Multivideo |
| 17 | 网管模块 | Tr069 |
| 18 | xTS 认证 | CTS / VTS / GTS / TVTS / STS / GGI / CTS-verify |
| 19 | MS12 认证 | MS12 |
| 20 | Dolby Vision 认证 | DV |
| 21 | NTS 认证 | NTS |
| 22 | Prime Video 认证 | Primevideo |

## 2. Component 选择

Component 请参考部门维护的 Jira Component List：

```text
https://confluence.amlogic.com/display/PM/JIRA+component+list
```

## 3. Description 格式

### 3.1 Bug 描述模板

```text
[Steps to reproduce]:
1. xxxxxxxxxxxxx;
2. xxxxxxxxxxxxx;

[Actual results]:
xxxxxxxxxxxxx

[Expected results]:
xxxxxxxxxxxxx

[Reproducibility rate]:
100% 或 4/4

[Comparision]:
填写客户平台、公版 OpenLinux 或其他芯片的测试情况。
功能明显缺失的问题可以填写“无需对比”。

[Notes]:
HW info: 硬件平台，例如 S905L3 #008
SW info: 软件信息或可访问的软件链接
```

### 3.2 填写说明

1. **Steps to reproduce**
   - 按顺序填写问题复现步骤。
   - 步骤应清晰、完整，并能够实际执行。

2. **Actual results**
   - 填写执行复现步骤后的实际异常结果。

3. **Expected results**
   - 填写正确情况下应出现的预期结果。

4. **Reproducibility rate**
   - 填写问题复现概率。
   - 支持百分比，例如 `100%`。
   - 也可以使用“复现次数/测试次数”，例如 `4/4` 表示测试 4 次均可复现。

5. **Comparision**
   - 填写客户平台、公版 OpenLinux 或其他芯片的对比测试情况。
   - 功能明显缺失、无需进行对比的问题，可以填写“无需对比”。

6. **HW info**
   - 填写硬件平台信息。
   - 需要记录平台编号，例如 `S905L3 #008`。
   - 部分问题可能只在个别测试平台上出现，因此平台编号必须尽量准确。

7. **SW info**
   - 填写软件版本、软件包名称或下载链接。
   - 上传的软件链接在无特殊情况下应保证相关人员能够获取。

### 3.3 其他注意事项

1. 创建问题前应进行简单排查。不同模块的异常现场可参考 Debugging Dictionary：

   ```text
   https://confluence.amlogic.com/pages/viewpage.action?spaceKey=DD&title=Debugging+Dictionary
   ```

2. 根据问题情况上传必要的 Log、图片和视频文件。

3. Jira 附件最大不能超过 10 MB。

4. 超过 10 MB 的附件应上传到 FTP 或部门文件服务，并在 Jira 中填写文件链接，例如：

   ```text
   http://10.28.8.30:8881/#/Public/OTT/OTT-xxxx
   ```

5. Feature 类型的需求需要描述清楚需求细节。

6. Feature 存在相关文档或邮件时，需要将文档、邮件内容或对应链接补充到 Jira 中。

## 4. Labels 填写规则

### 4.1 基本规则

- Labels 需要按照项目和问题类型填写规定标签。
- 添加一个 Label 后按回车，再继续添加其他 Label。
- 一个 Jira 可以填写多个 Label。
- 不同项目组可以增加自己定义的项目 Label。
- 项目自定义 Label 不能替代规范要求的专项 Label。

### 4.2 通用专项 Label

| Label | 说明 |
|---|---|
| Regression | 修改引入的问题，即之前版本不存在、当前版本出现的问题 |

### 4.3 HDMI TX 专项 Label

| Label | 说明 |
|---|---|
| HDMI_TX_Type1 | HDMI TX 硬件芯片问题 |
| HDMI_TX_Type2 | HDMI TX 兼容性问题 |
| HDMI_TX_Type3 | HDMI TX 认证测试 |
| HDMI_TX_Type4 | HDMI TX Case 问题，测试用例覆盖不全面 |
| HDMI_TX_Type5 | HDMI TX 需求 |
| HDMI_TX_Type7 | 线材兼容性 |
| HDMI_TX_Type8 | HDMI 软件问题 |
| HDMI_TX_Type9 | HDMI TX 特殊需求 |
| HDMI_TX_Type10 | 无效 Bug |
| HDMI_TX_Type11 | 需要公版增加的功能 |

> 原规范未列出 `HDMI_TX_Type6`。

### 4.4 认证相关 Label

| Label | 说明 |
|---|---|
| Smoking-Test | 冒烟测试 |
| GTVS-Cert | GTVS 认证测试，包括 CTS、VTS、GTS、CTSVerifier、STS、CTS-ON-GSI |
| NTS-Cert | NTS / Netflix 认证测试 |
| Dolby-Cert | 杜比认证测试 |
| DTS-Cert | DTS 认证测试 |
| HDR10+-Cert | HDR10+ 认证测试 |
| eARC-Cert | eARC 认证测试 |
| Dolby-Vision-Cert | Dolby Vision 认证测试 |
| AVS-Cert | AVS / Amazon 音箱认证 |
| AVTS-Cert | Prime Video 认证测试 |
| GVA-Cert | GVA / Google 音箱认证 |
| HDMI-Cert | HDMI 认证测试 |
| CEC-Cert | CEC 认证测试 |
| HDCP-Cert | HDCP 认证测试 |
| Youtube-Cert | YouTube 认证测试 |
| MS12-Cert | MS12 认证测试 |

### 4.5 Regression Label 特殊要求

添加 `Regression` Label 时，Description 中必须补充以下信息：

1. 使用红色字体说明之前哪个版本测试正常，作为 Regression 的佐证。
2. 说明当前出现问题的版本。
3. 如果已经定位到某个提交或某个 Jira Bug 的修改导致问题，需要一并补充对应的 Commit 或 Jira 信息。

## 5. 完整 Bug Description 示例

```text
[Steps to reproduce]:
1. Upgrade the device to the specified software version;
2. Connect the HDMI output to the TV;
3. Play the specified TS file;

[Actual results]:
The screen turns green during playback.

[Expected results]:
The video should play normally without a green screen.

[Reproducibility rate]:
4/4

[Comparision]:
The issue does not occur on the public OpenLinux build.

[Notes]:
HW info: S905X2 #008
SW info: <software version or accessible download link>
```

## 6. 规范来源

- 章节：5.4.2 Jira 创建规则；
- Summary：5.4.2.1；
- Component：5.4.2.2；
- Description 与 Labels：5.4.2.3；
- 原始资料版本：V1.8。
