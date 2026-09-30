// BackendManager tests (vitest, node env). Spawner + health are faked → no Python,
// no network. Covers dev/prod distinction, state transitions, stop, restart.
import { describe, it, expect, vi } from 'vitest'
import { BackendManager, BackendStartError } from '../manager'
import type { BackendProcessHandle, LogFn } from '../process'
import type { BackendConfig } from '../config'
import { createBackendConfig } from '../config'
import type { HealthChecker } from '../health'

function healthy(): HealthChecker {
  return { check: async () => true, waitHealthy: async () => {} }
}
function down(): HealthChecker {
  return { check: async () => false, waitHealthy: async () => {
    throw new BackendStartError('timeout')
  } }
}

function recordSpawner() {
  const spawned: BackendConfig[] = []
  let stopped = false
  const spawner = (config: BackendConfig, _log: LogFn): BackendProcessHandle => {
    spawned.push(config)
    return { pid: 777, stop: () => { stopped = true }, exited: Promise.resolve() }
  }
  return { spawner, spawned, isStopped: () => stopped }
}

const cfg = createBackendConfig()

describe('BackendManager — dev mode', () => {
  it('does NOT spawn; reports running when backend reachable', async () => {
    const { spawner, spawned } = recordSpawner()
    const m = new BackendManager({ config: cfg, mode: 'dev', spawner, health: healthy() })
    await m.startBackend()
    expect(spawned.length).toBe(0) // dev never spawns
    expect(m.state).toBe('starting')
    await expect(m.checkDevBackend()).resolves.toBe(true)
    expect(m.state).toBe('running')
  })

  it('reports offline (non-fatal → stopped) when backend down', async () => {
    const { spawner } = recordSpawner()
    const m = new BackendManager({ config: cfg, mode: 'dev', spawner, health: down(), devProbeMs: 0 })
    await expect(m.checkDevBackend()).resolves.toBe(false)
    expect(m.state).toBe('stopped')
  })
})

describe('BackendManager — prod mode', () => {
  it('spawns on start, then running on health success', async () => {
    const { spawner, spawned } = recordSpawner()
    const m = new BackendManager({ config: cfg, mode: 'prod', spawner, health: healthy() })
    expect(m.state).toBe('stopped')
    await m.startBackend()
    expect(spawned.length).toBe(1)
    expect(m.state).toBe('starting')
    await m.waitForHealth()
    expect(m.state).toBe('running')
    expect(m.pid).toBe(777)
  })

  it('spawn failure → state failed and rethrows', async () => {
    const spawner = () => { throw new Error('spawn ENOENT') }
    const m = new BackendManager({ config: cfg, mode: 'prod', spawner, health: healthy() })
    await expect(m.startBackend()).rejects.toThrow('spawn ENOENT')
    expect(m.state).toBe('failed')
  })

  it('health timeout → state failed (not running)', async () => {
    const { spawner } = recordSpawner()
    const m = new BackendManager({ config: cfg, mode: 'prod', spawner, health: down() })
    await m.startBackend()
    await expect(m.waitForHealth()).rejects.toBeInstanceOf(BackendStartError)
    expect(m.state).toBe('failed')
  })

  it('is idempotent when already started', async () => {
    const { spawner, spawned } = recordSpawner()
    const m = new BackendManager({ config: cfg, mode: 'prod', spawner, health: healthy() })
    await m.startBackend()
    await m.waitForHealth()
    await m.startBackend() // already running
    expect(spawned.length).toBe(1)
  })
})

describe('BackendManager — stop / restart', () => {
  it('stopBackend kills the process and returns to stopped', async () => {
    const { spawner, isStopped } = recordSpawner()
    const m = new BackendManager({ config: cfg, mode: 'prod', spawner, health: healthy() })
    await m.startBackend()
    await m.waitForHealth()
    await m.stopBackend()
    expect(isStopped()).toBe(true)
    expect(m.state).toBe('stopped')
    expect(m.pid).toBeUndefined()
  })

  it('restartBackend stops, spawns again, then waits for health', async () => {
    const { spawner, spawned } = recordSpawner()
    const m = new BackendManager({ config: cfg, mode: 'prod', spawner, health: healthy() })
    await m.startBackend()
    await m.waitForHealth()
    await m.restartBackend()
    expect(spawned.length).toBe(2)
    expect(m.state).toBe('running')
  })

  it('stopBackend is a safe no-op when nothing was spawned (dev)', async () => {
    const { spawner } = recordSpawner()
    const m = new BackendManager({ config: cfg, mode: 'dev', spawner, health: healthy() })
    await m.stopBackend()
    expect(m.state).toBe('stopped')
  })
})

