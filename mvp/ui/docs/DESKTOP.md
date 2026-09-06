# Electron 桌面壳

渲染层（Vue）**不依赖** Electron 也能运行（`npm run dev` / `npm run build`）。
Electron 是原生窗口 + **Python 后端生命周期管理**的外壳，默认不参与渲染层的类型检查
（见 `tsconfig.desktop.json` 与 `tsconfig.desktop.build.json`）。

## 组成

```
electron/
├── main.ts               # BrowserWindow + 后端生命周期接入 + `backend:request` IPC 桥
├── preload.ts            # contextBridge 暴露 window.desktop + window.backend（renderer→main）
├── backend/
│   ├── config.ts         # host/port/health path + 打包 python 路径（不散落 magic string）
│   ├── health.ts         # /api/health 轮询，超时抛 BackendStartError
│   ├── process.ts        # spawn + stdio 管道注入 spawnFn（可测试）
│   ├── manager.ts        # BackendManager：start/stop/restart/waitForHealth + 状态机
│   ├── bridge.ts         # renderer→main 后端请求桥（buildBackendBridge / createBackendRequestHandler）
│   ├── index.ts          # 统一导出（main 只 import 这里，不碰内部模块）
│   └── tests/            # vitest（注入 fake，不起真实 Python / 不联网）
└── (资源) resources/backend/  # 生产打包的 python（见其 README）
```

## renderer → 后端请求桥（避免 file:// CORS）

- `preload.ts` 暴露 `window.backend`：`request(path, {method, body})` / `health()`。
  它们经 `ipcRenderer.invoke('backend:request', payload)` 到主进程。
- `main.ts` 注册 `ipcMain.handle('backend:request', ...)`，用 **Node fetch** 打到
  `http://127.0.0.1:8765{path}`，再把标准化 `BridgeResponse` 回给 renderer。**renderer
  从不直接访问 localhost**，因此打包后的 `file://` 页面不再受 FastAPI 桥 CORS 拦截。
- renderer 侧 `HttpServiceAdapter` 通过 `services/transport.ts` 择路：检测到
  `window.backend`（Electron）→ 走桥；否则（纯浏览器 dev）→ 直接 `fetch`（后者正是
  FastAPI CORS 放行 localhost:5173/5174 的场景）。
- `window.backend.websocket(taskId, onEvent, onClose)`：实时任务进度订阅，经主进程（Node
  WebSocket 连 FastAPI `/ws/progress/{task_id}`）把进度帧转发给 renderer——打包 `file://`
  页不自己开本地 socket。renderer 侧 `services/progressSocket.ts` 择路：Electron→bridge，
  否则原生 `WebSocket`。
- 安全：桥只接受本地绝对路径（禁 scheme / 协议相对 URL）、方法白名单
  GET/POST/PUT/DELETE/PATCH；不暴露 child_process / fs / 任意 node API。
- **UI 任务管线**：`analysis` store 用任务式流程（`startAnalyzeTask` → `subscribeProgress` →
  `completed` 后取 result），`ProgressPipeline.vue` 显示真实阶段进度 + elapsed + cancel。


## 后端生命周期

- **dev 模式**（未打包，`app.isPackaged === false`）：不 spawn Python。主进程启动时
  `checkDevBackend()` 快速探测 `HTTP 127.0.0.1:8765/api/health`；开发者自行
  `uvicorn mvp.api.main:app --port 8765`。离线则弹「Backend offline」提示，窗口仍打开
  （渲染层独立显示 OFFLINE）。
- **prod 模式**（打包，`app.isPackaged === true`）：`startBackend()` 用
  `child_process.spawn` 启动 `resources/backend/backend.exe`（PyInstaller onedir 单进程入口，
  内部 `uvicorn.run`），`stdio: pipe` 捕获 stdout/stderr 写入 Electron runtime log，
  `env` 注入 `MEDIA_FFMPEG`/`MEDIA_FFPROBE` 指向打包内的 `ffmpeg.exe`/`ffprobe.exe`；
  `waitForHealth()` 每 500ms 轮询、最多 30s；失败则弹「Backend failed to start」对话框。
- **关闭**：`before-quit` → `stopBackend()`（同步 kill，无 Python 残留）。

## 开发 / 打包

`npm install` 默认**不会**执行 electron 的 postinstall（npm 11 的 allow-scripts
安全门拦了 `node install.js`，且 Electron 二进制从 GitHub 下载会被本机网络拦）。

```bash
# 1) 允许 electron 的 postinstall 脚本（npm 11 安全门）
npm approve-scripts electron        # 或按提示 npm approve-scripts --allow-scripts-pending

# 2) 用 npmmirror 镜像下载 Electron 二进制（避免 GitHub 443 被拦）
export ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
npm rebuild electron

# 3) 编译 electron/ TS → out/electron（CommonJS）
npm run compile:electron

# 4a) 开发运行（渲染层用 vite dev，先另起 `npm run dev`；主进程自动加载 localhost:5173）
npm run electron:dev

# 4b) 或手动：VITE_DEV_SERVER_URL=http://localhost:5173 npx electron out/electron/main.js

# 5) 打包
npm run build:electron
```

> `main` 字段指向 `out/electron/main.js`（CommonJS）。编译前 `main.js` 不存在属正常
> （不跑 Electron 则无碍）。渲染层由 vite 构建为 ESM（`dist/`）；Electron 主进程/proload
> 编译为 CommonJS（`out/electron/`），两者互不冲突。

## 当前状态

- 渲染层已接通（三栏工作台 + 关键页面 + 自定义 Fluent 组件），mock 数据可跑通。
- **后端生命周期管理已实现**（`electron/backend/`）：dev 探测 / prod spawn + health /
  graceful shutdown。
- **renderer→后端请求桥已实现**（`preload.ts` + `main.ts` `backend:request` + `bridge.ts`）：
  打包后 `file://` 页面经主进程 Node fetch 直达 FastAPI，绕开 CORS。
- vitest 54 项全过（renderer + electron），`npm run typecheck / build / test` +
  `typecheck:desktop` + `compile:electron` 全绿。

## CORS 说明

- 生产（打包，`file://`）：renderer 走 `window.backend` 桥 → 主进程 fetch，**不触发**浏览器
  CORS，故后端无需为此放行。
- 纯浏览器 dev（无 Electron 的 `vite dev` 页面直接打开）：renderer 直接 `fetch`，需 FastAPI 桥
  CORS 放行 `localhost:5173`/`5174`——桥已配置，保持不变。

