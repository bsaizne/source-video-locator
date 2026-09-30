# 打包端到端验收记录（2026-09-28 续20/续21，Windows 发行包）

> 验收对象 = `mvp/ui/release/win-unpacked/Video Locator.exe`（PyInstaller 后端 + Electron dir 包，
> 构建于 2026-09-28 16:3x，含续14~续20 全部改动）。驱动方式 = `--remote-debugging-port` CDP
> （截图/求值/点击）+ UIAutomation 驱动原生对话框；产物与截图在 `work/ui_accept/`。
> 素材 = `datasets/synthetic`（source.mp4 90s + a1.mp4 5s，GT=direct crop 20–25s，**验收夹具**，
> 不进三指标）。

## 结论：**通过**（3 个真缺陷现场修复后复验）

| # | 验收项 | 结果 | 证据 |
|---|---|---|---|
| 1 | 发行闸门负例：release 缺令牌拒启 | ✅ exit=1 + `ConfigError: release build requires SVL_SESSION_TOKEN` | 直接跑包内 backend.exe |
| 2 | 随机端口公告 | ✅ `SVL_BACKEND_PORT=0` → 主进程日志 `backend announced listen 127.0.0.1:<随机>`，页面 query 带 `svl_port` | main_console.log + targets.json |
| 3 | 本机 API 门禁 | ✅ `/api/health` 200 放行；`/api/media/info` 无令牌 401（LOC-1201 话术）、带令牌 200 实测元数据 | curl 实测 |
| 4 | 新建项目=先选文件；取消不创建 | ✅ 对话框弹出（原生"选择视频文件"）；取消后项目数=0 | CDP 点击 + UIA 关闭 |
| 5 | 元数据回填 | ✅ 详情页 时长 1m30s / 1280×720 / 30fps / 8.6MB（包内 ffprobe 实测） | detail.png |
| 6 | 分析全流程（打包态） | ✅ 索引 90 帧 `backend=directml` 0.8s；locate 29.3s；结果 1 段 HIGH 0.99 | video_locator.log |
| 7 | 预览直链（video 元素） | ✅ readyState=4、无 error、剪辑/原片画面逐图核对为同一彩条内容 | final_run.png |
| 8 | 导出四格式 | ✅ 剪映草稿（draft_content/meta + 素材 mp4，cbed284 防回归通过）/ FCP7 XML（clipitem in=660=22s×30fps）/ EDL / results.json | export_out/ |
| 9 | 错误条幅 | ✅ 杀 backend 后点分析 → 红色条幅、不崩、工作流复位 | err_banner.png |
| 10 | vote_prior 打包态生效 | ✅ `offset vote prior applied 1/1`（seed 19.6s）→ 窗口 22–24 变 **19–24 完整覆盖 GT** | 新包复跑日志 |

## 现场发现并修复的 3 个真缺陷（不修则打包态必炸）

1. **bundle 桥层漏收（启动即崩）**：`run_backend.py`/`backend.spec` 走 `mvp.api` 命名空间，能否收全
   取决于构建时 cwd；本次构建 cwd=mvp/ui → PYZ 无任何 `api.*`，backend.exe `ModuleNotFoundError: mvp`。
   修复=入口/spec 改 bundle 正规**顶层 `api`** 形态（`collect_submodules("api")` + try/except 双形态）。
   教训：过去"打包验证通过"隐含 cwd 运气，非受控事实。
2. **预览直链无令牌**：`/api/preview/media|edited` 不在放行清单，而 `<video src>` 无法带头 → 发行态预览
   全黑（MEDIA_ERR 4）。修复=`previewResult`/`getEditedVideoUrl` 拼 `svl_session` query（vitest 回归）。
3. **构建期 VITE_API_BASE 压过运行时 svl_port**：`.env.production` 钉死 8765，`resolveService` 又把它
   当构造参数传入 → 渲染层直连 URL 全指 8765。修复=`readBackendBootstrap` 与构造函数均**运行时端口优先**
   （vitest 双回归）。

## 遗留观察（不阻塞验收，已登记 TODO）

- 网络级失败条幅是英文技术串（`cannot reach backend: fetch failed`）——非 2xx 话术路径之外，待补中文话术；
- 后端被杀后侧栏"已连接"不重探（健康状态无轮询）；
- LOC-2001 碎片告警 UI 路径本轮未自然触发（单测+API 测试已锁契约）；
- 剪映草稿的**应用内双击**最终确认仍属用户动作（文件级结构已验）；
- `edited_cache` 目录 fsync 在 Windows 静默跳过（续19 表述偏乐观，已在档案更正）；
- 本机 userData 留有验收项目 `acc-source` 与合成索引（无害，可手动删）。
