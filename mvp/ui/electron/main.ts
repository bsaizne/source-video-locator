// Electron main process (CommonJS). The renderer (Vue) is the app; this owns the
// native window AND the Python backend lifecycle (see ./backend). Kept out of the
// renderer's strict typecheck via tsconfig.desktop.json so `npm run typecheck`
// stays green even before the electron binary is installed. See docs/DESKTOP.md.
import { app, BrowserWindow, shell, dialog, ipcMain, clipboard } from 'electron'
import * as path from 'node:path'
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

  const url = devServerUrl()
  if (url) {
    void win.loadURL(url)
  } else {
    void win.loadFile(path.join(__dirname, '../../dist/index.html'))
  }

  return win
}

async function bootstrap(): Promise<void> {
  if (backend.mode === 'prod') {
    try {
      await backend.startBackend()
      await backend.waitForHealth()
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
