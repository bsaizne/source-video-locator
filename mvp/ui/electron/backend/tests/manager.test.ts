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
