<script setup lang="ts">
import { ref } from 'vue'

export interface TimelineMarker {
  id: string
  label?: string
  start: number
  end: number
  tone?: 'high' | 'medium' | 'low' | 'accent' | 'manual'
}

const props = withDefaults(
  defineProps<{
    duration: number
    value: number
    markers?: TimelineMarker[]
    interactive?: boolean
    selectedId?: string | null
  }>(),
  { markers: () => [], interactive: true, selectedId: null },
)

const emit = defineEmits<{
  (e: 'seek', seconds: number): void
  (e: 'select', id: string | null): void
}>()

const track = ref<HTMLElement | null>(null)
// 仅按下拖动时才跟随（用户反馈：鼠标划过时间轴光标就被拖走=误触）。
// 单击 = 按下+抬起各定位一次；悬停不触发。
const dragging = ref(false)

function pct(t: number): number {
  if (!props.duration) return 0
  return (t / props.duration) * 100
}

function onSeek(ev: PointerEvent): void {
  if (!props.interactive || !track.value) return
  const rect = track.value.getBoundingClientRect()
  const frac = Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width))
  emit('seek', frac * props.duration)
}

function pickMarker(ev: PointerEvent): string | null {
  if (!track.value) return null
  const rect = track.value.getBoundingClientRect()
  const frac = (ev.clientX - rect.left) / rect.width
  const t = frac * props.duration
  const hit = props.markers.find((m) => t >= m.start && t <= m.end)
  return hit?.id ?? null
}

function onPointerDown(ev: PointerEvent): void {
  if (!props.interactive) return
  dragging.value = true
  try { (ev.currentTarget as HTMLElement).setPointerCapture(ev.pointerId) } catch { /* 非致命 */ }
  const id = pickMarker(ev)
  emit('select', id)
  onSeek(ev)
}

function onPointerMove(ev: PointerEvent): void {
  if (dragging.value) onSeek(ev)
}

function onPointerUp(ev: PointerEvent): void {
  if (!dragging.value) return
  dragging.value = false
  onSeek(ev)
}

function tickPcts(): number[] {
  if (!props.duration) return []
  const n = 8
  return Array.from({ length: n }, (_, i) => (i / (n - 1)) * 100)
}
</script>

<template>
  <div class="timeline">
    <div
      ref="track"
      class="timeline__track"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="dragging = false"
    >
      <div
        class="timeline__tick"
        v-for="(p, i) in tickPcts()"
        :key="i"
        :style="{ left: p + '%' }"
      />
      <button
        v-for="m in markers"
        :key="m.id"
        class="timeline__marker"
        :class="[`timeline__marker--${m.tone ?? 'accent'}`, { 'timeline__marker--active': selectedId === m.id }]"
        :style="{ left: pct(m.start) + '%', width: `calc(${pct(m.end - m.start)}% - 2px)` }"
        :title="m.label"
      />
      <div class="timeline__playhead" :style="{ left: pct(value) + '%' }" />
    </div>
  </div>
</template>

<style scoped>
.timeline {
  position: relative;
  padding: 14px 0 6px;
  user-select: none;
}
.timeline__track {
  position: relative;
  height: 28px;
  border-radius: var(--radius-s);
  background: var(--panel-2);
  cursor: pointer;
  overflow: hidden;
}
.timeline__tick {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
  background: var(--divider);
  height: 100%;
}
.timeline__marker {
  position: absolute;
  top: 5px;
  height: 18px;
  border-radius: 4px;
  border: none;
  cursor: pointer;
  background: rgba(76, 194, 255, 0.28);
}
.timeline__marker--high { background: rgba(108, 203, 95, 0.30); }
.timeline__marker--medium { background: rgba(242, 201, 76, 0.30); }
.timeline__marker--low { background: rgba(245, 73, 61, 0.30); }
.timeline__marker--manual { background: rgba(0, 120, 212, 0.55); }
.timeline__marker--active {
  box-shadow: 0 0 0 2px var(--accent-glow);
  cursor: grab;
}
.timeline__playhead {
  position: absolute;
  top: -2px;
  bottom: -2px;
  width: 2px;
  background: var(--fg);
  border-radius: 2px;
  pointer-events: none;
}
.timeline__playhead::after {
  content: '';
  position: absolute;
  top: -3px;
  left: -3px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--fg);
}
</style>
