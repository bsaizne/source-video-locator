// 预览双播放器的联动状态机（2026-10-06 修「一路播完把另一路拽停」）。
//
// 旧行为：两个播放器共享一个 `playing`，而子组件把 `<video>` 的 `pause` 事件一律上报成
// 「用户暂停」⇒ 剪辑片段播到末尾时浏览器自动触发的 pause 会把共享 playing 置 false，
// 于是还没播完的原片跟着停。
//
// 新语义（保持反馈 ⑦「各自按自己的速度播完，共享的只有播放/暂停和重置」）：
//   · 用户手动暂停任一路 ⇒ 两路都停（共享控制）
//   · 某一路**播完** ⇒ 只记该路已完，另一路继续；两路都完才把共享状态置停
export type PreviewWhich = 'ed' | 'og'

export interface PreviewSyncState {
  playing: boolean
  ended: Record<PreviewWhich, boolean>
}

export function initialSyncState(playing = false): PreviewSyncState {
  return { playing, ended: { ed: false, og: false } }
}

/** 子组件上报「真实暂停」（用户点暂停/外部暂停），非播完自动暂停。 */
export function reportPause(s: PreviewSyncState): PreviewSyncState {
  return { ...s, playing: false }
}

/** 子组件上报「开始播放」：清掉该路的已完标记（重播即重新计）。 */
export function reportPlay(s: PreviewSyncState, which: PreviewWhich): PreviewSyncState {
  if (!s.ended[which]) return s
  return { ...s, ended: { ...s.ended, [which]: false } }
}

/** 子组件上报「本路播完」：另一路继续，两路都完才整体置停。 */
export function reportEnded(s: PreviewSyncState, which: PreviewWhich): PreviewSyncState {
  const ended = { ...s.ended, [which]: true }
  return { playing: ended.ed && ended.og ? false : s.playing, ended }
}

/** 重置（换片段/点重置）。 */
export function resetSyncState(): PreviewSyncState {
  return initialSyncState(false)
}
