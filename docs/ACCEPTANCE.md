# 开发与验收记录

本地开发日期：2026-10-20；首次上线日期：2026-10-21（均为北京时间）。唯一需求：任务书 V3。原任务包保留；用户明确同意后已推送至指定公开仓库并部署 Pages。

## M1：完成

建立 Python 3.9+ 标准库项目、配置、50 台严格频道字典、M3U/BOM/CRLF/属性解析与去重、候选 CLI。阶段测试 `pytest -q` 为 **23 passed**。

真实运行命令：

```bash
.venv/bin/python -m iptv_clean --list-candidates --dns alidns --report-dir tmp/m1-public-dns
```

CCSH 下载 462,196 字节，保留目标候选 815 条；Oasisic 下载 142,474 字节，保留 138 条；跨源去重后 **50 台、925 候选**。候选不代表可播。完整记录 `tmp/m1-public-dns/candidates.json`。

系统 DNS 将 GitHub Raw 解析到 `198.18.0.81`，默认请求正确拒绝为 `unsafe_destination`（`tmp/m1/candidates.json`）。实际检查明确选择应用内 AliDNS DoH，未修改系统网络、路由或 OpenClash。本地网络路径不等于已确认的杭州电信电视路径。

## M2：完成

实现安全 HTTP、逐跳 SSRF/DNS 校验及固定连接 IP、HLS Master/Media 与相对 URI/字节范围、至少 30 秒前进观察、真实不同片段下载、受控本地 ffprobe。阶段测试 **60 passed**。

冻结测试使用 `MEDIA-SEQUENCE:359977910`、三片各 8 秒、HTTP 200，虚拟时钟推进至少 30 秒后必须返回 `frozen_playlist` 并不能入选。正常 HLS 使用测试时通过 ffmpeg 编码的真实 1920×1080 片段，实际 ffprobe 读取；640×360 即使 URL/master 标 1080p 也拒绝。自动测试不依赖公网直播。

## M3：完成开发，真实结果如下

阶段新增输出、去重、主备选择、发布门禁和整版替换回滚测试；阶段 **68 passed**。之后安全/传输/预算/历史复测及严格 M3U 头测试合计 **82 passed**，恢复工作后再次跑通。

首次完整真实运行：

```bash
.venv/bin/python -m iptv_clean --dry-run --dns alidns --report-dir tmp/live-check
```

耗时 **727.095 秒（约 12 分钟）**；925 条候选中实际检测 355 条，139 条进入深测。91 条通过，最终按每台最多两条及后端去重选择 **48 台、82 条线路**。通过候选中 73 条为 1080、18 条为 720；短暂分片读取总量约 711.8 MiB。CCTV10、甘肃卫视未选入。部分候选因限额未测，不能把缺席解释为所有潜在来源都不可用。

本轮发布门禁通过，但 dry-run 不生成或发布订阅。逐候选证据位于 `tmp/live-check/report.json`，逐频道原因位于 `tmp/live-check/summary.md`。首轮是在添加全局 1 GiB 读取限额之前运行；后续生成轮已启用该限额。

第二轮独立真实生成命令：

```bash
.venv/bin/python -m iptv_clean --publish-local --dns alidns --history-report tmp/live-check/report.json --output-dir tmp/site --report-dir tmp/local-build
.venv/bin/python scripts/check_outputs.py tmp/site
```

生成时间 **2026-10-20 22:03:52（北京时间）**，耗时 **645.557 秒（约 11 分钟）**，读取 HTTP 数据 **675,899,827 字节（约 644.6 MiB）**，低于全局 1 GiB 限额。82 个历史合格候选被优先安排，但均需本轮重新检查。实际检测 276 条、135 条进入深测、84 条通过；后端去重及每台最多两条选出 **46 台、77 条线路**。最终选中线路中 **56 条 1080、21 条 720**。

`tmp/site/live.m3u` 为 **46 条主线**，`backup.m3u` 为 **77 条主备记录**；均通过 `check_outputs.py` 的逐条格式/本轮检测证据校验。报告及状态页一并生成到 `tmp/site/`，诊断在 `tmp/local-build/report.json`、`summary.md`。这轮产物只用于本地验收，未上传；后续上线使用 M4 独立云端重新验证的版本。

