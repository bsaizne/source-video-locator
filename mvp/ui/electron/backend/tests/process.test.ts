// Spawn wrapper tests (vitest, node env). A fake ChildProcess is injected; the real
// `spawn` is never called and no Python is launched.
import { describe, it, expect, vi } from 'vitest'
import { EventEmitter } from 'node:events'
import type { ChildProcess, SpawnOptions } from 'node:child_process'
import { buildSpawnCommand, spawnBackendProcess } from '../process'
import { createBackendConfig } from '../config'

function fakeChild(): ChildProcess & EventEmitter {
  const child = new EventEmitter() as ChildProcess & EventEmitter
  Object.assign(child, { pid: 4242, killed: false })
  child.stdout = new EventEmitter() as unknown as NonNullable<ChildProcess['stdout']>
  child.stderr = new EventEmitter() as unknown as NonNullable<ChildProcess['stderr']>
  child.kill = () => {
    ;(child as { killed: boolean }).killed = true
    child.emit('exit', 0, 'SIGTERM')
    return true
  }
  return child
}

describe('buildSpawnCommand', () => {
  it('returns python + uvicorn args + cwd', () => {
    const cfg = createBackendConfig({ pythonExecutable: 'C:/app/resources/backend/python.exe', backendCwd: 'C:/app/resources/backend' })
    const cmd = buildSpawnCommand(cfg)
    expect(cmd.command).toBe('C:/app/resources/backend/python.exe')
    expect(cmd.args).toContain('uvicorn')
    expect(cmd.args).toContain('mvp.api.main:app')
    expect(cmd.cwd).toBe('C:/app/resources/backend')
  })
})

describe('spawnBackendProcess', () => {
  it('spawns with piped stdio and the right command/args/cwd', () => {
    const cfg = createBackendConfig({ pythonExecutable: 'py.exe', backendCwd: 'cwd' })
    const child = fakeChild()
    const spawnFn = vi.fn().mockReturnValue(child)
    spawnBackendProcess(cfg, () => {}, spawnFn)
    const [command, args, opts] = spawnFn.mock.calls[0] as [string, string[], SpawnOptions]
    expect(command).toBe('py.exe')
    expect(args).toEqual(cfg.uvicornArgs)
    expect(opts.cwd).toBe('cwd')
    expect(opts.stdio).toEqual(['ignore', 'pipe', 'pipe'])
  })

  it('forwards stdout/stderr lines to the logger (stripping trailing whitespace)', () => {
    const cfg = createBackendConfig({ pythonExecutable: 'py.exe', backendCwd: 'cwd' })
    const child = fakeChild()
    const log = vi.fn()
    spawnBackendProcess(cfg, log, vi.fn().mockReturnValue(child))
    ;(child.stdout as unknown as EventEmitter).emit('data', Buffer.from('running on 8765\n'))
    ;(child.stderr as unknown as EventEmitter).emit('data', Buffer.from('INFO started\r\n'))
    expect(log).toHaveBeenCalledWith('running on 8765')
    expect(log).toHaveBeenCalledWith('INFO started')
  })

  it('exposes pid and stop() kills the child', () => {
    const cfg = createBackendConfig({ pythonExecutable: 'py.exe', backendCwd: 'cwd' })
    const child = fakeChild()
    const handle = spawnBackendProcess(cfg, () => {}, vi.fn().mockReturnValue(child))
    expect(handle.pid).toBe(4242)
    handle.stop()
    expect((child as unknown as { killed: boolean }).killed).toBe(true)
  })

  it('resolves exited once the process exits', async () => {
    const cfg = createBackendConfig({ pythonExecutable: 'py.exe', backendCwd: 'cwd' })
    const child = fakeChild()
    const handle = spawnBackendProcess(cfg, () => {}, vi.fn().mockReturnValue(child))
    let exited = false
    void handle.exited.then(() => {
      exited = true
    })
    child.emit('exit', 1, null)
    await handle.exited
    expect(exited).toBe(true)
  })
})
