// HttpServiceAdapter unit tests (vitest, node env).
// Stubs global fetch with response-like objects so no real network or JS DOM is
// needed. Verifies the adapter drives the real FastAPI endpoints and preserves
// the flattened ResultBatch confidence contract.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { HttpServiceAdapter, BackendUnavailableError, readBackendBootstrap } from '../HttpServiceAdapter'
import type { ResultBatchJson } from '../types'

// Minimal Response-like object (avoids depending on a global Response in Node).
function res(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response
}

const BASE = 'http://127.0.0.1:8765'

describe('HttpServiceAdapter', () => {
  let adapter: HttpServiceAdapter
  beforeEach(() => {
    adapter = new HttpServiceAdapter(BASE)
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('checkHealth returns CONNECTED on ok body', async () => {
    const fetchMock = vi.fn().mockResolvedValue(res({ status: 'ok', version: '0.1' }))
    vi.stubGlobal('fetch', fetchMock)
    await expect(adapter.checkHealth()).resolves.toBe('CONNECTED')
    expect(fetchMock).toHaveBeenCalledWith(`${BASE}/api/health`, expect.anything())
  })

  it('checkHealth returns OFFLINE on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('fetch failed')))
    await expect(adapter.checkHealth()).resolves.toBe('OFFLINE')
  })

  it('buildIndex POSTs /api/index with {video_path} and maps IndexStatus', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      res({ status: 'completed', frames: 3834, backend: { device_name: 'cpu', device_type: 'cpu' } }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const status = await adapter.buildIndex('D:/movie/source.mkv')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe(`${BASE}/api/index`)
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual({ video_path: 'D:/movie/source.mkv' })
    expect(status.indexMeta?.num_frames).toBe(3834)
    expect(status.backend.deviceType).toBe('cpu')
    expect(status.backend.isAccelerator).toBe(false)
    expect(status.validation.status).toBe('VALID')
  })

  it('getDeviceSettings GETs /api/settings/device and maps directml (not clamp to cpu)', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      res({ preferred: 'directml', actual_device_name: 'directml', actual_device_type: 'amd', is_accelerator: true, fallback: false, available_devices: ['cpu', 'directml'] }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const ds = await adapter.getDeviceSettings()
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe(`${BASE}/api/settings/device`)
    expect(init.method).toBe('GET')
    expect(ds.preferred).toBe('directml')
    expect(ds.actual_device_name).toBe('directml') // 关键：不再被 normDeviceName clamp 成 cpu
    expect(ds.actual_device_type).toBe('amd')
    expect(ds.is_accelerator).toBe(true)
  })

  it('setDeviceSettings POSTs preferred and returns updated settings', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      res({ preferred: 'directml', actual_device_name: 'directml', actual_device_type: 'amd', is_accelerator: true, fallback: false, available_devices: ['cpu', 'directml'] }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const ds = await adapter.setDeviceSettings('directml')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe(`${BASE}/api/settings/device`)
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual({ preferred: 'directml' })
    expect(ds.actual_device_name).toBe('directml')
  })

  it('getIndexStatus queries GET /api/index/status and maps real status', async () => {
    const fetchMock = vi.fn().mockResolvedValue(res({ status: 'VALID', reason: null }))
    vi.stubGlobal('fetch', fetchMock)
    const st = await adapter.getIndexStatus('D:/movie/source.mkv')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe(`${BASE}/api/index/status?video_path=${encodeURIComponent('D:/movie/source.mkv')}`)
    expect(init.method).toBe('GET')
    expect(st.validation.status).toBe('VALID')
  })

  it('getIndexStatus surfaces INVALID source-video-missing', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      res({ status: 'INVALID', reason: 'source video missing' }),
    ))
    const st = await adapter.getIndexStatus('D:/movie/source.mkv')
    expect(st.validation.status).toBe('INVALID')
    expect(st.validation.reason).toBe('source video missing')
  })

  it('getMediaInfo GETs /api/media/info with encoded absolute path', async () => {
    const media = {
      path: 'D:\\电影 2014\\movie.mkv', duration: 7667.9, fps: 23.976,
      width: 1920, height: 804, size_bytes: 123456789,
      format_name: 'matroska,webm', video_codec: 'hevc', has_audio: true,
    }
    const fetchMock = vi.fn().mockResolvedValue(res(media))
    vi.stubGlobal('fetch', fetchMock)
    const info = await adapter.getMediaInfo('D:\\电影 2014\\movie.mkv')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe(`${BASE}/api/media/info?path=${encodeURIComponent('D:\\电影 2014\\movie.mkv')}`)
    expect(init.method).toBe('GET')
    expect(info.duration).toBe(7667.9)
    expect(info.fps).toBe(23.976)
    expect(info.size_bytes).toBe(123456789)
  })

  it('getMediaInfo 400 invalid_path surfaces the backend detail', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      res({ error: 'invalid_path', detail: 'path must be absolute' }, false, 400),
    ))
    await expect(adapter.getMediaInfo('movie.mkv')).rejects.toThrow('path must be absolute')
  })

  it('getMediaInfo 500 shows user message with stable LOC code', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      res({ code: 'LOC-1000', message: '视频读取/剪辑处理失败，请确认文件未损坏、未被其它程序占用后重试。', error: 'MediaError', detail: 'ffprobe boom' }, false, 500),
    ))
    await expect(adapter.getMediaInfo('D:/broken.mkv')).rejects.toThrow(/视频读取\/剪辑处理失败.*LOC-1000/)
  })

  it('locate POSTs /api/results and keeps confidence flattened', async () => {
    const batch: ResultBatchJson = {
      schema_version: 1,
      original_video: 'orig.mkv',
      edited_video: 'clip.mp4',
      results: [
        {
          result_id: 'r1',
          edited_segment: { start: 3.1, end: 21.4 },
          original: { candidate_start: 5025, candidate_end: 5042 },
          confidence: 'HIGH',
          confidence_score: 0.94,
          reasons: ['rank1'],
          candidate_rank: 1,
          alternatives: [],
          original_segments: [],
          source: 'auto',
          manual_override: false,
          montage_flag: false,
          extracted_path: null,
          failure_reason: null,
          not_in_source: false,
        },
      ],
    }
    const fetchMock = vi.fn().mockResolvedValue(res(batch))
    vi.stubGlobal('fetch', fetchMock)
    const out = await adapter.locate('D:/clip.mp4', 'D:/movie/source.mkv')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe(`${BASE}/api/results`)
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual({ edited_path: 'D:/clip.mp4', original_path: 'D:/movie/source.mkv' })
    // confidence is flattened onto the result — not a nested object.
    expect(out.results[0].confidence).toBe('HIGH')
    expect(out.results[0].confidence_score).toBe(0.94)
    expect('level' in out.results[0]).toBe(false)
  })

  it('analyzeEdited POSTs /api/analyze and returns segments', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      res({ segments: [{ id: 'seg-000', label: 'Clip 01', span: { start: 3.1, end: 21.4 }, nq: 36 }] }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const out = await adapter.analyzeEdited('D:/clip.mp4')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe(`${BASE}/api/analyze`)
    expect(JSON.parse(init.body)).toEqual({ edited_path: 'D:/clip.mp4' })
    expect(out.segments[0].span).toEqual({ start: 3.1, end: 21.4 })
  })

  it('exportResults POSTs /api/export with output_dir', async () => {
    const fetchMock = vi.fn().mockResolvedValue(res({ path: 'D:/export/result.results.json' }))
    vi.stubGlobal('fetch', fetchMock)
    const { path } = await adapter.exportResults(
      { schema_version: 1, original_video: null, edited_video: null, results: [] },
      { outDir: 'D:/export', filename: 'x' },
    )
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe(`${BASE}/api/export`)
    expect(JSON.parse(init.body)).toEqual({
      output_dir: 'D:/export',
      format: 'json',
      min_confidence: 'MEDIUM',
      low_policy: 'exclude',
      snap_scenes: true,
      material_width: 'scene',
    })
    expect(path).toBe('D:/export/result.results.json')
  })

  it('exportResults passes backend warnings through', async () => {
    // LOC-2001 碎片告警（后端已产出）：适配器必须原样带给结果页，不得吞掉。
    const fetchMock = vi.fn().mockResolvedValue(
      res({ path: 'D:/export/x.loc.edl', warnings: ['LOC-2001 导出清单中有 2 个不足 0.15 秒的极短片段'] }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const out = await adapter.exportResults(
      { schema_version: 1, original_video: null, edited_video: null, results: [] },
      { outDir: 'D:/export', format: 'edl' },
    )
    expect(out.warnings).toEqual(['LOC-2001 导出清单中有 2 个不足 0.15 秒的极短片段'])
  })

  it('exportResults forwards user-chosen options instead of hardcoded defaults', async () => {
    // A4 回归守护：门槛/低置信处理/吸附/片段宽度曾被子页面写死。
    const fetchMock = vi.fn().mockResolvedValue(res({ path: 'D:/export/x.xml' }))
    vi.stubGlobal('fetch', fetchMock)
    await adapter.exportResults(
      { schema_version: 1, original_video: null, edited_video: null, results: [] },
      { outDir: 'D:/export', format: 'fcp7_xml', minConfidence: 'HIGH',
        lowPolicy: 'backup', snapScenes: false, materialWidth: 'core' },
    )
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      output_dir: 'D:/export',
      format: 'fcp7_xml',
      min_confidence: 'HIGH',
      low_policy: 'backup',
      snap_scenes: false,
      material_width: 'core',
    })
  })

  it('loadResults POSTs /api/results/load with the batch path', async () => {
    // A3：读回已导出结果批（此前无端点，直接抛 BackendUnavailableError）。
    const batch: ResultBatchJson = {
      schema_version: 1, original_video: 'D:/movie.mkv', edited_video: 'D:/clip.mp4',
      results: [],
    }
    const fetchMock = vi.fn().mockResolvedValue(res(batch))
    vi.stubGlobal('fetch', fetchMock)
    const out = await adapter.loadResults('D:/export/clip.results.json')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe(`${BASE}/api/results/load`)
    expect(JSON.parse(init.body)).toEqual({ path: 'D:/export/clip.results.json' })
    expect(out.original_video).toBe('D:/movie.mkv')
  })

  it('network failure throws BackendUnavailableError', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network down')))
    await expect(adapter.buildIndex('x')).rejects.toBeInstanceOf(BackendUnavailableError)
  })

  it('HTTP 500 surfaces the bridge {error,detail} message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res({ error: 'IndexError', detail: 'boom' }, false, 500)))
    await expect(adapter.buildIndex('x')).rejects.toThrow('boom')
  })

  it('getIndexStatus is MISSING placeholder before any build', async () => {
    // 离线（拒绝连接）→ 诚实 MISSING 占位；stub 避免打到本机可能在跑的真实后端。
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('fetch failed')))
    const status = await adapter.getIndexStatus('D:/movie/source.mkv')
    expect(status.validation.status).toBe('MISSING')
    expect(status.indexMeta).toBeNull()
  })

  it('non-2xx with {code,message} surfaces the user wording plus the stable code', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(
      { error: 'load_failed', code: 'LOC-1103',
        message: '结果文件无法读取，请重新运行分析或改选其它结果文件。',
        detail: 'FileNotFoundError' },
      false, 400,
    )))
    await expect(adapter.loadResults('D:/nope.results.json')).rejects.toThrow(
      '结果文件无法读取，请重新运行分析或改选其它结果文件。（LOC-1103）',
    )
  })

  it('previewResult POSTs /api/preview and returns the media URL', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      res({ path: 'D:/data/previews/movie__6349-6602.mp4', duration: 253 }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const url = await adapter.previewResult('D:/movie/source.mkv', 6349, 6602)
    const [callUrl, init] = fetchMock.mock.calls[0]
    expect(callUrl).toBe(`${BASE}/api/preview`)
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual({ original_path: 'D:/movie/source.mkv', start: 6349, end: 6602 })
    // URL points at the media route that serves the extracted clip.
    expect(url).toBe(`${BASE}/api/preview/media/movie__6349-6602.mp4`)
  })

  it('getEditedVideoUrl returns the session edited-video route', () => {
    expect(adapter.getEditedVideoUrl()).toBe(`${BASE}/api/preview/edited`)
  })
})

