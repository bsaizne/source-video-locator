// 导出任务（B 方案，2026-10-13）的 UI 侧契约测试。
// Http：POST /api/tasks/export 的请求体口径 + **与同步 /api/export 同源**（一份构造函数）；
// Mock：kind='export' 的即时完成形态与 warnings 开关；
// composable：轮询到完成/失败/取消三条分支 + 产物路径与告警透传。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { HttpServiceAdapter } from '../HttpServiceAdapter'
import { MockServiceAdapter } from '../MockServiceAdapter'
import { useExportTask } from '@/composables/useExportTask'
import { setServiceForTest } from '../inject'

const BASE = 'http://127.0.0.1:8765'
const EMPTY_BATCH = { schema_version: 1, original_video: null, edited_video: null, results: [] }

function res(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response
}

describe('HttpServiceAdapter.startExportTask', () => {
  let adapter: HttpServiceAdapter
  beforeEach(() => {
    adapter = new HttpServiceAdapter(BASE)
  })
  afterEach(() => vi.unstubAllGlobals())

  it('缺省口径 = LOW 门槛 / exclude / 吸附 / scene 宽（与 ResultsPage 初始值一致）', async () => {
    const fetchMock = vi.fn().mockResolvedValue(res({ task_id: 'x1' }))
    vi.stubGlobal('fetch', fetchMock)
    const out = await adapter.startExportTask()
    expect(fetchMock.mock.calls[0][0]).toBe(`${BASE}/api/tasks/export`)
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      output_dir: '',
      format: 'json',
      min_confidence: 'LOW',   // 2026-10-01 拍板「默认全部导出」，不得退回 MEDIUM
      low_policy: 'exclude',
      snap_scenes: true,
      material_width: 'scene',
    })
    expect(out.task_id).toBe('x1')
  })

  it('透传用户选的格式/门槛/低置信/吸附/片段宽度/目录', async () => {
    const fetchMock = vi.fn().mockResolvedValue(res({ task_id: 'x2' }))
    vi.stubGlobal('fetch', fetchMock)
    await adapter.startExportTask({
      outDir: 'D:/exports', format: 'jianying', minConfidence: 'HIGH',
      lowPolicy: 'backup', snapScenes: false, materialWidth: 'core',
    })
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      output_dir: 'D:/exports',
      format: 'jianying',
      min_confidence: 'HIGH',
      low_policy: 'backup',
      snap_scenes: false,
      material_width: 'core',
    })
  })

  it('同源锁：任务通道与同步通道的请求体逐字段相同（两处各写一份必然漂移）', async () => {
    const opts = {
      outDir: 'D:/exports', format: 'fcp7_xml' as const, minConfidence: 'MEDIUM' as const,
      lowPolicy: 'exclude' as const, snapScenes: true, materialWidth: 'core' as const,
    }
    const a = vi.fn().mockResolvedValue(res({ task_id: 'x3' }))
    const b = vi.fn().mockResolvedValue(res({ path: 'D:/x.xml' }))
    vi.stubGlobal('fetch', a)
    await adapter.startExportTask(opts)
    vi.stubGlobal('fetch', b)
    await adapter.exportResults(EMPTY_BATCH as never, opts)
    expect(a.mock.calls[0][1].body).toBe(b.mock.calls[0][1].body)
  })

  it('后端话术（LOC 码）原样抛出，供 UI 直接展示', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res(
      { code: 'LOC-1107', message: '视频读取/剪辑处理失败，请确认文件未损坏、未被其它程序占用后重试。',
        error: 'MediaError', detail: 'ffmpeg rc=1' }, false, 400)))
    await expect(adapter.startExportTask({ format: 'jianying' })).rejects.toThrow(/LOC-1107/)
  })
})

describe('MockServiceAdapter.startExportTask', () => {
  it('返回 kind=export 的即时完成任务（dev 态能走通 UI 分支）', async () => {
    const mock = new MockServiceAdapter()
    const { task_id } = await mock.startExportTask({ format: 'jianying', outDir: 'D:/x' })
    const t = await mock.getTask(task_id)
    expect(t.kind).toBe('export')
    expect(t.status).toBe('completed')
    const r = t.result as { kind: string; path: string; format: string }
    expect(r.kind).toBe('export')
    expect(r.format).toBe('jianying')
    expect(r.path).toBe('D:/x/results.loc.jy_draft')   // 与同步通道同一套命名规则
  })

  it('warnings 默认不给（不造假告警），与同步 exportResults 同开关', async () => {
    const mock = new MockServiceAdapter()
    const { task_id } = await mock.startExportTask()
    const t = await mock.getTask(task_id)
    expect((t.result as { warnings?: string[] }).warnings).toBeUndefined()
  })
})

