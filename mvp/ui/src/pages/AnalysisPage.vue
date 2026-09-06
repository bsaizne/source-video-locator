<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAnalysisStore } from '@/stores/analysis'
import { useResultsStore } from '@/stores/results'
import { useProjectsStore } from '@/stores/projects'
import ProgressPipeline from '@/components/ProgressPipeline.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'

const router = useRouter()
const analysis = useAnalysisStore()
const results = useResultsStore()
const projects = useProjectsStore()

// 固定项目（反馈 ⑫）：分析界面有自己的项目选择，别处切项目不偷换这里的 UI。
onMounted(() => {
  if (!analysis.pinnedProjectId || !projects.projects.some((p) => p.id === analysis.pinnedProjectId)) {
    analysis.setPinnedProject(projects.activeProject?.id ?? projects.projects[0]?.id ?? null)
  }
})
const pinned = computed(() =>
  projects.projects.find((p) => p.id === analysis.pinnedProjectId) ?? null,
)

function onSwitchProject(id: string): void {
  analysis.setPinnedProject(id)
  projects.selectProject(id)
}

const editedList = computed(() => {
  const list = pinned.value?.editedVideos.length ? pinned.value.editedVideos : []
  return [...new Set(list)]
})

const edited = ref('')
// 切项目/首次进入时，默认选该项目第一个剪辑视频
watch([editedList, () => analysis.pinnedProjectId], () => {
  if (!editedList.value.includes(edited.value)) edited.value = editedList.value[0] ?? ''
}, { immediate: true })

const original = computed(() => pinned.value?.sourceVideo ?? '')

const progress = computed(() => analysis.progress)

// Elapsed wall-clock seconds while the analysis task runs.
const elapsedSec = ref(0)
let elapsedTimer: ReturnType<typeof setInterval> | null = null
function startElapsed(): void {
  elapsedSec.value = 0
  if (elapsedTimer) clearInterval(elapsedTimer)
  elapsedTimer = setInterval(() => (elapsedSec.value += 1), 1000)
}
function stopElapsed(): void {
  if (elapsedTimer) {
    clearInterval(elapsedTimer)
    elapsedTimer = null
  }
}
onBeforeUnmount(stopElapsed)

async function run(): Promise<void> {
  if (!pinned.value || !edited.value) return
  analysis.reset()
  startElapsed()
  try {
    // 一键分析（反馈 ②）：原片索引已包含在流程内，无需单独构建。
    const batch = await analysis.runLocate(edited.value, original.value)
    results.setBatch(batch)
    router.push('/results')
  } catch {
    // error surfaced in analysis.error
  } finally {
    stopElapsed()
  }
}

function cancel(): void {
  analysis.cancelTask()
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">分析</h1>
      <p class="page-subtitle">在原始母片中定位每个剪辑片段</p>
    </div>

    <div class="an__card">
      <div class="an__row">
        <label class="an__field">
          <span class="an__k">项目</span>
          <BaseSelect :model-value="analysis.pinnedProjectId ?? ''" @update:model-value="onSwitchProject">
            <option v-for="p in projects.projects" :key="p.id" :value="p.id">{{ p.name }}</option>
          </BaseSelect>
        </label>
        <label class="an__field">
          <span class="an__k">剪辑视频</span>
          <BaseSelect v-model="edited" style="min-width: 220px">
            <option v-for="e in editedList" :key="e" :value="e">{{ e }}</option>
          </BaseSelect>
        </label>
      </div>
      <div class="an__row" v-if="original">
        <span class="an__k">源片</span>
        <span class="mono">{{ original }}</span>
      </div>
      <p v-if="!pinned" class="an__hint">还没有项目——先到「项目」页新建一个。</p>
    </div>

    <div class="an__actions">
      <BaseButton variant="primary" size="lg" @click="run" :loading="analysis.running"
                  :disabled="analysis.running || !pinned || !edited" icon="play">
        {{ analysis.running ? '分析中…' : '开始分析' }}
      </BaseButton>
      <BaseButton v-if="analysis.running" variant="danger" @click="cancel">取消</BaseButton>
    </div>

    <div class="an__pipeline">
      <div class="section-title">工作流程</div>
      <ProgressPipeline
        :steps="analysis.steps"
        :progress="progress"
        :elapsed-sec="elapsedSec"
        @cancel="cancel"
      />
    </div>

    <div v-if="analysis.error" class="an__error">
      {{ analysis.error }}
    </div>
  </div>
</template>

<style scoped>
.an__card {
  padding: 18px; border-radius: var(--radius-m);
  background: var(--panel); border: 1px solid var(--border);
  display: flex; flex-direction: column; gap: 12px;
}
.an__row { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.an__field { display: flex; flex-direction: column; gap: 6px; font-size: var(--fs-xs); color: var(--fg-faint); }
.an__k { font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: 0.04em; color: var(--fg-faint); }
.an__hint { color: var(--fg-faint); font-size: var(--fs-sm); margin: 0; }
.an__actions { display: flex; gap: 12px; margin: 22px 0; }
.an__pipeline { background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius-m); padding: 18px; }
.an__error {
  margin-top: 16px; padding: 12px 14px; border-radius: var(--radius-s);
  background: var(--conf-low-bg); color: var(--conf-low); font-size: var(--fs-sm);
}
</style>
