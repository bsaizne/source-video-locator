<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useResultsStore } from '@/stores/results'
import { useService } from '@/services'
import { useRenderMovie } from '@/composables/useRenderMovie'
import { formatOriginal } from '@/utils/format'
import { reasonText } from '@/utils/reasons'
import ResultTable from '@/components/ResultTable.vue'
import VideoComparisonPlayer from '@/components/VideoComparisonPlayer.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import ConfidenceBadge from '@/components/ConfidenceBadge.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'

const router = useRouter()
const results = useResultsStore()
const service = useService()

const exporting = ref(false)
const exportedPath = ref<string | null>(null)
const exportError = ref<string | null>(null)
// /api/export 的对外告警（如 LOC-2001 碎片告警）：后端只产出不裁剪，这里如实展示。
const exportWarnings = ref<string[]>([])
const showExport = ref(false)
// 反馈 ⑨ + 2026-10-01 用户拍板：置信门槛默认「全部」（低置信也作为主片段导出）；
// 格式默认剪映草稿。
// A4：门槛/低置信处理/边界吸附为**用户可选**（后端与适配器本就支持，此前被页面写死）。
const exportFormat = ref<'jianying' | 'fcp7_xml' | 'edl' | 'json'>('jianying')
const materialWidth = ref<'scene' | 'core'>('scene')   // 片段宽度（反馈四轮：可选+提示）
const minConfidence = ref<'HIGH' | 'MEDIUM' | 'LOW'>('LOW')
const lowPolicy = ref<'exclude' | 'backup'>('exclude')
const snapScenes = ref<'on' | 'off'>('on')   // BaseSelect 只吃 string，调用处再转 bool
const EXPORT_DIR_KEY = 'vl.exportDir'
const JY_EXPORT_DIR_KEY = 'vl.exportDirJianying'
const exportDir = computed(() => localStorage.getItem(EXPORT_DIR_KEY) ?? '')
const jyExportDir = computed(() => localStorage.getItem(JY_EXPORT_DIR_KEY) ?? '')
const activeExportDir = computed(() =>
  exportFormat.value === 'jianying' ? jyExportDir.value : exportDir.value)

const hasResults = computed(() => (results.batch?.results.length ?? 0) > 0)
const selected = computed(() => results.selected)

const reasonsList = computed(() => {
  const r = selected.value
  if (!r) return []
  return [...r.reasons].map((key) => reasonText(key))
})

// 手动修正输入（原 Inspector 的手动覆盖区，反馈 ⑪ 并入结果页）
const editStart = ref('')
const editEnd = ref('')
const editError = ref('')
watch(selected, (r) => {
  if (r) {
    editStart.value = String(Number((r.original.candidate_start).toFixed(2)))
    editEnd.value = String(Number((r.original.candidate_end).toFixed(2)))
    editError.value = ''
  }
})

// 接受两种写法：纯秒（444.5）或 分:秒 / 时:分:秒（7:24.5 / 1:07:24.5）。
// 旧版只认纯秒，用户输 7:24.5 时 Number()=NaN 静默返回=「点了没反应」。
function parseTimeInput(v: string): number | null {
  const t = v.trim()
  if (!t) return null
  if (/^\d+(\.\d+)?$/.test(t)) return Number(t)
  const m = t.match(/^(?:(\d+):)?(\d{1,2}):(\d{1,2}(?:\.\d+)?)$/)
  if (m) return (m[1] ? Number(m[1]) * 3600 : 0) + Number(m[2]) * 60 + Number(m[3])
  return null
}

function applyOverride(): void {
  const s = parseTimeInput(editStart.value)
  const e = parseTimeInput(editEnd.value)
  if (!selected.value || s === null || e === null || e <= s) {
    editError.value = '时间格式不对：填秒（444.5）或 分:秒（7:24.5），且终点要大于起点。'
    return
  }
  editError.value = ''
  results.markManualOverride(selected.value.result_id, s, e)
}

function toggleExclude(id: string, excluded: boolean): void {
  results.setExcluded(id, excluded)
}

function useCandidate(start: number, end: number): void {
  if (!selected.value) return
  results.markManualOverride(selected.value.result_id, start, end)
}

function previewCandidate(
  start: number,
  end: number,
  src?: { kind: 'alt' | 'seg'; index: number },
): void {
  void results.previewCandidate(start, end, src)
}

