import type {
  AnalysisOutput,
  ConnectionStatus,
  DevicePreference,
  DeviceSettingsJson,
  IndexMetaJson,
  IndexStatus,
  ProgressEventJson,
  ResultBatchJson,
  ResultJson,
  TaskEvent,
  TaskJson,
} from './types'
import type { CancelToken } from './cancel'

export type { CancelToken } from './cancel'

export interface BuildOpts {
  cancelToken?: CancelToken
}

export type ExportFormat = 'json' | 'edl' | 'fcp7_xml' | 'jianying'

// The single seam between the UI and the backend. Every concrete adapter
// (Mock for standalone dev, Http for the real Python service — see
// HttpServiceAdapter) implements this interface; pages depend only on it.
export interface ServiceAPI {
  // ---- Index Service ----
  getIndexStatus(originalPath: string): Promise<IndexStatus>
  buildIndex(originalPath: string, opts?: BuildOpts): Promise<IndexStatus>
  getIndexMeta(originalPath: string): Promise<IndexMetaJson | null>

  // ---- Analysis Service ----
  analyzeEdited(editedPath: string, opts?: BuildOpts): Promise<AnalysisOutput>
  locate(editedPath: string, originalPath: string, opts?: BuildOpts): Promise<ResultBatchJson>

  // ---- Result Service ----
  exportResults(
    batch: ResultBatchJson,
    opts?: {
      outDir?: string
      filename?: string
      format?: ExportFormat
      minConfidence?: 'HIGH' | 'MEDIUM' | 'LOW'
      lowPolicy?: 'exclude' | 'backup'
      snapScenes?: boolean
      materialWidth?: 'scene' | 'core'
      cancelToken?: CancelToken
    },
  ): Promise<{ path: string }>
  loadResults(path: string): Promise<ResultBatchJson>
  // 手动替换某条结果的原片区（后端批同步更新 → 导出即替换后的最终工程）。
  overrideResult(resultId: string, start: number, end: number): Promise<ResultJson>
  excludeResult(resultId: string, excluded: boolean): Promise<ResultJson>

  // ---- logs (设置页日志快照) ----
  fetchRecentLogs(bytesLimit?: number): Promise<{ path: string; truncated: boolean; text: string }>
  downloadLogsArchive(): Promise<void>

  // ---- video preview ----
  // Extract `[start, end]` from `originalPath` and return a playable URL for the
  // extracted original clip (used as the Original preview src).
  previewResult(originalPath: string, start: number, end: number): Promise<string>
  // URL that serves the current session's edited video (seekable) — the Edited
  // preview src. Stable per session; no extraction needed on the backend.
  getEditedVideoUrl(): string

  // ---- backend health ----
  checkHealth(): Promise<ConnectionStatus>

  // ---- device backend settings (GPU/CPU switch) ----
  getDeviceSettings(): Promise<DeviceSettingsJson>
  setDeviceSettings(preferred: DevicePreference): Promise<DeviceSettingsJson>

  // ---- async task lifecycle (WS real-time progress) ----
  startAnalyzeTask(editedPath: string, originalPath: string): Promise<{ task_id: string }>
  getTask(taskId: string): Promise<TaskJson>
  cancelTask(taskId: string): Promise<void>
  subscribeProgress(taskId: string, cb: (event: TaskEvent) => void): () => void

  // ---- progress + cancellation ----
  onProgress(listener: (event: ProgressEventJson) => void): () => void
  cancel(): void
}
