<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    current?: number
    total?: number
    value?: number // 0..100 alternative
    indeterminate?: boolean
    label?: string
  }>(),
  { current: 0, total: 0, value: undefined, indeterminate: false, label: '' },
)

const pct = computed(() => {
  if (props.indeterminate) return 0
  if (props.value !== undefined) return Math.max(0, Math.min(100, props.value))
  if (!props.total) return 0
  return Math.round((props.current / props.total) * 100)
})
</script>

<template>
  <div class="pbar">
    <div v-if="label" class="pbar__label">{{ label }}</div>
    <div class="pbar__track">
      <div
        class="pbar__fill"
        :class="{ 'pbar__fill--ind': indeterminate }"
        :style="{ width: indeterminate ? '34%' : pct + '%' }"
      />
    </div>
  </div>
</template>

<style scoped>
.pbar__track {
  height: 4px;
  border-radius: var(--radius-pill);
  background: var(--panel-2);
  overflow: hidden;
}
.pbar__fill {
  height: 100%;
  border-radius: var(--radius-pill);
  background: var(--accent);
  transition: width var(--motion-3);
}
.pbar__fill--ind {
  animation: ind 1.1s ease-in-out infinite;
  width: 34%;
}
@keyframes ind { 0% { transform: translateX(-100%); } 100% { transform: translateX(300%); } }
.pbar__label { margin-bottom: 6px; color: var(--fg-muted); font-size: var(--fs-xs); }
</style>
