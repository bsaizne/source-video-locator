<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProjectsStore } from '@/stores/projects'
import { useSessionStore } from '@/stores/session'
import { useService } from '@/services'
import { formatBytes, formatDuration } from '@/utils/format'
import { isAbsolutePath, nameWithoutExt } from '@/utils/path'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseIcon from '@/components/ui/BaseIcon.vue'
import type { Project } from '@/stores/projects'

const route = useRoute()
const router = useRouter()
const projects = useProjectsStore()
const session = useSessionStore()

const project = computed<Project | null>(() =>
  projects.projects.find((p) => p.id === String(route.params.id)) ?? null,
)

const renaming = ref(false)
const renameDraft = ref('')

function startRename(): void {
  if (!project.value) return
  renameDraft.value = project.value.name
  renaming.value = true
}

function applyRename(): void {
  if (project.value && renameDraft.value.trim()) {
    projects.renameProject(project.value.id, renameDraft.value)
  }
  renaming.value = false
}

const confirmingDelete = ref(false)
function removeProject(): void {
  if (!project.value) return
  projects.removeProject(project.value.id)
  void router.push('/projects')
}

function runAnalysis(): void {
  projects.selectProject(project.value?.id ?? null)
  router.push('/analysis')
}

function isAbsPath(p: string): boolean {
  return isAbsolutePath(p)
}

// 原片库（多原片入库，2026-09-29 续27 video.concat 的 UI 入口）
const lib = computed<string[]>(() => project.value?.sourceVideos ?? [])
const absLib = computed<string[]>(() => projects.absoluteSources(project.value))
// 头部副标题：单段显示路径；多段显示合并产物或「N 段待合并」。
const sourceLine = computed(() => {
  const proj = project.value
  if (!proj) return ''
  if (absLib.value.length >= 2) return proj.merge ? proj.merge.mergedPath : `${absLib.value.length} 段原片`
  return proj.sourceVideo
})
const isBareSource = computed(
  () => !!(project.value?.sourceVideo && !isAbsPath(project.value.sourceVideo)),
)

function followName(p: string): void {
  const proj = project.value
  if (proj && (!proj.name || proj.name.startsWith('未命名项目'))) proj.name = nameWithoutExt(p)
}

/** 单段「选择源片文件」= 替换整个原片库（旧版行为逐字保持）。 */
function setSingleSource(p: string): void {
  const proj = project.value
  if (!proj || !p) return
  projects.setSourceVideos(proj.id, [p])
  followName(p)
  void projects.refreshSourceMeta(proj.id)
}

/** 追加原片（多选/拖拽/手动粘贴走这里）：顺序即合并时间轴顺序。 */
function addSources(paths: string[]): void {
  const proj = project.value
  const clean = paths.filter(Boolean)
  if (!proj || !clean.length) return
  projects.addSourceVideos(proj.id, clean)
  followName(clean[0])
  void projects.refreshSourceMeta(proj.id)
}

async function chooseSource(): Promise<void> {
  const p = await window.desktop?.openFile?.() ?? null
  if (p) setSingleSource(p)
}

async function chooseSources(): Promise<void> {
  const ps = (await window.desktop?.openFiles?.()) ?? []
  addSources(ps)
}

// --- 立即合并（POST /api/source/merge）：产物当普通单原片用，下游索引/导出零改动 ---
const merging = ref(false)
const mergeError = ref('')

async function mergeNow(): Promise<void> {
  const proj = project.value
  if (!proj || absLib.value.length < 2 || merging.value) return
  merging.value = true
  mergeError.value = ''
  try {
    const res = await useService().mergeSources(absLib.value)
    projects.applyMerge(proj.id, res)
    await projects.refreshSourceMeta(proj.id)
  } catch (e) {
    // 后端 public_error 已是「对外话术（LOC 码）」，直接展示，不再吐技术栈。
    mergeError.value = e instanceof Error ? e.message : String(e)
  } finally {
    merging.value = false
  }
}

function dropMerge(): void {
  const proj = project.value
  if (!proj) return
  projects.clearMerge(proj.id)
  void projects.refreshSourceMeta(proj.id)
}

function removeSource(path: string): void {
  const proj = project.value
  if (!proj) return
  projects.removeSourceVideo(proj.id, path)
  void projects.refreshSourceMeta(proj.id)
}

