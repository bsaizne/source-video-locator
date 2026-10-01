// HttpServiceAdapter — drives the real Python FastAPI bridge (mvp/api) over localhost.
//
// Implements the same ServiceAPI seam as MockServiceAdapter; the UI is switched by
// setting VITE_BACKEND_MODE=http (default is Mock). Endpoints match mvp/api/README:
//   POST /api/index   {video_path}          -> {status,frames,backend}
//   POST /api/analyze {edited_path}         -> {segments:[{id,label,span,nq}]}
//   POST /api/results {edited_path,original_path} -> ResultBatchJson  (confidence flattened)
//   POST /api/export  {output_dir}          -> {path}
//   POST /api/results/load {path}           -> ResultBatchJson
//   GET  /api/health                        -> {status,version}
//
// The Python bridge has no WS and no GET index-status endpoint, so:
//   - onProgress emits coarse "INDEXING / ANALYZING / LOCATING" stage hints (no WebSocket).
//   - getIndexStatus / getIndexMeta reflect the last buildIndex result, else a MISSING
//     placeholder (the backend exposes no status query; this is honest, not fabricated).
//   - cancel() is a no-op over a blocking HTTP request (no WS to signal cancellation).

import { type CancelToken } from './cancel'
import { createTransport, type Transport } from './transport'
import { openProgressSocket, type ProgressSocket } from './progressSocket'
import type {
  AnalysisOutput,
  ConnectionStatus,
  DeviceName,
  DevicePreference,
  DeviceSettingsJson,
  DeviceType,
  IndexStatus,
  IndexValidationJson,
  MediaInfoJson,
  ProgressEventJson,
  ResultJson,
  ResultBatchJson,
  SourceMergeJson,
  TaskEvent,
  TaskJson,
} from './types'
import type { BuildOpts, RenderOpts, ServiceAPI } from './ServiceAPI'

type Listener = (event: ProgressEventJson) => void

const DEFAULT_BASE = 'http://127.0.0.1:8765'
const SESSION_QUERY = 'svl_session'

/** Electron 主进程把后端实际端口与会话令牌挂在页面 URL query 上（T1-3 本机门禁）。
 *  浏览器 dev（Vite + 手工 uvicorn）没有这两个参数：端口回退 env/默认、令牌为空 = 门禁关闭。
 *  ⚠️ 优先级（2026-09-28 打包验收修正）：**运行时 svl_port > 构建期 VITE_API_BASE**——
 *  发行包 .env.production 钉死了 8765，而后端打包态走 OS 随机端口；env 优先会让
 *  渲染层所有直连 baseUrl 的媒体 URL（<video src>）指错端口（实测 MEDIA_ERR_SRC_NOT_SUPPORTED）。 */
export function readBackendBootstrap(): { baseUrl: string; session: string } {
  const q = typeof location === 'undefined' ? null : new URLSearchParams(location.search)
  const port = q?.get('svl_port')
  const session = q?.get(SESSION_QUERY) ?? ''
  const envBase = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''
  const baseUrl = (port && /^\d+$/.test(port) ? `http://127.0.0.1:${port}` : '') || envBase || DEFAULT_BASE
  return { baseUrl, session }
}

const TERMINAL_TYPES = new Set(['completed', 'failed', 'cancelled', 'error'])
function isTerminal(event: TaskEvent): boolean {
  return 'type' in event && TERMINAL_TYPES.has(event.type)
}

// The bridge reports `backend.device_name`/`device_type` as free strings. Clamp
// to the legal display unions (defaulting to 'cpu') so the UI never sees an
// unknown value; this is display-only, never used as a branching key.
const DEVICE_NAMES: readonly DeviceName[] = ['cpu', 'directml', 'cuda:0', 'mps', 'rocm:0', 'AMD_GPU_BACKEND_BLOCKED']
const DEVICE_TYPES: readonly DeviceType[] = ['cpu', 'amd', 'mps', 'cuda']

function normDeviceName(v: string | undefined): DeviceName {
  return v && (DEVICE_NAMES as readonly string[]).includes(v) ? (v as DeviceName) : 'cpu'
}