本轮缺失 **CCTV5+、CCTV10、河北卫视、甘肃卫视**；部分首轮通过的线路复测超时或失败，没有沿用，说明免费公开源结果会随时间变化。两个检测轮次均不是 GitHub Runner 或电视验收，不能用首轮 48 台覆盖本轮 46 台的实际结果。

## M4：部署与公网验证完成，电视人工验收待进行

已准备同一工作流的每日/手动检测、质量门禁、Pages artifact、部署、真实 HTTPS 内容比对、成功后归档和诊断工件。官方 Actions 均固定经过官方 tag 核对的完整 SHA；工作流 YAML、所有 shell 片段语法检查通过，Python 编译检查通过。

用户在本轮明确授权推送到 `LeoSun0223/TTTVVV`、启用 Pages 并运行首次发布。现有 GitHub CLI 已登录正确账号，无需新登录；远端确认为空公开仓库。SSH 推送被现有 deploy key 拒绝后，改用该公开仓库的 HTTPS remote 和现有 `gh` 凭据完成推送，没有变更 SSH 密钥或 GitHub 全局权限。

真实运行：[Actions 39452035213](https://github.com/LeoSun0223/TTTVVV/actions/runs/39452035213)，整体 **success**，耗时 **13 分 48 秒**。Ubuntu Runner / Python 3.12.15 上 **82 passed in 1.45s**。云端检测使用系统 DNS，报告明确标记 `environment.location=github-actions`。

独立云端检测耗时 **723.736 秒**，925 条候选中实际检测 348 条、145 条进入深测、91 条通过；去重/选优后发布 **47 台主线、77 条主备线路**，其中 **59 条 1080P、18 条 720P**。读取 HTTP 数据 **680,406,094 字节（约 648.9 MiB）**，未超过 1 GiB 限额。本轮缺失 **CCTV5+、CCTV10、甘肃卫视**。未测试候选明确标记，未沿用本地结果代替云端复测。

生成时间 **2026-10-21 00:03:05**，部署和公网校验成功后于 **00:03:55** 归档（北京时间）。`output/` 已由 bot 提交，包含本次真实发布版本和 `_deployment.json`。门禁、上传、部署、HTTPS 校验及归档各步骤均成功。

真实 HTTPS 地址已由 Runner 和本机分别校验 HTTP 200，内容与 `output/` 逐字节一致：

| 文件 | 真实地址 | SHA-256 |
| --- | --- | --- |
| 主线 | [live.m3u](https://leosun0223.github.io/TTTVVV/live.m3u) | `97e942dfa554037a83b10ca1ec5e71baa394fc0906ae8b00a1fcbf607087b8bc` |
| 主备 | [backup.m3u](https://leosun0223.github.io/TTTVVV/backup.m3u) | `764bafb2707dc46a84a93af984f38197c055f6016a65ab1d23a1225eca91d762` |
| 报告 | [report.json](https://leosun0223.github.io/TTTVVV/report.json) | `343f52735585be2592dfa4d2c6ade1fdeb64a370ed527cac05fc24ad950d2e27` |

本机复核命令为 `.venv/bin/python scripts/verify_site.py https://leosun0223.github.io/TTTVVV/ --expected-dir output --dns alidns`；`check_outputs.py output` 再次确认 47 条主线和 77 条主备均能对应本轮连续性/片段/画质证据。完整云端诊断下载到 `tmp/cloud-first-run/diagnostics/`，日志保存到 `tmp/cloud-first-run/job-complete.log`。

**尚未完成：** Redmi X65 的 TiviMate 家庭网络人工导入与观看验收。见 [电视验收表](TV_ACCEPTANCE.md)。开发机和 Runner 不能代填；没有承诺电视端完全不卡或自动无缝切换备用。

完整源不可由本项目修复；已实现历史冻结源的自动识别、剔除及阻止错误发布，不宣称所有频道永久流畅。