const MODE_LABEL: Record<string, string> = {
  copy: '流复制（不重编码）',
  transcode: '重编码合并',
  passthrough: '单段直通',
}
function modeLabel(mode: string): string {
  return MODE_LABEL[mode] ?? mode
}

// 打开旧项目时自愈：源片是绝对路径但时长还没探到（假数据时代/元数据接口上线前建的项目）→ 补一次探测。
onMounted(() => {
  const proj = project.value
  if (proj && !proj.sourceDuration && (isAbsolutePath(proj.sourceVideo) || absLib.value.length)) {
    void projects.refreshSourceMeta(proj.id)
  }
})

async function chooseEdited(): Promise<void> {
  const p = await window.desktop?.openFile?.() ?? null
  if (p && project.value) project.value.editedVideos = [...project.value.editedVideos, p]
}

// --- 拖拽导入视频（Electron 经 webUtils 取文件路径；纯浏览器环境降级为空实现）---
function filePath(f: File): string | null {
  try { return window.desktop?.getPathForFile(f) ?? null } catch { return null }
}
function onDragOver(ev: DragEvent): void { ev.preventDefault() }
function onDropEdited(ev: DragEvent): void {
  if (!project.value) return
  const paths = [...(ev.dataTransfer?.files ?? [])].map(filePath).filter((p): p is string => !!p)
  if (!paths.length) return
  project.value.editedVideos = [...project.value.editedVideos, ...paths]
}
// 源片区支持一次拖入多段（拖入即追加，顺序按 dataTransfer.files）
function onDropSource(ev: DragEvent): void {
  const paths = [...(ev.dataTransfer?.files ?? [])].map(filePath).filter((p): p is string => !!p)
  addSources(paths)
}

