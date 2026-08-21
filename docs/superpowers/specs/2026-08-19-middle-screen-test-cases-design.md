# Android 中屏 29 条测试用例设计

## 1. 已批准边界

- 来源：`中屏用例评估.xlsx` / `SmartTest覆盖评估`，行号见下表。
- 执行模式：29 条均为 Python；pytest 是业务 owner，ADB/DUT feature 返回事实，QML 仅使用通用参数页。
- APK executor：不适用；本批均可通过运行期间可用的 ADB、节点、网络和现有播放器能力完成。
- 检测设备：不适用；U 盘、网线、AP、播放服务器和媒体文件是人工准备的测试环境。
- 完整覆盖：4、10、18、20、21、29、31、32、33、49、52、53、54、55。
- 软件部分覆盖：57～66、95～98、114。固定说明：**本结果仅代表软件播放状态检查通过，不代表原始用例完整通过。**
- 不改动 5、67、68、69 的业务行为。

## 2. Single-Case Implementation Contract 公共字段

以下字段适用于下表每一条合同，和每行的差异字段共同构成完整合同：

- 模块 / 优先级 / milestone：Android 中屏 / 沿用源表 / 本批实施。
- 客观自动化边界：仅执行该行“checkpoint”；不得以人工观察替代自动 PASS。
- 执行模式 / 理由：Python；现有 DUT 的 ADB、shell、网络和媒体 session owner 可完成，运行期间 ADB 必须在线。
- 前置状态：DUT 已选择且 ADB 状态为 `device`；人工准备动作按行执行。
- 动态参数：CPU 频点和本地媒体文件由现有 DUT 动态选项 owner 提供；其余不适用。
- 环境/设备参数：全局 DUT serial；31/32 不重复定义 serial。
- pytest：每个 source ID 对应独立的 `testing/tests/android/common/iptv/test_middle_screen_<source_id>_<name>.py` 和同名测试函数；33 条均为独立 discovery/catalog 业务条目。
- `SMARTTEST_CASE_PLAN`：每个独立测试模块使用 `build_middle_screen_plan(CASE)` 声明本用例步骤；不使用参数化 batch，不存在 batch nodeid。
- Python 业务 owner：上述 pytest；DUT feature 为 `testing.tool.dut_tool.features.iptv_middle_screen.execute_middle_screen_case`。
- APK executor：不适用；禁止 Python/APK 双实现。
- 现有复用能力：Android DUT shell、Wi-Fi、ping、CPU 频率、local playback media session、公共参数/step/evidence/report。
- 通用扩展：case-scoped 参数、33 个独立 pytest 入口、共享 runner、结构化解析和覆盖摘要；不新增逐用例驱动。
- 缺失且阻塞能力：不适用；真机环境缺失只限制 L3，不改变客观规则。
- 复用决定与预计净新增生产代码：扩展现有 owner；新增代码集中在 catalog、参数合同、planner 和既有 feature。
- steps：完整用例为参数环境校验、前状态、驱动执行、事实采集、checkpoint、恢复、报告；媒体为解析源、启动、等待、采样、判定、停止、部分覆盖报告。
- evidence：source identity、实际参数、DUT serial、命令/结构化输出、expected/actual、恢复与覆盖边界。
- cleanup / timeout / cancel：CPU、Wi-Fi、播放器在 `finally` 恢复；播放器等待使用配置超时；114 默认 86400 秒；取消通过异常路径进入 cleanup。
- 报告字段：source ID/文件/sheet/行、nodeid、DUT、实际参数、step/checkpoint expected/actual/evidence、`coverage_level`、`unverified_items`、状态和错误。
- Wi-Fi 密码：按 Coco 本轮决定，测试参数、现有持久化、运行展示和报告均使用明文；不新增 secret owner、QML 或 Bridge 行为。
- Wi-Fi cleanup：恢复进入测试前的启用/禁用状态并保留 saved networks；现有 API 无原连接凭据，因此不恢复原 SSID，不增加猜测或兜底。
- 参数映射：33 条用例只绑定各自 `iptv_middle_screen_<source_id>:<param>`；已删除 `iptv_middle_screen:*` 广域合同和兼容读取。20、29、31、32、33 无用例参数，UI 必须显示零个字段。
- 固定文字：每个实际暴露参数均在 `TestPageBridge` 翻译上下文提供中英文 label 和 description；运行时 `.qm` 必须能解析，不显示原始 `test.param...` key。
- 自测 / discovery / 真机验证：解析器、驱动异常、参数、计划、报告、collect-only；最高可声明 L2，实际 DUT 成功后才可升 L3。

## 3. 29 条合同差异字段

