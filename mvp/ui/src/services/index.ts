// Service barrel. Pages and stores use `useService()` for the single backend
// connection; concrete adapters (Mock / Http) are behind the ServiceAPI seam.
export { useService } from './inject'
export type { ServiceAPI } from './ServiceAPI'
export * from './types'
export { createCancelToken } from './cancel'
export type { CancelToken } from './cancel'
