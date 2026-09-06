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
export type TaskStage =
  | 'idle'
  | 'indexing'
  | 'segmenting'
  | 'embedding'
  | 'retrieval'
  | 'exporting'
  | 'finished'

export interface TaskJson {
  task_id: string
  status: TaskStatus
  stage: TaskStage
  progress: number
  created_at: string
  finished_at: string | null
  result: ResultBatchJson | null
  error: string | null
  cancel_requested: boolean
  /** Human-readable current step, e.g. "特征提取 50/200 帧". */
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
  backend: BackendInfoJson
}
