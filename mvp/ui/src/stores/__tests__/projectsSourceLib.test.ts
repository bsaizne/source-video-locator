// 多原片入库（2026-09-29 续27 video.concat 的 UI 接线）项目侧状态机测试。
// 覆盖：旧 localStorage 项目迁移、原片库增删与顺序、合并产物生效/过期规则、
// 多段元数据聚合。服务层走默认 MockServiceAdapter（vitest 未设 VITE_BACKEND_MODE）。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useProjectsStore } from '../projects'

const EP1 = 'D:/原片/ep1.mkv'
const EP2 = 'D:/原片/ep2.mkv'
const EP3 = 'D:/原片/ep3.mkv'
const MERGED = 'D:/appdata/merged/abc123.mp4'

/** 用给定 JSON 假装 localStorage 里已有历史项目（迁移路径）。 */
function seedStorage(projects: unknown[]): void {
  const store = new Map<string, string>()
  if (projects.length) store.set('vl.projects.v1', JSON.stringify(projects))
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
  })
}

function legacyProject(extra: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: 'prj-legacy',
    name: '老项目',
    sourceVideo: EP1,
    sourceDuration: 0,
    editedVideos: [],
    lastAnalysis: null,
    status: 'ready',
    ...extra,
  }
}

describe('多原片库：旧项目迁移', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('旧版只有 sourceVideo → 原片库补成单元素，不丢项目', () => {
    seedStorage([legacyProject()])
    setActivePinia(createPinia())
    const projects = useProjectsStore()
    const p = projects.projects[0]
    expect(p.sourceVideos).toEqual([EP1])
    expect(p.merge).toBeNull()
    expect(p.sourceVideo).toBe(EP1)
  })

  it('假数据时代的裸文件名项目保持原样（不被迁移逻辑清空）', () => {
    seedStorage([legacyProject({ sourceVideo: 'movie.mkv' })])
    setActivePinia(createPinia())
    const projects = useProjectsStore()
    const p = projects.projects[0]
    expect(p.sourceVideo).toBe('movie.mkv')
    expect(p.sourceVideos).toEqual(['movie.mkv'])
  })

  it('库里只剩裸文件名时不覆盖已生效路径（syncEffectiveSource 只认绝对路径）', () => {
    seedStorage([legacyProject({ sourceVideo: 'movie.mkv' })])
    setActivePinia(createPinia())
    const projects = useProjectsStore()
    const p = projects.projects[0]
    projects.addSourceVideos(p.id, [EP2])
    expect(projects.absoluteSources(p)).toEqual([EP2])
    expect(p.sourceVideo).toBe(EP2)
  })

  it('合并留痕与原片库不一致（历史脏数据）→ 判过期，回到未合并态', () => {
    seedStorage([
      legacyProject({
        sourceVideo: MERGED,
        sourceVideos: [EP1, EP2],
        merge: { mergedPath: MERGED, mode: 'copy', reused: false, durationS: null, sources: [EP1], at: '' },
      }),
    ])
    setActivePinia(createPinia())
    const projects = useProjectsStore()
    const p = projects.projects[0]
    expect(p.merge).toBeNull()
    expect(p.sourceVideo).toBe('')
  })
})

