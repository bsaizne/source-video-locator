// 项目元数据链路（GET /api/media/info 接线）单元测试。
// 覆盖：utils/path 口径、projects store 的 updateProject/refreshSourceMeta、
// useCreateProject 的"直接建空项目跳构建页"交互（2026-10-06：不再先弹对话框选片）。
// 服务层走默认 MockServiceAdapter（vitest 环境 VITE_BACKEND_MODE 未设 → mock）。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useProjectsStore } from '../projects'
import { useCreateProject } from '@/composables/useCreateProject'
import { isAbsolutePath, basename, nameWithoutExt } from '@/utils/path'

describe('utils/path', () => {
  it('isAbsolutePath: 盘符/UNC/Unix 绝对通过，裸文件名/相对拒绝', () => {
    expect(isAbsolutePath('D:\\movie.mkv')).toBe(true)
    expect(isAbsolutePath('C:/a/b.mkv')).toBe(true)
    expect(isAbsolutePath('\\\\server\\share\\a.mkv')).toBe(true)
    expect(isAbsolutePath('/mnt/a.mkv')).toBe(true)
    expect(isAbsolutePath('movie.mkv')).toBe(false)
    expect(isAbsolutePath('sub\\movie.mkv')).toBe(false)
    expect(isAbsolutePath('')).toBe(false)
  })

  it('basename / nameWithoutExt 对反斜杠与正斜杠都生效', () => {
    expect(basename('D:\\电影\\big bang.mkv')).toBe('big bang.mkv')
    expect(basename('D:/x/Interstellar (2014).mkv')).toBe('Interstellar (2014).mkv')
    expect(nameWithoutExt('D:\\x\\movie.mkv')).toBe('movie')
    expect(nameWithoutExt('noext')).toBe('noext')
    expect(basename('')).toBe('')
  })
})

describe('projects store: metadata', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('refreshSourceMeta 对绝对路径回填 Mock 元数据（8310s / 1920x804）', async () => {
    const projects = useProjectsStore()
    const p = projects.addProject({ name: 'X', sourceVideo: 'D:/movies/real.mkv' })
    expect(p.sourceDuration).toBe(0)
    await projects.refreshSourceMeta(p.id)
    expect(p.sourceDuration).toBe(8310)
    expect(p.sourceWidth).toBe(1920)
    expect(p.sourceHeight).toBe(804)
    expect(p.sourceFps).toBeCloseTo(23.976)
    expect(p.sourceSizeBytes).toBe(1_073_741_824)
  })

  it('refreshSourceMeta 对裸文件名（历史假数据项目）跳过，不请求后端', async () => {
    const projects = useProjectsStore()
    const p = projects.addProject({ name: 'legacy', sourceVideo: 'movie.mkv' })
    await projects.refreshSourceMeta(p.id)
    expect(p.sourceDuration).toBe(0)
    expect(p.sourceWidth).toBeUndefined()
  })

  it('updateProject 合并补丁且不动 id', () => {
    const projects = useProjectsStore()
    const p = projects.addProject({ name: 'Y', sourceVideo: '' })
    projects.updateProject(p.id, { name: '改名', status: 'ready' })
    expect(p.name).toBe('改名')
    expect(p.status).toBe('ready')
    expect(p.id).toBeTruthy()
  })
})

describe('useCreateProject', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('新建项目 = 直接创建空项目（2026-10-06：不再先弹对话框选剪辑视频，素材在构建页自选）', async () => {
    const projects = useProjectsStore()
    // 即便桌面桥在位也不得弹对话框：openFile 若被调用即失败。
    vi.stubGlobal('window', {
      desktop: { openFile: vi.fn().mockRejectedValue(new Error('不得弹对话框')) },
    })
    const { createProject } = useCreateProject()
    const p = await createProject()
    expect(p.sourceVideo).toBe('')
    expect(p.editedVideos).toEqual([])
    expect(p.name).toBe('未命名项目 1')
    expect(projects.projects).toHaveLength(1)

    const p2 = await createProject()
    expect(p2.name).toBe('未命名项目 2')
    expect(projects.projects).toHaveLength(2)
  })
})
