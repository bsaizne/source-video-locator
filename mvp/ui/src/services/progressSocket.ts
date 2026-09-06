// ProgressSocket — real-time task progress subscription.
//
// Two transports, chosen at runtime like the HTTP transport:
//   - Electron (preload injected `window.backend.websocket`): routed via the main
//     process, so the packaged `file://` renderer never talks to localhost directly.
//   - Otherwise a browser `WebSocket` to the local FastAPI bridge.
//
// Returns a handle with `close()`. The socket must not be exposed to the renderer
// beyond this narrow event-interface.
import type { TaskEvent } from './types'

export interface ProgressSocket {
  close(): void
}

export interface ProgressSocketHandlers {
  onEvent: (event: TaskEvent) => void
  onClose?: () => void
}

function toWsBase(base: string): string {
  return base.replace(/^http/, 'ws').replace(/\/+$/, '')
}

export function openProgressSocket(
  baseUrl: string,
  taskId: string,
  handlers: ProgressSocketHandlers,
): ProgressSocket {
  const electron = typeof window !== 'undefined' ? window.backend?.websocket : undefined
  if (electron) {
    return electron(taskId, (ev) => handlers.onEvent(ev as TaskEvent), handlers.onClose)
  }

  const url = `${toWsBase(baseUrl)}/ws/progress/${encodeURIComponent(taskId)}`
  const ws = new WebSocket(url)
  ws.onmessage = (msg) => {
    try {
      handlers.onEvent(JSON.parse(String(msg.data)) as TaskEvent)
    } catch {
      /* ignore malformed frame */
    }
  }
  ws.onerror = () => handlers.onClose?.()
  ws.onclose = () => handlers.onClose?.()
  return { close: () => ws.close() }
}