describe('多原片库：生效原片与合并产物', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', { getItem: () => null, setItem: () => {}, removeItem: () => {} })
    setActivePinia(createPinia())
  })
  afterEach(() => vi.unstubAllGlobals())

  it('两段未合并：sourceVideo 置空（不再拿第一段假装全片），交给后端 worker 合并', () => {
    const projects = useProjectsStore()
    const p = projects.addProject({ name: 'X', sourceVideo: '' })
    projects.addSourceVideos(p.id, [EP1, EP2])
    expect(p.sourceVideos).toEqual([EP1, EP2])
    expect(p.sourceVideo).toBe('')
  })

  it('追加保持用户选择顺序且去重（顺序＝合并时间轴顺序）', () => {
    const projects = useProjectsStore()
    const p = projects.addProject({ name: 'X', sourceVideo: '' })
    projects.addSourceVideos(p.id, [EP2, EP2, EP1])
    expect(p.sourceVideos).toEqual([EP2, EP1])
    projects.addSourceVideos(p.id, [EP3])
    expect(p.sourceVideos).toEqual([EP2, EP1, EP3])
  })

  it('回到单段：sourceVideo 立即等于该段（单原片旧行为）', () => {
    const projects = useProjectsStore()
    const p = projects.addProject({ name: 'X', sourceVideo: '' })
    projects.addSourceVideos(p.id, [EP1, EP2])
    projects.removeSourceVideo(p.id, EP2)
    expect(p.sourceVideos).toEqual([EP1])
    expect(p.sourceVideo).toBe(EP1)
  })

  it('删掉最后一段：生效原片一并清空（不能留着旧路径继续分析）', () => {
    const projects = useProjectsStore()
    const p = projects.addProject({ name: 'X', sourceVideo: '' })
    projects.addSourceVideos(p.id, [EP1])
    expect(p.sourceVideo).toBe(EP1)
    projects.removeSourceVideo(p.id, EP1)
    expect(p.sourceVideos).toEqual([])
    expect(p.sourceVideo).toBe('')
  })

  it('单段「选择源片文件」= 替换整库（旧版行为）', () => {
    const projects = useProjectsStore()
    const p = projects.addProject({ name: 'X', sourceVideo: '' })
    projects.addSourceVideos(p.id, [EP1, EP2])
    projects.setSourceVideos(p.id, [EP3])
    expect(p.sourceVideos).toEqual([EP3])
    expect(p.sourceVideo).toBe(EP3)
    expect(p.merge).toBeNull()
  })

  it('合并留痕写入后 sourceVideo 指向合并产物（下游索引/定位/导出零改动）', () => {
    const projects = useProjectsStore()
    const p = projects.addProject({ name: 'X', sourceVideo: '' })
    projects.addSourceVideos(p.id, [EP1, EP2])
    projects.applyMerge(p.id, { merged_path: MERGED, mode: 'copy', reused: false, duration_s: 152 })
    expect(p.sourceVideo).toBe(MERGED)
    expect(p.merge?.sources).toEqual([EP1, EP2])
    expect(p.merge?.mode).toBe('copy')
  })

  it('合并后改库（增/删/换顺序）→ 产物过期并回到未合并态', () => {
    const projects = useProjectsStore()
    const p = projects.addProject({ name: 'X', sourceVideo: '' })
    projects.addSourceVideos(p.id, [EP1, EP2])
    projects.applyMerge(p.id, { merged_path: MERGED, mode: 'copy', reused: true, duration_s: null })

    projects.addSourceVideos(p.id, [EP3])
    expect(p.merge).toBeNull()
    expect(p.sourceVideo).toBe('')

    // 顺序变化同样是另一条时间轴 → 旧产物不可复用
    projects.applyMerge(p.id, { merged_path: MERGED, mode: 'copy', reused: true, duration_s: null })
    expect(p.sourceVideo).toBe(MERGED)
    projects.removeSourceVideo(p.id, EP1)
    projects.addSourceVideos(p.id, [EP1])
    expect(p.sourceVideos).toEqual([EP2, EP3, EP1])
    expect(p.merge).toBeNull()
    expect(p.sourceVideo).toBe('')
  })

  it('取消合并结果：只清留痕，原片库不动', () => {
    const projects = useProjectsStore()
    const p = projects.addProject({ name: 'X', sourceVideo: '' })
    projects.addSourceVideos(p.id, [EP1, EP2])
    projects.applyMerge(p.id, { merged_path: MERGED, mode: 'transcode', reused: false, duration_s: null })
    projects.clearMerge(p.id)
    expect(p.merge).toBeNull()
    expect(p.sourceVideo).toBe('')
    expect(p.sourceVideos).toEqual([EP1, EP2])
  })
})

describe('多原片库：元数据聚合', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', { getItem: () => null, setItem: () => {}, removeItem: () => {} })
    setActivePinia(createPinia())
  })
  afterEach(() => vi.unstubAllGlobals())

  it('两段未合并：逐段探测后时长/大小求和，分辨率取首段（Mock 单段 8310s/1GB）', async () => {
    const projects = useProjectsStore()
    const p = projects.addProject({ name: 'X', sourceVideo: '' })
    projects.addSourceVideos(p.id, [EP1, EP2])
    await projects.refreshSourceMeta(p.id)
    expect(p.sourceDuration).toBe(16620)
    expect(p.sourceSizeBytes).toBe(2 * 1_073_741_824)
    expect(p.sourceWidth).toBe(1920)
  })

  it('已合并：探合并产物本身（单文件口径），不重复累加', async () => {
    const projects = useProjectsStore()
    const p = projects.addProject({ name: 'X', sourceVideo: '' })
    projects.addSourceVideos(p.id, [EP1, EP2])
    projects.applyMerge(p.id, { merged_path: MERGED, mode: 'copy', reused: false, duration_s: 16620 })
    await projects.refreshSourceMeta(p.id)
    expect(p.sourceDuration).toBe(8310)
    expect(p.sourceSizeBytes).toBe(1_073_741_824)
  })

  it('剪辑主线项目（无源片）仍探第一个绝对路径剪辑视频——续26 回归锁维持', async () => {
    const projects = useProjectsStore()
    const p = projects.addProject({ name: 'X', sourceVideo: '', editedVideos: ['D:/clips/ed1.mp4'] })
    await projects.refreshSourceMeta(p.id)
    expect(p.sourceDuration).toBe(8310)
  })
})
