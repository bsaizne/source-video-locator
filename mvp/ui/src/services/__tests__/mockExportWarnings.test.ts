// Mock 通道导出告警（续31 登记尾巴：dev 态结果页看不到 LOC-2001/2002）。
// 判据不在这儿算（真实告警由后端导出守卫产出），这里只锁「opt-in 开关 + 话术」。
import { describe, it, expect, vi, afterEach } from 'vitest'
import { MockServiceAdapter } from '../MockServiceAdapter'

const batch = {
  schema_version: 1, original_video: 'D:/a.mp4', edited_video: 'D:/b.mp4', results: [],
} as never

function stubStorage(values: Record<string, string>) {
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => values[k] ?? null,
    setItem: () => {},
    removeItem: () => {},
  })
}

describe('MockServiceAdapter.exportResults warnings', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('默认不产告警（不与后端通道抢判据）', async () => {
    stubStorage({})
    const out = await new MockServiceAdapter().exportResults(batch, { outDir: 'D:/x', filename: 'export' })
    expect(out.warnings).toBeUndefined()
    expect(out.path).toBe('D:/x/export.results.json')
  })

  it("开 svl.mock.exportWarnings=1 时给出两条与后端逐字同话术的样例", async () => {
    stubStorage({ 'svl.mock.exportWarnings': '1' })
    const out = await new MockServiceAdapter().exportResults(batch, { outDir: 'D:/x' })
    expect(out.warnings).toHaveLength(2)
    expect(out.warnings?.[0].startsWith('LOC-2001 导出清单中有')).toBe(true)
    expect(out.warnings?.[1].startsWith('LOC-2002 第')).toBe(true)
  })
})
