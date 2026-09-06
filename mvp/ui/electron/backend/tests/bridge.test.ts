// Electron backend bridge tests (vitest, node env). The main-process handler and
// the preload object builder are exercised with fakes — no Electron, no network.
import { describe, it, expect, vi } from 'vitest'
import { buildBackendBridge, createBackendRequestHandler } from '../bridge'
import type { BridgeResponse } from '../bridge'
import { createBackendConfig } from '../config'

const cfg = createBackendConfig()
const BASE = `http://${cfg.host}:${cfg.port}`

function jsonRes(status: number, body: unknown) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

describe('createBackendRequestHandler', () => {
  it('GETs the health path and returns ok + data', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonRes(200, { status: 'ok', version: '0.1' }))
    const handler = createBackendRequestHandler(cfg, fetchImpl)
    const res = await handler({ path: '/api/health', method: 'GET' })
    expect(fetchImpl).toHaveBeenCalledWith(`${BASE}/api/health`, {
      method: 'GET',
      headers: { 'content-type': 'application/json' },
      body: undefined,
    })
    expect(res.ok).toBe(true)
    expect(res.status).toBe(200)
    expect(res.data).toEqual({ status: 'ok', version: '0.1' })
  })

  it('POSTs the body as JSON string', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonRes(200, { frames: 5 }))
    const handler = createBackendRequestHandler(cfg, fetchImpl)
    await handler({ path: '/api/index', method: 'POST', body: { video_path: 'D:/m.mkv' } })
    const [, init] = fetchImpl.mock.calls[0] as [string, { body?: string; method: string }]
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body ?? '')).toEqual({ video_path: 'D:/m.mkv' })
  })

  it('surfaces detail on a 5xx', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonRes(500, { error: 'IndexError', detail: 'boom' }))
    const handler = createBackendRequestHandler(cfg, fetchImpl)
    const res = await handler({ path: '/api/index', method: 'POST' })
    expect(res.ok).toBe(false)
    expect(res.status).toBe(500)
    expect(res.detail).toBe('boom')
  })

  it('reports network:true when fetch rejects', async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new TypeError('conn refused'))
    const handler = createBackendRequestHandler(cfg, fetchImpl)
    const res = await handler({ path: '/api/health' })
    expect(res.network).toBe(true)
    expect(res.ok).toBe(false)
    expect(res.error).toBe('network')
  })

  it('rejects absolute / protocol-relative / non-local paths without fetching', async () => {
    const fetchImpl = vi.fn()
    const handler = createBackendRequestHandler(cfg, fetchImpl)
    for (const bad of ['http://evil.com/x', '//evil.com/x', 'cloud:/x', 'relative/path', '']) {
      const res = await handler({ path: bad })
      expect(res.error).toBe('invalid_path')
    }
    expect(fetchImpl).not.toHaveBeenCalled()
  })

  it('rejects disallowed methods', async () => {
    const fetchImpl = vi.fn()
    const handler = createBackendRequestHandler(cfg, fetchImpl)
    const res = await handler({ path: '/api/health', method: 'TRACE' })
    expect(res.error).toBe('invalid_method')
    expect(fetchImpl).not.toHaveBeenCalled()
  })
})

describe('buildBackendBridge', () => {
  function fakeIpc() {
    const listeners: Record<string, Array<(e: unknown, p: unknown) => void>> = {}
    const ipc = {
      invoke: vi.fn().mockResolvedValue({ ok: true, status: 200 } satisfies BridgeResponse),
      on: vi.fn((ch: string, fn: (e: unknown, p: unknown) => void) => {
        ;(listeners[ch] ??= []).push(fn)
      }),
      send: vi.fn(),
      removeListener: vi.fn((ch: string, fn: (e: unknown, p: unknown) => void) => {
        const a = listeners[ch]
        if (a) {
          const i = a.indexOf(fn)
          if (i >= 0) a.splice(i, 1)
        }
      }),
    }
    return { ipc, listeners }
  }

  it('exposes ONLY request/health/websocket (no node / child_process / fs)', () => {
    const { ipc } = fakeIpc()
    const bridge = buildBackendBridge(ipc)
    expect(Object.keys(bridge).sort()).toEqual(['health', 'request', 'websocket'])
    expect(bridge).not.toHaveProperty('child_process')
    expect(bridge).not.toHaveProperty('fs')
    expect(bridge).not.toHaveProperty('spawn')
  })

  it('request forwards path/method/body via the backend:request channel', async () => {
    const { ipc } = fakeIpc()
    const bridge = buildBackendBridge(ipc)
    await bridge.request('/api/analyze', { method: 'POST', body: { x: 1 } })
    expect(ipc.invoke).toHaveBeenCalledWith('backend:request', {
      path: '/api/analyze',
      method: 'POST',
      body: { x: 1 },
    })
  })

  it('health hits /api/health with GET', async () => {
    const { ipc } = fakeIpc()
    const bridge = buildBackendBridge(ipc)
    await bridge.health()
    expect(ipc.invoke).toHaveBeenCalledWith('backend:request', { path: '/api/health', method: 'GET' })
  })

  it('websocket opens via backend:ws:open and relays frames for its own id', () => {
    const { ipc, listeners } = fakeIpc()
    const bridge = buildBackendBridge(ipc)
    const onEvent = vi.fn()
    const handle = bridge.websocket('task-1', onEvent)
    expect(ipc.send).toHaveBeenCalledWith('backend:ws:open', {
      id: expect.stringContaining('ws-'),
      taskId: 'task-1',
    })
    const sentId = (ipc.send.mock.calls[0] as unknown[])[1] as { id: string }
    // A frame for this id reaches onEvent; a frame for another id is dropped.
    listeners['backend:ws:message'].forEach((fn) => fn(null, { id: 'ws-other', data: '{}' }))
    listeners['backend:ws:message'].forEach((fn) => fn(null, { id: sentId.id, data: '{"type":"progress"}' }))
    expect(onEvent).toHaveBeenCalledWith({ type: 'progress' })
    // close() sends a client-close to stop the main-side socket.
    handle.close()
    expect(ipc.send).toHaveBeenCalledWith('backend:ws:client-close', { id: sentId.id })
  })
})