describe('useExportTask composable', () => {
  afterEach(() => {
    setServiceForTest(null)
    vi.unstubAllGlobals()
  })

  function taskFrame(over: Record<string, unknown>) {
    return {
      task_id: 't1', kind: 'export', status: 'running', stage: 'exporting',
      progress: 0, created_at: '', finished_at: null, result: null, error: null,
      cancel_requested: false, message: '', ...over,
    }
  }

  /** 按脚本依次给出 getTask 结果（列表用完后重复最后一帧）。 */
  function fakeService(frames: Array<Record<string, unknown>>) {
    let i = 0
    return {
      startExportTask: vi.fn(async () => ({ task_id: 't1' })),
      getTask: vi.fn(async () => {
        const f = frames[Math.min(i, frames.length - 1)]
        i += 1
        return taskFrame(f)
      }),
      cancelTask: vi.fn(async () => {}),
    }
  }

  const done = {
    status: 'completed', progress: 100, stage: 'finished',
    result: { kind: 'export', format: 'jianying', path: 'D:/out/e.loc.jy_draft',
      warnings: ['LOC-2001 导出清单中有 2 个不足 0.15 秒的极短片段'] },
  }

  it('轮询到完成 → 写入产物路径与后端告警', async () => {
    const svc = fakeService([
      { progress: 41.2, message: '准备素材 26/64' },
      done,
    ])
    setServiceForTest(svc as never)
    const r = useExportTask({ pollMs: 1 })
    expect(await r.start({ format: 'jianying', outDir: 'D:/out' })).toBe(true)
    expect(r.running.value).toBe(false)
    expect(r.exportedPath.value).toBe('D:/out/e.loc.jy_draft')
    expect(r.warnings.value).toEqual(['LOC-2001 导出清单中有 2 个不足 0.15 秒的极短片段'])
    expect(r.progress.value).toBe(100)
    expect(svc.startExportTask).toHaveBeenCalledWith({ format: 'jianying', outDir: 'D:/out' })
  })

  it('失败任务 → error 用后端话术（LOC 码），running 复位', async () => {
    setServiceForTest(fakeService([{ status: 'failed', error: '导出失败（LOC-9999）' }]) as never)
    const r = useExportTask({ pollMs: 1 })
    expect(await r.start()).toBe(false)
    expect(r.error.value).toContain('LOC-9999')
    expect(r.running.value).toBe(false)
    expect(r.exportedPath.value).toBe('')
  })

  it('取消终态 → error=已取消 + cancelled 置位 + outDir 供页面解释残留', async () => {
    const svc = fakeService([{ status: 'cancelled' }])
    setServiceForTest(svc as never)
    const r = useExportTask({ pollMs: 1 })
    expect(await r.start({ outDir: 'D:/exports' })).toBe(false)
    expect(r.error.value).toBe('已取消')
    expect(r.cancelled.value).toBe(true)
    expect(r.outDir.value).toBe('D:/exports')
  })

  it('成功终态不得留下 cancelled 残值（重跑口径）', async () => {
    const svc = fakeService([{ status: 'cancelled' }, { status: 'running', progress: 5 }, done])
    setServiceForTest(svc as never)
    const r = useExportTask({ pollMs: 1 })
    expect(await r.start({ outDir: 'D:/a' })).toBe(false)
    expect(r.cancelled.value).toBe(true)
    // 第二次跑：先 cancelled 后完成 ⇒ 结束时应为 false、outDir 换成新的
    setServiceForTest(fakeService([done]) as never)
    expect(await r.start({ outDir: 'D:/b' })).toBe(true)
    expect(r.cancelled.value).toBe(false)
    expect(r.outDir.value).toBe('D:/b')
  })

  it('重跑会清掉上一次的产物路径与告警（不残留旧结果）', async () => {
    // 同一个 composable 实例、同一个假 service：假 getTask 按脚本走
    // （done → failed），第二次 start() 先 reset 再轮询到 failed。
    const svc = fakeService([done, { status: 'failed', error: 'x（LOC-9999）' }])
    setServiceForTest(svc as never)
    const r = useExportTask({ pollMs: 1 })
    expect(await r.start()).toBe(true)
    expect(r.exportedPath.value).not.toBe('')
    expect(r.warnings.value.length).toBe(1)
    expect(await r.start()).toBe(false)
    expect(r.exportedPath.value).toBe('')
    expect(r.warnings.value).toEqual([])
    expect(r.error.value).toContain('LOC-9999')
  })

  it('cancel() 只在任务在飞时打后端取消', async () => {
    const svc = fakeService([{ progress: 10 }, done])
    setServiceForTest(svc as never)
    const r = useExportTask({ pollMs: 1 })
    r.cancel()                       // 还没提交 → 不该打后端
    const p = r.start()
    await new Promise((res2) => setTimeout(res2, 0))
    r.cancel()                       // 在飞 → 应该打
    await p
    expect(svc.cancelTask).toHaveBeenCalledTimes(1)
  })
})
