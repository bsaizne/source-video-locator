// 工程/结果导出任务（2026-10-13 B 方案）。
//
// 为什么不用同步 /api/export：真机实测分钟级导出（374s / 783s），同步通道里 UI 只能
// 干等且不能取消（补十六 把桥接层等待上限抬到 30min，只消掉了「连不上后端」的误报）。
// 与分析/渲染任务同通道（POST /api/tasks/export → GET /api/tasks/{id} 轮询）：打包 exe 里
// Electron 主进程没有 WebSocket，进度只能轮询（`useRenderMovie.ts` 同源）。
import { ref } from 'vue'
import { useService } from '@/services'
import type { ExportOpts, ExportResultJson } from '@/services'

const DEFAULT_POLL_MS = 800

export function useExportTask(opts?: { pollMs?: number }) {
  const service = useService()
  const pollMs = opts?.pollMs ?? DEFAULT_POLL_MS

  const running = ref(false)
  const progress = ref(0)
  const message = ref('')
  const exportedPath = ref('')
  const warnings = ref<string[]>([])
  const error = ref('')
  // 取消单独一位：页面据此解释「已转好的素材留在原地」（不删 = 下次重跑复用转码缓存）。
  const cancelled = ref(false)
  /** 本次任务请求的输出目录（取消后用它说明残留在哪；空 = 后端默认导出根）。 */
  const outDir = ref('')
  const taskId = ref<string | null>(null)
  let timer: ReturnType<typeof setTimeout> | null = null

  function clearTimer(): void {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  function reset(): void {
    clearTimer()
    running.value = false
    progress.value = 0
    message.value = ''
    exportedPath.value = ''
    warnings.value = []
    error.value = ''
    cancelled.value = false
    outDir.value = ''
    taskId.value = null
  }

  const sleep = () => new Promise<void>((resolve) => {
    timer = setTimeout(resolve, pollMs)
  })

  /** 轮询到终态。返回 true=成功完成。 */
  async function waitUntilDone(id: string): Promise<boolean> {
    for (;;) {
      const t = await service.getTask(id)
      progress.value = t.progress ?? 0
      if (t.message) message.value = t.message
      if (t.status === 'completed') {
        const r = (t.result ?? {}) as ExportResultJson
        exportedPath.value = r.path ?? ''
        // warnings 由产出它的那个后端 service 带进信封（隔离子进程与父进程不同实例）
        warnings.value = r.warnings ?? []
        progress.value = 100
        return true
      }
      if (t.status === 'failed') {
        error.value = t.error || '导出失败'
        return false
      }
      if (t.status === 'cancelled') {
        error.value = '已取消'
        cancelled.value = true
        return false
      }
      await sleep()
    }
  }

  /** 提交并等待导出任务；返回 false 表示失败/取消（error 已置位）。 */
  async function start(exportOpts: ExportOpts = {}): Promise<boolean> {
    if (running.value) return false
    reset()
    running.value = true
    outDir.value = exportOpts.outDir ?? ''
    message.value = '提交导出任务…'
    try {
      const res = await service.startExportTask(exportOpts)
      taskId.value = res.task_id
      message.value = '准备导出…'
      return await waitUntilDone(res.task_id)
    } catch (e) {
      // 后端 public_error 已是「对外话术（LOC 码）」，直接展示，不吐技术串
      error.value = e instanceof Error ? e.message : String(e)
      return false
    } finally {
      clearTimer()
      running.value = false
    }
  }

  function cancel(): void {
    if (taskId.value) void service.cancelTask(taskId.value)
  }

  /** 在系统文件管理器里打开导出产物所在目录（桌面态才有桥；浏览器态静默忽略）。 */
  function revealFolder(): void {
    const p = exportedPath.value
    if (!p || !window.desktop?.openPath) return
    const dir = p.replace(/[\\/][^\\/]*$/, '')
    void window.desktop.openPath(dir || p)
  }

  return {
    running,
    progress,
    message,
    exportedPath,
    warnings,
    error,
    cancelled,
    outDir,
    taskId,
    start,
    cancel,
    revealFolder,
    reset,
  }
}
