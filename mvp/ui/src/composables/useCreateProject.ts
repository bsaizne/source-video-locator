// 新建项目的统一入口（HomePage / ProjectsPage 共用）。
// 2026-10-06 用户反馈：新建项目不该先弹对话框选剪辑视频——应直接创建项目并跳到
// 项目构建页（ProjectDetailPage），源片/剪辑视频都在那里自己选（桌面态有原生对话框
// 入口「选择单个源片 / 拖拽 / 浏览选择剪辑片」，浏览器态有粘贴路径，无功能损失）。
// 旧「先选剪辑视频再跳转」流程已删（真机 2026-09-29 的 editedVideos 断链修复随之失效，
// 该断链的前提——新建时选片——已不存在）。
import { useProjectsStore, type Project } from '@/stores/projects'

export function useCreateProject() {
  const projects = useProjectsStore()

  /** 创建空项目并立即返回（调用方负责跳转构建页）；不会失败。 */
  async function createProject(): Promise<Project> {
    return projects.addProject({
      name: `未命名项目 ${projects.projects.length + 1}`,
      sourceVideo: '',
    })
  }

  return { createProject }
}
