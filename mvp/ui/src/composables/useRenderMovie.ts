// 成片渲染任务（2026-09-29 续30，竞品 video_renderer 移植的 UI 侧）。
//
// 与分析任务同通道（POST /api/tasks/render → GET /api/tasks/{id} 轮询）：打包 exe 里
// Electron 主进程没有 WebSocket，进度只能轮询（`stores/analysis.ts` 同源教训）。
// 渲染结果不是结果批而是 ``RenderMovieJson``，靠 ``task.kind === 'render'`` 区分。
import { ref } from 'vue'
import { useService } from '@/services'
import type { RenderMovieJson, RenderOpts } from '@/services'

const DEFAULT_POLL_MS = 800

export function useRenderMovie(opts?: { pollMs?: number }) {
  const service = useService()
  const pollMs = opts?.pollMs ?? DEFAULT_POLL_MS

  const running = ref(false)
  const progress = ref(0)
  const message = ref('')
  const moviePath = ref('')
  const result = ref<RenderMovieJson | null>(null)
  const error = ref('')
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
    moviePath.value = ''
    result.value = null
    error.value = ''
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
        result.value = (t.result ?? null) as RenderMovieJson | null
        moviePath.value = result.value?.movie_path ?? ''
        progress.value = 100
        message.value = '最终视频生成成功'
        return true
      }
      if (t.status === 'failed') {
        error.value = t.error || '成片渲染失败'
        return false
      }
      if (t.status === 'cancelled') {
        error.value = '已取消'
        return false
      }
      await sleep()
    }
  }

  /** 提交并等待渲染任务；返回 false 表示失败/取消（error 已置位）。 */
  async function start(renderOpts: RenderOpts = {}): Promise<boolean> {
    if (running.value) return false
    reset()
    running.value = true
    message.value = '提交渲染任务…'
    try {
      const res = await service.startRenderTask(renderOpts)
      taskId.value = res.task_id
      message.value = '准备渲染…'
      const ok = await waitUntilDone(res.task_id)
      return ok
    } catch (e) {
      // 后端 public_error 已是「对外话术（LOC 码）」，直接展示，不吐技术串
      error.value = e instanceof Error ? e.message : String(e)
      return false
    } finally {
      clearTimer()
      running.value = false
      taskId.value = null
    }
  }

  function cancel(): void {
    if (taskId.value) void service.cancelTask(taskId.value)
  }

  /** 在系统文件管理器里打开成片所在目录（桌面态才有桥；浏览器态静默忽略）。 */
  function revealFolder(): void {
    const p = moviePath.value
    if (!p || !window.desktop?.openPath) return
    const dir = p.replace(/[\\/][^\\/]*$/, '')
    void window.desktop.openPath(dir || p)
  }

  return {
    running,
    progress,
    message,
    moviePath,
    result,
    error,
    taskId,
    start,
    cancel,
    revealFolder,
    reset,
  }
}
