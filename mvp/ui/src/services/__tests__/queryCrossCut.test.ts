// `query_cross_cut`（段内含画面跳变，只标注不改置信度）的 UI 侧契约锁。
//
// 为什么要锁：后端是 `Result.to_dict()` 直出，UI 走两条路——HTTP 适配器（打包态真实路径）
// 与 mockData.mkResult（**逐字段挑键**）。后者漏一个键就静默变 undefined，
// 界面上只是「少个提示」，没有任何报错 ⇒ 这类缺陷只能靠锁抓。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { HttpServiceAdapter } from '../HttpServiceAdapter'
import { mockResultBatch } from '../mockData'
import type { QueryCrossCutJson, ResultBatchJson, ResultJson } from '../types'

function res(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response
}

const BASE = 'http://127.0.0.1:8765'

function batchWith(results: ResultBatchJson['results']): ResultBatchJson {
  return { schema_version: 1, original_video: 'movie.mkv', edited_video: 'clip.mp4', results }
}

const ANN: QueryCrossCutJson = { max_d: 0.95, at: 99.875, n_jumps: 13 }
const BASE_RESULT: ResultJson = {
  result_id: 'r1',
  edited_segment: { start: 95.4, end: 118.9 },
  original: { candidate_start: 4100, candidate_end: 4124 },
  confidence: 'MEDIUM',
  confidence_score: 0.58,
  reasons: [],
  candidate_rank: 2,
  alternatives: [],
  original_segments: [],
  source: 'auto',
  manual_override: false,
  montage_flag: true,
  extracted_path: null,
  failure_reason: null,
  not_in_source: false,
}

describe('query_cross_cut 契约', () => {
  let adapter: HttpServiceAdapter
  beforeEach(() => { adapter = new HttpServiceAdapter(BASE) })
  afterEach(() => { vi.unstubAllGlobals() })

  it('HTTP 路径原样透传标注（含 at / n_jumps）', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      res(batchWith([{ ...BASE_RESULT, query_cross_cut: ANN }]))))
    const out = await adapter.locate('D:/clip.mp4', 'D:/movie.mkv')
    expect(out.results[0].query_cross_cut).toEqual(ANN)
  })

  it('后端给 null 时不报错、不误造对象', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      res(batchWith([{ ...BASE_RESULT, query_cross_cut: null }]))))
    const out = await adapter.locate('D:/clip.mp4', 'D:/movie.mkv')
    expect(out.results[0].query_cross_cut).toBeNull()
  })

  it('旧结果文件（无该键）读回为 undefined，不抛', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(batchWith([{ ...BASE_RESULT }]))))
    const out = await adapter.locate('D:/clip.mp4', 'D:/movie.mkv')
    expect(out.results[0].query_cross_cut).toBeUndefined()
  })

  it('mock 适配器：mkResult 缺键补 null，带键的原样保留', () => {
    const batch = mockResultBatch()
    const withAnn = batch.results.filter((r) => r.query_cross_cut !== null)
    expect(withAnn.length).toBeGreaterThanOrEqual(1)   // 反空锁：mock 里必须有一条能看见
    expect(withAnn[0].query_cross_cut?.n_jumps).toBeGreaterThan(1)
    expect(batch.results.filter((r) => r.query_cross_cut === null).length)
      .toBeGreaterThan(0)                              // 其余条必须是 null 而非 undefined
  })
})
