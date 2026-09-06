import { MockServiceAdapter } from './MockServiceAdapter'
import { HttpServiceAdapter } from './HttpServiceAdapter'
import type { ServiceAPI } from './ServiceAPI'

// Pick the concrete adapter behind the ServiceAPI seam.
//   - default (no VITE_BACKEND_MODE) = Mock: the UI runs standalone.
//   - VITE_BACKEND_MODE=http   = HttpServiceAdapter at VITE_API_BASE (or 127.0.0.1:8765).
// The Mock adapter stays available so the UI can still be exercised without the
// Python backend (and unit tests use it); the switch is a config swap, not a delete.
export function resolveFor(mode: string | undefined, base?: string): ServiceAPI {
  if (mode === 'http') return new HttpServiceAdapter(base)
  return new MockServiceAdapter()
}

export function resolveService(): ServiceAPI {
  return resolveFor(
    import.meta.env.VITE_BACKEND_MODE as string | undefined,
    import.meta.env.VITE_API_BASE as string | undefined,
  )
}
