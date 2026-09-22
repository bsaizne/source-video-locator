import { MockServiceAdapter } from './MockServiceAdapter'
import { HttpServiceAdapter } from './HttpServiceAdapter'
import type { ServiceAPI } from './ServiceAPI'

// Pick the concrete adapter behind the ServiceAPI seam.
//   - VITE_BACKEND_MODE=http          = HttpServiceAdapter at VITE_API_BASE (or 127.0.0.1:8765).
//   - no VITE_BACKEND_MODE + PROD     = HttpServiceAdapter (packaged app always talks to the real backend).
//   - no VITE_BACKEND_MODE + dev/test = Mock: the UI runs standalone.
// The Mock adapter stays available so the UI can still be exercised without the
// Python backend (and unit tests use it); the switch is a config swap, not a delete.
export function resolveFor(mode: string | undefined, base?: string): ServiceAPI {
  if (mode === 'http') return new HttpServiceAdapter(base)
  return new MockServiceAdapter()
}

export function resolveService(): ServiceAPI {
  // 显式 VITE_BACKEND_MODE 优先; 未设置时 **打包发布(production build)默认连真实后端**。
  // 不能依赖 .env.production 是否存在 —— 它曾被 .gitignore 的 `.env.*` 排除, CI 构建时
  // 并不存在, 导致 macOS 整包静默跑在 MockServiceAdapter 上(恒报"已连接" + 假日志)。
  const explicit = import.meta.env.VITE_BACKEND_MODE as string | undefined
  const mode = explicit ?? (import.meta.env.PROD ? 'http' : undefined)
  return resolveFor(mode, import.meta.env.VITE_API_BASE as string | undefined)
}
