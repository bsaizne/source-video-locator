// 素材入库浏览（入库层四件，2026-10-02）服务契约测试。
// Http 侧：GET /api/fs/browse 的 URL 编码（路径含中文/反斜杠/空格）；
// Mock 侧：假树语义与后端一致（自然排序、白名单、parent=''、未知道具抛错）。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { HttpServiceAdapter } from '../HttpServiceAdapter'
import { MockServiceAdapter } from '../MockServiceAdapter'

function res(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response
}

const BASE = 'http://127.0.0.1:8765'

describe('HttpServiceAdapter: browseFs', () => {
  let adapter: HttpServiceAdapter
  beforeEach(() => { adapter = new HttpServiceAdapter(BASE) })
  afterEach(() => vi.unstubAllGlobals())

  it('GET /api/fs/browse?path= 编码原样（中文盘目录）', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      res({ kind: 'dir', path: 'D:\\素材库', parent: 'D:\\', drives: [], entries: [],
            free_bytes: 1, total_bytes: 2 }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const out = await adapter.browseFs('D:\\素材库')
    expect(fetchMock.mock.calls[0][0]).toBe(
      `${BASE}/api/fs/browse?path=${encodeURIComponent('D:\\素材库')}`)
    expect(out.kind).toBe('dir')
    expect(out.parent).toBe('D:\\')
  })

  it("空 path → 根查询（'此电脑'）", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      res({ kind: 'root', path: '', parent: null, drives: [], entries: [] }),
    )
    vi.stubGlobal('fetch', fetchMock)
    await adapter.browseFs('')
    expect(fetchMock.mock.calls[0][0]).toBe(`${BASE}/api/fs/browse?path=`)
  })
})

describe('MockServiceAdapter: browseFs 与后端语义一致', () => {
  const adapter = new MockServiceAdapter()

  it('根 = 盘符列表带剩余空间', async () => {
    const out = await adapter.browseFs('')
    expect(out.kind).toBe('root')
    expect(out.drives.length).toBeGreaterThanOrEqual(2)
    expect(out.drives[0].free_bytes).toBeGreaterThan(0)
  })

  it('目录 = 自然排序 + 白名单（txt 不出现）', async () => {
    const out = await adapter.browseFs('D:\\')
    const names = out.entries.map((e) => e.name)
    expect(names).toEqual(['素材库', 'clip2.mp4', 'clip10.mp4'])
  })

  it('未知道具抛 not_found（面板按普通错误显示）', async () => {
    await expect(adapter.browseFs('Z:\\nope')).rejects.toThrow('not_found')
  })
})
