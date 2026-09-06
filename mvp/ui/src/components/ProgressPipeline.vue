<script setup lang="ts">
import { computed } from 'vue'
import BaseIcon from './ui/BaseIcon.vue'
import Spinner from './ui/Spinner.vue'
import type { PipelineStep } from '@/stores/analysis'
import type { ProgressStage } from '@/services'

const props = withDefaults(
  defineProps<{
    steps: PipelineStep[]
    progress?: { stage: ProgressStage; current: number; total: number; message: string } | null
    elapsedSec?: number
  }>(),
  { progress: null, elapsedSec: 0 },
)

const emit = defineEmits<{ (e: 'cancel'): void }>()

const running = computed(() => props.steps.some((s) => s.status === 'running'))

const progressPct = computed(() => {
  if (!props.progress || !props.progress.total) return 0
  return Math.round((props.progress.current / props.progress.total) * 100)
})

// Friendly label for the current task stage（粗粒度：内部阶段折叠为面向用户的说法）。
const STAGE_LABEL: Record<string, string> = {
  INDEX_BUILD: '准备原片索引',
  EDITED_FEATURE_EXTRACTION: '读取剪辑视频',
  SEGMENT_DETECTION: '镜头分析',
  CANDIDATE_RETRIEVAL: '镜头分析',
  LOCALIZATION: '镜头分析',
  CONFIDENCE: '完成输出',
  EXPORT: '输出结果',
}
const currentStageLabel = computed(
  () => (props.progress && STAGE_LABEL[props.progress.stage]) || '分析中',
)

const elapsed = computed(() => {
  const s = Math.max(0, Math.floor(props.elapsedSec ?? 0))
  const mm = String(Math.floor(s / 60)).padStart(2, '0')
  const ss = String(s % 60).padStart(2, '0')
  return `${mm}:${ss}`
})
</script>

<template>
  <div class="pl">
    <ol class="pl__list">
      <li v-for="(step, i) in props.steps" :key="step.key" class="pl__row" :class="`pl--${step.status}`">
        <div class="pl__rail">
          <div class="pl__node">
            <Spinner v-if="step.status === 'running'" :size="14" />
            <BaseIcon v-else-if="step.status === 'done'" name="check" :size="14" />
            <BaseIcon v-else-if="step.status === 'error'" name="x" :size="14" />
            <span v-else class="pl__idx">{{ String(i + 1).padStart(2, '0') }}</span>
          </div>
        </div>
        <div class="pl__body">
          <div class="pl__head">
            <span class="pl__label">{{ step.label }}</span>
            <span v-if="step.status === 'running'" class="pl__running mono">运行中</span>
          </div>
          <div v-if="step.message" class="pl__msg mono">{{ step.message }}</div>
        </div>
      </li>
    </ol>

    <div v-if="props.progress" class="pl__live">
      <div class="pl__bar">
        <div class="pl__fill" :style="{ width: progressPct + '%' }" />
      </div>
      <div class="pl__meta">
        <span class="mono faint">{{ currentStageLabel }}</span>
        <span class="mono">{{ progressPct }}%</span>
        <span class="mono faint">{{ elapsed }}</span>
        <button v-if="running" class="pl__cancel" type="button" @click="emit('cancel')">取消</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pl__list { list-style: none; margin: 0; padding: 0; }
.pl__row { display: flex; gap: 14px; }
.pl__row + .pl__row { margin-top: 2px; }
.pl__rail { display: flex; flex-direction: column; align-items: center; }
.pl__node {
  width: 28px; height: 28px; flex-shrink: 0; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  border: 1px solid var(--border); color: var(--fg-faint); background: var(--panel-2);
}
.pl__idx { font-size: 10px; font-weight: 600; }
.pl__body { padding: 4px 0 16px; min-width: 0; }
.pl__head { display: flex; align-items: baseline; gap: 10px; }
.pl__label { font-size: var(--fs-md); font-weight: 500; color: var(--fg-muted); }
.pl__msg { font-size: var(--fs-xs); color: var(--fg-faint); margin-top: 3px; }
.pl__running { font-size: var(--fs-2xs); color: var(--accent-glow); }

.pl--done .pl__node { border-color: var(--ok); color: var(--ok); background: rgba(108, 203, 95, 0.08); }
.pl--done .pl__label { color: var(--fg); }
.pl--running .pl__node { border-color: var(--accent); color: var(--accent-glow); }
.pl--running .pl__label { color: var(--fg); }
.pl--error .pl__node { border-color: var(--err); color: var(--err); background: rgba(245, 73, 61, 0.08); }
.pl--error .pl__label { color: var(--err); }

.pl__live { margin-top: 10px; border-top: 1px solid var(--border); padding-top: 12px; }
.pl__bar { height: 6px; border-radius: var(--radius-pill); background: var(--border); overflow: hidden; }
.pl__fill { height: 100%; border-radius: var(--radius-pill); background: var(--accent); transition: width 0.2s ease; }
.pl__meta { display: flex; align-items: center; gap: 12px; margin-top: 8px; font-size: var(--fs-xs); }
.pl__cancel {
  margin-left: auto; border: 1px solid var(--border); background: transparent;
  color: var(--err); border-radius: var(--radius-s); padding: 3px 10px; cursor: pointer; font-size: var(--fs-xs);
}
.pl__cancel:hover { background: rgba(245, 73, 61, 0.08); }
</style>
