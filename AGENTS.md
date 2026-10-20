# IPTV 自动订阅系统

## 唯一需求与边界
- 唯一有效需求：`IPTV_Codex%E5%AE%8C%E6%95%B4%E4%BB%BB%E5%8A%A1%E5%8C%85_V3/IPTV_最终任务书_Codex版.md`（V3）。V1/V2 作废。
- Redmi X65、杭州电信、TiviMate 免费版一份订阅；仅 CCTV / 省级卫视，实际视频高度至少 720。
- Python 3.9+ 标准库 + ffprobe；pytest 用于测试。无 NAS、Docker、代理、后台或视频转发。
- 真实 HLS 前进、分片下载、实际分辨率均通过才能入选；域名、HTTP 200 和标称高清不能代替检测。
- 冻结/检测失败不得覆盖上次成功版本。首次至少 10 台且包含央视和卫视，更新不少于上次 70%。

## 当前状态与命令
- 开发分 M1 采集解析、M2 安全直播检测、M3 产物和发布门禁、M4 Actions/Pages。
- M1～M3 已完成，M4 于 2026-10-21 首次成功部署。Actions 39452035213 成功，82 项测试通过，首次云端 47 台/77 条线路；电视人工验收待进行。证据见 `docs/ACCEPTANCE.md`。
- 真实订阅：`https://leosun0223.github.io/TTTVVV/live.m3u`；以在线报告为准，不能把首次数量当永久保证。`output/` 为已发布版本，bot 已归档。
- `python3 -m venv .venv`；`.venv/bin/pip install -r requirements.txt`。
- `.venv/bin/pytest -q`；`.venv/bin/python -m iptv_clean --list-candidates`。
- `.venv/bin/python -m iptv_clean --dry-run --report-dir tmp/check`。
- 系统 DNS 返回保留地址时可明确选择 `--dns alidns`；不放宽 SSRF，不改系统网络。`--history-report` 只调整顺序，所有入选线路须本轮复测。
- 配置在 `config/`，代码在 `src/iptv_clean/`，网络实测与离线测试分离。

## 协作与权限
- 先检查 Git 状态，保留已有任务包和无关文件；提交信息默认中文。
- 本地开发测试已授权。GitHub 登录、推送、权限变更和公开发布须用户明确确认。
- 本轮用户已明确同意推送到 `LeoSun0223/TTTVVV`、启用 Pages 和首次发布，完成本任务不重复询问。新的无关权限/发布操作仍需确认。
- 不把预计 Pages URL 当成已上线；不把 Runner 通过当作家庭电视验收通过。
- 不记录凭据或敏感查询；报告写明环境和真实结果。仅成功发布的版本进入 `output/`。
