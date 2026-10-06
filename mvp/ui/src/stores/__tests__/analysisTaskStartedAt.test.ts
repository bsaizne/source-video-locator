// 计时起点归 store 所有（2026-10-06 修「时间消失 / 一直显示 00:00」）：
// 原先 elapsed 是分析页组件里的 setInterval 计数器 ⇒ 换页/重挂即归零且不再走。
// 现在起点时刻存在 store，任何组件实例都能按 Date.now() - taskStartedAt 续算。
import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { setServiceForTest } from '@/services/inject'
import type { ServiceAPI } from '@/services/ServiceAPI'
import { useAnalysisStore } from '../analysis'

function fakeService(getTask: (n: number) => unknown) {
  let polls = 0
  const svc = {
    onProgress: () => () => {},
    startAnalyzeTask: async () => ({ task_id: 't-1' }),
    getTask: async () => {
      polls += 1
      return getTask(polls)
    },
    cancelTask: async () => ({}),
  }
  return svc as unknown as ServiceAPI
}

describe('analysis 任务起点', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('提交后起点写进 store，终态后清空（不随组件存活）', async () => {
    const seen: Array<number | null> = []
    setServiceForTest(fakeService((n) => {
      const a = useAnalysisStore()
      seen.push(a.taskStartedAt)
      return n === 1
        ? { status: 'running', stage: 'retrieval', progress: 92.1, message: '画面深度复核' }
        : { status: 'completed', result: { results: [] } }
    }))
    const a = useAnalysisStore()
    await a.runLocate('ed.mp4', 'om.mp4')
    expect(seen[0]).toBeTypeOf('number')     // 轮询进行中起点已在 store
    expect(a.taskStartedAt).toBeNull()       // 结束后清空
    expect(a.running).toBe(false)
  })
})
