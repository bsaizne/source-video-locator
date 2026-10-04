// TS types that mirror the Python JSON wire contract produced by
// `mvp/src/domain/models.py` `to_dict()`. Field names are copied exactly —
// note the deliberate asymmetry: `edited_segment` uses `start/end`, while
// `original` uses `candidate_start/candidate_end`; `confidence` /
// `confidence_score` / `reasons` are flattened onto `Result`, and
// `manual_timestamp` / `auto_result` only appear when `manual_override`.

export type ConfidenceLevel = 'HIGH' | 'MEDIUM' | 'LOW'
export type ResultSource = 'auto' | 'manual'
export type IndexValidationStatus = 'VALID' | 'INVALID' | 'MISSING'

// Backend connection health (from GET /api/health). Display-only; CONNECTED
// means the FastAPI bridge answered /api/health with status ok.
export type ConnectionStatus = 'CONNECTED' | 'CONNECTING' | 'OFFLINE'

// device_name() legal values from DEVICE_BACKEND_SPEC §1 — display/log only,
// never used as a branching key in UI logic. `directml` is the Windows AMD GPU
// backend actually shipped (DirectMLBackend.device_name()).
export type DeviceName =
  | 'cpu'
  | 'directml'
  | 'cuda:0'
  | 'mps'
  | 'rocm:0'
  | 'AMD_GPU_BACKEND_BLOCKED'

export type DeviceType = 'cpu' | 'amd' | 'mps' | 'cuda'

// The only user-setting that changes the runtime inference backend.
export type DevicePreference = 'auto' | 'directml' | 'cpu' | 'mps'

// Mirror of GET/POST /api/settings/device (mvp/api/routes/settings.py).
export interface DeviceSettingsJson {
  preferred: DevicePreference
  actual_device_name: DeviceName
  actual_device_type: DeviceType
  is_accelerator: boolean
  /** True when GPU/DML was requested (auto|directml) but the actual backend fell back to CPU. */
  fallback: boolean
  available_devices: string[]
}

export interface TimeSpanJson {
  start: number
  end: number
}

export interface AlternativeJson {
  candidate_start: number
  candidate_end: number
  confidence: ConfidenceLevel
  score: number
}

export interface OriginalSegmentJson {
  candidate_start: number
  candidate_end: number
  cover: number
  score: number | null
  /** Phase 21 场景指纹扩池产物:仅展示候选,不参与主定位改写 */
  from_scene_pool?: boolean
  /** 方向 A 事件单元扩池产物(2026-09-05):与场景扩池同语义,仅展示候选 */
  from_event_pool?: boolean
}

export interface ResultJson {
  result_id: string
  edited_segment: TimeSpanJson
  original: { candidate_start: number; candidate_end: number }
  confidence: ConfidenceLevel
  confidence_score: number
  reasons: string[]
  candidate_rank: number
  alternatives: AlternativeJson[]
  original_segments: OriginalSegmentJson[]
  source: ResultSource
  manual_override: boolean
  montage_flag: boolean
  extracted_path: string | null
  failure_reason: string | null
  not_in_source: boolean
  excluded?: boolean
  manual_timestamp?: string | null
  auto_result?: ResultJson | null
}

export interface ResultBatchJson {
  schema_version: number
  original_video: string | null
  edited_video: string | null
  results: ResultJson[]
}

export interface ExtractorConfigJson {
  normalize: string
  resize: string
  mean_std: string
  preprocess_sha: string
}

export interface IndexMetaJson {
  index_version: number
  source_file: string
  file_size: number
  duration: number
  file_hash: string
  feature_model: string
  feature_version: string
  sampling_fps: number
  feature_dim: number
  num_frames: number
  backend: DeviceName
  created_at: string
  device_machine_id: string
  extractor: ExtractorConfigJson
}

export interface IndexValidationJson {
  status: IndexValidationStatus
  reason: string | null
}

// Mirror of GET /api/media/info (mvp/api/routes/media.py — ffprobe metadata).
// Display-only (project cards / detail page); never a branching key.
export interface MediaInfoJson {
  path: string
  duration: number      // seconds (format.duration; reliable on MKV)
  fps: number           // avg_frame_rate; 0 when unknown
  width: number
  height: number
  size_bytes: number
  format_name: string
  video_codec: string
  has_audio: boolean
}

