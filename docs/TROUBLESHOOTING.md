# 故障排查

先看 `report.json` 的 `publish_gate`、`reason_counts`，再看对应频道的 `candidates`。`not_tested` 表示达到限额/预算或已有足够线路，不能当作已验证可用或不可用。缺失频道可能没有候选，也可能候选均被拒绝。

| 原因 | 含义及处理 |
| --- | --- |
| `unsafe_destination` | 域名、重定向或字面 IP 落入非公网地址，包括 Fake-IP。保持安全检查；可使用明确的 `--dns alidns` 本地复测，无需更改 OpenClash。公共 DNS 也返回私网则仍拒绝 |
| `dns_failed` / `connection_failed` / `http_timeout` | 本次网络无法解析/连接/及时读取，稍后重试，检查报告中的测试环境；不自动改代理 |
| `http_403/404/429/5xx` | 上游拒绝、下线或限流；跳过，不破解授权，不高频重试 |
| `credentialed_url` / `credentialed_or_header_dependent` | 发现签名/鉴权或特殊请求头依赖；不作为可持续公开订阅 |
| `not_m3u` / `not_hls` | HTML、非 HLS 或错误页面；扩展名和 200 都不能证明可播放 |
| `vod_endlist` | 结束流或点播，不作为直播 |
| `frozen_playlist` | 观察至少 30 秒仍未达到持续媒体前进要求，历史 3×8 秒冻结案例会被拒绝 |
| `repeated_segment` | 清单变化但首尾下载内容完全一致，疑似重复媒体 |
| `sequence_regression` | 观察期媒体序号倒退，可能切换节点或异常重启；保守拒绝 |
| `invalid_segment_media` / `resolution_unknown` | 非媒体数据、只有音频、损坏或 ffprobe 无法确认视频尺寸 |
| `resolution_below_minimum` | 真实视频低于 720，不降级成 360 备用 |
| `segment_too_slow` | 完整分片下载耗时达到片段播放时长，没有足够播放余量 |
| `response_too_large` / `download_budget_exceeded` | 超过读取/流量限制；不无限下载 |
| `unsupported_encryption` / `unsupported_hls` | 当前保守实现不支持此 HLS；加密与 DRM 不绕过，不能标为通过 |
| `ffprobe_missing` / `ffprobe_timeout` | 安装 ffprobe 或检查本地媒体解析；不以 manifest 的 RESOLUTION 替代 |
| `below_minimum_channels` / `missing_required_category` / `channel_count_regression` | 整版未通过质量门槛，旧版保持。先看逐频道失败原因，不为了上线随意降低阈值 |
| `baseline_invalid` | `output/` 上次归档缺失/损坏；从 Git 成功归档历史恢复，不能当成冷启动重置基线 |
| `run_budget_exhausted` / `precheck_limit` / `deep_limit` | 本轮未测到该候选。可缩小频道范围定位或合理调整时间/候选上限，不能当作通过 |

## 播放约 24 秒后冻结

旧浙江卫视案例固定 `MEDIA-SEQUENCE:359977910`，仅三个约 8 秒片段，播放器播完后没有新媒体。本系统不会通过域名提权保留它；`tests/fixtures/frozen_24s.m3u8` 和 `test_historical_24_seconds_freeze` 在每次 CI 中复现并验证剔除。

这修复的是错误地址入选与继续发布的逻辑，不能修复外部源站。通过 30～45 秒检测也不能承诺之后数小时正常。电视仍卡顿时，用 `--channels 频道名` 本地复测，并观察实际节目至少 5 分钟。免费版备用需手选，不会自动无缝切线。

## Pages 或 Actions 不成功

确认仓库 Pages Source 为 GitHub Actions、运行在默认分支、Pages environment 允许该分支、工作流权限具备声明所需权限。测试/门禁失败时不会部署；没有首次成功就没有可信在线订阅。

公网 `live.m3u` 必须 HTTP 200、以 `#EXTM3U` 开头且与本次 artifact 完全一致。`scripts/verify_site.py` 会同时校验主线、备用和报告，避免把旧 Pages 200 当作本次部署成功。若 bot 归档 push 遇到分支保护或其他提交，不 force push；先处理写权限或整合变更，检查 Pages 是否已部署。
