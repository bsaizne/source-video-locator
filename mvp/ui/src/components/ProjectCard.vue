<script setup lang="ts">
import { computed } from 'vue'
import type { Project } from '@/stores/projects'
import { formatDuration } from '@/utils/format'
import StatusBadge from './StatusBadge.vue'
import BaseIcon from './ui/BaseIcon.vue'

const props = defineProps<{ project: Project }>()
const emit = defineEmits<{ (e: 'open'): void }>()

const statusTone = computed(() => {
  switch (props.project.status) {
    case 'ready': return 'ok'
    case 'indexing': return 'warn'
    case 'analyzing': return 'accent'
    default: return 'muted'
  }
})

const STATUS_LABEL: Record<string, string> = {
  ready: '就绪',
  indexing: '索引中',
  analyzing: '分析中',
}
</script>

<template>
  <button class="pcard" @click="emit('open')">
    <div class="pcard__top">
      <span class="pcard__icon"><BaseIcon name="film" :size="18" /></span>
      <StatusBadge :label="STATUS_LABEL[project.status] ?? project.status" :tone="statusTone" />
    </div>
    <div class="pcard__name">{{ project.name }}</div>
    <div class="pcard__meta mono">{{ project.sourceVideo }}</div>
    <div class="pcard__meta"><span class="faint">时长</span> {{ formatDuration(project.sourceDuration) }}</div>
    <div class="pcard__meta"><span class="faint">剪辑</span> {{ project.editedVideos.length ? project.editedVideos.join(', ') : '—' }}</div>
    <div class="pcard__foot">
      <span class="faint">上次分析</span>
      <span>{{ project.lastAnalysis ?? '—' }}</span>
    </div>
  </button>
</template>

<style scoped>
.pcard {
  display: flex;
  flex-direction: column;
  gap: 8px;
  text-align: left;
  padding: 16px;
  border-radius: var(--radius-l);
  background: var(--card);
  border: 1px solid var(--border);
  color: var(--fg);
  font-family: inherit;
  cursor: pointer;
  transition: background var(--motion-2), border-color var(--motion-2), transform var(--motion-2);
}
.pcard:hover {
  background: var(--card-hover);
  border-color: var(--border-strong);
  transform: translateY(-1px);
}
.pcard__top { display: flex; align-items: center; justify-content: space-between; }
.pcard__icon {
  width: 36px; height: 36px; border-radius: var(--radius-m);
  background: var(--accent-soft); color: var(--accent-glow);
  display: flex; align-items: center; justify-content: center;
}
.pcard__name { font-size: var(--fs-lg); font-weight: 600; margin-top: 4px; }
.pcard__meta { font-size: var(--fs-xs); color: var(--fg-muted); }
.pcard__foot {
  display: flex; justify-content: space-between;
  margin-top: 8px; padding-top: 10px; border-top: 1px solid var(--divider);
  font-size: var(--fs-2xs); color: var(--fg-muted);
}
</style>
