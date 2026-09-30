// 项目元数据链路（GET /api/media/info 接线）单元测试。
// 覆盖：utils/path 口径、projects store 的 updateProject/refreshSourceMeta、
// useCreateProject 的"先选文件后建项目"交互（含取消不建、无桥降级、元数据异步回填）。
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

  it('无桌面桥（浏览器 dev）→ 创建空源片项目，不写假文件名', async () => {
    const projects = useProjectsStore()
    const { createProjectViaPicker } = useCreateProject()
    const p = await createProjectViaPicker()
    expect(p).not.toBeNull()
    expect(p!.sourceVideo).toBe('')
    expect(p!.name).toBe('未命名项目 1')
    expect(projects.projects).toHaveLength(1)
  })

  it('桌面桥取消 → 返回 null 且不创建项目', async () => {
    const projects = useProjectsStore()
    vi.stubGlobal('window', { desktop: { openFile: vi.fn().mockResolvedValue(null) } })
    const { createProjectViaPicker } = useCreateProject()
    const p = await createProjectViaPicker()
    expect(p).toBeNull()
    expect(projects.projects).toHaveLength(0)
  })

  it('桌面桥选中文件 → 项目名=文件名去扩展名、异步回填真实时长', async () => {
    vi.stubGlobal('window', {
      desktop: { openFile: vi.fn().mockResolvedValue('D:\\movies\\大片 2014.mkv') },
    })
    const { createProjectViaPicker } = useCreateProject()
    const p = await createProjectViaPicker()
    expect(p).not.toBeNull()
    expect(p!.name).toBe('大片 2014')
    // 真机验收 2026-09-29 回归锁: 对话框选的是**剪辑视频**——必须进 editedVideos
    // （分析页下拉数据源），且不得污染 sourceVideo（旧实现写反导致下拉恒空、开始分析永禁）。
    expect(p!.editedVideos).toEqual(['D:\\movies\\大片 2014.mkv'])
    expect(p!.sourceVideo).toBe('')
    // fire-and-forget 的元数据回填：等待微任务队列冲刷完成。
    await vi.waitFor(() => expect(p!.sourceDuration).toBe(8310))
  })
})
