# 杭州电信家庭高清 IPTV 自动订阅系统 — Codex 最终任务书（V3 精简可靠版）

**版本：** V3.0  
**日期：** 2026-10-20  
**状态：** 开发需求，不是已经验证可用的直播源  
**实施主体：** Codex / 其他本地编码 Agent  
**项目名建议：** `iptv-clean`  

> 一句话目标：无需 NAS、Docker、VPS、代理或复杂后台，由 GitHub Actions 每日更新和验证公开 CCTV／省级卫视播放地址，GitHub Pages 提供一个稳定的 HTTPS M3U 订阅链接，Redmi X65 的 TiviMate 只需添加一次。若视频源本身不可用，宁可不发布，也不伪称“已修复卡顿”。

---

## 0. 不可误解的约束（最高优先级）

1. 用户设备为 **Redmi X65 电视**（不是 TCL）；电视上已安装 **TiviMate 免费版**，仅维护 **一个**在线 M3U 播放列表。
2. 用户家庭网络为 **杭州中国电信宽带**，可能存在 iStoreOS / OpenClash，但此项目 **不配置代理、不接管路由、不测试香港／海外出口**，不假定用户有香港线路。
3. 用户有 **Mac mini（macOS）**，作为 Codex 开发、一次性本地验收设备；**不要求 Mac 常驻、不运行定时服务**。
4. **不使用 NAS、Docker、VPS、收费 API、数据库服务器、管理后台**。实现优先考虑 Python 标准库、`requests`/`httpx`、`m3u8`、`ffprobe`，依赖要少。
5. **只收 CCTV 和主要省级卫视**。画质以 **1080P 优先、720P 为最低标准**；不把 360P 作为备用，不为凑数量加入假直播或错误节目。
6. **自动更新 ≠ 自动加速**。本项目不转播视频、不缓存视频、不承担 CDN 功能；M3U 只包含外部源 URL，播放器从原始视频源取流。
7. **禁止用域名或端口直接判定可用或高清。** 旧方案把 `ottrrs.hl.chinamobile.com` 提权后，50/51 条主线共用一个域名，导致全军覆没。本项目必须废除这一评分逻辑。
8. **重要历史反例：** 曾有浙江卫视 HLS `#EXT-X-MEDIA-SEQUENCE:359977910`，三个约 8 秒分片，连续多次轮询序号不变；IINA 播放约 24 秒后冻结。必须把这一场景写进自动测试；**HTTP 200、首次能播放、文件名含 1080p 都不算通过**。
9. **不要声称 GitHub Actions 海外 Runner 的测试代表杭州电信的播放效果。** 发布报告必须注明测试地点 `github-actions`。本地 Mac 的测试仅代表当时用户所处的真实网络路径。
10. 不自动创建公开 GitHub 仓库、推送公开直播地址、变更用户 GitHub 权限；**先展示方案并获得用户确认，才实施联网账户侧写操作**。开发测试可以直接执行。

## 1. 交付的用户体验

用户在电视上只需输入以下形式的订阅地址（**部署成功后才是真实地址**）：

```text
https://<github-username>.github.io/<repo-name>/live.m3u
```

TiviMate 订阅该 URL。之后：

- GitHub Actions 每天执行一次采集→检测→生成→发布；支持手动运行。
- `live.m3u`：频道尽量简洁，**同一个频道只保留最优的合格候选**。
- `backup.m3u`：同频道最多 2 条，按「主用」「备用」分组，方便诊断。免费 TiviMate 只能添加一份，默认用 `live.m3u`，测试时可将其替换为 `backup.m3u`。
- `report.json`：每个频道的通过／拒绝原因、候选来源、实际解析主机、HLS 动态检查、分辨率、耗时、运行环境及生成时间。
- `index.html`：可选最简状态页，仅显示最近成功时间、合格频道数和下载链接；不要做复杂后台。
- 发生大规模失败时，**保持上次成功发布的 Pages 内容不变**，在 GitHub Actions 日志明确报错；不得以失败、空文件或只有几个坏源的列表覆盖旧版。

