// MockServiceAdapter — the default adapter. Implements ServiceAPI entirely in
// memory with deterministic mock data and simulated progress, so the UI runs
// with zero backend. Real data arrives later by swapping in HttpServiceAdapter
// (same interface, per ServiceAPI.ts).

import { createCancelToken, type CancelToken } from './cancel'
import {
  mockBackend,
  mockIndexBuildSteps,
  mockIndexMeta,
  mockIndexValidation,
  mockMediaInfo,
  mockResultBatch,
  mockSegments,
  mockSourceMerge,
} from './mockData'
import type {
  AnalysisOutput,
  BackendInfoJson,
  ConnectionStatus,
  DevicePreference,
  DeviceSettingsJson,
  IndexMetaJson,
  IndexStatus,
  IndexValidationJson,
  MediaInfoJson,
  ProgressEventJson,
  ResultBatchJson,
  ResultJson,
  SourceMergeJson,
  TaskEvent,
  TaskJson,
  TaskStage,
} from './types'
import type { BuildOpts, RenderOpts, ServiceAPI } from './ServiceAPI'

type Listener = (event: ProgressEventJson) => void

const sleep = (ms: number, token: CancelToken | null) =>
  new Promise<void>((resolve) => {
    setTimeout(() => {
      token?.raiseIfCancelled()
      resolve()
    }, ms)
  })

const MOCK_EXPORT_WARNINGS_STORAGE_KEY = 'svl.mock.exportWarnings'

/**
 * dev 态导出告警展示开关（续31 登记尾巴：Mock 通道不产 warnings，结果页看不到 LOC-2001/2002）。
 *
 * 真实告警由后端导出守卫（engine/localization/degradation_gate）算出，Mock **不重算那套判据**
 * ——两处实现同一判据必然漂移，比「看不到」更糟。要在 dev 验证展示链路时显式开：
 *   localStorage.setItem('svl.mock.exportWarnings', '1')
 * 文案与后端对外话术逐字一致（仅计数/段号是示例）。
 */
function mockExportWarnings(): string[] | undefined {
  if (typeof localStorage === 'undefined'
    || localStorage.getItem(MOCK_EXPORT_WARNINGS_STORAGE_KEY) !== '1') return undefined
  return [
    'LOC-2001 导出清单中有 2 个不足 0.15 秒的极短片段，导入剪辑软件后可能表现为闪烁或无效素材；建议在这些位置改用完整镜头边界。',
    'LOC-2002 第 3、7 段都指向原片同一区间 120.0-125.0s，导出工程里会出现重复素材；若是刻意的画面复用可忽略，否则建议在剪辑软件中合并为一条。',
  ]
}

export class MockServiceAdapter implements ServiceAPI {
  private listeners = new Set<Listener>()
  private token = createCancelToken()
  private _mockTask: TaskJson | null = null
  private _timer: ReturnType<typeof setTimeout> | null = null
  private devicePref: DevicePreference = 'auto'

  // Mock 阶段序列（映射后端 TaskStage）。
  private static readonly TASK_STAGES: Array<{ stage: TaskStage; progress: number; message: string }> = [
    { stage: 'indexing', progress: 15, message: 'indexing original @0.5fps' },
    { stage: 'embedding', progress: 35, message: 'embedding edited frames @2fps' },
    { stage: 'segmenting', progress: 50, message: 'detecting shots' },
    { stage: 'retrieval', progress: 72, message: 'retrieving candidates' },
    { stage: 'retrieval', progress: 88, message: 'assessing confidence' },
  ]

  onProgress(listener: Listener): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  checkHealth(): Promise<ConnectionStatus> {
    // Mock is always online (runs standalone in the browser).
    return Promise.resolve('CONNECTED')
  }

  getDeviceSettings(): Promise<DeviceSettingsJson> {
    return Promise.resolve(this.toDeviceSettings())
  }

  setDeviceSettings(preferred: DevicePreference): Promise<DeviceSettingsJson> {
    this.devicePref = preferred
    return Promise.resolve(this.toDeviceSettings())
  }

  private toDeviceSettings(): DeviceSettingsJson {
    // Mock 恒报告"支持 GPU (DirectML)"（对应本机 POC 通过的环境）：auto/directml -> amd，cpu -> cpu，无 fallback。
    const wantGpu = this.devicePref === 'directml' || this.devicePref === 'auto'
    return {
      preferred: this.devicePref,
      actual_device_name: wantGpu ? 'directml' : 'cpu',
      actual_device_type: wantGpu ? 'amd' : 'cpu',
      is_accelerator: wantGpu,
      fallback: false,
      available_devices: ['cpu', 'directml'],
    }
  }

  cancel(): void {
    this.token.cancel()
  }

