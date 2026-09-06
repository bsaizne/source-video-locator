// Preload — the only bridge between the sandboxed renderer and the host.
// Exposes a minimal, safe API surface and nothing else:
//   - `window.desktop` : platform/versions (informational).
//   - `window.backend` : request/health, routed via IPC to the main process,
//     which does the actual Node fetch to the local FastAPI backend. This keeps
//     the renderer from ever talking to localhost directly (so a packaged `file://`
//     page works despite CORS) and never exposes child_process or fs.
import { contextBridge, ipcRenderer, webUtils } from 'electron'
import { buildBackendBridge, type BackendIpc } from './backend/bridge'

const api = {
  platform: process.platform,
  versions: {
    chrome: process.versions.chrome,
    node: process.versions.node,
    electron: process.versions.electron,
  },
  /** User data paths (Phase 4) — the renderer shows the log dir for diagnostics. */
  getPaths: () => ipcRenderer.invoke('app:paths'),
  openPath: (target: string) => ipcRenderer.invoke('app:openPath', target),
  /** Native file picker for a video — returns the absolute path, or null if cancelled. */
  openFile: () => ipcRenderer.invoke('app:openFile'),
  openDirectory: () => ipcRenderer.invoke('app:openDirectory'),
  /** Absolute path of a File dropped into the renderer (for video import). */
  getPathForFile: (file: File) => webUtils.getPathForFile(file),
}

contextBridge.exposeInMainWorld('desktop', api)
contextBridge.exposeInMainWorld('backend', buildBackendBridge(ipcRenderer as unknown as BackendIpc))
