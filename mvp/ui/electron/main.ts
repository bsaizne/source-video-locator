// Electron main process (CommonJS). The renderer (Vue) is the app; this owns the
// native window AND the Python backend lifecycle (see ./backend). Kept out of the
// renderer's strict typecheck via tsconfig.desktop.json so `npm run typecheck`
// stays green even before the electron binary is installed. See docs/DESKTOP.md.
import { app, BrowserWindow, shell, dialog, ipcMain, clipboard } from 'electron'
import * as path from 'node:path'
import { randomBytes } from 'node:crypto'
import * as fs from 'node:fs'
import {
  BackendManager,
  createBackendConfig,
  prodBackendConfig,
  createBackendRequestHandler,
  type BackendMode,
} from './backend'

// CommonJS gives us `__dirname` directly (no fileURLToPath(import.meta.url) dance).

// Packaged app → spawn the bundled python (prod). Unpacked dev → health-check an
// already-running backend (the developer runs `uvicorn mvp.api.main:app --port 8765`).
function resolveMode(): BackendMode {
  return app.isPackaged ? 'prod' : 'dev'
}

const backendConfig = app.isPackaged ? prodBackendConfig(process.resourcesPath) : createBackendConfig()

// --- User data directory (Phase 4) ------------------------------------------
// All runtime data lives under Electron's userData — never in Program Files.
// The Python backend reads SVL_DATA_DIR (infrastructure.paths.app_data_dir) and
// SVL_LOG_DIR (infrastructure.logging.configure_logging), so we point them here
// *without* touching mvp/src. Only takes effect when we spawn (prod); in dev the
// developer runs uvicorn with their own env.
const userData = app.getPath('userData')
const dataDir = path.join(userData, 'data')
const logsDir = path.join(userData, 'logs')
for (const d of [dataDir, logsDir]) fs.mkdirSync(d, { recursive: true })
backendConfig.spawnEnv = {
  ...backendConfig.spawnEnv,
  SVL_DATA_DIR: dataDir,
  SVL_LOG_DIR: logsDir,
}

// --- 本机 API 门禁 (T1-3) ---------------------------------------------------
// 打包态 = 发行通道：每次启动生成一次性会话令牌注入后端，并由后端强制校验
// （缺令牌时后端直接拒启，不静默降级为无鉴权服务）。开发态由开发者自己跑
// uvicorn，不注入令牌 = 门禁关闭，本地手工调试不受影响。
const sessionToken = app.isPackaged ? randomBytes(24).toString('base64url') : ''
if (sessionToken) {
  backendConfig.spawnEnv.SVL_SESSION_TOKEN = sessionToken
  backendConfig.spawnEnv.SVL_BUILD_CHANNEL = 'release'
}
// --- 随机端口 (续20, T1-3 接线补全) ------------------------------------------
// 打包态让 OS 分配端口（backend.exe 走 SVL_BACKEND_PORT=0），真实监听地址由后端
// 绑定成功后打印的 BACKEND_LISTEN 公告回报（manager 解析并据此做健康检查）。
// config.port 此时置 0 = "必须等公告"；bootstrap 成功后回填真实 host/port，
// bridge/WS/页面 query 全部走该真实值。开发态不 spawn，维持固定 8765。
if (app.isPackaged) {
  backendConfig.spawnEnv.SVL_BACKEND_PORT = '0'
  backendConfig.port = 0
}
// Ship the DirectML/CPU ONNX model with the app (resources/models) and point the
// backend at it via SVL_DML_MODEL — so GPU (DirectML) works out of the box, and
// the model never needs to be at the (userData) data dir. Dev resolves its own.
if (app.isPackaged) {
  backendConfig.spawnEnv.SVL_DML_MODEL = path.join(
    process.resourcesPath, 'models', 'dinov2_cls_384', 'dinov2_cls_384.onnx')
  // CPU backend uses the original torch weights; ship them so CPU also works in
  // the packaged app (DirectML uses the ONNX above; CPU needs this .pth).
  backendConfig.spawnEnv.SVL_DINOV2_WEIGHTS = path.join(
    process.resourcesPath, 'models', 'dinov2_vits14', 'dinov2_vits14_pretrain.pth')
}

const backend = new BackendManager({
  config: backendConfig,
  mode: resolveMode(),
  log: (msg) => console.log(`[backend] ${msg}`),
})

// Expose paths to the renderer (for the error dialog's "打开日志目录" + context).
ipcMain.handle('app:paths', () => ({ userData, data: dataDir, logs: logsDir }))
ipcMain.handle('app:openPath', (_event, target: string) => shell.openPath(target))
// Open a native file picker for a video; returns the absolute path or null. This
// is how the renderer sets the source/edited video to a real absolute path (the
// fix for "源片存成了裸文件名导致构建索引失败").
ipcMain.handle('app:openDirectory', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog({
    title: '选择目录',
    properties: ['openDirectory'],
  })
  return canceled || filePaths.length === 0 ? null : filePaths[0]
})

// Open a native file picker for a video; returns the absolute path or null. This
// is how the renderer sets the source/edited video to a real absolute path (the
// fix for "源片存成了裸文件名导致构建索引失败").
ipcMain.handle('app:openFile', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog({
    title: '选择视频文件',
    properties: ['openFile'],
    filters: [{ name: '视频', extensions: ['mp4', 'mkv', 'mov', 'avi', 'webm', 'm4v', 'ts', 'flv', 'wmv'] }],
  })
  return canceled || filePaths.length === 0 ? null : filePaths[0]
})