  private emit(event: ProgressEventJson): void {
    for (const l of this.listeners) l(event)
  }

  async getIndexMeta(_originalPath: string): Promise<IndexMetaJson | null> {
    return mockIndexMeta()
  }

  async getMediaInfo(_path: string): Promise<MediaInfoJson> {
    return mockMediaInfo()
  }

  // 多原片合并（Mock）：与后端一样拒绝 <2 段，便于 UI 契约测试覆盖两条分支。
  async mergeSources(paths: string[]): Promise<SourceMergeJson> {
    const sources = paths.map((p) => p.trim()).filter(Boolean)
    if (sources.length < 2) throw new Error('at least 2 original files are required')
    await sleep(200, this.token)
    return mockSourceMerge(sources)
  }

  getIndexValidation(_originalPath: string): IndexValidationJson {
    return mockIndexValidation()
  }

  async getIndexStatus(_originalPath: string): Promise<IndexStatus> {
    return {
      indexMeta: mockIndexMeta(),
      validation: mockIndexValidation(),
      backend: mockBackend(),
    }
  }

  async buildIndex(_originalPath: string, opts?: BuildOpts): Promise<IndexStatus> {
    const token = opts?.cancelToken ?? this.token
    for (const step of mockIndexBuildSteps()) {
      token.raiseIfCancelled()
      this.emit(step)
      await sleep(260, token)
    }
    return this.getIndexStatus(_originalPath)
  }

  async analyzeEdited(_editedPath: string, opts?: BuildOpts): Promise<AnalysisOutput> {
    const token = opts?.cancelToken ?? this.token
    const segments = mockSegments()
    const total = segments.length
    this.emit({ stage: 'EDITED_FEATURE_EXTRACTION', current: 0, total, message: 'extracting edited frames @2fps' })
    await sleep(300, token)
    this.emit({ stage: 'EDITED_FEATURE_EXTRACTION', current: total, total, message: 'features ready' })
    this.emit({ stage: 'SEGMENT_DETECTION', current: 0, total, message: 'detecting shots' })
    await sleep(220, token)
    this.emit({ stage: 'SEGMENT_DETECTION', current: total, total, message: `${total} segments` })
    return { segments }
  }

  async locate(editedPath: string, originalPath: string, opts?: BuildOpts): Promise<ResultBatchJson> {
    const token = opts?.cancelToken ?? this.token
    const segments = mockSegments()
    await this.analyzeEdited(editedPath, opts)
    const pipeline: ProgressEventJson[] = [
      { stage: 'CANDIDATE_RETRIEVAL', current: 4, total: segments.length, message: 'retrieving candidates' },
      { stage: 'LOCALIZATION', current: 6, total: segments.length, message: 'localizing segments' },
      { stage: 'CONFIDENCE', current: segments.length, total: segments.length, message: 'assessing confidence' },
    ]
    for (const e of pipeline) {
      token.raiseIfCancelled()
      this.emit(e)
      await sleep(240, token)
    }
    void originalPath
    return mockResultBatch()
  }

  async exportResults(
    _batch: ResultBatchJson,
    opts?: {
      outDir?: string
      filename?: string
      format?: 'json' | 'edl' | 'fcp7_xml' | 'jianying'
      minConfidence?: 'HIGH' | 'MEDIUM' | 'LOW'
      lowPolicy?: 'exclude' | 'backup'
      snapScenes?: boolean
      materialWidth?: 'scene' | 'core'
      cancelToken?: CancelToken
    },
  ): Promise<{ path: string; warnings?: string[] }> {
    const token = opts?.cancelToken ?? this.token
    token.raiseIfCancelled()
    this.emit({ stage: 'EXPORT', current: 0, total: 1, message: 'exporting selected clips' })
    await sleep(280, null)
    this.emit({ stage: 'EXPORT', current: 1, total: 1, message: 'export complete' })
    const name = opts?.filename ?? 'results'
    const dir = opts?.outDir ?? 'C:/Users/Public/Videos/VideoLocator/exports'
    const fmt = opts?.format ?? 'json'
    const path = fmt === 'jianying' ? `${dir}/${name}.loc.jy_draft`
      : fmt === 'edl' ? `${dir}/${name}.loc.edl`
      : fmt === 'fcp7_xml' ? `${dir}/${name}.loc.xml`
      : `${dir}/${name}.results.json`
    return { path, warnings: mockExportWarnings() }
  }

  async overrideResult(resultId: string, start: number, end: number): Promise<ResultJson> {
    const r = mockResultBatch().results.find((x) => x.result_id === resultId) ??
      mockResultBatch().results[0]
    return {
      ...r,
      original: { candidate_start: start, candidate_end: end },
      source: 'manual',
      manual_override: true,
      manual_timestamp: new Date().toISOString(),
    }
  }