describe('本机门禁 bootstrap (T1-3)', () => {
  const saved = (globalThis as { location?: unknown }).location
  afterEach(() => {
    Object.defineProperty(globalThis, 'location', { value: saved, configurable: true, writable: true })
    vi.unstubAllGlobals()
  })

  function setLocation(search: string) {
    Object.defineProperty(globalThis, 'location', { value: { search }, configurable: true, writable: true })
  }

  it('reads svl_port + svl_session from the page query', () => {
    setLocation('?svl_port=9111&svl_session=tok_123')
    expect(readBackendBootstrap()).toEqual({ baseUrl: 'http://127.0.0.1:9111', session: 'tok_123' })
  })

  it('运行时 svl_port 优先于构建期 VITE_API_BASE（打包随机端口回归，2026-09-28 验收）', () => {
    vi.stubEnv('VITE_API_BASE', 'http://127.0.0.1:8765')
    setLocation('?svl_port=9111')
    expect(readBackendBootstrap().baseUrl).toBe('http://127.0.0.1:9111')
    // 关键回归：resolveService 会把构建期 base 作为构造参数传入，运行时端口仍必须赢。
    const a = new HttpServiceAdapter('http://127.0.0.1:8765')
    expect(a.getEditedVideoUrl()).toContain('http://127.0.0.1:9111')
    vi.unstubAllEnvs()
  })

  it('ignores a non-numeric port and falls back to 8765', () => {
    setLocation('?svl_port=abc')
    expect(readBackendBootstrap().baseUrl).toBe('http://127.0.0.1:8765')
  })

  it('appends svl_session to gated requests, not to the exempt health probe', async () => {
    setLocation('?svl_port=9111&svl_session=tok/123')
    const a = new HttpServiceAdapter()
    const healthMock = vi.fn().mockResolvedValue(res({ status: 'ok', version: '0.1' }))
    vi.stubGlobal('fetch', healthMock)
    await expect(a.checkHealth()).resolves.toBe('CONNECTED')
    expect(healthMock.mock.calls[0][0]).toBe('http://127.0.0.1:9111/api/health')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res({ status: 'completed' })))
    await a.buildIndex('D:/movie/source.mkv')
    expect(vi.mocked(fetch).mock.calls[0][0]).toBe(
      'http://127.0.0.1:9111/api/index?svl_session=tok%2F123')
  })

  it('sends no session param when the token is absent (browser dev)', async () => {
    setLocation('')
    const a = new HttpServiceAdapter(BASE)
    const fetchMock = vi.fn().mockResolvedValue(res({ status: 'ok', version: '0.1' }))
    vi.stubGlobal('fetch', fetchMock)
    await a.checkHealth()
    expect(fetchMock.mock.calls[0][0]).toBe(`${BASE}/api/health`)
  })

  it('媒体直链（<video src> 无法带头）必须把会话令牌拼进 query（打包验收实测缺陷回归）', async () => {
    setLocation('?svl_port=9111&svl_session=tok_123')
    const a = new HttpServiceAdapter()
    expect(a.getEditedVideoUrl()).toBe(
      'http://127.0.0.1:9111/api/preview/edited?svl_session=tok_123')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res({ path: 'D:/p/a1__0-5.mp4', duration: 5 })))
    const url = await a.previewResult('D:/movie/source.mkv', 0, 5)
    expect(url).toBe(
      'http://127.0.0.1:9111/api/preview/media/a1__0-5.mp4?svl_session=tok_123')
  })
})
