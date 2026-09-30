import { MockServiceAdapter } from './MockServiceAdapter'
import { resolveService } from './resolveService'
import type { ServiceAPI } from './ServiceAPI'

// The app has exactly one backend connection. Lazily created so the import
// graph stays straightforward for both components and Pinia stores.
let singleton: ServiceAPI | null = null

export function useService(): ServiceAPI {
  singleton ??= resolveService()
  return singleton
}

/** 测试接缝：注入替身 service（传 null 恢复惰性解析）。生产代码不调用。 */
export function setServiceForTest(svc: ServiceAPI | null): void {
  singleton = svc
}

/** 当前是否跑在 Mock 假数据上（开发模式未设 VITE_BACKEND_MODE 时即为真）。
 *  macOS 整包曾因 CI 缺 .env.production 而**静默跑在 Mock 上**、界面恒显"已连接"
 *  且分析永不结束（2026-09-22 `83c73e1`），故 UI 必须把这个状态显式亮出来。 */
export function serviceIsMock(): boolean {
  return useService() instanceof MockServiceAdapter
}
