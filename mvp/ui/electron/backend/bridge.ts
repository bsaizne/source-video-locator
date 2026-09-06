// Backend request bridge — the transport between the sandboxed renderer and the
// FastAPI backend, routed through the Electron main process.
//
// Pure Node (no `electron` import), so both halves are unit-testable in Vitest:
//   - buildBackendBridge(ipc)            -> the object preload exposes as `window.backend`
//   - createBackendRequestHandler(...)   -> the main-process handler for `backend:request`
// The main process does the actual fetch (Node), so the renderer never talks to
// localhost directly — which removes the CORS restriction a `file://` page hits.
import type { BackendConfig } from './config'

export interface BridgeRequestPayload {
  /** Local backend path, e.g. `/api/health`. Must start with `/` (never a full URL). */
  path: string
  method?: string
  /** Raw JSON body (a string from the renderer; an object is JSON.stringified). */
  body?: unknown
}

export interface BridgeResponse {
  ok: boolean
  status: number
  data?: unknown
  error?: string
  detail?: string
  /** true when the request never reached the backend (network-level failure). */
  network?: boolean
}

/** The API surface preload exposes to the renderer as `window.backend`. */
export interface BackendBridge {
  request(path: string, options?: { method?: string; body?: unknown }): Promise<BridgeResponse>
  health(): Promise<BridgeResponse>
  /** Real-time task progress WS, proxied by the main process (no localhost from renderer). */
  websocket(taskId: string, onEvent: (event: unknown) => void, onClose?: () => void): { close(): void }
}

type IpcInvoker = (channel: string, payload: BridgeRequestPayload) => Promise<BridgeResponse>
type IpcListener = (event: unknown, payload: unknown) => void

/** The minimal ipc the preload bridge needs (a subset of Electron's ipcRenderer). */
export interface BackendIpc {
  invoke: IpcInvoker
  on(channel: string, listener: IpcListener): void
  send(channel: string, payload: unknown): void
  removeListener?(channel: string, listener: IpcListener): void
}

// Minimal fetch shape so the handler is testable with a stub (no real network).
type FetchLike = (
  url: string,
  init?: { method?: string; headers?: Record<string, string>; body?: string },
) => Promise<{ ok: boolean; status: number; json(): Promise<unknown> }>

const ALLOWED_METHODS = new Set(['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])

/** Only accept a local absolute path (e.g. `/api/health`) — never a scheme or
 *  protocol-relative URL, so the bridge can't be used to reach arbitrary hosts. */
function normalizePath(path: string): string | null {
  if (typeof path !== 'string') return null
  const p = path.trim()
  if (!p.startsWith('/')) return null
  if (p.startsWith('//')) return null // protocol-relative //host/...
  if (/:\/\//.test(p)) return null // scheme://  (http://, ws://, ...)
  return p
}

/** Build the object preload exposes as `window.backend`. */
export function buildBackendBridge(ipc: BackendIpc): BackendBridge {
  return {
    request: (path, options) =>
      ipc.invoke('backend:request', {
        path,
        method: options?.method ?? 'GET',
        body: options?.body,
      }),
    health: () => ipc.invoke('backend:request', { path: '/api/health', method: 'GET' }),
    websocket: (taskId, onEvent, onClose) => {
      const id = `ws-${Math.random().toString(36).slice(2)}`
      const onMessage: IpcListener = (_e, payload) => {
        const p = payload as { id?: string; data?: string } | null
        if (!p || p.id !== id || p.data == null) return
        try {
          onEvent(JSON.parse(p.data))
        } catch {
          onEvent(p.data)
        }
      }
      const onClosed: IpcListener = (_e, payload) => {
        const p = payload as { id?: string } | null
        if (!p || p.id !== id) return
        ipc.removeListener?.('backend:ws:message', onMessage)
        ipc.removeListener?.('backend:ws:close', onClosed)
        onClose?.()
      }
      ipc.on('backend:ws:message', onMessage)
      ipc.on('backend:ws:close', onClosed)
      ipc.send('backend:ws:open', { id, taskId })
      return {
        close() {
          ipc.send('backend:ws:client-close', { id })
        },
      }
    },
  }
}

/** Build the main-process `backend:request` IPC handler. Fetches the local backend
 *  and normalises the reply to a BridgeResponse (never throws). */
export function createBackendRequestHandler(
  config: BackendConfig,
  fetchImpl: FetchLike = (globalThis as unknown as { fetch: FetchLike }).fetch,
): (payload: BridgeRequestPayload) => Promise<BridgeResponse> {
  return async (payload) => {
    const path = normalizePath(payload?.path)
    if (!path) {
      return {
        ok: false,
        status: 0,
        error: 'invalid_path',
        detail: 'path must be a local absolute path like /api/health',
      }
    }
    const method = (payload?.method ?? 'GET').toUpperCase()
    if (!ALLOWED_METHODS.has(method)) {
      return { ok: false, status: 0, error: 'invalid_method', detail: `method ${method} not allowed` }
    }

    const url = `http://${config.host}:${config.port}${path}`
    const body =
      typeof payload?.body === 'string'
        ? payload.body
        : payload?.body != null
          ? JSON.stringify(payload.body)
          : undefined

    let res: { ok: boolean; status: number; json(): Promise<unknown> }
    try {
      res = await fetchImpl(url, { method, headers: { 'content-type': 'application/json' }, body })
    } catch (err) {
      return {
        ok: false,
        status: 0,
        network: true,
        error: 'network',
        detail: err instanceof Error ? err.message : String(err),
      }
    }

    let data: { error?: string; detail?: string } | unknown = null
    try {
      data = await res.json()
    } catch {
      /* non-JSON body */
    }
    const bodyData = (data ?? {}) as { error?: string; detail?: string }
    if (!res.ok) {
      return {
        ok: false,
        status: res.status,
        error: bodyData.error,
        detail: bodyData.detail ?? `HTTP ${res.status}`,
      }
    }
    return { ok: true, status: res.status, data: bodyData }
  }
}
