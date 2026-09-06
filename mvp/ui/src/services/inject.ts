import { resolveService } from './resolveService'
import type { ServiceAPI } from './ServiceAPI'

// The app has exactly one backend connection. Lazily created so the import
// graph stays straightforward for both components and Pinia stores.
let singleton: ServiceAPI | null = null

export function useService(): ServiceAPI {
  singleton ??= resolveService()
  return singleton
}
