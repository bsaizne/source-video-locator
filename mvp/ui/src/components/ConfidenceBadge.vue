<script setup lang="ts">
import { computed } from 'vue'
import type { ConfidenceLevel } from '@/services'

const props = withDefaults(
  defineProps<{
    level: ConfidenceLevel
    score?: number | null
    reasons?: string[]
    showScore?: boolean
  }>(),
  { score: null, reasons: () => [], showScore: false },
)

const CONFIDENCE_LABEL: Record<string, string> = { HIGH: '高', MEDIUM: '中', LOW: '低' }
const label = computed(() => CONFIDENCE_LABEL[props.level] ?? props.level)

// The engineering score is a 0..1 value, never a probability. Show it as a
// plain number (0.94), never "94%".
const scoreText = computed(() =>
  props.score == null ? '' : props.score.toFixed(2),
)

const tip = computed(() =>
  props.reasons.length ? props.reasons.join(' · ') : '',
)
</script>

<template>
  <span class="cbadge" :class="`cbadge--${level.toLowerCase()}`" :title="tip || undefined">
    <span class="cbadge__dot" />
    <span>{{ label }}</span>
    <span v-if="showScore && scoreText" class="cbadge__score">{{ scoreText }}</span>
  </span>
</template>

<style scoped>
.cbadge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  border-radius: var(--radius-pill);
  font-size: var(--fs-2xs);
  font-weight: 600;
  letter-spacing: 0.03em;
  border: 1px solid transparent;
  white-space: nowrap;
}
.cbadge__dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.cbadge__score { font-weight: 500; font-variant-numeric: tabular-nums; opacity: 0.9; }

.cbadge--high { color: var(--conf-high); background: var(--conf-high-bg); }
.cbadge--medium { color: var(--conf-medium); background: var(--conf-medium-bg); }
.cbadge--low { color: var(--conf-low); background: var(--conf-low-bg); }
</style>
