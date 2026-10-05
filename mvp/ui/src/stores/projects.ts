import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { useService } from '@/services'
import type { SourceMergeJson } from '@/services'
import { isAbsolutePath } from '@/utils/path'

// UI-level project (not part of the backend domain model — it's the local
// workbench notion of a project tying a source video to its edited clips).
// 持久化到 localStorage（用户反馈 ③⑤：新建项目不能丢、要能删能改名）。

/** 一次「多原片合并」的留痕（POST /api/source/merge 的响应 + UI 侧记录）。 */
export interface SourceMergeInfo {
  mergedPath: string
  mode: string
  reused: boolean
  durationS: number | null
  /** 参与合并的原片（有序）。库内容/顺序变化即视为过期（见 syncEffectiveSource）。 */
  sources: string[]
  at: string
}

export interface Project {
  id: string
  name: string
  /** 本次分析实际使用的单个原片路径；多段未合并时为空串（由后端 worker 合并）。 */
  sourceVideo: string
  /** 原片库（多原片入库，2026-09-29 续27 video.concat 的 UI 侧）：有序 = 合并时间轴顺序。 */
  sourceVideos: string[]
  /** 手动「立即合并」的产物留痕；null = 未合并（分析时自动合并）。 */
  merge: SourceMergeInfo | null
  // 以下为 GET /api/media/info 回填的真实元数据；0/缺省 = 尚未探到（旧项目/未选文件）。
  sourceDuration: number
  sourceFps?: number
  sourceWidth?: number
  sourceHeight?: number
  sourceSizeBytes?: number
  editedVideos: string[]
  lastAnalysis: string | null
  status: 'ready' | 'indexing' | 'analyzing' | 'empty'
}

const STORAGE_KEY = 'vl.projects.v1'

const nid = () => `prj-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`

/** 去重且保序（合并顺序有意义，不能排序）。 */
function dedupe(paths: string[]): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const raw of paths) {
    const p = raw.trim()
    if (!p || seen.has(p)) continue
    seen.add(p)
    out.push(p)
  }
  return out
}

/** 旧版 localStorage 项目（无 sourceVideos/merge 字段）的补齐——一条历史项目都不丢。 */
function normalize(p: Project): Project {
  const q: Project = { ...p, merge: p.merge ?? null }
  if (!Array.isArray(q.sourceVideos)) {
    q.sourceVideos = q.sourceVideo ? [q.sourceVideo] : []
  } else {
    q.sourceVideos = dedupe(q.sourceVideos)
  }
  // 合并留痕与原片库不一致（库被改过）→ 产物过期，清空并回到「未合并」态。
  if (q.merge && !sameList(q.merge.sources, q.sourceVideos)) {
    q.merge = null
    q.sourceVideo = ''
  }
  return q
}

function sameList(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((v, i) => v === b[i])
}

function load(): Project[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as Project[]
    return Array.isArray(parsed) ? parsed.map(normalize) : []
  } catch {
    return []
  }
}

function persist(projects: Project[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(projects))
  } catch {
    // 存储满/禁用 → 退化为会话内状态,不阻塞
  }
}

/** 库变化后重算「生效原片」，并让过期的合并产物失效。
 *  - 1 段（绝对路径）：sourceVideo = 该段（单原片口径，行为与旧版逐字一致）
 *  - ≥2 段且未合并：sourceVideo = ''（分析时后端 worker 先合并；不再拿第一段假装全片）
 *  - ≥2 段且合并产物仍对得上库：sourceVideo = 合并文件（下游索引/导出零改动）
 *  - 库为空：sourceVideo = ''（删掉最后一段后不该继续用旧路径）
 *  - 库里只剩裸文件名：不动（历史假数据项目仍能显示/警告，由 isBareSource 提示重选） */
function syncEffectiveSource(p: Project): void {
  if (p.merge && sameList(p.merge.sources, p.sourceVideos)) {
    p.sourceVideo = p.merge.mergedPath
    return
  }
  if (p.merge) p.merge = null
  if (p.sourceVideos.length === 0) {
    // 库清空 = 没有生效原片（否则删掉最后一段后「开始分析」还会用旧路径）
    p.sourceVideo = ''
    return
  }
  const abs = p.sourceVideos.filter(isAbsolutePath)
  if (abs.length === 1) p.sourceVideo = abs[0]
  else if (abs.length >= 2) p.sourceVideo = ''
}