// ---- 预览来源标识（用户反馈：候选换来换去记不清哪个是原本剪出来的片段）----
const previewBadge = computed(() => {
  const s = results.previewSource
  if (!s) return null
  const span = `${formatOriginal(s.start)} – ${formatOriginal(s.end)}`
  if (s.kind === 'auto') return `自动定位(${span})`
  if (s.kind === 'manual') return `替换后定位(${span})`
  if (s.kind === 'seg') return `定位拆分段 ${s.index! + 1}(${span})`
  return `其它候选 ${s.index! + 1}(${span})`
})
const canResetPreview = computed(() => {
  const s = results.previewSource
  return !!s && s.kind !== 'auto' && s.kind !== 'manual'
})
function resetPreview(): void {
  void results.generatePreview()
}

// ---- 播放头打点（用户反馈：直接在原片预览上修 定位起止）----
const playerRef = ref<InstanceType<typeof VideoComparisonPlayer> | null>(null)
function setPointFromPlayhead(which: 'start' | 'end'): void {
  const player = playerRef.value
  const r = selected.value
  if (!player || !r) return
  const span = results.previewSource ?? {
    start: r.original.candidate_start,
    end: r.original.candidate_end,
  }
  const t = span.start + player.getOriginalTime()
  if (which === 'start') editStart.value = String(Number(t.toFixed(2)))
  else editEnd.value = String(Number(t.toFixed(2)))
}
// 手动修正输入的 mm:ss 实时换算（输入框单位=原片秒）
const editStartHuman = computed(() => {
  const v = parseTimeInput(editStart.value)
  return v !== null ? formatOriginal(v) : '—'
})
const editEndHuman = computed(() => {
  const v = parseTimeInput(editEnd.value)
  return v !== null ? formatOriginal(v) : '—'
})

// 预览候选时把预览区间传给播放器：标题/时间轴跟随正在预览的片段
const previewOverrideSpan = computed(() => {
  const s = results.previewSource
  if (!s || (s.kind !== 'alt' && s.kind !== 'seg')) return null
  return { start: s.start, end: s.end }
})

function onSelect(id: string): void {
  results.select(id)
}

async function doExport(): Promise<void> {
  if (!results.batch) return
  exporting.value = true
  exportedPath.value = null
  exportError.value = null
  exportWarnings.value = []
  try {
    const res = await service.exportResults(results.batch, {
      outDir: activeExportDir.value,
      format: exportFormat.value,
      minConfidence: minConfidence.value,
      lowPolicy: lowPolicy.value,
      snapScenes: snapScenes.value === 'on',
      materialWidth: materialWidth.value,
    })
    exportedPath.value = res.path
    exportWarnings.value = res.warnings ?? []
    // 有告警 → 对话框保持打开，用户确认过内容才收；无告警 → 维持旧行为直接关。
    if (!exportWarnings.value.length) showExport.value = false
  } catch (e) {
    exportError.value = e instanceof Error ? e.message : String(e)
  } finally {
    exporting.value = false
  }
}

const FORMAT_LABEL: Record<string, string> = {
  jianying: '剪映草稿（推荐）',
  fcp7_xml: 'FCP7 XML（Premiere）',
  edl: 'CMX3600 EDL',
  json: 'JSON 结果数据',
}

// ---- 成片渲染（2026-09-29 续30，竞品 video_renderer 移植）----
// 与导出共用同一套策略（门槛/低置信/吸附），渲染的是**同一份 clip 计划**；
// 独立异步任务（渲染要几十秒到几分钟），进度走轮询、可取消。
const {
  running: renderRunning,
  progress: renderProgress,
  message: renderMessage,
  moviePath: renderMoviePath,
  result: renderResult,
  error: renderError,
  start: startRender,
  cancel: cancelRender,
  revealFolder: revealRender,
} = useRenderMovie()

function doRender(): void {
  void startRender({
    outDir: activeExportDir.value,
    minConfidence: minConfidence.value,
    lowPolicy: lowPolicy.value,
    snapScenes: snapScenes.value === 'on',
  })
}

