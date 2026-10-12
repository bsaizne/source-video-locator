// Electron backend bridge tests (vitest, node env). The main-process handler and
// the preload object builder are exercised with fakes; the `httpRequester` block below
// uses a real 127.0.0.1 server on an ephemeral port (no Electron, no external network).
import { describe, it, expect, vi } from 'vitest'
import * as http from 'node:http'
import type { AddressInfo } from 'node:net'
import { buildBackendBridge, createBackendRequestHandler, httpRequester } from '../bridge'
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

  it('forwards the error body as data on non-2xx (packaged UI reads message/code from it)', async () => {
    // 后端第二层边界/结构化错误的成品文案在 body.message + body.code 里。
    // 旧桥接层非 ok 时不回 data ⇒ 渲染层拿不到话术，包内只显示英文技术串。
    const fetchImpl = vi.fn().mockResolvedValue(jsonRes(400, {
      code: 'LOC-9999',
      message: '导出失败（SegmentOverlap），请把日志发给支持人员',
      error: 'SegmentOverlap',
      detail: 'New segment overlaps with existing segment',
    }))
    const handler = createBackendRequestHandler(cfg, fetchImpl)
    const res = await handler({ path: '/api/export', method: 'POST' })
    expect(res.ok).toBe(false)
    expect(res.network).toBeUndefined()
    expect(res.data).toMatchObject({ code: 'LOC-9999', message: expect.stringContaining('支持人员') })
  })

  it('still returns detail fallback when the error body is not JSON', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: false, status: 502, json: async () => { throw new Error('bad json') } })
    const handler = createBackendRequestHandler(cfg, fetchImpl)
    const res = await handler({ path: '/api/index', method: 'POST' })
    expect(res.ok).toBe(false)
    expect(res.detail).toBe('HTTP 502')
    expect(res.data).toEqual({})
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

// 分钟级同步导出 × 客户端 300s 头超时（真机 r21/r22 支持档实测 374s/783s 崩、571s/475s 成功
// 却被报成「无法连接后端服务」）。根因 = Node 全局 fetch 的 undici headersTimeout=300s
// （实测 reject_after_ms=300504、message="fetch failed"）⇒ 桥接层默认实现换成 node:http
// （无隐式头超时，超时只由显式 setTimeout 决定）。下列锁跑真 socket，不用桩。
describe('httpRequester (node:http 默认 transport)', () => {
  function startServer(onRequest: (req: http.IncomingMessage, res: http.ServerResponse) => void) {
    return new Promise<{ s: http.Server; port: number }>((resolve) => {
      const s = http.createServer(onRequest)
      s.listen(0, '127.0.0.1', () => resolve({ s, port: (s.address() as AddressInfo).port }))
    })
  }
  async function stop(s: http.Server) {
    s.closeAllConnections?.()
    await new Promise<void>((r) => s.close(() => r()))
  }

  it('round-trips status + json 并转发查询串（会话令牌在串里）', async () => {
    const { s, port } = await startServer((req, res) => {
      res.writeHead(200, { 'content-type': 'application/json' })
      res.end(JSON.stringify({ path: req.url }))
    })
    try {
      const out = await httpRequester(`http://127.0.0.1:${port}/api/health?svl_session=abc123`)
      expect(out.ok).toBe(true)
      expect(out.status).toBe(200)
      expect(await out.json()).toEqual({ path: '/api/health?svl_session=abc123' })
    } finally {
      await stop(s)
    }
  })

  it('createBackendRequestHandler 默认走 node:http（不是 global fetch）', async () => {
    // 结构锁：不注入桩 = 生产装配路径。若哪天默认又回 globalThis.fetch，undici 的 300s
    // 会在长导出上原样复发，而这条锁先红。
    let seen = false
    const { s, port } = await startServer((req, res) => {
      seen = true
      res.writeHead(200, { 'content-type': 'application/json' })
      res.end('{"path":"ok"}')
    })
    try {
      const handler = createBackendRequestHandler(createBackendConfig({ port }))
      const r = await handler({ path: '/api/export', method: 'POST', body: '{}' })
      expect(r.ok).toBe(true)
      expect(seen).toBe(true)
    } finally {
      await stop(s)
    }
  })

  it('显式超时到点会断（挂死连接不静默永久转圈），并经处理层落 network:true', async () => {
    const { s, port } = await startServer(() => {
      /* 永不发响应头：模拟后端挂死 */
    })
    try {
      await expect(httpRequester(`http://127.0.0.1:${port}/boom`, {}, 150)).rejects.toThrow(/timed out/)
      const handler = createBackendRequestHandler(
        createBackendConfig({ port }),
        (url, init) => httpRequester(String(url), init, 150),
      )
      const r = await handler({ path: '/api/export', method: 'POST' })
      expect(r.network).toBe(true)
      expect(r.ok).toBe(false)
      expect(r.detail).toMatch(/timed out/)
    } finally {
      await stop(s)
    }
  })

  it('服务端主动断连（非超时）也落 network:true', async () => {
    const { s, port } = await startServer((req) => {
      req.socket.destroy()
    })
    try {
      const handler = createBackendRequestHandler(createBackendConfig({ port }))
      const r = await handler({ path: '/api/index', method: 'POST' })
      expect(r.network).toBe(true)
      expect(r.status).toBe(0)
    } finally {
      await stop(s)
    }
  })
})
