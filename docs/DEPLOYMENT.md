# 部署与维护

本步骤涉及公开直播 URL 和 GitHub 写操作。须先由用户明确确认使用 `LeoSun0223/TTTVVV` 推送代码、启用 Pages 并运行发布；开发阶段仅准备文件。不要发送密码、Cookie 或 token 到聊天。

## 首次部署（确认后操作）

1. 在 GitHub 打开 `LeoSun0223/TTTVVV`，确认仓库可见性和内容。当前准备针对用户已建的空仓库；若远程已有提交，先 fetch 并整合，不覆盖、不 force push。
2. 本地若未登录，用 `gh auth login` 的浏览器流程登录；只有确认后才执行。Git 已初始化，remote 可设置为 `git@github.com:LeoSun0223/TTTVVV.git`。提交默认使用中文信息，推送 `main`。如 SSH 尚未配置，可在用户同意的 GitHub CLI 登录流程中按账户现状选择协议；此项目不部署 NAS。
3. 仓库 Settings → Actions → General：确认允许运行仓库中的官方 Actions，允许此工作流以 `contents: write` 归档 `output/`。分支保护若拒绝 bot 直接提交，需用户自行决定允许相应写入或调整归档方案，不擅自关闭保护。
4. Settings → Pages → Build and deployment → Source 选择 **GitHub Actions**。必要的最小权限已在工作流任务内声明：`contents: write`、`pages: write`、`id-token: write`；不需要另建个人 token。
5. Actions → “每日检测并发布 IPTV” → Run workflow → 选择默认分支。工作流先跑离线测试，再进行真实直播检测，失败则停在门禁。诊断在 Run 的 Summary 和 `iptv-diagnostics-运行ID` artifact 中。
6. 只有门禁通过，才会配置 Pages、上传完整 artifact、部署并校验公网 HTTPS 文件内容；成功后 bot 将同一版本归档到 `output/` 并提交。检查 Actions 整体成功和 Pages 部署记录。
7. 使用部署步骤真正返回的 `page_url`，执行下面的只读校验；以此确认上线，不凭仓库名称推测成功。

```bash
python scripts/verify_site.py '实际部署返回的 HTTPS 站点根地址' --expected-dir tmp/site
```

本仓库已于 **2026-10-21** 完成首次部署，并由 Runner 和本机验证 HTTP 200、内容与归档一致。真实订阅：[live.m3u](https://leosun0223.github.io/TTTVVV/live.m3u)，对应 [成功的 Actions 运行](https://github.com/LeoSun0223/TTTVVV/actions/runs/39452035213)。不要把 GitHub 网页里的文件页或 Mac 本地路径输入电视。后续部署仍应按实际返回地址与内容校验，不凭名称推测成功。

## 每日更新与诊断

- 工作流只在默认分支运行，计划 UTC 23:17（北京时间次日 07:17），可随时手动运行。并发组排队，避免两个发布交错。
- 全局检测预算 22 分钟，任务总超时 40 分钟（含安装、测试和部署）；每主机请求并发最多 2。
- 第一次至少 10 个合格频道且有央视、卫视。以后低于上次 70% 或不足基本门槛时整版不部署；上次成功 Pages 保持不变，日志明确失败。
- `report.json` 的 `environment.location` 在 Runner 上必须是 `github-actions`，不能写成杭州电信。`generated_at` 表示该版本检测时间；仓库 `output/_deployment.json` 的 `published_at` 才是访问校验成功后的归档时间。
- 如 HTTPS 校验或归档 push 在 Pages 部署之后失败，站点可能已是新版本，但整个运行标为失败；根据 Pages 部署记录及公开文件与 artifact 比对确认状态。不要将此类失败误称检测失败，也不要强制推送覆盖开发者提交。
- GitHub 计划任务可能延迟，公开仓库长期无活动可能停用；检查默认分支、Actions 是否启用和最近成功日期，必要时手动 Run workflow。

## 回滚

检测失败本身不需要回滚：失败发生在上传 artifact 前，Pages 保留原版本。

如需要人工回滚已部署的版本，在 Git 历史查找已成功归档的 `output/` 提交，将这次提交的整个 `output/` 导出到本地独立目录，核对 `_deployment.json` 与直播源是否仍然有效。旧地址不保证今天可用。优先重新执行真实检测生成当前有效版本；若用户明确授权发布历史版本，另做一次人工 Pages artifact 部署并标记“历史版本，未通过今日复测”，不能把它伪装成今日更新。原自动流程从不无条件发布历史地址。

## 来源及官方依据

- [GitHub Pages 自定义工作流](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [Actions schedule 事件](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)

所有 action SHA 在开发时通过各官方仓库的版本 tag 读取核对；更新版本时重新核对官方来源和 Node/Runner 兼容性。