## 2. 候选直播源（都只是地址仓库，不是视频保证）

默认配置：

| 优先级 | 名称 | 在线 M3U（现有已知路径，部署时再次核实） | 默认 |
|---|---|---|---|
| 1 | CCSH/IPTV 精简版 | `https://raw.githubusercontent.com/CCSH/IPTV/main/live_lite.m3u` | 启用 |
| 2 | Oasisic-IPTV 备用版 | `https://raw.githubusercontent.com/Hawaiine/Oasisic-IPTV/main/output/live_backup.m3u` | 启用 |
| 3 | vbskycn/iptv | `https://live.zbds.top/tv/iptv4.m3u` | 可选、默认关闭（曾遇到卡顿） |
| 4 | fanmingming/live IPv6 | `https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u` | 可选、默认关闭（IPv6/鉴权兼容性需验证） |

要求：

- 所有仓库及 URL 都定义在 `config/sources.yaml`（或 JSON）；以后更换源不需要改代码。
- 源下载出现 403/404/429/超时，只记录错误并跳过，其他源继续处理。
- 去重依据正规化 URL、频道标签与重定向后端信息；**多个仓库包含同一个视频 URL 不算不同线路**。
- 不对上游平台进行逆向破解、不伪造会员／授权信息、不绕过地域或 DRM。尊重版权和服务条款；如果无法确认某一来源可被合法公开分发，不要镜像其媒体数据。

### 2.1 目标频道

- CCTV1～CCTV17，另外 CCTV5+；处理 `CCTV-1综合`、`CCTV1`、`央视一套` 等常见别名，避免混入 CCTV4K、CCTV8K 或 CCTV 体育赛事非同名直播。
- 主要上星卫视，至少考虑：浙江、湖南、江苏、东方（上海）、北京、广东、深圳、安徽、山东、湖北、河南、河北、江西、福建东南、四川、重庆、天津、辽宁、吉林、黑龙江、陕西、山西、广西、贵州、云南、海南、甘肃、青海、宁夏、新疆、西藏、内蒙古等。
- 浙江卫视优先展示在省级卫视分类靠前位置。频道排序可配置。
- 没有合格源就缺席该频道，并在报告中记录；**不虚构、不错配、不用固定视频冒充直播**。
- EPG 台标可以作为独立附属信息，失败不应影响播放列表；不要用第三方 EPG 成功推断源成功。

## 3. 整体架构

```text
CCSH / Oasisic（及可选源）
          │ 每日下载文本 M3U
          ▼
Python：解析 / 频道名称标准化 / 去重 / 安全过滤
          ▼
候选流检测：HTTP → HLS 主/媒体列表 → 分片下载 → 动态前进 → ffprobe 画质
          ▼
选择：每频道最优主线 + 尽量独立的备用线路
          ▼
生成 live.m3u + backup.m3u + report.json
          ▼
发布门槛 / 异常回滚
          ▼
GitHub Pages（HTTPS 静态文件）
          ▼
Redmi X65 · TiviMate
```

**不引入额外服务**。GitHub 是列表分发与检测执行平台，不是视频中继平台。

## 4. 功能与算法细则

### 4.1 解析与清洗

