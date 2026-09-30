// BackendManager — owns the Python backend lifecycle for the Electron main process.
//
// Responsibilities: start / stop / restart + health-gate, with an explicit state
// machine. Mode-aware: in `dev` it does NOT spawn (the developer runs uvicorn
// themselves); it only health-checks. In `prod` it spawns the bundled python and
// won't report `running` until /api/health answers ok.
//
// Random port (续20): spawn config with `port === 0` means the backend picks an
// OS-assigned port and announces it on stdout as `BACKEND_LISTEN <host> <port>`
// (printed by mvp/api/launcher AFTER a successful bind — never a guess). The
// manager parses each forwarded line, gates waitForHealth on that announcement,
// and health-checks the REAL address via configWithListen.
//
// Everything here is injected (spawner, health, logger, config) so tests drive the
// whole lifecycle with fakes and never launch Python or touch the network.
import { configWithListen, type BackendConfig } from './config'
import type { BackendProcessHandle, LogFn } from './process'
import { spawnBackendProcess } from './process'
import { createHealthChecker, BackendStartError, type HealthChecker } from './health'

export type BackendState = 'starting' | 'running' | 'stopped' | 'failed'
export type BackendMode = 'dev' | 'prod'

/** Parsed `BACKEND_LISTEN <host> <port>` stdout announcement. */
export interface BackendListen {
  host: string
  port: number
}

const LISTEN_RE = /^BACKEND_LISTEN\s+(\S+)\s+(\d+)\s*$/

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
  private readonly _healthOverride: HealthChecker | null
  private readonly _log: (msg: string) => void
  private readonly _devProbeMs: number

  /** 最近一次 BACKEND_LISTEN 公告（随机端口模式下的唯一真实端口来源）。 */
  private _listen: BackendListen | null = null
  /** 本次 spawn 的公告等待器；resolve 于收到 BACKEND_LISTEN，reject 于进程提前退出。 */
  private _announce: {
    promise: Promise<BackendListen>
    resolve: (l: BackendListen) => void
    reject: (err: Error) => void
  } | null = null

  constructor(opts: BackendManagerOptions) {
    this._config = opts.config
    this._mode = opts.mode
    this._spawner = opts.spawner ?? nodeSpawner
    this._healthOverride = opts.health ?? null
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

  /** 公告过的真实监听地址；未收到公告 = null。 */
  get listen(): BackendListen | null {
    return this._listen
  }

  get listenPort(): number | null {
    return this._listen?.port ?? null
  }

  /** 健康检查用的有效配置：收到公告后切到真实 host/port（否则维持 spawn 配置）。 */
  private _resolvedConfig(): BackendConfig {
    return this._listen ? configWithListen(this._config, this._listen) : this._config
  }

  private _healthFor(): HealthChecker {
    return this._healthOverride ?? createHealthChecker(this._resolvedConfig())
  }

  /** stdout/stderr 行分发：识别 BACKEND_LISTEN 公告（其余行只进日志）。 */
  private _handleOutputLine(line: string): void {
    const m = LISTEN_RE.exec(line)
    if (!m) return
    const port = Number(m[2])
    if (!Number.isInteger(port) || port <= 0) return
    this._listen = { host: m[1], port }
    this._log(`backend announced listen ${m[1]}:${port}`)
    this._announce?.resolve(this._listen)
  }

  private _beginAnnounce(): void {
    this._listen = null
    let resolve!: (l: BackendListen) => void
    let reject!: (err: Error) => void
    const promise = new Promise<BackendListen>((res, rej) => {
      resolve = res
      reject = rej
    })
    // 无人等待时（如公告后来但 waitForHealth 已失败）不产生 unhandled rejection。
    promise.catch(() => {})
    this._announce = { promise, resolve, reject }
  }

  private async _awaitAnnounce(timeoutMs?: number): Promise<void> {
    if (!this._announce) {
      throw new BackendStartError('backend not started; cannot await BACKEND_LISTEN')
    }
    const ms = timeoutMs ?? this._config.timeoutMs
    let timer: ReturnType<typeof setTimeout> | undefined
    try {
      await Promise.race([
        this._announce.promise,
        new Promise<never>((_, rej) => {
          timer = setTimeout(
            () => rej(new BackendStartError(`no BACKEND_LISTEN announcement within ${ms}ms`)),
            ms,
          )
        }),
      ])
    } finally {
      if (timer !== undefined) clearTimeout(timer)
    }
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
      this._beginAnnounce()
      this._proc = this._spawner(this._config, (line: string) => {
        this._handleOutputLine(line)
        this._log(`backend: ${line}`)
      })
      this._log(`backend pid=${this._proc.pid ?? '?'}`)
      const proc = this._proc
      void proc.exited.then(() =>
        this._announce?.reject(
          new BackendStartError('backend exited before announcing BACKEND_LISTEN'),
        ),
      )
    } catch (err) {
      this._state = 'failed'
      this._log(`backend failed to spawn: ${String(err)}`)
      throw err
    }
  }

  /** Poll /api/health until ok (or the config timeout → BackendStartError).
   *  随机端口（config.port===0）时先等 BACKEND_LISTEN 公告，再打真实地址。 */
  async waitForHealth(timeoutMs?: number): Promise<void> {
    try {
      if (this._config.port === 0 && !this._listen) await this._awaitAnnounce(timeoutMs)
      await this._healthFor().waitHealthy({ timeoutMs })
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
      await this._healthFor().waitHealthy({ timeoutMs: this._devProbeMs })
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
