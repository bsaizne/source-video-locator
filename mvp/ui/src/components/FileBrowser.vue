<script setup lang="ts">
// FileBrowser — 应用内素材浏览面板（入库层四件，2026-10-02，竞品 web.file_api.browser）。
// 数据全部来自 service.browseFs（后端 = infrastructure.fsbrowse：盘符/自然排序/白名单/
// 磁盘剩余）。本组件**不再排序、不再过滤**——口径只在一处。
// multi=true 时按点选顺序累积多选（顺序 = 合并时间轴顺序），确认后 emit('picked', paths)。
import { computed, ref, watch } from 'vue'
import { useService } from '@/services'
import type { FsBrowseResult, FsEntryJson } from '@/services/types'
import BaseButton from './ui/BaseButton.vue'
import BaseIcon from './ui/BaseIcon.vue'

const props = withDefaults(defineProps<{ multi?: boolean }>(), { multi: true })
const emit = defineEmits<{
  (e: 'picked', paths: string[]): void
  (e: 'close'): void
}>()

const service = useService()
const current = ref('')            // '' = 此电脑
const data = ref<FsBrowseResult | null>(null)
const error = ref('')
const loading = ref(false)
const selected = ref<FsEntryJson[]>([])   // 点选顺序即返回顺序

async function go(path: string): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    data.value = await service.browseFs(path)
    current.value = data.value.path
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}
void go('')

const isRoot = computed(() => (data.value?.kind ?? 'root') === 'root')
const dirs = computed(() => (data.value?.entries ?? []).filter((e) => !e.is_video))
const vids = computed(() => (data.value?.entries ?? []).filter((e) => e.is_video))
const selectedPaths = computed(() => selected.value.map((s) => s.path))

function toggleVideo(v: FsEntryJson): void {
  if (!props.multi) { emit('picked', [v.path]); return }
  const i = selected.value.findIndex((s) => s.path === v.path)
  if (i >= 0) selected.value.splice(i, 1)
  else selected.value.push(v)
}
function orderOf(p: string): number {
  return selected.value.findIndex((s) => s.path === p)
}

function fmtSize(bytes?: number): string {
  if (bytes == null) return '—'
  // <1GB 用 MB 显示——否则小剪辑片渲染成「0.0 GB」像坏了一样
  return bytes >= 1e9 ? (bytes / 1e9).toFixed(1) + ' GB' : Math.max(1, Math.round(bytes / 1e6)) + ' MB'
}

watch(() => props.multi, (m) => { if (!m) selected.value = [] })

function confirm(): void {
  if (selected.value.length) emit('picked', selectedPaths.value)
}
</script>

<template>
  <div class="fb">
    <div class="fb__bar">
      <BaseButton :disabled="loading || current === ''" @click="go(data?.parent ?? '')">上一级</BaseButton>
      <span class="fb__path mono">{{ current === '' ? '此电脑' : current }}</span>
      <BaseButton :disabled="loading" icon="refresh" @click="go(current)">刷新</BaseButton>
      <BaseButton icon="x" @click="emit('close')">关闭</BaseButton>
    </div>
    <div v-if="error" class="fb__err">{{ error }}</div>
    <div v-if="loading" class="fb__hint">读取中…</div>
    <div v-else class="fb__list">
      <!-- 此电脑：盘符 + 剩余空间（磁盘预检的可视来源） -->
      <template v-if="isRoot">
        <button v-for="d in data?.drives ?? []" :key="d.path" class="fb__row" @click="go(d.path)">
          <BaseIcon name="drive" :size="16" />
          <span class="fb__name">{{ d.label ? `${d.name} (${d.label})` : d.name }}</span>
          <span class="fb__meta">剩 {{ fmtSize(d.free_bytes) }} / {{ fmtSize(d.total_bytes) }}</span>
        </button>
      </template>
      <template v-else>
        <button v-for="d in dirs" :key="d.path" class="fb__row" @click="go(d.path)">
          <BaseIcon name="folder" :size="16" />
          <span class="fb__name">{{ d.name }}</span>
        </button>
        <button v-for="v in vids" :key="v.path" class="fb__row fb__row--vid"
                :class="{ 'fb__row--on': orderOf(v.path) >= 0 }" @click="toggleVideo(v)">
          <span v-if="orderOf(v.path) >= 0" class="fb__ord">{{ orderOf(v.path) + 1 }}</span>
          <BaseIcon v-else name="film" :size="16" />
          <span class="fb__name">{{ v.name }}</span>
          <span class="fb__meta">{{ fmtSize(v.size_bytes) }}</span>
        </button>
        <div v-if="!dirs.length && !vids.length" class="fb__hint">此目录没有可读视频文件</div>
      </template>
    </div>
    <div v-if="multi && !isRoot" class="fb__foot">
      <span class="fb__hint">已选 {{ selected.length }} 项（顺序 = 合并顺序）</span>
      <BaseButton variant="primary" :disabled="!selected.length" @click="confirm">添加选中</BaseButton>
    </div>
  </div>
</template>

<style scoped>
.fb { display: flex; flex-direction: column; gap: 8px; border: 1px solid var(--border);
  border-radius: var(--radius-m); background: var(--card); padding: 10px; }
.fb__bar { display: flex; align-items: center; gap: 8px; }
.fb__path { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-size: var(--fs-xs); color: var(--fg-muted); }
.fb__list { max-height: 280px; overflow-y: auto; display: flex; flex-direction: column; gap: 2px; }
.fb__row { display: flex; align-items: center; gap: 8px; width: 100%; text-align: left;
  padding: 6px 8px; border: 0; border-radius: var(--radius-s); background: transparent;
  color: var(--fg); font: inherit; font-size: var(--fs-sm); cursor: pointer; }
.fb__row:hover { background: var(--card-hover); }
.fb__row--on { background: var(--accent-soft); }
.fb__name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fb__meta { flex-shrink: 0; font-size: var(--fs-2xs); color: var(--fg-faint); }
.fb__ord { width: 18px; height: 18px; border-radius: 50%; background: var(--accent);
  color: var(--bg); font-size: 11px; display: flex; align-items: center; justify-content: center; }
.fb__err { color: var(--err); font-size: var(--fs-xs); }
.fb__hint { color: var(--fg-faint); font-size: var(--fs-xs); }
.fb__foot { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
</style>