function normDeviceType(v: string | undefined): DeviceType {
  return v && (DEVICE_TYPES as readonly string[]).includes(v) ? (v as DeviceType) : 'cpu'
}

// Raised on any network-level failure (fetch rejects, non-2xx handled separately).
export class BackendUnavailableError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'BackendUnavailableError'
  }
}

export class HttpServiceAdapter implements ServiceAPI {
  private listeners = new Set<Listener>()
  private lastIndexStatus: IndexStatus | null = null
  private readonly baseUrl: string
  private readonly transport: Transport

  private readonly session: string

  constructor(baseUrl?: string) {
    const boot = readBackendBootstrap()
    // ⚠️ 运行时 svl_port 优先于调用方传入的 base（resolveService 会把构建期
    // VITE_API_BASE 当 base 传进来；打包态后端是随机端口，构建期值赢就会让
    // 所有直连 URL——<video src>/WS——指向 8765。2026-09-28 打包验收实测缺陷）。
    const port = typeof location === 'undefined' ? null : new URLSearchParams(location.search).get('svl_port')
    this.baseUrl = (port && /^\d+$/.test(port)) ? boot.baseUrl : (baseUrl ?? boot.baseUrl)
    this.session = boot.session
    // Electron -> bridge (via main process, bypasses CORS); otherwise direct fetch.
    this.transport = createTransport(this.baseUrl)
  }

  /** 令牌走查询参数（后端 `X-Locator-Session` 头亦可），避免改动 transport 契约。 */
  private withSession(path: string): string {
    if (!this.session) return path
    return `${path}${path.includes('?') ? '&' : '?'}${SESSION_QUERY}=${encodeURIComponent(this.session)}`
  }

