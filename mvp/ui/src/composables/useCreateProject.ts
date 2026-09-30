// 新建项目的统一入口（HomePage / ProjectsPage 共用）。
// 旧版在这里写死 'movie.mkv' 假数据（2026-09-28 续19 遗留 P0）——现改为：
//   Electron 桌面态：原生文件对话框选真实视频 → 取消则不创建任何项目；
//   浏览器/Mock 开发态（无 window.desktop 桥）：创建空源片项目，
//   详情页仍可用「选择单个源片 / 添加多个源片 / 粘贴路径」补。
import { useProjectsStore, type Project } from '@/stores/projects'
import { nameWithoutExt } from '@/utils/path'

export function useCreateProject() {
  const projects = useProjectsStore()

  /** 返回新建的项目；用户在对话框取消 → null（不创建）。 */
  async function createProjectViaPicker(): Promise<Project | null> {
    if (typeof window === 'undefined' || !window.desktop?.openFile) {
      return projects.addProject({
        name: `未命名项目 ${projects.projects.length + 1}`,
        sourceVideo: '',
      })
    }
    const path = await window.desktop.openFile()
    if (!path) return null
    // 对话框选的是**剪辑视频**（项目以剪辑为主线, 源片由详情页「源片库」补）——
    // 真机验收 2026-09-29 抓到的断链: 旧实现把它写进 sourceVideo 且不填 editedVideos,
    // 导致分析页「剪辑视频」下拉恒空、开始分析永禁。
    const p = projects.addProject({
      name: nameWithoutExt(path),
      sourceVideo: '',
      editedVideos: [path],
    })
    void projects.refreshSourceMeta(p.id) // 异步回填真实时长/分辨率，不阻塞跳转
    return p
  }

  return { createProjectViaPicker }
}
