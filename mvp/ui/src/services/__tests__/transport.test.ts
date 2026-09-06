// Renderer transport tests (vitest, node env). Verifies the transport selection
// (Electron bridge vs direct fetch) and that HttpServiceAdapter keeps its error
// contract when routed over the electron `window.backend` bridge.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { createTransport, type BridgeResult } from '../transport'
import { HttpServiceAdapter, BackendUnavailableError } from '../HttpServiceAdapter'

const BASE = 'http://127.0.0.1:8765'

describe('createTransport detection', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('uses direct fetch when no window.backend (plain browser dev)', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ ok: true, status: 200, json: async () => ({ status: 'ok' }) })
    vi.stubGlobal('fetch', fetchMock)
    const t = createTransport(BASE)
    const res = await t.request('/api/health', { method: 'GET' })
    expect(res.ok).toBe(true)
    expect(fetchMock).toHaveBeenCalledWith(`${BASE}/api/health`, expect.anything())
  })

  it('uses the electron bridge when window.backend is present', async () => {
    const backendRequest = vi
      .fn()
      .mockResolvedValue({ ok: true, status: 200, data: { status: 'ok' } } satisfies BridgeResult)
    vi.stubGlobal('window', { backend: { request: backendRequest } })
    const t = createTransport(BASE)
    const res = await t.request('/api/health')
    expect(backendRequest).toHaveBeenCalledWith('/api/health', { method: 'GET', body: undefined })
    expect(res.data).toEqual({ status: 'ok' })
  })
})

describe('HttpServiceAdapter over the electron bridge', () => {
  afterEach(() => vi.unstubAllGlobals())

  function stubBackend(impl: (path: string) => Promise<BridgeResult>) {
    vi.stubGlobal('window', { backend: { request: impl } })
  }

  it('checkHealth reports CONNECTED on ok', async () => {
    stubBackend(async () => ({ ok: true, status: 200, data: { status: 'ok' } }))
    const adapter = new HttpServiceAdapter(BASE)
    await expect(adapter.checkHealth()).resolves.toBe('CONNECTED')
  })

  it('checkHealth reports OFFLINE when the bridge errors (network)', async () => {
    stubBackend(async () => {
      throw new Error('ipc gone')
    })
    const adapter = new HttpServiceAdapter(BASE)
    await expect(adapter.checkHealth()).resolves.toBe('OFFLINE')
  })

  it('surfaces a 5xx {detail} as a thrown Error', async () => {
    stubBackend(async () => ({ ok: false, status: 500, error: 'IndexError', detail: 'boom' }))
    const adapter = new HttpServiceAdapter(BASE)
    await expect(adapter.buildIndex('D:/m.mkv')).rejects.toThrow('boom')
  })

  it('throws BackendUnavailableError on a network-level bridge failure', async () => {
    stubBackend(async () => {
      throw new Error('backend unreachable')
    })
    const adapter = new HttpServiceAdapter(BASE)
    await expect(adapter.locate('D:/e.mp4', 'D:/m.mkv')).rejects.toBeInstanceOf(
      BackendUnavailableError,
    )
  })
})