  // ------------------------------------------------------------------ transport
  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await this.transport.request(this.withSession(path), {
      method: init?.method ?? 'GET',
      body: init?.body as string | undefined,
    })
    if (res.network) {
      // 网络级失败：话术面向用户，技术 detail 保留在括号内供工程师定位（续21 登记的英文技术串尾巴）。
      throw new BackendUnavailableError(
        `无法连接后端服务，请重新启动软件；若反复出现请下载日志发给支持人员（${res.detail ?? 'network error'}）`,
      )
    }
    if (!res.ok) {
      // Surface the bridge's {code,message,detail}: 面向用户的话术 + 稳定错误码优先，
      // 技术 detail 留在括号外供工程师读日志（T1-2）。
      const body = (res.data ?? {}) as { code?: string; message?: string }
      if (body.message) {
        throw new Error(body.code ? `${body.message}（${body.code}）` : body.message)
      }
      let detail = `HTTP ${res.status}`
      if (res.detail) detail = res.detail
      else if (res.error) detail = res.error
      throw new Error(detail)
    }
    return res.data as T
  }

  // ------------------------------------------------------------------ health
  async checkHealth(): Promise<ConnectionStatus> {
    const res = await this.transport.request('/api/health', { method: 'GET' })
    if (res.network || !res.ok) return 'OFFLINE'
    const body = res.data as { status?: string }
    return body?.status === 'ok' ? 'CONNECTED' : 'OFFLINE'
  }

  // --------------------------------------------------- device backend settings
  async getDeviceSettings(): Promise<DeviceSettingsJson> {
    return this.request<DeviceSettingsJson>('/api/settings/device', { method: 'GET' })
  }

  async setDeviceSettings(preferred: DevicePreference): Promise<DeviceSettingsJson> {
    return this.request<DeviceSettingsJson>('/api/settings/device', {
      method: 'POST',
      body: JSON.stringify({ preferred }),
    })
  }

  // ------------------------------------------------------------------ Index
  async getIndexStatus(originalPath: string): Promise<IndexStatus> {
    // Real query against GET /api/index/status (VALID/INVALID/MISSING from disk),
    // so the badge reflects reality even after an app restart or a failed build.
    try {
      const res = await this.request<{ status: string; reason: string | null }>(
        `/api/index/status?video_path=${encodeURIComponent(originalPath)}`,
        { method: 'GET' },
      )
      const validation: IndexValidationJson = {
        status: res.status as IndexValidationJson['status'],
        reason: res.reason,
      }
      return {
        indexMeta: this.lastIndexStatus?.indexMeta ?? null,
        validation,
        backend: this.lastIndexStatus?.backend ?? null,
      }
    } catch {
      // Backend unreachable (Http offline) — honest MISSING placeholder, not a crash.
      return this.lastIndexStatus ?? this.unknownIndexStatus()
    }
  }

  // ------------------------------------------------------------------ media metadata
  // GET /api/media/info -> ffprobe 元数据（真实时长/fps/分辨率，替代项目卡假数据）。
  // 路径含中文/空格/反斜杠 → 必须 encodeURIComponent。
  async getMediaInfo(path: string): Promise<MediaInfoJson> {
    return this.request<MediaInfoJson>(
      `/api/media/info?path=${encodeURIComponent(path)}`,
      { method: 'GET' },
    )
  }

  async getIndexMeta(_originalPath: string): Promise<IndexStatus['indexMeta']> {
    return this.lastIndexStatus?.indexMeta ?? null
  }

  // 多原片合并：POST /api/source/merge {paths} -> {merged_path,mode,reused,duration_s}。
  // 后端 <2 个文件直接 400（合并语义上 0/1 段无需合并），调用方须先自己挡。
  // MediaError（缺视频轨/时长未知/合并失败）走后端全局 handler -> 500 + public_error，
  // 由 request() 统一转成「对外话术（LOC 码）」。
  async mergeSources(paths: string[]): Promise<SourceMergeJson> {
    return this.request<SourceMergeJson>('/api/source/merge', {
      method: 'POST',
      body: JSON.stringify({ paths }),
    })
  }

  async buildIndex(originalPath: string, opts?: BuildOpts): Promise<IndexStatus> {
    void opts
    this.emit({ stage: 'INDEX_BUILD', current: 0, total: 0, message: 'indexing…' })
    const res = await this.request<{
      status: string
      frames: number
      backend: { device_name: string; device_type: string }
    }>('/api/index', { method: 'POST', body: JSON.stringify({ video_path: originalPath }) })
    const st = this.toIndexStatus(res)
    this.lastIndexStatus = st
    this.emit({ stage: 'INDEX_BUILD', current: 1, total: 1, message: 'index ready' })
    return st
  }

  // ------------------------------------------------------------------ Analysis
  async analyzeEdited(editedPath: string, opts?: BuildOpts): Promise<AnalysisOutput> {
    void opts
    this.emit({ stage: 'EDITED_FEATURE_EXTRACTION', current: 0, total: 0, message: 'extracting edited frames' })
    const res = await this.request<{ segments: AnalysisOutput['segments'] }>('/api/analyze', {
      method: 'POST',
      body: JSON.stringify({ edited_path: editedPath }),
    })
    this.emit({ stage: 'SEGMENT_DETECTION', current: res.segments.length, total: res.segments.length, message: `${res.segments.length} segments` })
    return { segments: res.segments }
  }

  // ------------------------------------------------------------------ Results
  async locate(editedPath: string, originalPath: string, opts?: BuildOpts): Promise<ResultBatchJson> {
    void opts
    // Coarse stage hints (the bridge gives no per-step WS progress this stage).
    this.emit({ stage: 'INDEX_BUILD', current: 1, total: 1, message: 'index' })
    this.emit({ stage: 'EDITED_FEATURE_EXTRACTION', current: 1, total: 1, message: 'features' })
    this.emit({ stage: 'SEGMENT_DETECTION', current: 1, total: 1, message: 'segments' })
    this.emit({ stage: 'CANDIDATE_RETRIEVAL', current: 1, total: 1, message: 'retrieving candidates' })
    this.emit({ stage: 'LOCALIZATION', current: 1, total: 1, message: 'localizing segments' })
    this.emit({ stage: 'CONFIDENCE', current: 1, total: 1, message: 'assessing confidence' })
    return this.request<ResultBatchJson>('/api/results', {
      method: 'POST',
      body: JSON.stringify({ edited_path: editedPath, original_path: originalPath }),
    })
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
    // The bridge's /api/export exports its own session's latest results batch
    // (set by the preceding /api/results or the async task). format/置信门槛/
    // 输出目录随请求转发。缺省门槛 = LOW（2026-10-01 拍板「默认全部导出」，与
    // ResultsPage 的初始值一致；取代 Phase 22 反馈⑨「默认不含低置信」口径）。
    // warnings：后端导出前守卫产出的对外告警（如 LOC-2001 碎片告警），透传给 UI 展示。
    void _batch
    void opts?.filename
    void opts?.cancelToken
    return this.request<{ path: string; warnings?: string[] }>('/api/export', {
      method: 'POST',
      body: JSON.stringify({
        output_dir: opts?.outDir ?? '',
        format: opts?.format ?? 'json',
        min_confidence: opts?.minConfidence ?? 'LOW',
        low_policy: opts?.lowPolicy ?? 'exclude',
        snap_scenes: opts?.snapScenes ?? true,
        material_width: opts?.materialWidth ?? 'scene',
      }),
    })
  }

  async excludeResult(resultId: string, excluded: boolean): Promise<ResultJson> {
    return this.request<ResultJson>('/api/results/exclude', {
      method: 'POST',
      body: JSON.stringify({ result_id: resultId, excluded }),
    })
  }

  async overrideResult(resultId: string, start: number, end: number): Promise<ResultJson> {
    return this.request<ResultJson>('/api/results/override', {
      method: 'POST',
      body: JSON.stringify({ result_id: resultId, start, end }),
    })
  }

  async fetchRecentLogs(bytesLimit = 49152): Promise<{ path: string; truncated: boolean; text: string }> {
    return this.request<{ path: string; truncated: boolean; text: string }>(
      `/api/logs/recent?bytes_limit=${bytesLimit}`,
    )
  }

  async downloadLogsArchive(): Promise<void> {
    const res = await fetch(this.withSession(`${this.baseUrl}/api/logs/archive`))
    if (!res.ok) throw new BackendUnavailableError(`logs archive failed: ${res.status}`)
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'video_locator_logs.zip'
    a.click()
    URL.revokeObjectURL(url)
  }

  async loadResults(path: string): Promise<ResultBatchJson> {
    // POST /api/results/load -> 读回已导出的结果批（重启后恢复会话与手工修正）
    return this.request<ResultBatchJson>('/api/results/load', {
      method: 'POST',
      body: JSON.stringify({ path }),
    })
  }

  // ------------------------------------------------------------------ video preview
  // POST /api/preview -> { path, duration }; the playable URL is the media route
  // that serves the extracted clip (Starlette Range -> HTML5 video seeking works).
  // ⚠️ 这两个 URL 直接进 <video src>（无法带请求头），必须把会话令牌拼进 query，
  // 否则发行通道门禁（/api/preview/* 非放行清单）会 401 → MEDIA_ERR_SRC_NOT_SUPPORTED
  //（2026-09-28 打包验收实测发现的真实缺陷）。
  async previewResult(originalPath: string, start: number, end: number): Promise<string> {
    const res = await this.request<{ path: string; duration: number }>('/api/preview', {
      method: 'POST',
      body: JSON.stringify({ original_path: originalPath, start, end }),
    })
    const name = res.path.split(/[\\/]/).pop() ?? ''
    return this.withSession(`${this.baseUrl}/api/preview/media/${encodeURIComponent(name)}`)
  }

  getEditedVideoUrl(): string {
    return this.withSession(`${this.baseUrl}/api/preview/edited`)
  }

  // ------------------------------------------------------------------ async tasks
  // originalPaths ≥2（多原片未合并）时后端 worker 先合并再定位；此时 original_path 留空，
  // 由 worker 把合并产物回写任务（桥层 routes/tasks.py 同口径）。
  async startAnalyzeTask(
    editedPath: string,
    originalPath: string,
    originalPaths?: string[],
  ): Promise<{ task_id: string }> {
    const sources = (originalPaths ?? []).map((p) => p.trim()).filter(Boolean)
    const body =
      sources.length > 1
        ? { edited_path: editedPath, original_path: '', original_paths: sources }
        : { edited_path: editedPath, original_path: originalPath }
    return this.request<{ task_id: string }>('/api/tasks/analyze', {
      method: 'POST',
      body: JSON.stringify(body),
    })
  }

  // 成片渲染任务（POST /api/tasks/render，2026-09-29 续30）。结果批由后端取会话当前批，
  // 不在请求体里传；策略参数缺省 = 用后端 config.export/render 的默认值。
  async startRenderTask(opts?: RenderOpts): Promise<{ task_id: string }> {
    return this.request<{ task_id: string }>('/api/tasks/render', {
      method: 'POST',
      body: JSON.stringify({
        output_dir: opts?.outDir ?? '',
        min_confidence: opts?.minConfidence ?? null,
        low_policy: opts?.lowPolicy ?? null,
        snap_scenes: opts?.snapScenes ?? null,
      }),
    })
  }

  async getTask(taskId: string): Promise<TaskJson> {    return this.request<TaskJson>(`/api/tasks/${encodeURIComponent(taskId)}`, { method: 'GET' })
  }

  async cancelTask(taskId: string): Promise<void> {
    await this.request(`/api/tasks/${encodeURIComponent(taskId)}/cancel`, { method: 'POST' })
  }

  subscribeProgress(taskId: string, cb: (event: TaskEvent) => void): () => void {
    let finished = false
    let disposed = false
    let reconnected = false
    let socket: ProgressSocket | null = null
    const onEvent = (event: TaskEvent) => {
      cb(event)
      if (isTerminal(event)) finished = true
    }
    // On unexpected disconnect (before a terminal frame), reconnect once.
    const onClose = () => {
      if (disposed || finished || reconnected) return
      reconnected = true
      socket = openProgressSocket(this.baseUrl, taskId, { onEvent, onClose })
    }
    socket = openProgressSocket(this.baseUrl, taskId, { onEvent, onClose })
    return () => {
      disposed = true
      socket?.close()
    }
  }

  // ------------------------------------------------------------------ progress + cancel
  onProgress(listener: Listener): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  cancel(): void {
    // No WebSocket; the bridge locate is a blocking HTTP request. Cancellation is
    // a next-stage feature (WS /ws/progress). Honest no-op for now.
  }

  // ------------------------------------------------------------------ helpers
  private emit(event: ProgressEventJson): void {
    for (const l of this.listeners) l(event)
  }

  private toIndexStatus(res: { frames: number; backend: { device_name: string; device_type: string } }): IndexStatus {
    const deviceName = normDeviceName(res.backend?.device_name)
    const deviceType = normDeviceType(res.backend?.device_type)
    return {
      indexMeta: {
        index_version: 1,
        source_file: '',
        file_size: 0,
        duration: 0,
        file_hash: '',
        feature_model: 'dinov2_vits14',
        feature_version: '',
        sampling_fps: 0.5,
        feature_dim: 384,
        num_frames: res.frames ?? 0,
        backend: deviceName,
        created_at: '',
        device_machine_id: '',
        extractor: { normalize: 'l2', resize: '518x518', mean_std: 'imagenet', preprocess_sha: '' },
      },
      validation: { status: 'VALID', reason: null },
      backend: {
        deviceName,
        deviceType,
        isAccelerator: deviceType !== 'cpu',
        fallback: false,
      },
    }
  }

  private unknownIndexStatus(): IndexStatus {
    return {
      indexMeta: null,
      validation: { status: 'MISSING', reason: null },
      // 状态查询/未知时诚实返回 null，不硬编码 cpu（侧栏「后端 CPU」误标根因，2026-10-01 E2E）。
      backend: null,
    }
  }
}
