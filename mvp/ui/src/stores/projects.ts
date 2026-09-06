import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

// UI-level project (not part of the backend domain model — it's the local
// workbench notion of a project tying a source video to its edited clips).
// 持久化到 localStorage（用户反馈 ③⑤：新建项目不能丢、要能删能改名）。
export interface Project {
  id: string
  name: string
  sourceVideo: string
  sourceDuration: number
  editedVideos: string[]
  lastAnalysis: string | null
  status: 'ready' | 'indexing' | 'analyzing' | 'empty'
}

const STORAGE_KEY = 'vl.projects.v1'

const nid = () => `prj-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`

function load(): Project[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as Project[]
    return Array.isArray(parsed) ? parsed : []
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
      sourceDuration: partial.sourceDuration ?? 0,
      editedVideos: partial.editedVideos ?? [],
      lastAnalysis: null,
      status: 'empty',
    }
    projects.value.unshift(project)
    activeProjectId.value = project.id
    return project
  }

  function selectProject(id: string | null): void {
    activeProjectId.value = id
  }

  function renameProject(id: string, name: string): void {
    const p = projects.value.find((x) => x.id === id)
    const trimmed = name.trim()
    if (p && trimmed) p.name = trimmed
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
    removeProject,
  }
})