|源 ID / 行|标题 / 目标|用户参数（`<case_id>:<param>`）|人工准备动作|checkpoint / expected / actual / PASS 规则|边界|
|---|---|---|---|---|---|
|4 / 5|USB 存储识别|`usb_match` 必填|连接 U 盘或硬盘|`iptv.004.objective` / 匹配块设备且有挂载证据 / mounts+block / 同时满足|完整|
|10 / 11|有线网络速率|`interface=eth0`、`expected_speed_mbps` 必填|连接指定速率网线|`iptv.010.objective` / 接口有 IP 且速率相等 / 地址+speed / 精确相等|完整|
|18 / 19|CPU 频点|`frequencies` 动态必填|不适用|`iptv.018.objective` / 各频点锁定并恢复 / 每点读取值+恢复值 / 全部相等|完整|
|20 / 21|eMMC HS400|无|不适用|`iptv.020.objective` / MMC mode 为 HS400 / dmesg token / 明确包含 HS400|完整|
|21 / 22|Wi-Fi 2.4G/5G|两组 SSID 必填、密码可空|准备双频 AP|`iptv.021.objective` / 两频段扫描连接取 IP / scan/connect/address / 两组全部成功|完整|
|29 / 30|CPU 温度节点|无|不适用|`iptv.029.objective` / 节点为数值 / 原始节点值 / 整数可解析|完整|
|31 / 32|USB ADB|无|选择 USB serial|`iptv.031.objective` / 状态 device 且非网络 serial / status+serial / 同时满足|完整|
|32 / 33|网络 ADB|无|选择 host:port serial|`iptv.032.objective` / 状态 device 且为网络 serial / status+serial / 同时满足|完整|
|33 / 34|UI Mode|无|不适用|`iptv.033.objective` / 最终有效尺寸≥1920×1080 / wm size / 宽高均达标|完整|
|49 / 50|DHCP 双栈|interface、IPv4/IPv6 target 必填|双栈网络|`iptv.049.objective` / 两类地址和探测成功 / addr+ping / 全部成功|完整|
|52 / 53|有线 IPv4|interface、IPv4 target 必填|有线网络|`iptv.052.objective` / IPv4 与探测成功 / addr+ping / 全部成功|完整|
|53 / 54|有线 IPv6|interface、IPv6 target 必填|IPv6 有线网络|`iptv.053.objective` / global IPv6 与探测成功 / addr+ping6 / 全部成功|完整|
|54 / 55|无线 IPv4|interface、IPv4 target 必填|Wi-Fi 已连接|`iptv.054.objective` / IPv4 与探测成功 / addr+ping / 全部成功|完整|
|55 / 56|无线 IPv6|interface、IPv6 target 必填|IPv6 Wi-Fi|`iptv.055.objective` / global IPv6 与探测成功 / addr+ping6 / 全部成功|完整|
|57 / 58|H.264 解码|`media_files`、timeout 必填|选择源表两个文件|`iptv.057.objective` / 全部 PLAYING / session samples / 全部成功|software_partial|
|58 / 59|H.265 解码|同 57|选择源表两个文件|`iptv.058.objective` / 全部 PLAYING / samples / 全部成功|software_partial|
|59 / 60|AVS2 解码|同 57|选择源表两个文件|`iptv.059.objective` / 全部 PLAYING / samples / 全部成功|software_partial|
|60 / 61|H.264 4K60|`media_url` 可替换、timeout 必填|源表 URL 可访问|`iptv.060.objective` / PLAYING / samples / 成功|software_partial|
|61 / 62|H.265 4K120|同 60|同上|`iptv.061.objective` / PLAYING / samples / 成功|software_partial|
|62 / 63|AV1 4K120|同 60|同上|`iptv.062.objective` / PLAYING / samples / 成功|software_partial|
|63 / 64|VP9 4K120|同 60|同上|`iptv.063.objective` / PLAYING / samples / 成功|software_partial|
|64 / 65|AVS2 4K120|同 60|同上|`iptv.064.objective` / PLAYING / samples / 成功|software_partial|
|65 / 66|AVS3 4K50|同 60|同上|`iptv.065.objective` / PLAYING / samples / 成功|software_partial|
|66 / 67|MJPEG 4K30|同 60|同上|`iptv.066.objective` / PLAYING / samples / 成功|software_partial|
|95 / 96|HTTP|`media_url`、timeout 必填|准备 HTTP 服务|`iptv.095.objective` / PLAYING / samples / 成功|software_partial|
|96 / 97|HLS|同 95|准备 HLS 服务|`iptv.096.objective` / PLAYING / samples / 成功|software_partial|
|97 / 98|UDP|同 95|准备 UDP 服务|`iptv.097.objective` / PLAYING / samples / 成功|software_partial|
|98 / 99|RTSP|同 95|准备 RTSP 服务|`iptv.098.objective` / PLAYING / samples / 成功|software_partial|
|114 / 115|本地 4K 24H|`media_files`、timeout、`playback_duration_s=86400` 必填|选择本地 4K 文件|`iptv.114.objective` / 全窗口 PLAYING / 带时间采样 / 任一非 PLAYING 失败|software_partial|

所有 `software_partial` 行的 `unverified_items` 固定为：画质、音质、花屏、卡顿、丢帧、解码正确性、音画同步。

### 其他四条保留用例的参数合同

|源 ID|标题|参数|默认 / 必填|用户动作|
|---|---|---|---|---|
|5|HDMI connection/output evidence|`iptv_middle_screen_005:hdmi_state_command` / string|空 / 否|可留空使用内置 HDMI 状态节点命令，或输入设备适配命令。|
|67|JPEG GIF BMP PNG images|`iptv_middle_screen_067:media_files` / multiline|空 / 是|每行输入一个图片路径；保留路径内部空格。|
|68|SBS/TAB 3D video|`media_files` / multi_enum；`playback_timeout_s` / float|空、10 / 均是|选择 SBS/TAB 文件并确认启动超时。|
|69|VR video|`media_files` / multi_enum；`playback_timeout_s` / float|空、10 / 均是|选择 VR 文件并确认启动超时。|

## 4. 批次与执行检查项

1. 系统硬件状态：4、18、20、29、33。
2. 连接能力：10、21、31、32。
3. IP 网络：49、52、53、54、55。
4. 基础解码：57～60。
5. 高帧率解码一：61～63。
6. 高帧率解码二：64～66。
7. 协议与稳定性：95～98、114。

检查项：参数开始校验；33 个独立文件、函数、nodeid 和计划；不存在 batch nodeid；14 条严格判定；15 条部分覆盖标签；Wi-Fi 密码明文透传；CPU/Wi-Fi/播放器 cleanup；报告 JSON/HTML；compile/import；`git diff --check`；可用 DUT 时执行 L3。