- 正确解析 `#EXTINF` 的 `tvg-id`、`tvg-name`、`tvg-logo`、`group-title`、显示名，以及下一行 URL；支持 UTF-8／BOM、CRLF、中文名称、URL 编码、末尾空格。
- 将频道名称统一为 `CCTV1...CCTV17`、`CCTV5+`、`浙江卫视` 等；严格防止 `CCTV1` 误匹配 `CCTV10`，`CCTV5` 误匹配 `CCTV5+`。
- v1 只支持 **HTTP(S) 可获取的 HLS**，即 M3U8（也可支持经 HTTP 重定向最终落到 HLS 的接口）；跳过 `rtsp://`、`rtp://`、`udp://`、SWF、MP4、HTML、离线节目、来源不明的动态脚本接口。不要仅凭扩展名判断：须检测响应体是 HLS 清单。
- 过滤明显重复、拼接在同一字段中的多个 URL（例如 `#` 后又包含第二个 `http://`）、循环重定向、无法解析的异常字符。
- 对候选地址进行 SSRF 防护：拒绝环回、内网、链路本地和云平台 metadata 地址；校验重定向目标及 DNS 解析结果；给请求设置超时、重定向次数和最大读取字节数。不能任由公网 M3U 使 GitHub Runner 访问内部资源。
- 对长时效签名、鉴权标记、Cookie、User-Agent 依赖、频繁变化的 token 不做“绕过”；根据可持续性策略降低优先级或排除。日志中应对 URL 的敏感查询参数脱敏。

### 4.2 检测过程：真正验证持续直播

对每一条候选，分层执行、任意步骤失败即拒绝（设置合理的超时）：

1. **连接**：GET，允许有限次数的安全 HTTP 重定向。记录 HTTP 状态、首字节时间；拒绝 403/404/5xx、HTML/空响应。
2. **HLS 格式**：响应体有 `#EXTM3U`。如果是 Master Playlist，解析 `#EXT-X-STREAM-INF`，选择可探测的高清视频变体，再读取其 Media Playlist；正确解析相对 URL。
3. **直播性质**：`#EXT-X-ENDLIST` 直接拒绝（按常规 VOD 处理）。记录 `#EXT-X-MEDIA-SEQUENCE`、`#EXT-X-TARGETDURATION`、分片 URL 或 `#EXT-X-PART` 等；尽量支持常见 HLS，复杂 DRM 或不兼容格式标记 unsupported 而不是随意通过。
4. **连续更新**：根据 TARGETDURATION 自动确定轮询等待时间，例如至少轮询 3 次，总跨度通常 20～45 秒；要求能观察到新的媒体分片或可靠的直播进度变化。**如果连续 24～30 秒仍只返回相同三个 8 秒分片，则判定 `frozen_playlist` 并剔除**。不能只看序号存在就通过；有些源会换 URL，但也可能是假直播，留待片段验证。
5. **分片检查**：真实下载至少两个时间上不同的分片（或合理的部分分片），确认 HTTP 成功、数据非空且符合媒体内容特征。需要处理相对路径、query 参数、字节范围、受支持的加密；遇到 DRM 或需要未授权密钥时拒绝。限制单次总下载大小、防止高额流量。
6. **清晰度验证**：用受控超时的 `ffprobe` 对视频片段／HLS 流读取实际视频分辨率；Master Manifest 的 `RESOLUTION=1920x1080` 仅是候选参考，不可直接当作最终真值。必须存在视频轨且高度 ≥720，优先 1080 或更高；未知清晰度标为 `resolution_unknown`，**不得以“高清已验证”入选**。
7. **基本稳定性**：记录多次片段请求耗时、有效吞吐量、卡顿或下载失败次数。至少验证短时连续性，但不声称可以保证几小时不掉线。
8. **日志**：输出 `reachable`、`live_progress_ok`、`segment_ok`、`resolution_verified` 和 `final_status`，失败原因应有机器可读的枚举值。

说明：视频总码率和编码复杂度会影响播放稳定性；高分辨率不意味着在 Redmi X65 上必然流畅。GitHub Runner 和家庭网络是两种不同测试路径。

### 4.3 限流与检测时间

