// Health checker tests (vitest, node env). Fetcher/sleep are injected — no network.
import { describe, it, expect, vi } from 'vitest'
import { createHealthChecker, BackendStartError } from '../health'
import type { BackendConfig } from '../config'

const cfg = {
  healthUrl: 'http://127.0.0.1:8765/api/health',
  timeoutMs: 30000,
  pollIntervalMs: 500,
} as Pick<BackendConfig, 'healthUrl' | 'timeoutMs' | 'pollIntervalMs'>

function okBody(status = 'ok') {
  return { ok: true, json: async () => ({ status }) }
}
function nonOk() {
  return { ok: false, json: async () => ({}) }
}
async function reject() {
  throw new TypeError('connection refused')
}

const noSleep = async () => {}

describe('createHealthChecker.check', () => {
  it('returns true when status is ok', async () => {
    const h = createHealthChecker(cfg, { fetch: vi.fn().mockResolvedValue(okBody()), sleep: noSleep })
    await expect(h.check()).resolves.toBe(true)
  })

  it('returns false on non-ok http status', async () => {
    const h = createHealthChecker(cfg, { fetch: vi.fn().mockResolvedValue(nonOk()), sleep: noSleep })
    await expect(h.check()).resolves.toBe(false)
  })

  it('returns false on network failure', async () => {
    const h = createHealthChecker(cfg, { fetch: vi.fn().mockImplementation(reject), sleep: noSleep })
    await expect(h.check()).resolves.toBe(false)
  })

  it('hits the configured healthUrl', async () => {
    const fetch = vi.fn().mockResolvedValue(okBody())
    const h = createHealthChecker(cfg, { fetch, sleep: noSleep })
    await h.check()
    expect(fetch).toHaveBeenCalledWith(cfg.healthUrl)
  })
})

describe('createHealthChecker.waitHealthy', () => {
  it('resolves once health turns ok after a transient failure', async () => {
    let calls = 0
    const fetch = vi.fn().mockImplementation(async () => {
      calls += 1
      return calls >= 3 ? okBody() : nonOk()
    })
    const h = createHealthChecker(cfg, { fetch, sleep: noSleep })
    await expect(h.waitHealthy({ timeoutMs: 5000 })).resolves.toBeUndefined()
    expect(calls).toBeGreaterThanOrEqual(3)
  })

  it('throws BackendStartError on timeout', async () => {
    const h = createHealthChecker(cfg, { fetch: vi.fn().mockResolvedValue(nonOk()), sleep: noSleep })
    await expect(h.waitHealthy({ timeoutMs: 0 })).rejects.toBeInstanceOf(BackendStartError)
  })
})