// 多原片选择（2026-09-29 续27 video.concat 移植的 UI 入口）：一次框选多集/多段母片。
// 返回**用户选择顺序**的绝对路径数组；取消 = 空数组（调用方据此不改状态）。
// 顺序有意义：合并是按时序拼接（ep1+ep2），乱序选会得到不同的时间轴。
ipcMain.handle('app:openFiles', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog({
    title: '选择多个源片文件（按播放顺序）',
    properties: ['openFile', 'multiSelections'],
    filters: [{ name: '视频', extensions: ['mp4', 'mkv', 'mov', 'avi', 'webm', 'm4v', 'ts', 'flv', 'wmv'] }],
  })
  return canceled ? [] : filePaths
})

// Renderer -> main -> Node fetch -> FastAPI. The renderer never hits localhost
// directly (no CORS issue for the packaged file:// page). The listener is wrapped
// because ipcMain.handle passes (event, ...args); we only need the payload.
const handleBackendRequest = createBackendRequestHandler(backendConfig)
ipcMain.handle('backend:request', (_event, payload) => handleBackendRequest(payload))

// --- Real-time progress WS proxy: renderer -> main -> FastAPI /ws/progress/{task_id}.
// The renderer never opens a localhost socket; the main process forwards frames.
const WSImpl = (globalThis as { WebSocket?: new (url: string) => unknown }).WebSocket
if (WSImpl) {
  const wsMap = new Map<string, { close(): void }>()
  ipcMain.on('backend:ws:open', (event, payload) => {
    const { id, taskId } = payload as { id: string; taskId: string }
    const url = `ws://${backendConfig.host}:${backendConfig.port}/ws/progress/${encodeURIComponent(taskId)}`
    const ws = new WSImpl(url) as {
      onopen: (() => void) | null
      onmessage: ((ev: { data: unknown }) => void) | null
      onclose: (() => void) | null
      onerror: (() => void) | null
      close(): void
    }
    wsMap.set(id, ws)
    ws.onopen = () => console.log(`[backend] ws open ${id} (${taskId})`)
    ws.onmessage = (ev) => event.sender.send('backend:ws:message', { id, data: String(ev.data) })
    ws.onclose = () => {
      event.sender.send('backend:ws:close', { id })
      wsMap.delete(id)
    }
    ws.onerror = () => {
      /* close will follow */
    }
  })
  ipcMain.on('backend:ws:client-close', (_event, payload) => {
    const { id } = payload as { id: string }
    const ws = wsMap.get(id)
    if (ws) {
      ws.close()
      wsMap.delete(id)
    }
  })
} else {
  console.warn('[backend] global WebSocket unavailable; progress WS proxy disabled')
}

// Dev run: load the Vite dev server if running, else fall back to the built dist.
function devServerUrl(): string | undefined {
  return process.env.VITE_DEV_SERVER_URL ?? (app.isPackaged ? undefined : 'http://localhost:5173')
}

function createWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1080,
    minHeight: 680,
    backgroundColor: '#111111',
    title: 'Video Locator AI',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  // 令牌/端口经页面 query 交给渲染进程（HttpServiceAdapter.readBackendBootstrap 读取）
  const query: Record<string, string> = {}
  if (sessionToken) query.svl_session = sessionToken
  if (backend.listenPort) query.svl_port = String(backend.listenPort)
  const url = devServerUrl()
  if (url) {
    const target = new URL(url)
    for (const [k, v] of Object.entries(query)) target.searchParams.set(k, v)
    void win.loadURL(target.toString())
  } else {
    void win.loadFile(path.join(__dirname, '../../dist/index.html'), { query })
  }

  return win
}

async function bootstrap(): Promise<void> {
  if (backend.mode === 'prod') {
    try {
      await backend.startBackend()
      await backend.waitForHealth()
      // 随机端口：公告解析成功 → bridge/WS/health 的活配置切到真实监听地址。
      const listen = backend.listen
      if (listen) {
        backendConfig.host = listen.host
        backendConfig.port = listen.port
        backendConfig.healthUrl = `http://${listen.host}:${listen.port}${backendConfig.healthPath}`
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      const { response } = await dialog.showMessageBox({
        type: 'error',
        title: 'AI 服务启动失败',
        message: 'AI 服务启动失败',
        detail: `可能原因：\n- 后端文件损坏\n- 模型初始化失败\n- 系统资源不足\n\n日志位置：\n${logsDir}\n\n错误信息：\n${msg}`,
        buttons: ['打开日志目录', '重新启动', '复制错误信息'],
      })
      if (response === 0) void shell.openPath(logsDir)
      else if (response === 1) { app.relaunch(); app.exit(0) }
      else if (response === 2) clipboard.writeText(msg)
    }
  } else {
    const ok = await backend.checkDevBackend()
    if (!ok) {
      void dialog.showMessageBox({
        type: 'warning',
        title: '后端离线',
        message: '本地后端未在运行。\n\n请用以下命令启动：\n\n  uvicorn mvp.api.main:app --port 8765',
      })
    }
  }
  createWindow()
}

app.whenReady().then(() => {
  void bootstrap()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('before-quit', () => {
  // Synchronous kill — no lingering Python even if the event isn't awaited.
  void backend.stopBackend()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

// Open external links in the OS browser, never inside the app.
app.on('web-contents-created', (_e, contents) => {
  contents.setWindowOpenHandler(({ url }) => {
    if (/^https?:/i.test(url)) void shell.openExternal(url)
    return { action: 'deny' }
  })
})
