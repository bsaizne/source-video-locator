// Transport abstraction for HttpServiceAdapter — the single place that decides how
// renderer requests reach the FastAPI backend.
//
//   - Electron (preload injected `window.backend`)  -> bridge via the main process
//     (Node fetch). Bypasses CORS, so the packaged `file://` page works and the
//     renderer never talks to localhost directly.
//   - Anything else (plain browser dev on the Vite server) -> direct `fetch`, which
//     is what the FastAPI bridge CORS (localhost:5173/5174) is for.
//
// The ServiceAPI contract is untouched: this is purely a transport swap behind
// HttpServiceAdapter's existing `request`/`checkHealth` methods.

/** Normalised reply from either transport. `network` is true when the request never
 *  reached the backend. Mirrors the main-process BridgeResponse wire shape. */
export interface BridgeResult {
  ok: boolean
  status: number
  data?: unknown
  error?: string
  detail?: string
  network?: boolean
}

export interface BridgeRequestInit {
  method?: string
  body?: string
}

export interface Transport {
  request(path: string, init?: BridgeRequestInit): Promise<BridgeResult>
}

function fetchTransport(base: string): Transport {
  return {
    async request(path, init) {
      try {
        const res = await fetch(`${base}${path}`, {
          headers: { 'content-type': 'application/json' },
          method: init?.method ?? 'GET',
          body: init?.body,
        })
        let data: { error?: string; detail?: string } | unknown = null
        try {
          data = await res.json()
        } catch {
          /* non-JSON body */
        }
        const body = (data ?? {}) as { error?: string; detail?: string }
        return { ok: res.ok, status: res.status, data: body, error: body.error, detail: body.detail }
      } catch {
        return { ok: false, status: 0, network: true }
      }
    },
  }
}

function bridgeTransport(): Transport {
  return {
    async request(path, init) {
      try {
        // window.backend.request goes: renderer -> IPC -> main Node fetch -> FastAPI.
        return await window.backend!.request(path, {
          method: init?.method ?? 'GET',
          body: init?.body,
        })
      } catch {
        return { ok: false, status: 0, network: true }
      }
    },
  }
}

/** Pick a transport: electron bridge if the preload injected `window.backend`, else fetch. */
export function createTransport(base: string): Transport {
  if (typeof window !== 'undefined' && window.backend?.request) return bridgeTransport()
  return fetchTransport(base)
}
