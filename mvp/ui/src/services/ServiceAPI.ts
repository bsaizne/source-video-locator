import type {
  AnalysisOutput,
  ConnectionStatus,
  DevicePreference,
  DeviceSettingsJson,
  FsBrowseResult,
  IndexMetaJson,
  IndexStatus,
  MediaInfoJson,
  ProgressEventJson,
  ResultBatchJson,
  ResultJson,
  SourceMergeJson,
  TaskEvent,
  TaskJson,
} from './types'
import type { CancelToken } from './cancel'

export type { CancelToken } from './cancel'

export interface BuildOpts {
  cancelToken?: CancelToken
}

export type ExportFormat = 'json' | 'edl' | 'fcp7_xml' | 'jianying'

// 成片渲染请求（POST /api/tasks/render；策略缺省取后端 config.export/render）。
export interface RenderOpts {
  outDir?: string
  minConfidence?: 'HIGH' | 'MEDIUM' | 'LOW'
  lowPolicy?: 'exclude' | 'backup'
  snapScenes?: boolean
}

// The single seam between the UI and the backend. Every concrete adapter
// (Mock for standalone dev, Http for the real Python service — see
// HttpServiceAdapter) implements this interface; pages depend only on it.
export interface ServiceAPI {
  // ---- Index Service ----
  getIndexStatus(originalPath: string): Promise<IndexStatus>
  buildIndex(originalPath: string, opts?: BuildOpts): Promise<IndexStatus>
  getIndexMeta(originalPath: string): Promise<IndexMetaJson | null>
  // ffprobe 元数据（项目卡/详情页展示真实时长与分辨率）。后端 GET /api/media/info。
  getMediaInfo(path: string): Promise<MediaInfoJson>

  // 素材入库浏览（GET /api/fs/browse，2026-10-02 入库层四件）：
  // path='' → 「此电脑」盘符列表；目录 → 子目录 + 视频白名单（自然排序，后端做）。
  browseFs(path: string): Promise<FsBrowseResult>

  // 多原片入库前物理合并（POST /api/source/merge，2026-09-29 video.concat 移植）。
  // ≥2 段才有效：后端 <2 返回 400。产物是稳定命名缓存文件，可直接当单原片索引/定位。
  mergeSources(paths: string[]): Promise<SourceMergeJson>

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
  ): Promise<{ path: string; warnings?: string[] }>
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
  // `originalPaths` ≥2 时后端 worker 会先把它们物理合并再建索引（多原片入库）。
  // `refine`= 快/精双模式（2026-10-02）：undefined=后端默认（高精度）；
  // false=快速档（跳过切镜拆分+画面深度复核，实测省 ~60% 墙钟）。
  startAnalyzeTask(
    editedPath: string,
    originalPath: string,
    originalPaths?: string[],
    refine?: boolean,
  ): Promise<{ task_id: string }>
  getTask(taskId: string): Promise<TaskJson>
  cancelTask(taskId: string): Promise<void>
  subscribeProgress(taskId: string, cb: (event: TaskEvent) => void): () => void

  // ---- 成片渲染任务（2026-09-29 续30，竞品 video_renderer 移植） ----
  // 渲染会话当前结果批为单个成片；进度/取消与定位任务同通道（GET /api/tasks/{id}）。
  startRenderTask(opts?: RenderOpts): Promise<{ task_id: string }>

  // ---- progress + cancellation ----
  onProgress(listener: (event: ProgressEventJson) => void): () => void
  cancel(): void
}
