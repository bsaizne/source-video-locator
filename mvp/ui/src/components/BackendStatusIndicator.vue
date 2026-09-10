<script setup lang="ts">
import { computed } from 'vue'
import type { BackendInfoJson, ConnectionStatus, IndexStatus } from '@/services'
import StatusBadge from './StatusBadge.vue'

const props = defineProps<{
  backend: BackendInfoJson | null
  indexStatus: IndexStatus | null
  connection: ConnectionStatus | null
}>()

const CONNECTION_META: Record<ConnectionStatus, { label: string; tone: 'ok' | 'warn' | 'err' }> = {
  CONNECTED: { label: '已连接', tone: 'ok' },
  CONNECTING: { label: '连接中', tone: 'warn' },
  OFFLINE: { label: '离线', tone: 'err' },
}

const connMeta = computed(() =>
  props.connection ? CONNECTION_META[props.connection] : { label: '连接中', tone: 'warn' as const },
)

const DEVICE_LABEL: Record<string, string> = {
  cpu: 'CPU',
  amd: 'GPU (DirectML)',
  mps: 'GPU (MPS)',
  cuda: 'GPU (CUDA)',
}

const backendLabel = computed(() => {
  if (!props.backend) return '—'
  return DEVICE_LABEL[props.backend.deviceType] ?? props.backend.deviceType
})

const blocked = computed(() => props.backend?.deviceName === 'AMD_GPU_BACKEND_BLOCKED')
const fallback = computed(() => props.backend?.fallback ?? false)
</script>

<template>
  <div class="backend">
    <div class="backend__row">
      <span class="backend__k">连接</span>
      <span class="backend__v">
        <StatusBadge :label="connMeta.label" :tone="connMeta.tone" />
      </span>
    </div>
    <div class="backend__row">
      <span class="backend__k">后端</span>
      <span class="backend__v">
        {{ backendLabel }}
        <StatusBadge v-if="blocked" label="已阻止" tone="err" />
        <StatusBadge v-else-if="fallback" label="回退" tone="warn" />
      </span>
    </div>
  </div>
</template>

<style scoped>
.backend {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border-top: 1px solid var(--divider);
}
.backend__row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: var(--fs-xs);
}
.backend__k { color: var(--fg-faint); }
.backend__v { color: var(--fg); display: inline-flex; align-items: center; gap: 6px; }
.backend__note { color: var(--fg-faint); font-size: var(--fs-2xs); }
</style>