- 上游 M3U 可能有千余条地址。先解析、严格归一化和去重，**优先对候选进行轻量预检**，控制每频道最多 4～6 条进入深度检测。
- 初版单次任务争取 10～25 分钟内完成；全局并发建议 4～8、单域名并发 ≤2，具体通过实测调整；尊重源站，不大规模高频扫公共服务。
- 允许使用上次合格线路作为首批候选，但**必须重新实际检查**。历史成功不等于今天有效。
- 对高优先级频道（CCTV1、CCTV5、CCTV13、浙江、湖南、江苏、东方卫视）先测，剩余频道按可控批次执行。
- 优先级不能等同于“域名品牌分数”；评分以已验证可持续性、实际分辨率、分片下载表现为主，来源类型只能用于风险提示与平手时参考。

### 4.4 主线和备用线

- 每个频道主线最多 1 条、备用最多 1 条；两条都必须独立通过本轮检测。
- 尽量避免主线与备用来自同一主机/IP 或重定向到同一最终节点；不保证两条不同主机一定有独立上游。
- `live.m3u` 只有频道主线；`backup.m3u` 分两个分组，例如 `央视-主线 / 央视-备用 / 卫视-主线 / 卫视-备用`，显示名称 `CCTV1` 与 `CCTV1 (备用)`，避免 TiviMate 错误去重。
- 输出标准 `#EXTM3U`、`#EXTINF`，保留合理的 `tvg-id`、`tvg-logo`、`group-title`。纯 HTTP 视频源 URL 可以保留，订阅文件本身必须由 HTTPS 提供；不要擅自将流地址从 http 改为 https。
- 若某频道仅通过一条，保留单条；若未通过，明确缺失。

### 4.5 发布保护、可追踪与版本保留

- 冷启动：只有首次检测满足基本成功标准才允许发布，例如 **至少 10 个合格频道，且有央视和卫视两个类别**；标准在配置里可调并需要注明目的；若达不到，则退出并明确提示“尚无可订阅的可信列表”。禁止放入未经验证的假数据凑数。
- 正常更新：和上一次成功发布版本比较。若新一轮合格频道数突然低于上次的 70%（可调），视为上游或检测环境异常，**整个版本不发布**。在 Action 日志和失败工件中保留诊断信息。
- 不能把“沿用上次成功列表”描述为“今天全部通过检测”；状态报告要显示上次成功发布日期。
- **以一次 GitHub Actions 工作流完成“生成、质量门禁、提交归档、上传 Pages artifact、部署 Pages”**；不要依靠 `GITHUB_TOKEN` 推送后再触发另一条 Pages 工作流，否则可能不触发。
- 将最近成功的 `live.m3u`、`backup.m3u`、`report.json` 保存到仓库的 `output/`，供回滚。发布后有固定 URL。GitHub Actions 更新期间不得让电视读到半成品。
- 如果 GitHub Pages 不可用，不要宣称“已经上线”；给出具体阻塞与人工可执行步骤。

### 4.6 网络和权限安全

- 只下载文本 M3U，短暂检验少量视频分片；不提供播放内容的公开代理／转发服务。
- 不抓取、传播付费或受 DRM 保护的媒体；遵守来源的版权授权和适用条款。
- 不在日志、仓库、报告中输出账号密码、Cookie、Bearer、长期私有 token。
- 工作流权限按最小化原则设置，部署 Pages 需 `pages: write`、`id-token: write`；若还向仓库提交 `output/`，需要 `contents: write`。确保 Action 的来源与版本合理，避免滥用密钥。

## 5. GitHub Actions 与 Pages 发布要求

- 仓库建议：`iptv-clean`，Public（只存代码、公开来源 URL 与状态，禁止敏感信息）。
- 工作流存放 `.github/workflows/update.yml`，触发 `workflow_dispatch` + `schedule`，**北京时间每天一次**，例如北京时间 07:17 对应 UTC 前一日 23:17。可改成北京时间其他非整点，减少 GitHub 排队拥堵。
- 使用 Python 环境、安装必要依赖与 FFmpeg/ffprobe，执行自动测试，然后运行更新。
- 使用 `actions/configure-pages`、`actions/upload-pages-artifact`、`actions/deploy-pages` 同一工作流发布静态目录。`index.html`、`live.m3u`、`backup.m3u`、`report.json` 在发布根目录。
- 设置适当 `concurrency`，避免手动触发与计划运行相互覆盖。
- GitHub Pages 站点：`https://<用户名>.github.io/<仓库>/live.m3u`，这**只是模板**，不要捏造用户账号或最终地址。
- GitHub Actions 定时触发可能延迟、公开库长期无活动可能停用；README 写明如何手动执行及检查最近一次成功状态。
- GitHub Pages 通过 Actions 发布所需权限与流程参考：https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
- Actions 计划任务说明：https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule

## 6. 建议的代码结构（Codex 可小幅调整）

```text
iptv-clean/
├── README.md
├── requirements.txt
├── pyproject.toml                 # 可选
├── config/
│   ├── sources.yaml
│   ├── channels.yaml
│   └── settings.yaml
├── src/iptv_clean/
│   ├── __init__.py
│   ├── __main__.py                # python -m iptv_clean
│   ├── fetch_sources.py
│   ├── parse_m3u.py
│   ├── normalize_channels.py
│   ├── validate_hls.py
│   ├── probe_video.py
│   ├── select_streams.py
│   ├── render_outputs.py
│   └── publish_gate.py
├── tests/
│   ├── fixtures/
│   │   ├── frozen_24s.m3u8
│   │   ├── progressing.m3u8
│   │   └── bad_source.m3u
│   ├── test_parse.py
│   ├── test_channel_names.py
│   ├── test_hls_freeze.py
│   ├── test_resolution.py
│   ├── test_publish_gate.py
│   └── test_security.py
├── output/                      # 仅存最后一次已发布版本
│   ├── live.m3u
│   ├── backup.m3u
│   └── report.json
├── .github/workflows/update.yml
└── docs/
    └── TROUBLESHOOTING.md
```

命令建议（以最终真实 CLI 为准，README 必须保证能复制运行）：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
python -m iptv_clean --dry-run --report-dir ./tmp/check
python -m iptv_clean --publish-local --output-dir ./tmp/site
```

`--dry-run` 只能做无副作用本地检查，不调用 GitHub 发布 API；`--publish-local` 生成静态文件，不自动上传。实际远程部署由 Actions 执行。

## 7. 自动化测试最低清单（必须实际跑通）

1. **冻结 24 秒反例**：3 个 8 秒分片、序号一直为 `359977910`，每次 HTTP 都返回 200；必须拒绝为 `frozen_playlist`，且不能选择为主线。
2. **正常 HLS**：序号或真实分片不断前进，多个分片可下载，分辨率 1920×1080；必须通过。
3. **伪装高清**：URL 含 `1080p` 但视频只有 640×360；必须拒绝。
4. **主列表 1080p、实际解析 360p**：实际分辨率优先，必须拒绝。
5. **主列表动态、分片 404/403**：必须拒绝。
6. **VOD/结束流**：有 `#EXT-X-ENDLIST`；必须拒绝。
7. **M3U 无效**：HTML、SWF、MP4、严重拼接 URL；必须拒绝。
8. **频道识别**：CCTV1 ≠ CCTV10，CCTV5 ≠ CCTV5+，浙江卫视不被错归类。
9. **安全**：候选 URL、重定向或 DNS 指向本地/内网/metadata 地址时拒绝。
10. **大面积失败**：上次成功 45 台，本次仅 8 台通过，必须拒绝发布并保留上次版本。
11. **所有候选失败**：首次运行不得生成冒充真实可用的空假订阅，不得声称成功。
12. **输出合法性**：M3U 每条 `EXTINF` 恰有一条正确 URL；频道/组名UTF-8；`backup.m3u` 每频道最多两条。

网络实测与单元测试分开。不要让依赖实时公网源的测试导致 `pytest` 随机失败；实时检测属于可独立运行的集成测试／人工验收。

## 8. 人工验收与成功定义

**必须通过：**