// Mirror of POST /api/source/merge (mvp/api/routes/source.py — 多原片入库前物理合并,
// 竞品 processing.video.concat 对应)。merged_path 是稳定命名缓存文件，可直接当普通单原片用。
export interface SourceMergeJson {
  merged_path: string
  /** copy=流复制(签名全等) / transcode=重编码链 / passthrough=单文件直通 */
  mode: string
  /** true = 命中既有缓存（同一组原片此前已合并过，秒回） */
  reused: boolean
  duration_s: number | null
}

// Mirror of GET /api/fs/browse (mvp/api/routes/fsbrowse.py — 素材入库浏览,
// 竞品 web.file_api.browser 四件：盘符/自然排序/白名单/磁盘剩余)。后端已完成
// 自然排序与白名单过滤；前端只渲染，不再排序。
export interface FsDriveJson {
  name: string
  path: string
  label: string
  total_bytes: number
  free_bytes: number
}
export interface FsEntryJson {
  name: string
  path: string
  is_video: boolean
  size_bytes?: number
}
export interface FsBrowseResult {
  kind: 'root' | 'dir'
  path: string
  /** 上一级；'' = 回「此电脑」；null = 无上级 */
  parent: string | null
  drives: FsDriveJson[]
  entries: FsEntryJson[]
  free_bytes?: number
  total_bytes?: number
}

// A query unit (edited-side shot). numpy `feats`/`times` stay on the backend;
// the UI only needs the span + a label.
export interface ShotSegmentJson {
  id: string
  label: string
  span: TimeSpanJson
  nq: number
}

export interface AnalysisOutput {
  segments: ShotSegmentJson[]
}

export interface BackendInfoJson {
  deviceName: DeviceName
  deviceType: DeviceType
  isAccelerator: boolean
  fallback: boolean
}

// ProgressStage from app/models.py (7 stages).
export type ProgressStage =
  | 'INDEX_BUILD'
  | 'EDITED_FEATURE_EXTRACTION'
  | 'SEGMENT_DETECTION'
  | 'CANDIDATE_RETRIEVAL'
  | 'LOCALIZATION'
  | 'CONFIDENCE'
  | 'EXPORT'

export interface ProgressEventJson {
  stage: ProgressStage
  current: number
  total: number
  message: string
}

// ---- Async task lifecycle (mvp/api/tasks + /ws/progress) ----
// Mirrors mvp/api/tasks/models.py Task + the WS frame shapes.
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
export type TaskKind = 'analyze' | 'render'
export type TaskStage =
  | 'idle'
  | 'indexing'
  | 'segmenting'
  | 'embedding'
  | 'retrieval'
  | 'exporting'
  | 'finished'

// 成片渲染结果（POST /api/tasks/render 完成后的 task.result，2026-09-29 续30）。
// ⚠️ 与分析任务的 ResultBatchJson 共用 task.result 字段，靠 task.kind 区分。
export interface RenderMovieJson {
  kind?: 'render'
  movie_path: string
  /** copy=流复制合并 / transcode=重编码合并 / reused=命中稳定命名缓存 */
  mode: string
  reused: boolean
  segments: number
  /** 成片恒定帧率（FFmpeg 分数字符串，如 24000/1001） */
  fps: string
  duration_s: number | null
  total_frames: number | null
  actual_encoder: string
  hdr_downgraded?: boolean
  clips?: number
  clip_ranges?: Array<[number, number]>
}

export interface TaskJson {
  task_id: string
  /** analyze=定位（默认）；render=成片渲染。缺省按 analyze 处理（旧后端兼容）。 */
  kind?: TaskKind
  status: TaskStatus
  stage: TaskStage
  progress: number
  created_at: string
  finished_at: string | null
  result: ResultBatchJson | RenderMovieJson | null
  error: string | null
  cancel_requested: boolean
  /** Human-readable current step, e.g. "分析剪辑画面 50/200 帧"（面向用户话术，续40）. */
  message: string
}

// A frame pushed over /ws/progress/{task_id}.
export type TaskEvent =
  | { type: 'progress'; task_id: string; status: TaskStatus; stage: TaskStage; progress: number; message: string }
  | { type: 'completed'; task_id: string }
  | { type: 'failed'; task_id: string; error: string }
  | { type: 'cancelled'; task_id: string }
  | { type: 'error'; error: string; detail?: string }

// ---- UI-level aggregates (not direct wire fields, but useful derivations) ----
export interface IndexStatus {
  indexMeta: IndexMetaJson | null
  validation: IndexValidationJson
  /** 状态查询不含设备信息时为 null（诚实未知，不硬编码 cpu——2026-10-01 E2E 发现的徽标误标）。 */
  backend: BackendInfoJson | null
}