// --- BACKEND_LISTEN 随机端口公告（续20 接线）----------------------------------
function listenSpawner(ports: number[]) {
  const lines: Array<(line: string) => void> = []
  let spawns = 0
  const spawner = (_config: BackendConfig, onLog: LogFn): BackendProcessHandle => {
    const idx = spawns++
    lines.push(onLog)
    let kill!: () => void
    const exited = new Promise<void>((res) => { kill = res })
    const handle: BackendProcessHandle = {
      pid: 1000 + idx,
      stop: () => kill(),
      exited,
    }
    // 模拟后端绑定成功后的公告（含前后噪声行、跨行由 process 层保证，这里给整行）。
    queueMicrotask(() => onLog(`INFO: Uvicorn running`))
    queueMicrotask(() => onLog(`BACKEND_LISTEN 127.0.0.1 ${ports[idx] ?? ports[0]}`))
    return handle
  }
  return { spawner, spawns: () => spawns }
}

describe('BackendManager — BACKEND_LISTEN (random port)', () => {
  const zeroCfg = createBackendConfig({ port: 0, timeoutMs: 2000 })

  it('port=0: gates waitForHealth on the announcement and exposes the real port', async () => {
    const { spawner } = listenSpawner([5555])
    const m = new BackendManager({ config: zeroCfg, mode: 'prod', spawner, health: healthy() })
    await m.startBackend() // 公告经 microtask 到达；此处 listen 可能已置
    await m.waitForHealth()
    expect(m.listen).toEqual({ host: '127.0.0.1', port: 5555 })
    expect(m.listenPort).toBe(5555)
    expect(m.state).toBe('running')
  })

  it('port=0: process exiting before the announcement fails fast', async () => {
    const spawner = (_c: BackendConfig, _l: LogFn): BackendProcessHandle => ({
      pid: 5,
      stop: () => {},
      exited: Promise.resolve(), // 立刻退出 = 永远不会公告
    })
    const m = new BackendManager({ config: zeroCfg, mode: 'prod', spawner, health: healthy() })
    await m.startBackend()
    await expect(m.waitForHealth()).rejects.toBeInstanceOf(BackendStartError)
    expect(m.state).toBe('failed')
  })

  it('port=0: announcement timeout fails with a clear error (no fake port ever used)', async () => {
    const spawner = (_c: BackendConfig, _l: LogFn): BackendProcessHandle => ({
      pid: 6,
      stop: () => {},
      exited: new Promise<void>(() => {}), // 活着但不公告
    })
    const m = new BackendManager({
      config: createBackendConfig({ port: 0, timeoutMs: 60 }), mode: 'prod', spawner, health: healthy(),
    })
    await m.startBackend()
    await expect(m.waitForHealth()).rejects.toBeInstanceOf(BackendStartError)
  })

  it('restart re-announces: listen tracks the newest spawn', async () => {
    const { spawner } = listenSpawner([5555, 6666])
    const m = new BackendManager({ config: zeroCfg, mode: 'prod', spawner, health: healthy() })
    await m.startBackend()
    await m.waitForHealth()
    expect(m.listenPort).toBe(5555)
    await m.restartBackend()
    expect(m.listenPort).toBe(6666)
    expect(m.state).toBe('running')
  })

  it('fixed-port config ignores announcement gating entirely (legacy path)', async () => {
    const { spawner } = listenSpawner([5555])
    const m = new BackendManager({ config: cfg, mode: 'prod', spawner, health: healthy() })
    await m.startBackend()
    await m.waitForHealth() // 不等待公告：端口非 0 → 直接健康检查
    // 公告行仍会被解析（无害），但等待路径未被门控 —— 通过成功到达 running 证明。
    expect(m.state).toBe('running')
  })
})

describe('configWithListen', () => {
  it('derives real host/port/healthUrl from announcement', async () => {
    const { configWithListen } = await import('../config')
    const base = createBackendConfig({ port: 0 })
    const next = configWithListen(base, { host: '127.0.0.1', port: 54321 })
    expect(next.port).toBe(54321)
    expect(next.healthUrl).toBe('http://127.0.0.1:54321/api/health')
  })
})