- `pytest -q` 全绿，冻结 24 秒反例有效，安全和回滚测试有效。
- GitHub Actions 手动运行一次成功，日志出现实际检验统计而不是单纯地址数量。
- GitHub Pages 的 `live.m3u` 返回 200 且内容以 `#EXTM3U` 开头；电视通过订阅 URL 显示频道名。
- `report.json` 中每一条列入播放列表的 URL 都有本轮 HLS 连续性、分片以及 720P+ 清晰度的通过记录；不允许暗中回退到未经验证的地址。
- 用户在 Redmi X65 的 TiviMate 进行家庭网络验收：CCTV1、CCTV5、浙江、湖南、江苏、东方卫视等实际存在的频道，各观看约 5 分钟；记录打开耗时和卡顿。若不能播放，明确列出失败节目，不要承诺流畅。
- 没有通过的频道应报告缺失；如首次运行找不到足够合格源，项目应正确地以失败/待改进状态结束，而不是给出虚假的成品链接。

**验收边界：**

- GitHub 海外 Runner 检测通过 ≠ 杭州电信一定流畅；需要电视人工抽测。
- TiviMate 免费版一份订阅；没有免费的无缝主备切换承诺，备用目录要人工选择／重新导入。
- 没有付费 IPTV 授权服务、没有直播服务器，不能承诺永远稳定。

## 9. 四个里程碑（Codex 依次执行）

### M1. 项目整理与最小可运行结构
- 建立目录、依赖、配置、标准化频道字典、M3U 解析器。
- 解析 CCSH 与 Oasisic，统计规范化频道和候选数量。
- 交付：CLI 可以列出候选；M3U 解析单测通过。

### M2. 真实直播检测与测试
- 实现安全 HTTP 请求、HLS 解析、动态连续性、分片下载、ffprobe 画质探测。
- 建立历史「浙江卫视 24 秒冻结」的本地可复现测试。
- 交付：明确的成功／失败状态和诊断报告；测试覆盖关键失败路径。

### M3. M3U 生成与发布保护
- 实现主线／双线路列表、排序、去重、状态报告和回滚门禁。
- 给出真实的 `--dry-run` 运行结果；不能拿临时样例冒充可用数据。
- 交付：本地生成的产物通过格式校验；失败时保留旧版。

### M4. GitHub Actions + Pages 上线
- **先问用户是否同意创建／使用公开仓库及上线**；同意后配置工作流、权限和 Pages。
- 手动触发并确认首次成功发布；得到真实 URL 和访问校验。
- 给出在 Redmi X65 上通过 TiviMate 添加 M3U 的简明步骤。
- 交付：真实订阅 URL、Actions 运行链接／运行结果、频道统计、未解决问题及后续维护说明。

## 10. 遇到阻塞时的动作

- 先执行可在当前环境完成的开发、测试与本地检查，不要因为 GitHub 未登录而停工。
- 远程操作无法授权时，明确告诉用户需要在 GitHub 哪个页面完成什么操作，**不要求粘贴密码或 token 到聊天**。
- 如果直播源真实可用率低，暂停发布，展示逐频道失败报告，并建议补充新的合规上游来源；不要盲目换国外 IP 或重新挑“看起来可靠”的域名。
- 若在 macOS 上缺少 `ffprobe`，检查是否可使用 Homebrew 安装 FFmpeg；需要改系统环境时先告知用户。不要未经允许删除现有文件或覆盖原 GitHub 仓库。
- 完成时提供清楚的 **已完成 / 尚未完成 / 测试证据 / 在线 URL**，不要把草稿说成部署成功。

---

### 与以前版本的关系

**本 V3 任务书替代之前所有 V1/V2、带香港代理和静态域名评分的任务书。** 如读取到旧 ZIP，仅作为历史失败案例，不得复用其中「按域名优先级直接选源」的逻辑。GitHub Pages 需先真实部署才有 URL，之前的文件链接不是网络订阅链接。
