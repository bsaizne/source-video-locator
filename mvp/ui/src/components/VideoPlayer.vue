<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseIcon from './ui/BaseIcon.vue'
import { formatClock } from '@/utils/format'

const props = withDefaults(
  defineProps<{
    src?: string | null
    poster?: string | null
    label?: string
    currentTime?: number
    playing?: boolean
  }>(),
  { src: null, poster: null, label: '', currentTime: 0, playing: false },
)

const emit = defineEmits<{
  (e: 'tick', currentTime: number): void
  (e: 'playingChange', playing: boolean): void
  (e: 'seek', seconds: number): void
  (e: 'duration', duration: number): void
}>()

const video = ref<HTMLVideoElement | null>(null)
const duration = ref(0)

// Ensure external time prop drives the element (and the other way around).
watch(
  () => props.currentTime,
  (t) => {
    const v = video.value
    if (v && Math.abs(v.currentTime - t) > 0.4) v.currentTime = t
  },
)

watch(
  () => props.playing,
  (p) => {
    const v = video.value
    if (!v) return
    if (p) void v.play().catch(() => {})
    else v.pause()
  },
)

function onTimeUpdate(): void {
  if (!video.value) return
  duration.value = video.value.duration || duration.value
  emit('tick', video.value.currentTime)
  emit('duration', video.value.duration)
}

function onPlay(): void {
  emit('playingChange', true)
}
function onPause(): void {
  emit('playingChange', false)
}

function toggle(): void {
  const v = video.value
  if (!v) return
  if (v.paused) void v.play().catch(() => {})
  else v.pause()
}

// Scrubbing on the progress bar — seek the underlying <video> (drives the shared
// playhead in VideoComparisonPlayer via the `seek` emit).
const scrubbing = ref(false)
function onScrub(ev: PointerEvent): void {
  const v = video.value
  const el = ev.currentTarget as HTMLElement
  if (!v || !duration.value || !el) return
  const rect = el.getBoundingClientRect()
  const frac = Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width))
  emit('seek', frac * duration.value)
}
function onScrubDown(ev: PointerEvent): void {
  scrubbing.value = true
  onScrub(ev)
}
function onScrubMove(ev: PointerEvent): void {
  if (scrubbing.value) onScrub(ev)
}
function onScrubUp(): void {
  scrubbing.value = false
}

const pct = computed(() => {
  if (!duration.value) return 0
  return (props.currentTime / duration.value) * 100
})

const disabled = computed(() => !props.src)
</script>

<template>
  <div class="vp" :class="{ 'vp--empty': !src }">
    <div class="vp__stage">
      <video
        v-if="src"
        ref="video"
        class="vp__video"
        :src="src"
        :poster="poster ?? undefined"
        preload="metadata"
        @timeupdate="onTimeUpdate"
        @play="onPlay"
        @pause="onPause"
      />
      <div v-else class="vp__placeholder">
        <BaseIcon name="film" :size="32" />
        <span>预览不可用</span>
      </div>
      <span v-if="label" class="vp__label">{{ label }}</span>
    </div>

    <div class="vp__controls" :class="{ 'vp__controls--disabled': disabled }">
      <button class="vp__btn" :disabled="disabled" @click="toggle">
        <BaseIcon :name="playing ? 'pause' : 'play'" :size="16" />
      </button>
      <span class="vp__time mono">{{ formatClock(currentTime, false) }}</span>
      <div class="vp__bar" @pointerdown="onScrubDown" @pointermove="onScrubMove" @pointerup="onScrubUp">
        <div class="vp__fill" :style="{ width: pct + '%' }" />
        <div class="vp__playhead" :style="{ left: pct + '%' }" />
      </div>
      <span class="vp__time mono">{{ formatClock(duration, false) }}</span>
    </div>
  </div>
</template>

<style scoped>
.vp { display: flex; flex-direction: column; border-radius: var(--radius-m); overflow: hidden; border: 1px solid var(--border); background: var(--overlay); }
.vp__stage {
  position: relative;
  aspect-ratio: 16 / 9;
  background: #000;
  max-height: 46vh;   /* 反馈 ⑥：竖屏视频不得把下方内容挤走 */
}
.vp__video { width: 100%; height: 100%; object-fit: contain; }
.vp__placeholder {
  width: 100%; height: 100%;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 10px; color: var(--fg-faint);
  background: radial-gradient(circle at 30% 40%, #1d1d1d, #0e0e0e);
}
.vp__label {
  position: absolute; top: 8px; left: 8px;
  padding: 3px 10px; border-radius: var(--radius-pill);
  background: rgba(0, 0, 0, 0.55); color: var(--fg);
  font-size: var(--fs-2xs); font-weight: 500;
}
.vp__controls {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px; background: var(--panel-2);
}
.vp__controls--disabled { opacity: 0.5; }
.vp__btn {
  width: 28px; height: 28px; border: none; border-radius: var(--radius-s);
  background: transparent; color: var(--fg); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.vp__btn:hover { background: var(--card-hover); }
.vp__time { font-size: var(--fs-2xs); color: var(--fg-muted); min-width: 40px; }
.vp__bar {
  position: relative; flex: 1; height: 4px; border-radius: var(--radius-pill);
  background: var(--border); cursor: pointer;
}
.vp__fill { position: absolute; left: 0; top: 0; bottom: 0; border-radius: var(--radius-pill); background: var(--accent); }
.vp__playhead { position: absolute; top: -3px; width: 8px; height: 10px; margin-left: -4px; border-radius: 3px; background: var(--fg); }
</style>