  excludeResult(resultId: string, excluded: boolean): Promise<ResultJson> {
    const r = mockResultBatch().results[0]
    return Promise.resolve({
      ...r,
      result_id: resultId,
      excluded,
    })
  }

  fetchRecentLogs(): Promise<{ path: string; truncated: boolean; text: string }> {
    return Promise.resolve({
      path: 'C:/mock/logs/video_locator.log',
      truncated: false,
      text: '[mock] log line 1\n[mock] log line 2\n',
    })
  }

  downloadLogsArchive(): Promise<void> {
    return Promise.resolve()
  }

  async loadResults(_path: string): Promise<ResultBatchJson> {
    return mockResultBatch()
  }

  // ------------------------------------------------------------------ video preview (mock)
  // Mock 返回可播放的公开示例视频地址（需要联网；离线时播放器显示占位，不影响流程）。
  previewResult(_originalPath: string, _start: number, _end: number): Promise<string> {
    return Promise.resolve('https://media.w3.org/2010/05/bunny/trailer.mp4')
  }

  getEditedVideoUrl(): string {
    return 'https://media.w3.org/2010/05/sintel/trailer.mp4'
  }

  // ------------------------------------------------------------------ async tasks (mock)
  async startAnalyzeTask(
    editedPath: string,
    originalPath: string,
    originalPaths?: string[],
  ): Promise<{ task_id: string }> {
    void editedPath
    void originalPath
    void originalPaths
    const task: TaskJson = {
      task_id: 'mock-task-0001',
      status: 'pending',
      stage: 'idle',
      progress: 0,
      created_at: new Date().toISOString(),
      finished_at: null,
      result: null,
      error: null,
      cancel_requested: false,
      message: '',
    }
    this._mockTask = task
    return { task_id: task.task_id }
  }

  // 成片渲染任务（Mock）：与后端同 kind='render' 形态，第一次轮询即完成，
  // 便于 dev 态把 UI 的进度/结果分支走通（产物路径是假路径，UI 会同时显示 Mock 横幅）。
  async startRenderTask(opts?: RenderOpts): Promise<{ task_id: string }> {
    void opts
    const task: TaskJson = {
      task_id: 'mock-render-0001',
      kind: 'render',
      status: 'completed',
      stage: 'finished',
      progress: 100,
      created_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
      result: {
        kind: 'render',
        movie_path: 'C:/mock/rendered/movie_mock.mp4',
        mode: 'copy',
        reused: false,
        segments: 3,
        fps: '25',
        duration_s: 12.5,
        total_frames: 312,
        actual_encoder: 'libx264',
        hdr_downgraded: false,
        clips: 3,
      },
      error: null,
      cancel_requested: false,
      message: '最终视频生成成功',
    }
    this._mockTask = task
    return { task_id: task.task_id }
  }

  async getTask(taskId: string): Promise<TaskJson> {
    if (this._mockTask && this._mockTask.task_id === taskId) return { ...this._mockTask }
    return {
      task_id: taskId,
      status: 'pending',
      stage: 'idle',
      progress: 0,
      created_at: new Date().toISOString(),
      finished_at: null,
      result: null,
      error: null,
      cancel_requested: false,
      message: '',
    }
  }

  async cancelTask(taskId: string): Promise<void> {
    if (this._mockTask && this._mockTask.task_id === taskId) {
      this._mockTask.cancel_requested = true
    }
  }

  subscribeProgress(taskId: string, cb: (event: TaskEvent) => void): () => void {
    if (this._mockTask) {
      this._mockTask.status = 'running'
    }
    const stages = MockServiceAdapter.TASK_STAGES
    let i = 0
    const tick = () => {
      if (this._mockTask?.cancel_requested) {
        cb({ type: 'cancelled', task_id: taskId })
        return
      }
      if (i >= stages.length) {
        if (this._mockTask) {
          this._mockTask.status = 'completed'
          this._mockTask.stage = 'finished'
          this._mockTask.progress = 100
          this._mockTask.result = mockResultBatch()
          this._mockTask.finished_at = new Date().toISOString()
        }
        cb({ type: 'completed', task_id: taskId })
        return
      }
      const s = stages[i]
      if (this._mockTask) {
        this._mockTask.stage = s.stage
        this._mockTask.progress = s.progress
      }
      cb({
        type: 'progress',
        task_id: taskId,
        status: 'running',
        stage: s.stage,
        progress: s.progress,
        message: s.message,
      })
      i += 1
      this._timer = setTimeout(tick, 300)
    }
    tick()
    return () => {
      if (this._timer) clearTimeout(this._timer)
    }
  }

  /** For dev/debug: the current backend info the UI displays. */
  get backends(): BackendInfoJson {
    return mockBackend()
  }
}