const renderSummary = computed(() => {
  const r = renderResult.value
  if (!r) return ''
  const mode = r.mode === 'reused' ? '命中既有成片'
    : r.mode === 'copy' ? '视频流复制合并' : '重编码合并'
  const hdr = r.hdr_downgraded ? ' · HDR 源已降为 SDR 成片' : ''
  return `${r.segments} 段 · ${r.total_frames} 帧 · ${r.fps}fps · ${mode} · 编码器 ${r.actual_encoder}${hdr}`
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div class="hstack" style="justify-content: space-between">
        <div>
          <h1 class="page-title">结果</h1>
          <p class="page-subtitle">复核并确认定位片段</p>
        </div>
        <div class="hstack">
          <StatusBadge :label="`${results.counts.high} 高`" tone="ok" />
          <StatusBadge :label="`${results.counts.medium} 中`" tone="warn" />
          <StatusBadge :label="`${results.counts.low} 低`" tone="err" />
          <BaseButton :disabled="!hasResults" icon="export" @click="showExport = true">导出工程</BaseButton>
        </div>
      </div>
    </div>

    <p v-if="exportedPath" class="results__exported mono">已导出 → {{ exportedPath }}</p>
    <p v-for="(w, i) in (!showExport ? exportWarnings : [])" :key="'ew' + i"
       class="rd__notice rd__notice--warn">{{ w }}</p>

    <div v-if="hasResults" class="results__split">
      <div class="results__list">
        <ResultTable :results="results.batch?.results ?? []" :selected-id="results.selectedId" @select="onSelect" />
      </div>
      <div class="results__view">
        <div v-if="previewBadge" class="rd__previewbar">
          <span>正在预览：<strong class="mono">{{ previewBadge }}</strong></span>
          <button v-if="canResetPreview" class="rd__mini" @click="resetPreview">回到自动定位</button>
        </div>
        <VideoComparisonPlayer
          ref="playerRef"
          :result="selected"
          :edited-src="results.previewEditedSrc"
          :original-src="results.previewOriginalSrc"
          :original-override-span="previewOverrideSpan"
        />

        <!-- 详情与修正（原右侧检查器并入此处，反馈 ⑪） -->
        <template v-if="selected">
          <div class="rd__head">
            <div class="rd__title">详情与修正</div>
            <ConfidenceBadge :level="selected.confidence" :show-score="true" :score="selected.confidence_score" />
          </div>

          <p v-if="selected.not_in_source" class="rd__notice rd__notice--warn">
            非源片内容——此段为片尾标识 / 转场 / 平台水印等，未在原片中定位，导出不包含它。
          </p>
          <p v-if="selected.montage_flag" class="rd__notice rd__notice--warn">
            疑似混剪——这段对应原片的多个片段，导出时会全部包含。
          </p>
          <p v-if="selected.failure_reason" class="rd__notice rd__notice--err">
            未定位：{{ reasonText(selected.failure_reason) }}
          </p>

          <div class="rd__kv"><span>原片位置</span><span class="mono">{{ formatOriginal(selected.original.candidate_start) }} – {{ formatOriginal(selected.original.candidate_end) }}</span></div>
          <div class="rd__kv"><span>来源</span><span>{{ selected.source === 'manual' ? '手动' : '自动' }}</span></div>

          <ul v-if="reasonsList.length" class="rd__reasons">
            <li v-for="(r, i) in reasonsList" :key="i">· {{ r }}</li>
          </ul>

          <div v-if="selected.alternatives.length" class="rd__section">
            <div class="rd__sec-title">其它候选位置</div>
            <p class="rd__hint faint">与当前定位二选一：当前定位不对时，预览后采用正确的那段。</p>
            <div v-for="(a, i) in selected.alternatives" :key="i" class="rd__cand"
                 :class="{ 'rd__cand--previewing': results.previewSource?.kind === 'alt' && results.previewSource?.index === i }">
              <span class="mono">{{ formatOriginal(a.candidate_start) }} – {{ formatOriginal(a.candidate_end) }}</span>
              <span class="rd__cand-actions">
                <button class="rd__mini" @click="previewCandidate(a.candidate_start, a.candidate_end, { kind: 'alt', index: i })">
                  {{ results.previewSource?.kind === 'alt' && results.previewSource?.index === i ? '预览中' : '预览' }}
                </button>
                <button class="rd__mini" @click="useCandidate(a.candidate_start, a.candidate_end)">采用这段</button>
                <ConfidenceBadge :level="a.confidence" />
              </span>
            </div>
          </div>

          <div class="rd__section">
            <div class="rd__sec-title">导出</div>
            <BaseButton
              :variant="selected.excluded ? 'primary' : 'ghost'"
              @click="toggleExclude(selected.result_id, !selected.excluded)"
            >
              {{ selected.excluded ? '恢复导出此段' : '不导出此段' }}
            </BaseButton>
            <p class="rd__note" style="margin-top: 6px">
              {{ selected.excluded ? '此段已排除，不会出现在导出的工程里。' : '内容对不上时可将该段排除在导出之外。' }}
            </p>
          </div>

          <div class="rd__section">
            <div class="rd__sec-title">手动修正</div>
            <div class="rd__form">
              <BaseInput v-model="editStart" placeholder="原片起点(秒)" />
              <BaseInput v-model="editEnd" placeholder="原片终点(秒)" />
              <BaseButton variant="primary" @click="applyOverride">替换定位</BaseButton>
            </div>
            <div class="rd__form rd__points" style="margin-top: 8px">
              <button class="rd__mini" @click="setPointFromPlayhead('start')">把播放头设为起点</button>
              <button class="rd__mini" @click="setPointFromPlayhead('end')">把播放头设为终点</button>
              <span class="mono faint">{{ editStartHuman }} – {{ editEndHuman }}</span>
            </div>
            <p v-if="editError" class="rd__notice rd__notice--err">{{ editError }}</p>
            <div class="rd__form" style="margin-top: 8px">
              <BaseButton :loading="results.previewLoading" :disabled="!results.batch?.original_video"
                          @click="results.generateEditedPreview(); results.generatePreview()">
                重新生成预览
              </BaseButton>
            </div>
            <p v-if="results.previewError" class="rd__notice rd__notice--err">{{ results.previewError }}</p>
          </div>
        </template>
      </div>
    </div>

    <div v-else class="results__empty">
      <p class="faint">还没有结果。</p>
      <BaseButton variant="primary" icon="play" @click="router.push('/analysis')">开始分析</BaseButton>
    </div>

    <!-- 导出对话框（反馈 ⑨⑭） -->
    <div v-if="showExport" class="ex__mask" @click.self="showExport = false">
      <div class="ex__card">
        <div class="rd__title">导出工程</div>
        <label class="rd__field">
          <span>格式</span>
          <BaseSelect v-model="exportFormat">
            <option v-for="(label, val) in FORMAT_LABEL" :key="val" :value="val">{{ label }}</option>
          </BaseSelect>
        </label>
        <label class="rd__field">
          <span>输出目录</span>
          <BaseInput :model-value="activeExportDir || ''" placeholder="留空 = 默认导出目录（在设置里按格式修改）" readonly />
        </label>
        <label class="rd__field">
          <span>片段宽度</span>
          <BaseSelect v-model="materialWidth">
            <option value="scene">完整镜头（推荐）——每个片段扩成它所在的完整原片镜头</option>
            <option value="core">仅核心窗口——只含定位命中部分，片段更紧凑</option>
          </BaseSelect>
        </label>
        <label class="rd__field">
          <span>置信门槛</span>
          <BaseSelect v-model="minConfidence">
            <option value="LOW">全部（低置信也作为主片段导出）</option>
            <option value="MEDIUM">高 + 中</option>
            <option value="HIGH">仅高置信</option>
          </BaseSelect>
        </label>
        <label v-if="minConfidence !== 'LOW'" class="rd__field">
          <span>低置信段</span>
          <BaseSelect v-model="lowPolicy">
            <option value="exclude">不进工程（默认）</option>
            <option value="backup">进独立备用轨，供人工核对</option>
          </BaseSelect>
        </label>
        <label class="rd__field">
          <span>边界吸附</span>
          <BaseSelect v-model="snapScenes">
            <option value="on">吸附到原片镜头切点（推荐）</option>
            <option value="off">保持定位给出的边界，不吸附</option>
          </BaseSelect>
        </label>
        <p class="rd__note">
          {{ minConfidence === 'LOW'
            ? '全部片段都会导出（含低置信）——低置信段定位可靠性较低，建议在剪辑软件里逐段核对。'
            : (lowPolicy === 'backup'
              ? '高/中置信进主轨；低置信段进独立备用轨，便于人工核对后取舍。'
              : '仅导出高/中置信片段，低置信不进工程。') }}
          剪映/PR 工程按剪辑时间轴摆放定位片段，导出即最终工程，可直接在剪辑软件里继续微调。
        </p>
        <p v-if="exportWarnings.length" class="rd__notice rd__notice--warn">
          导出已完成，但有以下提醒：
          <ul style="margin: 4px 0 0; padding-left: 18px">
            <li v-for="(w, i) in exportWarnings" :key="i">{{ w }}</li>
          </ul>
        </p>
        <p v-if="exportError" class="rd__notice rd__notice--err">{{ exportError }}</p>

        <!-- 成片渲染（2026-09-29 续30）：与工程文件同源的另一条交付通道 -->
        <div class="ex__render">
          <div class="rd__sec-title">成片渲染</div>
          <p class="rd__note">
            按上面的门槛与吸附口径，把定位片段从**原片**里裁出来拼成一个可直接播放的成片
            （音轨取原片对应区间；未定位/未过门槛的段直接跳过，不填黑场）。
            工程文件仍按剪辑时间轴摆放，两者互不影响。
          </p>
          <div class="hstack" style="gap: 8px">
            <BaseButton icon="film" :loading="renderRunning"
                        :disabled="!hasResults || renderRunning" @click="doRender">
              {{ renderRunning ? '渲染中…' : '渲染成片' }}
            </BaseButton>
            <BaseButton v-if="renderRunning" variant="danger" @click="cancelRender">取消</BaseButton>
            <BaseButton v-if="renderMoviePath" @click="revealRender">打开所在目录</BaseButton>
          </div>
          <p v-if="renderRunning" class="rd__note">
            {{ renderProgress }}% · {{ renderMessage || '准备渲染…' }}
          </p>
          <p v-if="renderMoviePath" class="results__exported mono">
            成片 → {{ renderMoviePath }}<span v-if="renderSummary"> · {{ renderSummary }}</span>
          </p>
          <p v-if="renderError" class="rd__notice rd__notice--err">{{ renderError }}</p>
        </div>

        <div class="rd__form" style="justify-content: flex-end">
          <BaseButton @click="showExport = false">{{ exportWarnings.length ? '知道了' : '取消' }}</BaseButton>
          <BaseButton variant="primary" :loading="exporting" :disabled="!hasResults" @click="doExport">导出</BaseButton>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.results__exported { margin: 0 0 12px; color: var(--fg-muted); font-size: var(--fs-xs); }
.results__split { display: grid; grid-template-columns: minmax(340px, 0.9fr) 1.1fr; gap: 18px; align-items: start; }
.results__list { border: 1px solid var(--border); border-radius: var(--radius-m); background: var(--panel); overflow: hidden; }
.results__view { background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius-m); padding: 16px; min-width: 0; }
.results__empty { display: flex; flex-direction: column; align-items: center; gap: 16px; padding: 56px; }

.rd__head { display: flex; align-items: center; justify-content: space-between; margin-top: 14px; padding-bottom: 8px; border-bottom: 1px solid var(--divider); }
.rd__title { font-size: var(--fs-lg); font-weight: 600; }
.rd__kv { display: flex; justify-content: space-between; padding: 4px 0; font-size: var(--fs-sm); color: var(--fg-muted); }
.rd__kv span:last-child { color: var(--fg); }
.rd__reasons { list-style: none; margin: 8px 0; padding: 0; display: flex; flex-direction: column; gap: 6px; font-size: var(--fs-sm); color: var(--fg-muted); }
.rd__section { margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--divider); }
.rd__sec-title { font-size: var(--fs-xs); font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--fg-muted); margin-bottom: 8px; }
.rd__cand { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 6px 8px; border-radius: var(--radius-s); background: var(--panel-2); border: 1px solid var(--border); font-size: var(--fs-xs); margin-bottom: 6px; }
.rd__cand-actions { display: flex; align-items: center; gap: 6px; }
.rd__mini { border: 1px solid var(--border-strong); background: transparent; color: var(--fg); border-radius: var(--radius-s); padding: 2px 8px; cursor: pointer; font-size: var(--fs-2xs); font-family: inherit; }
.rd__mini:hover { border-color: var(--accent); color: var(--accent-glow); }
.rd__previewbar { position: sticky; top: 8px; z-index: 5; display: flex; align-items: center; gap: 12px; padding: 6px 10px; margin-bottom: 8px; border-radius: var(--radius-s); background: var(--panel-2); border: 1px solid var(--border); font-size: var(--fs-xs); color: var(--fg-muted); box-shadow: 0 2px 10px rgba(0, 0, 0, 0.35); }
.rd__hint { margin: -2px 0 8px; font-size: var(--fs-2xs); }
.rd__cand--previewing { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent-glow); }
.rd__points { font-size: var(--fs-xs); }
.rd__form { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.rd__field { display: flex; flex-direction: column; gap: 6px; font-size: var(--fs-xs); color: var(--fg-muted); margin-bottom: 12px; }
.rd__note { font-size: var(--fs-xs); color: var(--fg-faint); }
.rd__notice { border-radius: var(--radius-s); padding: 8px 10px; font-size: var(--fs-xs); margin: 8px 0; }
.rd__notice--warn { background: var(--conf-medium-bg); color: var(--warn); }
.rd__notice--err { background: var(--conf-low-bg); color: var(--conf-low); }

.ex__mask { position: fixed; inset: 0; z-index: 100; background: rgba(0, 0, 0, 0.55); display: flex; align-items: center; justify-content: center; }
.ex__card { width: 460px; padding: 22px; border-radius: var(--radius-m); background: var(--panel); border: 1px solid var(--border-strong); display: flex; flex-direction: column; }
</style>
