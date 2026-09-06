// Renderer-side types for the window APIs injected by the Electron preload.
// Only the minimal, safe surface is typed here — never Node internals / child_process.
import type { BridgeResult } from '../services/transport'

export {}

declare global {
  interface Window {
    // Preload exposes platform/versions (informational only; not used as a branch key).
    desktop?: {
      platform: string
      versions: Record<string, string>
      /** User data paths (Phase 4): { userData, data, logs }. */
      getPaths(): Promise<{ userData: string; data: string; logs: string }>
      /** Open a directory in the OS file explorer. */
      openPath(target: string): Promise<string>
      /** Native video file picker — absolute path, or null if cancelled. */
      openFile(): Promise<string | null>
      openDirectory(): Promise<string | null>
      /** Absolute path of a File dropped into the renderer (Electron). */
      getPathForFile(file: File): string
    }
    // Preload exposes a backend request bridge: renderer -> IPC -> main Node fetch.
    // Present only when running inside Electron; absent in a plain browser.
    backend?: {
      request(
        path: string,
        options?: { method?: string; body?: unknown },
      ): Promise<BridgeResult>
      health(): Promise<BridgeResult>
      /** Real-time task progress WS, proxied by the main process (no localhost from renderer). */
      websocket(
        taskId: string,
        onEvent: (event: unknown) => void,
        onClose?: () => void,
      ): { close(): void }
    }
  }
}
