// 预览联动状态机（2026-10-06 修「剪辑播完把原片拽停」）。
// 组件测试框架（@vue/test-utils）未装 ⇒ 把判定抽成纯函数在这里锁住行为。
import { describe, it, expect } from 'vitest'
import {
  initialSyncState,
  reportEnded,
  reportPause,
  reportPlay,
  resetSyncState,
} from '../previewCoupling'

describe('previewCoupling', () => {
  it('一路播完不会把另一路拽停', () => {
    let s = initialSyncState(true)
    s = reportEnded(s, 'ed')
    expect(s.ended.ed).toBe(true)
    expect(s.playing).toBe(true)   // 原片继续放（旧行为：这里会被置 false）
  })

  it('两路都播完才整体置停', () => {
    let s = initialSyncState(true)
    s = reportEnded(reportEnded(s, 'ed'), 'og')
    expect(s.playing).toBe(false)
  })

  it('用户真实暂停 = 共享控制，两路都停', () => {
    const s = reportPause(initialSyncState(true))
    expect(s.playing).toBe(false)
  })

  it('播完后再按播放 = 清掉该路已完标记；无标记时不产生新对象', () => {
    let s = reportEnded(initialSyncState(false), 'ed')
    expect(s.ended.ed).toBe(true)
    s = reportPlay(s, 'ed')
    expect(s.ended.ed).toBe(false)
    const before = initialSyncState(true)
    expect(reportPlay(before, 'og')).toBe(before)   // 幂等：无变化返回同一引用
  })

  it('重置回到未播未停状态', () => {
    const s = resetSyncState()
    expect(s).toEqual({ playing: false, ended: { ed: false, og: false } })
  })
})