// --- 纯浏览器环境降级：无 Electron 桥时拖拽/文件选择都拿不到绝对路径，
// 提供手动粘贴路径入口（仅 dev/浏览器模式显示，桌面 exe 走原生对话框）---
const hasDesktop = !!window.desktop?.openFile
// 多选桥（旧包/旧 preload 没有 openFiles 时按钮不出现，避免点了没反应）
const hasMulti = !!window.desktop?.openFiles
const manualSource = ref('')
const manualEdited = ref('')
// 粘贴来源常见带首尾引号/空格（"D:\..."），统一剥掉再入库
function cleanPath(p: string): string {
  return p.trim().replace(/^["']+|["']+$/g, '').trim()
}
function applyManualSource(): void {
  const p = cleanPath(manualSource.value)
  if (p) addSources([p])
  manualSource.value = ''
}
function applyManualEdited(): void {
  const p = cleanPath(manualEdited.value)
  if (p && project.value) project.value.editedVideos = [...project.value.editedVideos, p]
  manualEdited.value = ''
}
</script>

<template>
  <div class="page">
    <template v-if="project">
      <div class="page-header">
        <button class="pd__back" @click="router.push('/projects')">
          <BaseIcon name="chevron-right" :size="14" style="transform: rotate(180deg)" /> 项目
        </button>
        <div class="pd__titlerow">
          <h1 v-if="!renaming" class="page-title">{{ project.name }}</h1>
          <template v-else>
            <input v-model="renameDraft" class="pd__rename mono" @keyup.enter="applyRename" @keyup.esc="renaming = false" />
            <BaseButton variant="primary" @click="applyRename">确定</BaseButton>
            <BaseButton @click="renaming = false">取消</BaseButton>
          </template>
          <template v-if="!renaming">
            <button class="pd__ghost" title="重命名" @click="startRename"><BaseIcon name="edit" :size="14" /></button>
            <button class="pd__ghost pd__ghost--danger" title="删除项目" @click="confirmingDelete = true">
              <BaseIcon name="x" :size="14" />
            </button>
          </template>
        </div>
        <p class="page-subtitle">{{ sourceLine }}</p>
        <p v-if="confirmingDelete" class="pd__confirm">
          确定删除项目「{{ project.name }}」？此操作不可撤销。
          <BaseButton variant="danger" @click="removeProject">确认删除</BaseButton>
          <BaseButton @click="confirmingDelete = false">取消</BaseButton>
        </p>
      </div>

      <div class="pd__meta">
        <div class="pd__stat"><span class="pd__k">时长</span><span>{{ project.sourceDuration > 0 ? formatDuration(project.sourceDuration) : '—' }}</span></div>
        <div v-if="project.sourceWidth" class="pd__stat"><span class="pd__k">分辨率</span><span>{{ project.sourceWidth }}×{{ project.sourceHeight }}</span></div>
        <div v-if="project.sourceFps" class="pd__stat"><span class="pd__k">FPS</span><span>{{ project.sourceFps.toFixed(2) }}</span></div>
        <div v-if="project.sourceSizeBytes" class="pd__stat"><span class="pd__k">大小</span><span>{{ formatBytes(project.sourceSizeBytes) }}</span></div>
        <div class="pd__stat"><span class="pd__k">后端</span><span>{{ session.backend?.deviceType.toUpperCase() ?? '—' }}</span></div>
      </div>

      <div class="pd__actions">
        <BaseButton variant="primary" @click="runAnalysis" icon="play">开始分析</BaseButton>
        <p class="pd__note faint" style="margin: 6px 0 0">原片索引会随分析自动准备，无需单独构建。</p>
      </div>

      <div class="pd__libraries">
        <section class="pd__lib">
          <div class="section-title">
            源片库
            <span v-if="lib.length > 1" class="pd__count">{{ lib.length }} 段</span>
          </div>
          <div class="pd__drop pd__drop--source" @dragover="onDragOver" @drop.prevent="onDropSource">
            <BaseIcon name="film" :size="26" />
            <span class="faint" style="font-size: var(--fs-xs)">
              拖入一段或多段母片到此区（顺序＝合并顺序），或点下面按钮选择文件
            </span>
          </div>
          <div class="pd__pickrow">
            <BaseButton icon="film" @click="chooseSource">选择单个源片</BaseButton>
            <BaseButton v-if="hasMulti" icon="plus" @click="chooseSources">添加多个源片…</BaseButton>
          </div>

          <ol v-if="lib.length" class="pd__list">
            <li v-for="(s, i) in lib" :key="s" class="pd__asset">
              <span class="pd__idx mono">{{ i + 1 }}</span>
              <BaseIcon name="film" :size="14" />
              <span class="mono pd__asset-path" :title="s">{{ s }}</span>
              <button class="pd__rm" title="从原片库移除" @click="removeSource(s)">
                <BaseIcon name="x" :size="12" />
              </button>
            </li>
          </ol>

          <!-- 多原片合并（竞品 video.concat 同形态：入库前物理合并成单文件） -->
          <template v-if="absLib.length >= 2">
            <div v-if="project.merge" class="pd__merged">
              <span>已合并 · {{ modeLabel(project.merge.mode) }}{{ project.merge.reused ? ' · 复用缓存' : '' }}</span>
              <span class="mono pd__asset-path">{{ project.merge.mergedPath }}</span>
            </div>
            <p v-else class="pd__note">
              {{ absLib.length }} 段原片未合并：开始分析时后端会先合并成单个母片。
              现在合并可提前拿到产物并复用同一份索引。
            </p>
            <div class="pd__pickrow">
              <BaseButton variant="primary" :loading="merging" :disabled="merging" @click="mergeNow">
                {{ project.merge ? '重新合并' : '立即合并' }}
              </BaseButton>
              <BaseButton v-if="project.merge" @click="dropMerge">取消合并结果</BaseButton>
            </div>
            <p v-if="mergeError" class="pd__note pd__note--err">{{ mergeError }}</p>
          </template>

          <div v-if="!hasDesktop" class="pd__pickrow pd__manual">
            <input v-model="manualSource" class="pd__manual-input mono"
                   placeholder="浏览器模式：粘贴一段原片绝对路径（可多次添加组成多段）"
                   @keyup.enter="applyManualSource" />
            <BaseButton variant="primary" @click="applyManualSource">添加到原片库</BaseButton>
          </div>
          <p v-if="isBareSource" class="pd__note" style="color: var(--warn)">
            源片是相对路径（只有文件名）。请点「选择单个源片」重新选真实视频，否则构建索引会失败。
          </p>
        </section>

        <section class="pd__lib">
          <div class="section-title">剪辑视频</div>
          <div class="pd__drop" @dragover="onDragOver" @drop.prevent="onDropEdited" @click="chooseEdited">
            <BaseIcon name="plus" :size="22" />
            <span>将剪辑片段拖到这里（或点击选择文件）</span>
          </div>
          <div v-if="!hasDesktop" class="pd__pickrow pd__manual">
            <input v-model="manualEdited" class="pd__manual-input mono"
                   placeholder="浏览器模式：粘贴剪辑视频绝对路径"
                   @keyup.enter="applyManualEdited" />
            <BaseButton variant="primary" @click="applyManualEdited">添加</BaseButton>
          </div>
          <div v-for="e in project.editedVideos" :key="e" class="pd__asset">
            <BaseIcon name="film" :size="14" />
            <span class="mono">{{ e }}</span>
          </div>
        </section>
      </div>
    </template>
    <div v-else class="pd__missing faint">未找到项目。</div>
  </div>
</template>

<style scoped>
.pd__back { display: inline-flex; align-items: center; gap: 4px; background: none; border: none; color: var(--fg-muted); cursor: pointer; font-family: inherit; font-size: var(--fs-xs); margin-bottom: 10px; }
.pd__back:hover { color: var(--fg); }
.pd__meta { display: flex; gap: 12px; flex-wrap: wrap; }
.pd__stat { display: flex; align-items: center; gap: 8px; padding: 8px 14px; border-radius: var(--radius-m); background: var(--panel); border: 1px solid var(--border); font-size: var(--fs-sm); }
.pd__k { color: var(--fg-faint); font-size: var(--fs-xs); }
.pd__actions { display: flex; gap: 12px; margin: 20px 0; }
.pd__note { color: var(--fg-muted); font-size: var(--fs-xs); }
.pd__libraries { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.pd__lib { background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius-m); padding: 18px; }
.pd__drop { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 28px; border: 1px dashed var(--border-strong); border-radius: var(--radius-m); color: var(--fg-muted); cursor: pointer; }
.pd__drop:hover { border-color: var(--accent); color: var(--fg); }
.pd__drop--source { cursor: default; }
.pd__pickrow { margin-top: 10px; }
.pd__manual { display: flex; gap: 8px; align-items: center; }
.pd__manual-input { flex: 1; background: var(--panel-2); border: 1px solid var(--border-strong); border-radius: var(--radius-s); color: var(--fg); font-size: var(--fs-sm); padding: 6px 10px; min-width: 0; }
.pd__asset { display: flex; align-items: center; gap: 8px; padding: 8px 0; color: var(--fg); font-size: var(--fs-sm); }
/* 多原片库 */
.pd__count { margin-left: 8px; font-size: var(--fs-xs); color: var(--accent-glow); }
.pd__list { list-style: none; margin: 10px 0 0; padding: 0; }
.pd__idx { min-width: 18px; color: var(--fg-faint); font-size: var(--fs-xs); text-align: right; }
.pd__asset-path { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pd__rm { display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; border-radius: var(--radius-s); border: 1px solid var(--border); background: transparent; color: var(--fg-muted); cursor: pointer; }
.pd__rm:hover { color: var(--err); border-color: var(--err); }
.pd__merged { display: flex; flex-direction: column; gap: 4px; margin-top: 12px; padding: 10px 12px; border-radius: var(--radius-s); background: var(--panel-2); border: 1px solid var(--border); font-size: var(--fs-xs); color: var(--fg-muted); }
.pd__note--err { color: var(--err); }
.pd__missing { padding: 40px; }
.pd__titlerow { display: flex; align-items: center; gap: 10px; }
.pd__rename { background: var(--panel-2); border: 1px solid var(--border-strong); border-radius: var(--radius-s); color: var(--fg); font-size: var(--fs-lg); padding: 4px 10px; min-width: 260px; }
.pd__ghost { display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: var(--radius-s); border: 1px solid var(--border); background: transparent; color: var(--fg-muted); cursor: pointer; }
.pd__ghost:hover { color: var(--fg); border-color: var(--border-strong); }
.pd__ghost--danger:hover { color: var(--err); border-color: var(--err); }
.pd__confirm { display: flex; align-items: center; gap: 10px; margin: 10px 0 0; padding: 10px 12px; border-radius: var(--radius-s); background: var(--conf-low-bg); color: var(--conf-low); font-size: var(--fs-sm); }
</style>
