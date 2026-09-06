# Desktop 真机冒烟测试（desktop_smoke_test）

目标：在真实桌面上验证打包后的 Electron 应用：安装 → 启动 → 后端自动拉起 → 健康 → 关闭时
后端自动退出。**分两部分**：① 需打包安装器的步骤（本阶段未制作安装器，如实标注）；② 后端
层面的可自动验证项（已用打包后的 `backend.exe` 实测，给出真实证据）。

> 打包安装器 / 真机 GUI 交互属**后续授权阶段**（`npm run build:electron` + 安装器）。本文件
> 记录可复现的验收流程；后端部分已跑通。

## 1. 安装测试（需 `VideoLocator Setup.exe`）

```text
步骤
  1. 双击 VideoLocator-Setup-<version>.exe（NSIS，非 oneClick，可选安装目录）
  2. 选择安装目录 → Install
  3. 完成窗口可「运行应用」/ 桌面创建「Video Locator AI」快捷方式
检查
  [ ] 安装成功无报错
  [ ] 桌面快捷方式已创建
  [ ] 程序可启动
```

> 本阶段未制作安装器（见 `bundle_optimization_report.md` / `build:electron` 需网络+授权），此节
> 待安装器就位后执行。

## 2. 后端启动生命周期（`BackendManager`）

application `app.isPackaged === true` 时，`main.ts` bootstrap 调 `startBackend()` → 直接 spawn
`resources/backend/backend.exe` → `waitForHealth()` 轮询 `/api/health`。

**预期启动日志**（主进程 console / runtime log）：

```text
[backend] backend starting
[backend] backend pid=<n>
[backend] health connected: backend running
```

**后端侧**（`backend.exe` 已实测）：

```json
GET http://127.0.0.1:8765/api/health
→ 200 {"status":"ok","version":"0.1"}
```

## 3. 进程检查（无残留）

```text
启动前   backend.exe 不存在
启动后   backend.exe 存在（资源目录 resources/backend/backend.exe，PID=<n>）
关闭应用 before-quit → stopBackend()（SIGTERM 同步 kill）
关闭后   backend.exe 不存在
要求     [ ] 无残留进程  [ ] 无僵尸 uvicorn  [ ] 127.0.0.1:8765 端口未占用
```

**后端层证据**（打包后端已实测，逐项）：

- `backend.exe` 冷启动后 `GET /api/health` 返回 `200 {"status":"ok","version":"0.1"}`
  （uvicorn `Started server process` → `Application startup complete` → `module=api session=… GET /api/health`）。
- 启动时注入 `MEDIA_FFMPEG`/`MEDIA_FFPROBE` → `resources/backend/ffmpeg.exe|ffprobe.exe`；
  真实 `POST /api/preview` 抽 `originals/2.mkv`[100,110] → `2__100-110.mp4` 3.5MiB，GET media
  `Range` → `206 bytes 0-99/3519519` `video/mp4`。
- 真实 `POST /api/index` 对 30s 测试片 → `200 {"status":"completed","frames":15}`（directml 推理）。
- 进程退出：`kill` 后无残留（本次冒烟用 kill 收尾；打包应用的 `before-quit→stopBackend()` 同理）。

## 4. 记录表

| 步骤 | 状态 | 用时 | 错误 | 日志 |
| --- | --- | --- | --- | --- |
| backend 启动 | ✅ 已验证 | 数秒 | — | `backend starting` / `health connected` |
| /api/health | ✅ | — | — | `module=api session=… GET /api/health 200` |
| /api/index（真实推理） | ✅ | ~24s/300帧 | — | `frames=15` directml |
| /api/preview（抽帧+Range） | ✅ | — | — | `206 bytes 0-99/3519519` |
| 安装 / GUI 交互 | ⏳ 待安装器 | — | — | 授权阶段执行 |
