<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProjectsStore } from '@/stores/projects'
import { useSessionStore } from '@/stores/session'
import { formatDuration } from '@/utils/format'
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
  // Windows 盘符 (C:\) 或 UNC (\\server) 或 Unix 绝对 (/…)；裸文件名不满足。
  return /^([A-Za-z]:[\\/]|\\\\[\\/]?|\/)/.test(p)
}
const isBareSource = computed(
  () => !!(project.value?.sourceVideo && !isAbsPath(project.value.sourceVideo)),
)

async function chooseSource(): Promise<void> {
  const p = await window.desktop?.openFile?.() ?? null
  if (p && project.value) project.value.sourceVideo = p
}

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
function onDropSource(ev: DragEvent): void {
  if (!project.value) return
  const first = [...(ev.dataTransfer?.files ?? [])][0]
  const path = first ? filePath(first) : null
  if (path) project.value.sourceVideo = path
}

// --- 纯浏览器环境降级：无 Electron 桥时拖拽/文件选择都拿不到绝对路径，
// 提供手动粘贴路径入口（仅 dev/浏览器模式显示，桌面 exe 走原生对话框）---
const hasDesktop = !!window.desktop?.openFile
const manualSource = ref('')
const manualEdited = ref('')
// 粘贴来源常见带首尾引号/空格（"D:\..."），统一剥掉再入库
function cleanPath(p: string): string {
  return p.trim().replace(/^["']+|["']+$/g, '').trim()
}
function applyManualSource(): void {
  const p = cleanPath(manualSource.value)
  if (p && project.value) project.value.sourceVideo = p
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
        <p class="page-subtitle">{{ project.sourceVideo }}</p>
        <p v-if="confirmingDelete" class="pd__confirm">
          确定删除项目「{{ project.name }}」？此操作不可撤销。
          <BaseButton variant="danger" @click="removeProject">确认删除</BaseButton>
          <BaseButton @click="confirmingDelete = false">取消</BaseButton>
        </p>
      </div>

      <div class="pd__meta">
        <div class="pd__stat"><span class="pd__k">时长</span><span>{{ formatDuration(project.sourceDuration) }}</span></div>
        <div class="pd__stat"><span class="pd__k">后端</span><span>{{ session.backend?.deviceType.toUpperCase() ?? '—' }}</span></div>
      </div>

      <div class="pd__actions">
        <BaseButton variant="primary" @click="runAnalysis" icon="play">开始分析</BaseButton>
        <p class="pd__note faint" style="margin: 6px 0 0">原片索引会随分析自动准备，无需单独构建。</p>
      </div>

      <div class="pd__libraries">
        <section class="pd__lib">
          <div class="section-title">源片库</div>
          <div class="pd__drop pd__drop--source" @dragover="onDragOver" @drop.prevent="onDropSource">
            <BaseIcon name="film" :size="26" />
            <span class="mono">{{ project.sourceVideo }}</span>
            <span class="faint" style="font-size: var(--fs-xs)">拖入视频到此区，或点下面按钮选择文件</span>
          </div>
          <div class="pd__pickrow">
            <BaseButton icon="film" @click="chooseSource">选择源片文件</BaseButton>
          </div>
          <div v-if="!hasDesktop" class="pd__pickrow pd__manual">
            <input v-model="manualSource" class="pd__manual-input mono"
                   placeholder="浏览器模式：粘贴源片绝对路径，如 D:\ProjectXIXI\test3\test3-om.mp4"
                   @keyup.enter="applyManualSource" />
            <BaseButton variant="primary" @click="applyManualSource">使用路径</BaseButton>
          </div>
          <p v-if="isBareSource" class="pd__note" style="color: var(--warn)">
            源片是相对路径（只有文件名）。请点「选择源片文件」重新选真实视频，否则构建索引会失败。
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
.pd__missing { padding: 40px; }
.pd__titlerow { display: flex; align-items: center; gap: 10px; }
.pd__rename { background: var(--panel-2); border: 1px solid var(--border-strong); border-radius: var(--radius-s); color: var(--fg); font-size: var(--fs-lg); padding: 4px 10px; min-width: 260px; }
.pd__ghost { display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: var(--radius-s); border: 1px solid var(--border); background: transparent; color: var(--fg-muted); cursor: pointer; }
.pd__ghost:hover { color: var(--fg); border-color: var(--border-strong); }
.pd__ghost--danger:hover { color: var(--err); border-color: var(--err); }
.pd__confirm { display: flex; align-items: center; gap: 10px; margin: 10px 0 0; padding: 10px 12px; border-radius: var(--radius-s); background: var(--conf-low-bg); color: var(--conf-low); font-size: var(--fs-sm); }
</style>
