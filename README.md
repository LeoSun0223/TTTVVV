# 高清 IPTV 自动订阅（V3）

面向 Redmi X65、杭州电信宽带、TiviMate 免费版的一份在线订阅。仅收 CCTV1～17、CCTV5+ 和 32 个主要省级卫视，浙江卫视排在卫视首位。V3 任务书是唯一需求，V1/V2 作废。

**M1～M3 已完成本地开发与验证，尚未部署 GitHub Pages。不存在已确认可用的在线订阅地址。** 当前 82 项测试通过，最近一轮本地实测生成 46 台主线、77 条主备记录；该结果不代表电视验收通过。完整证据见 [开发验收记录](docs/ACCEPTANCE.md)。

系统每天采集公开 M3U，只保留本轮实际通过 HLS 前进、分片下载和 ffprobe 画质检测的线路。1080P 优先，720P 是最低标准；每频道最多两条。本项目不转播、不缓存供人播放，不承担加速功能，也不需要 Mac 常驻、NAS、Docker、VPS、代理或后台。

## 本地运行

要求 Python 3.9+、FFmpeg（含 ffprobe）。macOS 已有 ffprobe 时直接复用；没有时可自行执行 `brew install ffmpeg`。下面命令在项目根目录运行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
pytest -q
python -m iptv_clean --list-candidates --report-dir tmp/candidates
python -m iptv_clean --dry-run --report-dir tmp/check
python -m iptv_clean --publish-local --output-dir tmp/site --report-dir tmp/build
python scripts/check_outputs.py tmp/site
```

候选采集不等于检测通过。`--dry-run` 写本地诊断报告，不生成在线订阅、不调用 GitHub 发布 API。`--publish-local` 执行同样的真实检测，质量门禁通过才生成完整静态目录；它也不会上传。返回码 0 表示此命令成功，2 表示没有可信可发布版本或输入配置失败。首次全失败不会生成空 M3U。

默认使用系统 DNS。如网络把域名解析为 `198.18.0.0/15` 等保留地址，程序按 SSRF 规则拒绝。可明确选择应用内 AliDNS HTTPS 查询：

```bash
python -m iptv_clean --list-candidates --dns alidns --report-dir tmp/candidates-doh
python -m iptv_clean --dry-run --dns alidns --report-dir tmp/check-doh
python -m iptv_clean --publish-local --dns alidns --output-dir tmp/site --report-dir tmp/build-doh
```

该选项只为本进程查询公网 A/AAAA，依旧拒绝私网结果并固定已验证 IP 建立连接；不修改系统 DNS、路由或 OpenClash，不使用视频代理。报告记载 `dns` 和检测环境。即使进程不使用代理，现有网络设施可能影响出口，因此本地结果仅代表当时的实际路径，不能证明特定运营商出口。

优先频道抽测可用 `--channels CCTV1,CCTV5,CCTV13,浙江卫视,湖南卫视,江苏卫视,东方卫视`；抽测依然执行全局发布门槛，不足 10 台会正确拒绝发布。正常完整检查通常需要 10～25 分钟，受源站响应影响；默认全局并发 6、每主机请求并发 2，深测每频道最多 4 条，轻测最多 12 条，22 分钟预算后停止接纳新检测。

默认总 HTTP 读取预算为每轮 1 GiB，另限制单分片 16 MiB、单候选约 36 MiB。可用 `--history-report tmp/check-doh/report.json` 将旧报告中合格候选优先安排；只调整检测顺序，不能代替本轮重新检查。已发布 `output/report.json` 默认也提供这一顺序提示。

## 配置和判断依据

- `config/sources.json`：默认启用 CCSH/IPTV 和 Oasisic-IPTV；vbskycn 和 IPv6 专用源默认关闭。任何源下载失败都跳过并记录，不中止其他源。
- `config/channels.json`：50 个标准频道及严格别名，数组顺序决定输出顺序。CCTV1、CCTV10、CCTV5、CCTV5+ 分别匹配；未知名称、4K/8K 独立频道和轮播不入库。
- `config/settings.json`：并发、流量/时间预算、最低画质、检测优先顺序和发布门槛。

请求真实读取 HLS 内容，递归解析主清单与相对 URL。每条深测先下载并探测一个分片，再按 TARGETDURATION 观察至少 30 秒、至少三个轮询间隔，最后下载另一个不同时间的分片并再次探测。要求至少两次新媒体进度，最近仍有更新，两个分片内容不同。序号存在或单独上涨、签名 URL 改变、HTTP 200、URL 名称和主清单标称分辨率都不能认证高清。

真实视频轨高度必须 ≥720。逐片段记录字节、耗时、吞吐和分辨率，下载时间超过片段时长时拒绝。选择以实际画质和请求表现为依据，无域名品牌加分。备用优先独立主机/IP，重定向至同一最终清单不算不同线路；不同域名仍不保证上游独立。

支持常规 MPEG-TS、带初始化段的 fMP4 和显式/可推导字节范围。AES-128、SAMPLE-AES/DRM、仅 LL-HLS PART、delta/变量清单等复杂格式保守标为 unsupported，不获取密钥。不保持 Cookie，不仿冒授权，不绕过 token；明显签名/鉴权参数和特殊请求头依赖会排除。未验证与失败候选均不会回填到输出。无法自动判定视频中的实际节目身份，名称来自上游；需电视抽测确认节目没有错配。

## 输出与失败保护

通过门槛后在 `tmp/site/` 生成：

| 文件 | 用途 |
| --- | --- |
| `live.m3u` | 每频道一条，TiviMate 日常订阅 |
| `backup.m3u` | 每频道最多两条，主线/备用分组，备用名带 `(备用)` |
| `report.json` | 本轮每候选状态、来源、DNS/实际节点、前进快照、片段与画质证据、缺失频道、门禁 |
| `index.html` | 当前版本检测时间、频道数量和下载链接 |

报告中的查询参数值全部脱敏；用 `candidate_id` 对应同次运行的选择与检测记录。M3U 保留可公开的原始取流地址，包括必要的普通查询参数，不能据此存放私有 token。不要手工把含账号/私密路径的源加入公开配置。

冷启动至少 10 台且同时包含央视和卫视；更新同时要求频道数不少于上次的 70%。这些阈值防止误将环境异常当作正常更新。只有本轮通过的线路入选，没有凑数或沿用未复测线路。`output/` 不放样例，只在 Pages 部署并访问校验成功后由 Actions 归档。诊断写入 `tmp/`，失败时不修改旧版或部署 Pages。

本地静态版本使用先暂存整版再替换目录，替换失败回滚；Pages 通过完整 artifact 发布。`output/` 的 Git 历史保留已发布版本，`_deployment.json` 记录真实部署时间与 Actions 链接。报告 `generated_at` 是检测时间，不冒充发布时间。最新运行失败时网站继续显示旧版检测时间，需要在 Actions 查看失败报告。

## GitHub Actions 与 Pages 部署

目标仓库是用户已创建的 [LeoSun0223/TTTVVV](https://github.com/LeoSun0223/TTTVVV)。本地准备工作不会登录、推送、开通 Pages 或变更权限；远程操作需要用户确认后执行。详细步骤见 [部署说明](docs/DEPLOYMENT.md)。

工作流 `.github/workflows/update.yml` 只接受手动运行和每日北京时间 07:17 的计划触发。同一工作流完成安装、离线测试、真实检测、门禁、Pages artifact 上传、部署、HTTPS 内容校验、最后归档提交，避免用 GITHUB_TOKEN 推送后依赖另一条工作流触发。归档在部署成功之后进行，防止把未部署版本冒充最后成功版本。

使用 GitHub 官方 Actions 并固定完整提交 SHA。部署任务需 `pages: write`、`id-token: write`，归档需 `contents: write`；不需要个人 token。计划触发可能延迟，公开仓库 60 天无活动时可能停用；在 Actions 选择“每日检测并发布 IPTV”→ Run workflow 手动恢复/运行并检查成功时间。[GitHub Pages 官方说明](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages) · [GitHub 计划任务说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。

## 电视使用与验收

部署成功并对真实 HTTPS 地址校验后，在 Redmi X65 的 TiviMate 选择“添加播放列表”→“M3U 播放列表”→“输入网址”，粘贴确认可用的 `live.m3u` URL。免费版只维护一份；排查时可将它替换为 `backup.m3u` 并手工选择备用，无免费无缝切换承诺。

对实际存在的 CCTV1、CCTV5、浙江、湖南、江苏、东方卫视各观看约 5 分钟，记录打开耗时、是否超过 24 秒后冻结、卡顿和节目是否对应。见 [验收表](docs/TV_ACCEPTANCE.md)。GitHub 海外 Runner 检测不能代表杭州电信播放体验；1080P 也不能保证电视解码、宽带及源站数小时持续稳定。故障说明见 [排查文档](docs/TROUBLESHOOTING.md)。

来源仓库提供的是待测地址：[CCSH/IPTV](https://github.com/CCSH/IPTV)、[Oasisic-IPTV](https://github.com/Hawaiine/Oasisic-IPTV)。本项目仅短暂读取少量分片用于检测，不镜像媒体，不抓取付费或 DRM 节目。
