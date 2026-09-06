// BackendManager — owns the Python backend lifecycle for the Electron main process.
//
// Responsibilities: start / stop / restart + health-gate, with an explicit state
// machine. Mode-aware: in `dev` it does NOT spawn (the developer runs uvicorn
// themselves); it only health-checks. In `prod` it spawns the bundled python and
// won't report `running` until /api/health answers ok.
//
// Everything here is injected (spawner, health, logger, config) so tests drive the
// whole lifecycle with fakes and never launch Python or touch the network.
import type { BackendConfig } from './config'
import type { BackendProcessHandle, LogFn } from './process'
import { spawnBackendProcess } from './process'
import { createHealthChecker, BackendStartError, type HealthChecker } from './health'

export type BackendState = 'starting' | 'running' | 'stopped' | 'failed'
export type BackendMode = 'dev' | 'prod'

/** Given config + logger, returns a process handle. Tests inject a fake. */
export type BackendSpawner = (config: BackendConfig, onLog: LogFn) => BackendProcessHandle

export const nodeSpawner: BackendSpawner = (config, onLog) => spawnBackendProcess(config, onLog)

export interface BackendManagerOptions {
  config: BackendConfig
  mode: BackendMode
  /** Defaults to nodeSpawner (real spawn). Tests inject a fake. */
  spawner?: BackendSpawner
  /** Defaults to an http health checker against config. Tests inject a fake. */
  health?: HealthChecker
  /** Runtime logger; defaults to no-op. main wires this to console / a file. */
  log?: (msg: string) => void
  /** Dev-mode quick probe window before declaring "offline" (non-fatal). */
  devProbeMs?: number
}

export class BackendManager {
  private _state: BackendState = 'stopped'
  private _proc: BackendProcessHandle | null = null
  private readonly _config: BackendConfig
  private readonly _mode: BackendMode
  private readonly _spawner: BackendSpawner
  private readonly _health: HealthChecker
  private readonly _log: (msg: string) => void
  private readonly _devProbeMs: number

  constructor(opts: BackendManagerOptions) {
    this._config = opts.config
    this._mode = opts.mode
    this._spawner = opts.spawner ?? nodeSpawner
    this._health = opts.health ?? createHealthChecker(this._config)
    this._log = opts.log ?? (() => {})
    this._devProbeMs = opts.devProbeMs ?? 2000
  }

  get state(): BackendState {
    return this._state
  }

  get mode(): BackendMode {
    return this._mode
  }

  get pid(): number | undefined {
    return this._proc?.pid
  }

  /**
   * Start the backend. Dev mode: no spawn, just leaves state `starting` (the
   * caller gates on health). Prod mode: spawn the bundled python.
   * Does NOT wait for health — call waitForHealth() afterwards.
   */
  async startBackend(): Promise<void> {
    if (this._state === 'running' || this._state === 'starting') {
      this._log('backend already started')
      return
    }
    this._state = 'starting'
    this._log('backend starting')
    if (this._mode === 'dev') {
      this._log('dev mode: using existing backend (not spawning)')
      return
    }
    try {
      this._proc = this._spawner(this._config, (line) => this._log(`backend: ${line}`))
      this._log(`backend pid=${this._proc.pid ?? '?'}`)
    } catch (err) {
      this._state = 'failed'
      this._log(`backend failed to spawn: ${String(err)}`)
      throw err
    }
  }

  /** Poll /api/health until ok (or the config timeout → BackendStartError). */
  async waitForHealth(timeoutMs?: number): Promise<void> {
    try {
      await this._health.waitHealthy({ timeoutMs })
      this._state = 'running'
      this._log('health connected: backend running')
    } catch (err) {
      this._state = 'failed'
      this._log(`health check failed: ${String(err)}`)
      throw err
    }
  }

  /** Dev-mode quick probe. Returns whether the already-running backend is up.
   *  Non-fatal: on timeout it marks `stopped` (not `failed`) and returns false. */
  async checkDevBackend(): Promise<boolean> {
    try {
      await this._health.waitHealthy({ timeoutMs: this._devProbeMs })
      this._state = 'running'
      this._log('dev backend connected')
      return true
    } catch {
      this._state = 'stopped'
      this._log('dev backend offline')
      return false
    }
  }

  /** Stop the child process (if any) and return to `stopped`. */
  async stopBackend(): Promise<void> {
    this._log('backend stopping')
    if (this._proc) {
      const proc = this._proc
      this._proc = null
      proc.stop()
    }
    this._state = 'stopped'
    this._log('backend stopped')
  }

  async restartBackend(): Promise<void> {
    await this.stopBackend()
    await this.startBackend()
    await this.waitForHealth()
  }
}

export { BackendStartError }
