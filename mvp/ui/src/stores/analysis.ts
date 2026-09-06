import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useService } from '@/services'
import type {
  ProgressStage,
  ResultBatchJson,
  ShotSegmentJson,
  TaskStage,
} from '@/services'

export type StepStatus = 'idle' | 'running' | 'done' | 'error'

export interface PipelineStep {
  key: ProgressStage
  label: string
  status: StepStatus
  message: string
}

// 粗粒度工作流（用户反馈 ②：不能事无巨细）——只暴露面向用户的四个阶段，
// 检索/定位/置信等内部阶段一律折叠进「镜头分析」。
const STEPS: Array<{ key: ProgressStage; label: string }> = [
  { key: 'INDEX_BUILD', label: '准备原片索引' },
  { key: 'EDITED_FEATURE_EXTRACTION', label: '读取剪辑视频' },
  { key: 'SEGMENT_DETECTION', label: '镜头分析' },
  { key: 'CONFIDENCE', label: '完成输出' },
]
const RANK: Record<string, number> = Object.fromEntries(STEPS.map((s, i) => [s.key, i]))

// TaskStage -> ProgressStage：把后端任务阶段映射到 UI 管线步骤（COARSE，非逐帧）。
const TASK_STAGE_MAP: Record<TaskStage, ProgressStage | undefined> = {
  idle: undefined,
  indexing: 'INDEX_BUILD',
  segmenting: 'SEGMENT_DETECTION',
  embedding: 'EDITED_FEATURE_EXTRACTION',
  retrieval: 'SEGMENT_DETECTION',
  exporting: 'CONFIDENCE',
  finished: undefined,
}

export const useAnalysisStore = defineStore('analysis', () => {
  const service = useService()

  const running = ref(false)
  const segments = ref<ShotSegmentJson[] | null>(null)
  const error = ref<string | null>(null)
  const progress = ref<{ stage: ProgressStage; current: number; total: number; message: string } | null>(null)
  const steps = ref<PipelineStep[]>(STEPS.map((s) => ({ ...s, status: 'idle', message: '' })))
  const activeTaskId = ref<string | null>(null)
  // 分析页固定项目（反馈 ⑫：别处切项目不打断/不偷换分析界面；顶部切换器改这里）
  const pinnedProjectId = ref<string | null>(null)

  function setPinnedProject(id: string | null): void {
    pinnedProjectId.value = id
  }

  const activeStep = computed(() => steps.value.find((s) => s.status === 'running') ?? null)

  function idleSteps(): void {
    steps.value = STEPS.map((s) => ({ ...s, status: 'idle', message: '' }))
  }

  function applyProgress(ev: { stage: ProgressStage; current: number; total: number; message: string }): void {
    progress.value = { stage: ev.stage, current: ev.current, total: ev.total, message: ev.message }
    const idx = RANK[ev.stage]
    if (idx === undefined) return
    for (let i = 0; i < steps.value.length; i++) {
      const st = steps.value[i]
      if (i < idx) st.status = st.status === 'error' ? 'error' : 'done'
      else if (i === idx) st.status = 'running'
      else st.status = st.status === 'done' ? 'done' : st.status
    }
    steps.value[idx].message = ev.message
  }

  function cancelTask(): void {
    if (activeTaskId.value) {
      void service.cancelTask(activeTaskId.value)
    }
  }

  const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms))

  let subscribed = false
  function ensureSubscribed(): void {
    if (subscribed) return
    subscribed = true
    service.onProgress(applyProgress)
  }

  // 轮询 GET /api/tasks/{id} 直到终态。不依赖 WebSocket——打包 exe 里 Electron 主进程
  // 无 globalThis.WebSocket，进度 WS 代理被禁用（日志 global WebSocket unavailable），
  // 前端收不到 WS 终态帧会一直「分析中」。轮询在任何环境都可靠。
  async function pollTaskUntilDone(taskId: string): Promise<ResultBatchJson> {
    for (;;) {
      const t = await service.getTask(taskId)
      if (t.status === 'completed') return t.result as ResultBatchJson
      if (t.status === 'failed') throw new Error(t.error || '分析失败')
      if (t.status === 'cancelled') throw new Error('已取消')
      if (t.status === 'running' || t.status === 'pending') {
        const stage = t.stage && TASK_STAGE_MAP[t.stage]
        if (stage) applyProgress({ stage, current: t.progress, total: 100, message: t.message ?? '' })
      }
      await sleep(800)
    }
  }

  async function runLocate(edited: string, original: string) {
    ensureSubscribed()
    running.value = true
    error.value = null
    idleSteps()
    try {
      const { task_id } = await service.startAnalyzeTask(edited, original)
      activeTaskId.value = task_id
      const batch = await pollTaskUntilDone(task_id)
      steps.value = steps.value.map((s) => (s.status === 'error' ? s : { ...s, status: 'done' }))
      return batch
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      steps.value = steps.value.map((s) =>
        s.status === 'running' ? { ...s, status: 'error', message: error.value ?? '' } : s,
      )
      throw e
    } finally {
      activeTaskId.value = null
      running.value = false
    }
  }

  function reset(): void {
    running.value = false
    segments.value = null
    error.value = null
    progress.value = null
    activeTaskId.value = null
    idleSteps()
  }

  return {
    running,
    segments,
    error,
    progress,
    steps,
    activeStep,
    activeTaskId,
    pinnedProjectId,
    setPinnedProject,
    runLocate,
    cancelTask,
    reset,
    ensureSubscribed,
  }
})
