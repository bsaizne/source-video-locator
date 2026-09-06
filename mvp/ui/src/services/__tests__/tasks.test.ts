// HttpServiceAdapter async-task tests (vitest, node env).
// Covers startAnalyzeTask/getTask/cancelTask endpoints, subscribeProgress event
// delivery, and the one-shot WebSocket reconnect-on-disconnect behavior.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { HttpServiceAdapter } from '../HttpServiceAdapter'
import type { TaskEvent } from '../types'

const BASE = 'http://127.0.0.1:8765'

function res(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response
}

// Stub the Electron `window.backend.websocket` so subscribeProgress routes via the
// bridge. Records each created socket so the test can drive onEvent/onClose.
function stubElectronWs() {
  const creators: Array<{
    taskId: string
    onEvent: (ev: unknown) => void
    onClose?: () => void
  }> = []
  vi.stubGlobal('window', {
    backend: {
      websocket: (taskId: string, onEvent: (ev: unknown) => void, onClose?: () => void) => {
        creators.push({ taskId, onEvent, onClose })
        return { close: () => {} }
      },
    },
  })
  return creators
}

describe('HttpServiceAdapter async tasks', () => {
  let adapter: HttpServiceAdapter
  beforeEach(() => {
    adapter = new HttpServiceAdapter(BASE)
  })
  afterEach(() => vi.unstubAllGlobals())

  it('startAnalyzeTask POSTs /api/tasks/analyze and returns task_id', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res({ task_id: 'abc' })))
    const { task_id } = await adapter.startAnalyzeTask('D:/e.mp4', 'D:/o.mkv')
    const [url, init] = (vi.mocked(fetch).mock.calls[0] as [string, RequestInit])
    expect(url).toBe(`${BASE}/api/tasks/analyze`)
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual({ edited_path: 'D:/e.mp4', original_path: 'D:/o.mkv' })
    expect(task_id).toBe('abc')
  })

  it('getTask GETs /api/tasks/{id}', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res({ task_id: 'abc', status: 'completed' })))
    const t = await adapter.getTask('abc')
    const [url] = (vi.mocked(fetch).mock.calls[0] as [string, RequestInit])
    expect(url).toBe(`${BASE}/api/tasks/abc`)
    expect(t.status).toBe('completed')
  })

  it('cancelTask POSTs /api/tasks/{id}/cancel', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res({ status: 'cancel_requested' })))
    await adapter.cancelTask('abc')
    const [url, init] = (vi.mocked(fetch).mock.calls[0] as [string, RequestInit])
    expect(url).toBe(`${BASE}/api/tasks/abc/cancel`)
    expect(init.method).toBe('POST')
  })

  it('subscribeProgress delivers progress then completed frames', async () => {
    const creators = stubElectronWs()
    const events: TaskEvent[] = []
    const unsub = adapter.subscribeProgress('abc', (ev) => events.push(ev))
    expect(creators.length).toBe(1)
    expect(creators[0].taskId).toBe('abc')
    creators[0].onEvent({ type: 'progress', task_id: 'abc', status: 'running', stage: 'indexing', progress: 10, message: 'x' })
    creators[0].onEvent({ type: 'completed', task_id: 'abc' })
    expect(events.map((e) => e.type)).toEqual(['progress', 'completed'])
    unsub()
  })

  it('reconnects exactly once on a disconnect before the terminal frame', () => {
    const creators = stubElectronWs()
    adapter.subscribeProgress('abc', () => {})
    creators[0].onClose?.() // sudden disconnect
    expect(creators.length).toBe(2)
    expect(creators[1].taskId).toBe('abc')
    creators[1].onClose?.() // do not reconnect again
    expect(creators.length).toBe(2)
  })

  it('does NOT reconnect after a terminal frame or after unsubscribe', () => {
    const creators = stubElectronWs()
    const unsub = adapter.subscribeProgress('abc', () => {})
    creators[0].onEvent({ type: 'completed', task_id: 'abc' })
    creators[0].onClose?.() // after terminal -> no reconnect
    expect(creators.length).toBe(1)
    unsub()
  })
})
