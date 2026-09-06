// Public surface of the Electron backend lifecycle. main.ts imports from here so
// it never reaches into individual modules. Kept electron-free (pure Node) so it
// is unit-testable and stays out of the renderer's strict typecheck.
export {
  BACKEND_HOST,
  BACKEND_PORT,
  BACKEND_HEALTH_PATH,
  HEALTH_POLL_INTERVAL_MS,
  HEALTH_TIMEOUT_MS,
  createBackendConfig,
  prodBackendConfig,
  buildUvicornArgs,
} from './config'
export type { BackendConfig } from './config'

export { BackendManager, BackendStartError, nodeSpawner } from './manager'
export type {
  BackendManagerOptions,
  BackendMode,
  BackendState,
  BackendSpawner,
} from './manager'

export { createHealthChecker } from './health'
export type { HealthChecker } from './health'

export { spawnBackendProcess, buildSpawnCommand } from './process'
export type { BackendProcessHandle, LogFn, SpawnFn } from './process'

export { buildBackendBridge, createBackendRequestHandler } from './bridge'
export type {
  BackendBridge,
  BackendIpc,
  BridgeRequestPayload,
  BridgeResponse,
} from './bridge'

