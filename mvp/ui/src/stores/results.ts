import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useService } from '@/services'
import type { ResultBatchJson, ResultJson } from '@/services'

// 预览来源（用户反馈：候选换来换去记不清哪个是原本剪出来的片段）。
// kind: auto=自动定位 manual=替换后定位 alt=候选项 seg=定位拆分段
export interface PreviewSource {
  kind: 'auto' | 'manual' | 'alt' | 'seg'
  index?: number
  start: number
  end: number
}

export const useResultsStore = defineStore('results', () => {
  const service = useService()

  const batch = ref<ResultBatchJson | null>(null)
  const selectedId = ref<string | null>(null)

  const selected = computed<ResultJson | null>(() =>
    batch.value?.results.find((r) => r.result_id === selectedId.value) ?? null,
  )

  const counts = computed(() => {
    const rs = batch.value?.results ?? []
    return {
      high: rs.filter((r) => r.confidence === 'HIGH').length,
      medium: rs.filter((r) => r.confidence === 'MEDIUM').length,
      low: rs.filter((r) => r.confidence === 'LOW').length,
      unresolved: rs.filter((r) => r.failure_reason != null).length,
    }
  })

  // ---- video preview state ----
  const previewEditedSrc = ref<string | null>(null)
  const previewOriginalSrc = ref<string | null>(null)
  const previewLoading = ref(false)
  const previewError = ref<string | null>(null)
  const previewSource = ref<PreviewSource | null>(null)

  function setBatch(b: ResultBatchJson): void {
    batch.value = b
    selectedId.value = b.results.length ? b.results[0].result_id : null
    // Auto-generate both previews on entering the results page: the edited clip is
    // extracted over edited_segment (like the original clip over its located span),
    // so both are H.264 MP4 the browser can actually play (the raw edited video may
    // be MKV/HEVC and renders black). See PreviewService.extract_segment.
    previewEditedSrc.value = null
    previewOriginalSrc.value = null
    previewLoading.value = false
    previewError.value = null
    previewSource.value = null
    void generateEditedPreview()
    void generatePreview()
  }

  function select(id: string | null): void {
    selectedId.value = id
    // A different result has a different edited/original span — invalidate and
    // regenerate both previews automatically.
    previewOriginalSrc.value = null
    previewEditedSrc.value = null
    previewError.value = null
    previewSource.value = null
    void generateEditedPreview()
    void generatePreview()
  }

  // Extract the selected result's edited_segment and expose it as the Edited
  // preview src (H.264 MP4). The raw edited video may be MKV/HEVC and renders
  // black in the browser, so we always extract (transcode) the segment — same as
  // the original clip. In Mock mode this resolves to a sample URL.
  async function generateEditedPreview(): Promise<void> {
    const b = batch.value
    const r = selected.value
    if (!b || !r) {
      previewEditedSrc.value = null
      return
    }
    const editedPath = b.edited_video
    if (!editedPath) {
      previewEditedSrc.value = null
      return
    }
    previewLoading.value = true
    try {
      previewEditedSrc.value = await service.previewResult(
        editedPath,
        r.edited_segment.start,
        r.edited_segment.end,
      )
    } catch {
      previewEditedSrc.value = null
    } finally {
      previewLoading.value = false
    }
  }

  // Extract the selected result's original clip and expose it as the Original
  // preview src. In Mock mode this resolves to a sample URL; in Http mode it
  // POSTs /api/preview and returns the media route URL.
  async function generatePreview(): Promise<void> {
    const b = batch.value
    const r = selected.value
    if (!b || !r) return
    const originalPath = b.original_video
    if (!originalPath) {
      previewError.value = 'No original video in session'
      return
    }
    previewLoading.value = true
    previewError.value = null
    if (r.not_in_source) {
      // 非源片内容(片尾/转场)——无原片定位,跳过原片预览
      previewOriginalSrc.value = null
      previewSource.value = null
      return
    }
    try {
      previewOriginalSrc.value = await service.previewResult(
        originalPath,
        r.original.candidate_start,
        r.original.candidate_end,
      )
      previewSource.value = {
        kind: r.source === 'manual' ? 'manual' : 'auto',
        start: r.original.candidate_start,
        end: r.original.candidate_end,
      }
    } catch (e) {
      previewError.value = e instanceof Error ? e.message : String(e)
    } finally {
      previewLoading.value = false
    }
  }

  // Manual override — preserves the auto result as `auto_result` (per the
  // domain's auto/manual dual-track design). Http 模式同步到后端批（反馈 ⑨：
  // 替换后的批才是导出源）；Mock 模式仅本地内存。
  function markManualOverride(id: string, start: number, end: number): void {
    const result = batch.value?.results.find((r) => r.result_id === id)
    if (!result) return
    // 注意：result 是 Vue 响应式代理，structuredClone 会抛 DataCloneError
    // （2026-08-30 实测：替换定位点击静默失败的根因），必须 JSON 深拷贝。
    const auto = JSON.parse(JSON.stringify(result)) as ResultJson
    auto.source = 'auto'
    auto.manual_override = false
    auto.manual_timestamp = undefined
    auto.auto_result = undefined
    result.auto_result = auto
    result.original = { candidate_start: start, candidate_end: end }
    result.source = 'manual'
    result.manual_override = true
    result.manual_timestamp = new Date().toISOString()
    // The manual override changes the located region; drop the stale clip.
    previewOriginalSrc.value = null
    previewError.value = null
    void generatePreview()
    void service.overrideResult(id, start, end).catch((e) => {
      // 后端替换失败不再静默（用户反馈：替换定位后毫无反应，无从排查）
      previewError.value = `后端替换失败（本地已更新，导出前请留意）：${e instanceof Error ? e.message : String(e)}`
    })
  }

  // 手动排除/恢复某段的导出（反馈四轮 r16：内容不匹配的段不进剪辑软件）。
  function setExcluded(id: string, excluded: boolean): void {
    const result = batch.value?.results.find((r) => r.result_id === id)
    if (!result) return
    result.excluded = excluded
    void service.excludeResult(id, excluded).catch(() => {
      // Http 失败不阻塞本地 UI（导出错误会在导出处体现）
    })
  }

  // 预览某个候选子 span（反馈 ⑧：候选选中后可预览，再决定是否替换）。
  // src 记录来源（候选序号/拆分段序号），供页面显示「正在预览」徽标。
  async function previewCandidate(
    start: number,
    end: number,
    src?: { kind: 'alt' | 'seg'; index: number },
  ): Promise<void> {
    const b = batch.value
    if (!b?.original_video || end - start <= 0) return
    previewLoading.value = true
    previewError.value = null
    try {
      previewOriginalSrc.value = await service.previewResult(b.original_video, start, end)
      candidateSpan.value = { start, end }
      previewSource.value = { kind: src?.kind ?? 'alt', index: src?.index, start, end }
    } catch (e) {
      previewError.value = e instanceof Error ? e.message : String(e)
    } finally {
      previewLoading.value = false
    }
  }
  const candidateSpan = ref<{ start: number; end: number } | null>(null)

  function clear(): void {
    batch.value = null
    selectedId.value = null
    previewEditedSrc.value = null
    previewOriginalSrc.value = null
    previewLoading.value = false
    previewError.value = null
    previewSource.value = null
  }

  return {
    batch,
    selectedId,
    selected,
    counts,
    candidateSpan,
    previewEditedSrc,
    previewOriginalSrc,
    previewLoading,
    previewError,
    previewSource,
    setBatch,
    select,
    markManualOverride,
    setExcluded,
    previewCandidate,
    generateEditedPreview,
    generatePreview,
    clear,
  }
})
