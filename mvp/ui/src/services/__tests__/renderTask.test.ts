// 成片渲染的 UI 侧契约测试（2026-09-29 续30，竞品 video_renderer 移植）。
// Http：POST /api/tasks/render 的请求体口径；Mock：kind='render' 的即时完成形态；
// composable：轮询到完成/失败/取消三条分支 + 产物路径与打开目录。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { HttpServiceAdapter } from '../HttpServiceAdapter'
import { MockServiceAdapter } from '../MockServiceAdapter'
import { useRenderMovie } from '@/composables/useRenderMovie'
import { setServiceForTest } from '../inject'

const BASE = 'http://127.0.0.1:8765'

function res(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response
}

describe('HttpServiceAdapter.startRenderTask', () => {
  let adapter: HttpServiceAdapter
  beforeEach(() => {
    adapter = new HttpServiceAdapter(BASE)
  })
  afterEach(() => vi.unstubAllGlobals())

  it('缺省策略 = 三个 null（由后端 config 决定），output_dir 空串', async () => {
    const fetchMock = vi.fn().mockResolvedValue(res({ task_id: 'r1' }))
    vi.stubGlobal('fetch', fetchMock)
    const out = await adapter.startRenderTask()
    expect(fetchMock.mock.calls[0][0]).toBe(`${BASE}/api/tasks/render`)
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      output_dir: '', min_confidence: null, low_policy: null, snap_scenes: null,
    })
    expect(out.task_id).toBe('r1')
  })

  it('透传用户选的门槛/低置信/吸附/目录', async () => {
    const fetchMock = vi.fn().mockResolvedValue(res({ task_id: 'r2' }))
    vi.stubGlobal('fetch', fetchMock)
    await adapter.startRenderTask({
      outDir: 'D:/exports', minConfidence: 'HIGH', lowPolicy: 'backup', snapScenes: false,
    })
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      output_dir: 'D:/exports', min_confidence: 'HIGH', low_policy: 'backup',
      snap_scenes: false,
    })
  })

  it('后端话术（LOC 码）原样抛出，供 UI 直接展示', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(
      { code: 'LOC-1107', message: '视频读取/剪辑处理失败，请确认文件未损坏、未被其它程序占用后重试。',
        error: 'MediaError', detail: 'ffmpeg rc=1' }, false, 500)))
    await expect(adapter.startRenderTask()).rejects.toThrow(/LOC-1107/)
  })
})

describe('MockServiceAdapter.startRenderTask', () => {
  it('返回 kind=render 的即时完成任务（dev 态能走通 UI 分支）', async () => {
    const mock = new MockServiceAdapter()
    const { task_id } = await mock.startRenderTask()
    const t = await mock.getTask(task_id)
    expect(t.kind).toBe('render')
    expect(t.status).toBe('completed')
    const result = t.result as { movie_path: string; mode: string; total_frames: number }
    expect(result.movie_path).toContain('mock')
    expect(result.mode).toBe('copy')
    expect(result.total_frames).toBeGreaterThan(0)
  })
})

describe('useRenderMovie composable', () => {
  afterEach(() => {
    setServiceForTest(null)
    vi.unstubAllGlobals()
  })

  function taskFrame(over: Record<string, unknown>) {
    return {
      task_id: 't1', kind: 'render', status: 'running', stage: 'exporting',
      progress: 0, created_at: '', finished_at: null, result: null, error: null,
      cancel_requested: false, message: '', ...over,
    }
  }

  /** 按脚本依次给出 getTask 结果（列表用完后重复最后一帧）。 */
  function fakeService(frames: Array<Record<string, unknown>>) {
    let i = 0
    return {
      startRenderTask: vi.fn(async () => ({ task_id: 't1' })),
      getTask: vi.fn(async () => {
        const f = frames[Math.min(i, frames.length - 1)]
        i += 1
        return taskFrame(f)
      }),
      cancelTask: vi.fn(async () => {}),
    }
  }

  const done = {
    status: 'completed', progress: 100, result: {
      kind: 'render', movie_path: 'D:/out/movie_a.mp4', mode: 'copy', reused: false,
      segments: 10, fps: '25', duration_s: 40, total_frames: 1000,
      actual_encoder: 'libx264',
    },
  }

  it('轮询到完成 → 写入成片路径与编码器信息', async () => {
    const svc = fakeService([
      { progress: 30, message: '片段 3/10 渲染 30%' },
      done,
    ])
    setServiceForTest(svc as never)
    const r = useRenderMovie({ pollMs: 1 })
    expect(await r.start({ outDir: 'D:/out' })).toBe(true)
    expect(r.running.value).toBe(false)
    expect(r.moviePath.value).toBe('D:/out/movie_a.mp4')
    expect(r.result.value?.actual_encoder).toBe('libx264')
    expect(r.progress.value).toBe(100)
    expect(svc.startRenderTask).toHaveBeenCalledWith({ outDir: 'D:/out' })
    expect(svc.getTask).toHaveBeenCalledTimes(2)
  })

  it('失败任务 → error 用后端话术（LOC 码），running 复位', async () => {
    setServiceForTest(fakeService([{ status: 'failed', error: '合并失败（LOC-1107）' }]) as never)
    const r = useRenderMovie({ pollMs: 1 })
    expect(await r.start()).toBe(false)
    expect(r.error.value).toContain('LOC-1107')
    expect(r.running.value).toBe(false)
    expect(r.moviePath.value).toBe('')
  })

  it('取消终态 → error=已取消', async () => {
    setServiceForTest(fakeService([{ status: 'cancelled' }]) as never)
    const r = useRenderMovie({ pollMs: 1 })
    expect(await r.start()).toBe(false)
    expect(r.error.value).toBe('已取消')
  })

  it('cancel() 只在任务在飞时打后端取消', async () => {
    const svc = fakeService([{ progress: 10 }, done])
    setServiceForTest(svc as never)
    const r = useRenderMovie({ pollMs: 1 })
    r.cancel()                       // 还没提交 → 不该打后端
    const p = r.start()
    await new Promise((res2) => setTimeout(res2, 0))
    r.cancel()                       // 在飞 → 应该打
    await p
    expect(svc.cancelTask).toHaveBeenCalledWith('t1')
    expect(svc.cancelTask).toHaveBeenCalledTimes(1)
  })

  it('提交即失败（后端 400 无结果批）→ 不进入轮询', async () => {
    const svc = fakeService([{}])
    svc.startRenderTask = vi.fn(async () => {
      throw new Error('no results batch; call /api/results first')
    })
    setServiceForTest(svc as never)
    const r = useRenderMovie({ pollMs: 1 })
    expect(await r.start()).toBe(false)
    expect(r.error.value).toContain('no results batch')
    expect(svc.getTask).not.toHaveBeenCalled()
  })
})
