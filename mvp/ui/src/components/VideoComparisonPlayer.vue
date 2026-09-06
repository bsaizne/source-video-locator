<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ResultJson } from '@/services'
import { formatEdited, formatOriginal } from '@/utils/format'
import VideoPlayer from './VideoPlayer.vue'
import Timeline, { type TimelineMarker } from './Timeline.vue'
import BaseIcon from './ui/BaseIcon.vue'

const props = withDefaults(
  defineProps<{
    result: ResultJson | null
    editedSrc?: string | null
    originalSrc?: string | null
    // 预览候选拆分/候选时的区间覆盖：原片标题/时间轴跟随正在预览的片段，
    // 而不是一直显示主定位区间（用户反馈：预览时标题一点没变）。
    originalOverrideSpan?: { start: number; end: number } | null
  }>(),
  { editedSrc: null, originalSrc: null, originalOverrideSpan: null },
)

// 两个播放器各自独立播放（反馈 ⑦：不再按比例强行同步——15s 原片和 7s 剪辑
// 各按自己的速度播完）。共享的只有播放/暂停和重置。
const edWin = computed(() => ({
  start: props.result?.edited_segment.start ?? 0,
  end: props.result?.edited_segment.end ?? 0,
}))
const ogWin = computed(() => {
  const o = props.originalOverrideSpan
  if (o && o.end > o.start) return { start: o.start, end: o.end }
  return {
    start: props.result?.original.candidate_start ?? 0,
    end: props.result?.original.candidate_end ?? 0,
  }
})

const edWidth = computed(() => Math.max(0, edWin.value.end - edWin.value.start))
const ogWidth = computed(() => Math.max(0, ogWin.value.end - ogWin.value.start))

const playing = ref(false)
const edCurrent = ref(0)
const ogCurrent = ref(0)

const editedMarkers = computed<TimelineMarker[]>(() =>
  edWidth.value > 0 ? [{ id: 'ed', start: 0, end: edWidth.value, tone: 'accent', label: '剪辑区间' }] : [],
)
const originalMarkers = computed<TimelineMarker[]>(() =>
  ogWidth.value > 0 ? [{ id: 'og', start: 0, end: ogWidth.value, tone: 'manual', label: '定位区域' }] : [],
)

function onEditedSeek(sec: number): void {
  edCurrent.value = Math.max(0, Math.min(edWidth.value, sec))
}

function onOriginalSeek(sec: number): void {
  ogCurrent.value = Math.max(0, Math.min(ogWidth.value, sec))
}

function reset(): void {
  edCurrent.value = 0
  ogCurrent.value = 0
  playing.value = false
}

function toggle(): void {
  playing.value = !playing.value
}

function onEditedTick(t: number): void {
  edCurrent.value = t
}

function onOriginalTick(t: number): void {
  ogCurrent.value = t
}

// Selecting a different result changes both windows; reset both playheads.
watch(() => props.result?.result_id, reset)

const selLabel = computed(() => (props.result ? `片段 ${props.result.result_id.slice(-4).toUpperCase()}` : ''))

// 原片预览播放头位置（预览片段内的本地秒）——供结果页「播放头设为起点/终点」打点。
defineExpose({
  getOriginalTime: (): number => ogCurrent.value,
})
</script>

<template>
  <div class="vcp">
    <div v-if="result" class="vcp__body">
      <VideoPlayer
        :src="editedSrc"
        :label="`剪辑 · ${formatEdited(edWin.start)} – ${formatEdited(edWin.end)}`"
        :current-time="edCurrent"
        :playing="playing"
        @tick="onEditedTick"
        @seek="onEditedSeek"
        @playing-change="(p) => (playing = p)"
      />
      <div class="vcp__sync">
        <button class="vcp__play" @click="toggle">
          <BaseIcon :name="playing ? 'pause' : 'play'" :size="16" />
        </button>
        <span class="vcp__sel mono">{{ selLabel }}</span>
        <span class="vcp__note faint">两个视频各自按原速播放</span>
        <button class="vcp__reset" @click="reset">重置</button>
      </div>
      <VideoPlayer
        :src="originalSrc"
        :label="`原片 · ${formatOriginal(ogWin.start)} – ${formatOriginal(ogWin.end)}`"
        :current-time="ogCurrent"
        :playing="playing"
        @tick="onOriginalTick"
        @seek="onOriginalSeek"
      />
    </div>

    <div class="vcp__timeline">
      <div class="vcp__row">
        <span class="vcp__axis">Edited</span>
        <Timeline
          class="vcp__tl"
          :duration="edWidth"
          :value="edCurrent"
          :markers="editedMarkers"
          :interactive="true"
          @seek="onEditedSeek"
        />
      </div>
      <div class="vcp__row">
        <span class="vcp__axis">Original</span>
        <Timeline
          class="vcp__tl"
          :duration="ogWidth"
          :value="ogCurrent"
          :markers="originalMarkers"
          :interactive="true"
          @seek="onOriginalSeek"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.vcp { display: flex; flex-direction: column; gap: 16px; }
.vcp__body { display: flex; flex-direction: column; gap: 8px; }
.vcp__sync { display: flex; align-items: center; gap: 10px; }
.vcp__play {
  width: 32px; height: 32px; border: none; border-radius: var(--radius-s);
  background: var(--accent); color: #fff; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.vcp__sel { color: var(--fg-muted); font-size: var(--fs-xs); }
.vcp__note { font-size: var(--fs-2xs); }
.vcp__reset { margin-left: auto; background: none; border: none; color: var(--fg-muted); cursor: pointer; font-size: var(--fs-xs); }
.vcp__reset:hover { color: var(--fg); }
.vcp__timeline { display: flex; flex-direction: column; gap: 4px; }
.vcp__row { display: flex; align-items: center; gap: 10px; }
.vcp__axis { width: 56px; flex-shrink: 0; font-size: var(--fs-2xs); color: var(--fg-faint); text-align: right; }
.vcp__tl { flex: 1; }
</style>
