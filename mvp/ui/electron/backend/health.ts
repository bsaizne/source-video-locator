// Backend health polling. Pure Node (injectable fetch/sleep) so it is unit-testable
// without a live server or Python process.
import type { BackendConfig } from './config'

/** Thrown when the backend never reports healthy within the timeout. */
export class BackendStartError extends Error {
  name = 'BackendStartError'

  constructor(message: string) {
    super(message)
  }
}

export interface HealthChecker {
  /** One-shot check; false on any failure (network, non-2xx, status != ok). */
  check(): Promise<boolean>
  /** Poll until healthy or throw BackendStartError after the (config) timeout. */
  waitHealthy(opts?: { timeoutMs?: number; intervalMs?: number }): Promise<void>
}

// Minimal fetch shape (avoids depending on lib.dom / a global Response type).
type Fetcher = (url: string) => Promise<{ ok: boolean; json(): Promise<unknown> }>
type Sleeper = (ms: number) => Promise<void>

const delay = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms))

export function createHealthChecker(
  config: Pick<BackendConfig, 'healthUrl' | 'timeoutMs' | 'pollIntervalMs'>,
  opts: { fetch?: Fetcher; sleep?: Sleeper } = {},
): HealthChecker {
  const fetcher = opts.fetch ?? ((globalThis as unknown as { fetch: Fetcher }).fetch)
  const sleep = opts.sleep ?? delay

  async function check(): Promise<boolean> {
    try {
      const res = await fetcher(config.healthUrl)
      if (!res.ok) return false
      const body = (await res.json()) as { status?: string }
      return body?.status === 'ok'
    } catch {
      return false
    }
  }

  async function waitHealthy(overrides?: { timeoutMs?: number; intervalMs?: number }): Promise<void> {
    const timeoutMs = overrides?.timeoutMs ?? config.timeoutMs
    const intervalMs = overrides?.intervalMs ?? config.pollIntervalMs
    const deadline = Date.now() + timeoutMs
    // Loop forever but re-check the deadline every iteration so a long sleep can't
    // overshoot without bound.
    for (;;) {
      if (await check()) return
      if (Date.now() >= deadline) {
        throw new BackendStartError(
          `backend health check timed out after ${timeoutMs}ms at ${config.healthUrl}`,
        )
      }
      await sleep(intervalMs)
    }
  }

  return { check, waitHealthy }
}
