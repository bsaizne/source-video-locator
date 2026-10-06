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
// 快/精双模式（2026-10-02）：'precise' → refine 不传（后端 config 默认=开）；
// 'fast' → refine:false。持久化到 localStorage，下次启动记住用户档位。
const mode = ref<'precise' | 'fast'>(
  localStorage.getItem('svl.analyzeMode') === 'fast' ? 'fast' : 'precise')
watch(mode, (m) => localStorage.setItem('svl.analyzeMode', m))
// 切项目/首次进入时，默认选该项目第一个剪辑视频
watch([editedList, () => analysis.pinnedProjectId], () => {
  if (!editedList.value.includes(edited.value)) edited.value = editedList.value[0] ?? ''
}, { immediate: true })

const original = computed(() => pinned.value?.sourceVideo ?? '')
// 多原片（续27 video.concat）：库里 ≥2 段且尚未合并 → 把清单交给后端，
// worker 在建索引前物理合并成单个母片（合并进度复用「准备原片索引」阶段展示）。
const sources = computed(() => projects.absoluteSources(pinned.value))
const willMerge = computed(() => sources.value.length >= 2 && !pinned.value?.merge)
const hasSource = computed(() => !!original.value || sources.value.length > 0)

const progress = computed(() => analysis.progress)

// 计时从 store 里的任务起点时刻算（2026-10-06 修「时间消失/一直 00:00」）：
// 原先是组件本地 setInterval 计数器 ⇒ 换页或重挂即归零且不再走（run() 才会重启）。
const nowTick = ref(Date.now())
let elapsedTimer: ReturnType<typeof setInterval> | null = null
function ensureTicking(on: boolean): void {
  if (on && !elapsedTimer) {
    nowTick.value = Date.now()
    elapsedTimer = setInterval(() => (nowTick.value = Date.now()), 1000)
  }
  if (!on && elapsedTimer) {
    clearInterval(elapsedTimer)
    elapsedTimer = null
  }
}
const elapsedSec = computed(() =>
  analysis.taskStartedAt
    ? Math.max(0, Math.floor((nowTick.value - analysis.taskStartedAt) / 1000))
    : 0)
watch(() => analysis.running, (r) => ensureTicking(r), { immediate: true })
onBeforeUnmount(() => ensureTicking(false))

async function run(): Promise<void> {
  if (!pinned.value || !edited.value) return
  analysis.reset()
  try {
    // 一键分析（反馈 ②）：原片索引已包含在流程内，无需单独构建。
    const batch = await analysis.runLocate(
      edited.value,
      original.value,
      willMerge.value ? sources.value : undefined,
      mode.value === 'fast' ? false : undefined,
    )
    results.setBatch(batch)
    router.push('/results')
  } catch {
    // error surfaced in analysis.error
  } finally {
    ensureTicking(false)
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
      <div v-if="hasSource" class="an__row an__row--source">
        <span class="an__k">源片</span>
        <template v-if="pinned?.merge">
          <span class="mono">{{ original }}</span>
          <span class="an__tag">合并自 {{ sources.length }} 段 · {{ pinned.merge.mode }}</span>
        </template>
        <template v-else-if="willMerge">
          <span class="mono an__multi">{{ sources.length }} 段原片（分析开始时先合并为单个母片）</span>
        </template>
        <span v-else class="mono">{{ original }}</span>
      </div>
      <ul v-if="willMerge" class="an__srclist">
        <li v-for="(s, i) in sources" :key="s" class="mono">{{ i + 1 }}. {{ s }}</li>
      </ul>
      <p v-if="!pinned" class="an__hint">还没有项目——先到「项目」页新建一个。</p>
      <p v-else-if="!hasSource" class="an__hint">该项目还没有源片：到项目详情页「源片库」选择或添加原片。</p>

      <!-- 快/精双模式（2026-10-02）：默认高精度；快速档跳过画面深度复核两阶段，
           实测省 ~60% 墙钟（test2 27→~11 min 级），精度略降、结果不含细拆分。 -->
      <div v-if="pinned && hasSource" class="an__row an__row--mode">
        <span class="an__k">模式</span>
        <label class="an__radio"><input type="radio" value="precise" v-model="mode">
          高精度（默认，更全面，耗时较长）</label>
        <label class="an__radio"><input type="radio" value="fast" v-model="mode">
          快速（省时约六成，精度略降）</label>
      </div>
    </div>

    <div class="an__actions">
      <BaseButton variant="primary" size="lg" @click="run" :loading="analysis.running"
                  :disabled="analysis.running || !pinned || !edited || !hasSource" icon="play">
        {{ analysis.running ? '分析中…' : (willMerge ? '合并并分析' : '开始分析') }}
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
.an__row--mode { flex-wrap: wrap; }
.an__radio { display: inline-flex; align-items: center; gap: 5px;
  font-size: var(--fs-sm); color: var(--fg-muted); cursor: pointer; }
.an__row--source { align-items: baseline; }
.an__tag {
  padding: 2px 8px; border-radius: var(--radius-s);
  background: var(--accent-soft); color: var(--accent-glow);
  font-size: var(--fs-2xs); white-space: nowrap;
}
.an__multi { color: var(--fg-muted); }
.an__srclist { list-style: none; margin: 6px 0 0; padding: 0 0 0 4px; color: var(--fg-faint); font-size: var(--fs-xs); }
.an__srclist li { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.an__actions { display: flex; gap: 12px; margin: 22px 0; }
.an__pipeline { background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius-m); padding: 18px; }
.an__error {
  margin-top: 16px; padding: 12px 14px; border-radius: var(--radius-s);
  background: var(--conf-low-bg); color: var(--conf-low); font-size: var(--fs-sm);
}
</style>
