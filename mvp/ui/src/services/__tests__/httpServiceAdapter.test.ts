// HttpServiceAdapter unit tests (vitest, node env).
// Stubs global fetch with response-like objects so no real network or JS DOM is
// needed. Verifies the adapter drives the real FastAPI endpoints and preserves
// the flattened ResultBatch confidence contract.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { HttpServiceAdapter, BackendUnavailableError } from '../HttpServiceAdapter'
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

  it('loadResults is unsupported', async () => {
    await expect(adapter.loadResults('x')).rejects.toBeInstanceOf(BackendUnavailableError)
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
