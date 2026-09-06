<script setup lang="ts">
import type { ResultJson } from '@/services'
import { formatEdited, formatOriginal } from '@/utils/format'
import ConfidenceBadge from './ConfidenceBadge.vue'
import StatusBadge from './StatusBadge.vue'

const props = defineProps<{
  results: ResultJson[]
  selectedId?: string | null
}>()

const emit = defineEmits<{ (e: 'select', id: string): void }>()
</script>

<template>
  <div class="rt">
    <div class="rt__head rt__grid">
      <span>片段</span>
      <span>剪辑区间</span>
      <span>原片区间</span>
      <span>置信度</span>
      <span>得分</span>
      <span />
    </div>

    <button
      v-for="(r, i) in props.results"
      :key="r.result_id"
      class="rt__row rt__grid"
      :class="{ 'rt__row--active': r.result_id === props.selectedId }"
      @click="emit('select', r.result_id)"
    >
      <span class="rt__clip mono">{{ String(i + 1).padStart(2, '0') }}</span>
      <span class="rt__val mono">{{ formatEdited(r.edited_segment.start) }} – {{ formatEdited(r.edited_segment.end) }}</span>
      <span class="rt__val mono">{{ formatOriginal(r.original.candidate_start) }} – {{ formatOriginal(r.original.candidate_end) }}</span>
      <span>
        <ConfidenceBadge :level="r.confidence" />
      </span>
      <span class="rt__score mono">{{ r.confidence_score.toFixed(2) }}</span>
      <span class="rt__flags">
        <StatusBadge v-if="r.not_in_source" label="非源片" tone="warn" icon="warn" />
        <StatusBadge v-if="r.montage_flag && !r.not_in_source" label="疑似蒙太奇" tone="warn" icon="warn" />
        <StatusBadge v-if="r.source === 'manual'" label="手动" tone="accent" />
        <StatusBadge
          v-if="r.failure_reason"
          label="未定位"
          tone="err"
          :title="r.failure_reason"
        />
        <StatusBadge v-if="r.excluded" label="不导出" tone="muted" />
      </span>
    </button>

    <div v-if="props.results.length === 0" class="rt__empty">还没有结果——请先运行分析。</div>
  </div>
</template>

<style scoped>
.rt { display: flex; flex-direction: column; }
.rt__grid {
  display: grid;
  grid-template-columns: 44px minmax(150px, 1.1fr) minmax(150px, 1.1fr) 106px 58px 170px;
  gap: 10px;
  align-items: center;
  padding: 9px 12px;
}
.rt__head {
  color: var(--fg-faint);
  font-size: var(--fs-2xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-bottom: 1px solid var(--divider);
}
.rt__row {
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--divider);
  color: var(--fg);
  font-family: inherit;
  font-size: var(--fs-sm);
  cursor: pointer;
  text-align: left;
  transition: background var(--motion-1);
}
.rt__row:hover { background: var(--card); }
.rt__row--active { background: var(--card-hover); box-shadow: inset 2px 0 0 var(--accent); }
.rt__clip { color: var(--fg-muted); font-size: var(--fs-xs); }
.rt__val { color: var(--fg); }
.rt__score { color: var(--fg-muted); }
.rt__flags { display: flex; flex-wrap: wrap; gap: 6px; justify-content: flex-end; }
.rt__empty { padding: 32px; text-align: center; color: var(--fg-faint); }
</style>
