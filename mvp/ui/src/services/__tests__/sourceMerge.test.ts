// 多原片合并的服务契约测试（2026-09-29 续27 后端已就绪，本批补 UI 接线）。
// Http 侧：POST /api/source/merge 的 body 形态 + /api/tasks/analyze 的 original_paths 口径；
// Mock 侧：与后端同规则的 <2 段拒绝（UI 的两条分支都能在 dev 态跑通）。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { HttpServiceAdapter } from '../HttpServiceAdapter'
import { MockServiceAdapter } from '../MockServiceAdapter'

function res(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response
}

const BASE = 'http://127.0.0.1:8765'

describe('HttpServiceAdapter: 多原片合并', () => {
  let adapter: HttpServiceAdapter
  beforeEach(() => {
    adapter = new HttpServiceAdapter(BASE)
  })
  afterEach(() => vi.unstubAllGlobals())

  it('mergeSources POSTs /api/source/merge with {paths}（顺序原样透传）', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      res({ merged_path: 'D:/appdata/merged/a.mp4', mode: 'copy', reused: false, duration_s: 152.4 }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const out = await adapter.mergeSources(['D:/v/ep1.mkv', 'D:/v/ep2.mkv'])
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe(`${BASE}/api/source/merge`)
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual({ paths: ['D:/v/ep1.mkv', 'D:/v/ep2.mkv'] })
    expect(out.merged_path).toBe('D:/appdata/merged/a.mp4')
    expect(out.mode).toBe('copy')
    expect(out.reused).toBe(false)
    expect(out.duration_s).toBe(152.4)
  })

  it('mergeSources 命中缓存（reused=true）仍是同一形态', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      res({ merged_path: 'D:/appdata/merged/a.mp4', mode: 'copy', reused: true, duration_s: null }),
    ))
    const out = await adapter.mergeSources(['D:/v/ep1.mkv', 'D:/v/ep2.mkv'])
    expect(out.reused).toBe(true)
    expect(out.duration_s).toBeNull()
  })

  it('后端 MediaError → 展示对外话术（LOC 码），不吐技术串/本机路径', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(
      { code: 'LOC-1000', message: '视频读取/剪辑处理失败，请确认文件未损坏、未被其它程序占用后重试。',
        error: 'MediaError', detail: 'ffmpeg exit 1 on D:\\secret\\path' },
      false, 500,
    )))
    await expect(adapter.mergeSources(['D:/v/a.mkv', 'D:/v/b.mkv'])).rejects.toThrow(
      /视频读取\/剪辑处理失败.*LOC-1000/,
    )
  })

  it('单段分析：body 与旧版逐字一致（不带 original_paths）', async () => {
    const fetchMock = vi.fn().mockResolvedValue(res({ task_id: 't1' }))
    vi.stubGlobal('fetch', fetchMock)
    await adapter.startAnalyzeTask('D:/v/ed.mp4', 'D:/v/om.mkv')
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      edited_path: 'D:/v/ed.mp4', original_path: 'D:/v/om.mkv',
    })
  })

  it('多段未合并：original_path 置空 + original_paths 透传（由 worker 先合并）', async () => {
    const fetchMock = vi.fn().mockResolvedValue(res({ task_id: 't2' }))
    vi.stubGlobal('fetch', fetchMock)
    await adapter.startAnalyzeTask('D:/v/ed.mp4', '', ['D:/v/ep1.mkv', 'D:/v/ep2.mkv'])
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      edited_path: 'D:/v/ed.mp4', original_path: '', original_paths: ['D:/v/ep1.mkv', 'D:/v/ep2.mkv'],
    })
  })

  it('original_paths 只有 1 段/含空白项 → 退回单原片口径（后端 ≥2 才合并）', async () => {
    const fetchMock = vi.fn().mockResolvedValue(res({ task_id: 't3' }))
    vi.stubGlobal('fetch', fetchMock)
    await adapter.startAnalyzeTask('D:/v/ed.mp4', 'D:/v/om.mkv', ['D:/v/om.mkv', '  '])
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      edited_path: 'D:/v/ed.mp4', original_path: 'D:/v/om.mkv',
    })
  })
})

describe('MockServiceAdapter: 多原片合并契约', () => {
  it('<2 段拒绝（与 routes/source.py 同规则）', async () => {
    const mock = new MockServiceAdapter()
    await expect(mock.mergeSources(['D:/v/only.mkv'])).rejects.toThrow(/at least 2/)
  })

  it('≥2 段返回与后端同形状的响应', async () => {
    const mock = new MockServiceAdapter()
    const out = await mock.mergeSources(['D:/v/ep1.mkv', 'D:/v/ep2.mkv'])
    expect(out).toMatchObject({ mode: 'copy', reused: false })
    expect(typeof out.merged_path).toBe('string')
    expect(out.merged_path).toContain('merged')
  })
})
