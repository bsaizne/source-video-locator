// HttpServiceAdapter — drives the real Python FastAPI bridge (mvp/api) over localhost.
//
// Implements the same ServiceAPI seam as MockServiceAdapter; the UI is switched by
// setting VITE_BACKEND_MODE=http (default is Mock). Endpoints match mvp/api/README:
//   POST /api/index   {video_path}          -> {status,frames,backend}
//   POST /api/analyze {edited_path}         -> {segments:[{id,label,span,nq}]}
//   POST /api/results {edited_path,original_path} -> ResultBatchJson  (confidence flattened)
//   POST /api/export  {output_dir}          -> {path}
//   GET  /api/health                        -> {status,version}
//
// The Python bridge has no WS and no GET index-status/load-results endpoints, so:
//   - onProgress emits coarse "INDEXING / ANALYZING / LOCATING" stage hints (no WebSocket).
//   - getIndexStatus / getIndexMeta reflect the last buildIndex result, else a MISSING
//     placeholder (the backend exposes no status query; this is honest, not fabricated).
//   - loadResults throws BackendUnavailableError (no endpoint).
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
  ProgressEventJson,
  ResultJson,
  ResultBatchJson,
  TaskEvent,
  TaskJson,
} from './types'
import type { BuildOpts, ServiceAPI } from './ServiceAPI'

type Listener = (event: ProgressEventJson) => void

const DEFAULT_BASE = 'http://127.0.0.1:8765'

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
  private readonly transport: Transport

  constructor(private readonly baseUrl = import.meta.env.VITE_API_BASE ?? DEFAULT_BASE) {
    // Electron -> bridge (via main process, bypasses CORS); otherwise direct fetch.
    this.transport = createTransport(this.baseUrl)
  }

  // ------------------------------------------------------------------ transport
  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await this.transport.request(path, {
      method: init?.method ?? 'GET',
      body: init?.body as string | undefined,
    })
    if (res.network) {
      throw new BackendUnavailableError(
        `cannot reach backend: ${res.detail ?? 'network error'}`,
      )
    }
    if (!res.ok) {
      // Surface the bridge's {error,detail} (or a bare HTTP status) as an Error.
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
        backend: this.lastIndexStatus?.backend ?? this.unknownIndexStatus().backend,
      }
    } catch {
      // Backend unreachable (Http offline) — honest MISSING placeholder, not a crash.
      return this.lastIndexStatus ?? this.unknownIndexStatus()
    }
  }

  async getIndexMeta(_originalPath: string): Promise<IndexStatus['indexMeta']> {
    return this.lastIndexStatus?.indexMeta ?? null
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
  ): Promise<{ path: string }> {
    // The bridge's /api/export exports its own session's latest results batch
    // (set by the preceding /api/results or the async task). format/置信门槛/
    // 输出目录随请求转发（Phase 22 反馈 ⑨：默认不含低置信，导出即最终工程）。
    void _batch
    void opts?.filename
    void opts?.cancelToken
    return this.request<{ path: string }>('/api/export', {
      method: 'POST',
      body: JSON.stringify({
        output_dir: opts?.outDir ?? '',
        format: opts?.format ?? 'json',
        min_confidence: opts?.minConfidence ?? 'MEDIUM',
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
    const res = await fetch(`${this.baseUrl}/api/logs/archive`)
    if (!res.ok) throw new BackendUnavailableError(`logs archive failed: ${res.status}`)
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'video_locator_logs.zip'
    a.click()
    URL.revokeObjectURL(url)
  }

  async loadResults(_path: string): Promise<ResultBatchJson> {
    // The bridge exposes no GET /api/results/load endpoint.
    throw new BackendUnavailableError('loadResults is not supported by the current API')
  }

  // ------------------------------------------------------------------ video preview
  // POST /api/preview -> { path, duration }; the playable URL is the media route
  // that serves the extracted clip (Starlette Range -> HTML5 video seeking works).
  async previewResult(originalPath: string, start: number, end: number): Promise<string> {
    const res = await this.request<{ path: string; duration: number }>('/api/preview', {
      method: 'POST',
      body: JSON.stringify({ original_path: originalPath, start, end }),
    })
    const name = res.path.split(/[\\/]/).pop() ?? ''
    return `${this.baseUrl}/api/preview/media/${encodeURIComponent(name)}`
  }

  getEditedVideoUrl(): string {
    return `${this.baseUrl}/api/preview/edited`
  }

  // ------------------------------------------------------------------ async tasks
  async startAnalyzeTask(editedPath: string, originalPath: string): Promise<{ task_id: string }> {
    return this.request<{ task_id: string }>('/api/tasks/analyze', {
      method: 'POST',
      body: JSON.stringify({ edited_path: editedPath, original_path: originalPath }),
    })
  }

  async getTask(taskId: string): Promise<TaskJson> {
    return this.request<TaskJson>(`/api/tasks/${encodeURIComponent(taskId)}`, { method: 'GET' })
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
      backend: { deviceName: 'cpu', deviceType: 'cpu', isAccelerator: false, fallback: false },
    }
  }
}