export const useProjectsStore = defineStore('projects', () => {
  const projects = ref<Project[]>(load())
  const activeProjectId = ref<string | null>(null)

  watch(projects, (ps) => persist(ps), { deep: true })

  const activeProject = computed(() =>
    projects.value.find((p) => p.id === activeProjectId.value) ?? null,
  )

  function addProject(partial: Partial<Project> & { name: string; sourceVideo: string }): Project {
    const project: Project = {
      id: nid(),
      name: partial.name,
      sourceVideo: partial.sourceVideo,
      sourceVideos: dedupe(partial.sourceVideos ?? (partial.sourceVideo ? [partial.sourceVideo] : [])),
      merge: null,
      sourceDuration: partial.sourceDuration ?? 0,
      editedVideos: partial.editedVideos ?? [],
      lastAnalysis: null,
      status: 'empty',
    }
    projects.value.unshift(project)
    activeProjectId.value = project.id
    return project
  }

  // ---------------------------------------------------------------- 原片库（多原片）
  function requireProject(id: string): Project | null {
    return projects.value.find((x) => x.id === id) ?? null
  }

  /** 追加原片（保序去重）→ 重算生效原片。返回当前库。 */
  function addSourceVideos(id: string, paths: string[]): string[] {
    const p = requireProject(id)
    if (!p) return []
    p.sourceVideos = dedupe([...p.sourceVideos, ...paths])
    syncEffectiveSource(p)
    return p.sourceVideos
  }

  /** 用这批路径**替换**整个原片库（单段「选择单个源片」= 替换语义，与旧版一致）。 */
  function setSourceVideos(id: string, paths: string[]): string[] {
    const p = requireProject(id)
    if (!p) return []
    p.sourceVideos = dedupe(paths)
    syncEffectiveSource(p)
    return p.sourceVideos
  }

  function removeSourceVideo(id: string, path: string): void {
    const p = requireProject(id)
    if (!p) return
    p.sourceVideos = p.sourceVideos.filter((x) => x !== path)
    syncEffectiveSource(p)
  }

  /** 移除一条剪辑视频（2026-10-06 用户反馈：剪辑列表此前只能加不能删）。 */
  function removeEditedVideo(id: string, path: string): void {
    const p = requireProject(id)
    if (!p) return
    p.editedVideos = p.editedVideos.filter((x) => x !== path)
  }

  /** 合并完成：记录留痕 + 生效原片改指合并产物（下游索引/定位/导出维持单原片口径）。 */
  function applyMerge(id: string, res: SourceMergeJson): void {
    const p = requireProject(id)
    if (!p || !res.merged_path) return
    p.merge = {
      mergedPath: res.merged_path,
      mode: res.mode,
      reused: res.reused,
      durationS: res.duration_s,
      sources: [...p.sourceVideos],
      at: new Date().toISOString(),
    }
    p.sourceVideo = res.merged_path
  }

  /** 丢弃合并产物，回到「多段原片，分析时自动合并」态。 */
  function clearMerge(id: string): void {
    const p = requireProject(id)
    if (!p) return
    p.merge = null
    syncEffectiveSource(p)
  }

  /** 库里的绝对路径段（裸文件名不参与合并）。 */
  function absoluteSources(p: Project | null): string[] {
    return p ? p.sourceVideos.filter(isAbsolutePath) : []
  }

  function selectProject(id: string | null): void {
    activeProjectId.value = id
  }

  function renameProject(id: string, name: string): void {
    const p = projects.value.find((x) => x.id === id)
    const trimmed = name.trim()
    if (p && trimmed) p.name = trimmed
  }

  function updateProject(id: string, patch: Partial<Omit<Project, 'id'>>): void {
    const p = projects.value.find((x) => x.id === id)
    if (p) Object.assign(p, patch)
  }

  /** 用 GET /api/media/info 的真实探测结果回填源片元数据（时长/fps/分辨率/大小）。
   *  探测目标优先级：
   *    1) 多段原片且未合并 → 逐段探测后聚合（时长/大小求和，分辨率/帧率取首段）；
   *    2) 生效原片（单段或多段已合并的产物）；
   *    3) 第一个绝对路径剪辑视频（新建项目流程——真机验收 2026-09-29: 旧实现只认
   *       sourceVideo, 剪辑主线项目时长/分辨率恒 0）。
   *  非绝对路径（旧假数据项目/未选文件）直接跳过；探测失败保持原值不阻塞 UI。 */
  async function refreshSourceMeta(id: string): Promise<void> {
    const p = requireProject(id)
    if (!p) return
    const lib = absoluteSources(p)
    if (lib.length >= 2 && !p.merge) {
      const infos = await Promise.all(
        lib.map((path) => useService().getMediaInfo(path).catch(() => null)),
      )
      const ok = infos.filter((x): x is NonNullable<typeof x> => !!x)
      if (!ok.length) return
      const first = ok[0]
      Object.assign(p, {
        sourceDuration: ok.reduce((s, x) => s + x.duration, 0),
        sourceSizeBytes: ok.reduce((s, x) => s + x.size_bytes, 0),
        sourceFps: first.fps,
        sourceWidth: first.width,
        sourceHeight: first.height,
      })
      return
    }
    const target = [p.sourceVideo, ...lib, ...p.editedVideos].find((v) => isAbsolutePath(v))
    if (!target) return
    try {
      const info = await useService().getMediaInfo(target)
      Object.assign(p, {
        sourceDuration: info.duration,
        sourceFps: info.fps,
        sourceWidth: info.width,
        sourceHeight: info.height,
        sourceSizeBytes: info.size_bytes,
      })
    } catch {
      // ffprobe 失败（文件被移动/非视频）：元数据留旧值/0，错误由使用侧（建索引）呈现。
    }
  }

  function removeProject(id: string): void {
    projects.value = projects.value.filter((x) => x.id !== id)
    if (activeProjectId.value === id) activeProjectId.value = null
  }

  return {
    projects,
    activeProjectId,
    activeProject,
    addProject,
    selectProject,
    renameProject,
    updateProject,
    refreshSourceMeta,
    removeProject,
    addSourceVideos,
    setSourceVideos,
    removeSourceVideo,
    removeEditedVideo,
    applyMerge,
    clearMerge,
    absoluteSources,
  }
})
