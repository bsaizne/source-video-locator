// Backend config tests (vitest, node env). Pure — no network, no process.
import { describe, it, expect } from 'vitest'
import * as path from 'node:path'
import {
  createBackendConfig,
  prodBackendConfig,
  buildUvicornArgs,
  BACKEND_HOST,
  BACKEND_PORT,
  BACKEND_HEALTH_PATH,
} from '../config'

describe('buildUvicornArgs', () => {
  it('produces the exact uvicorn module argv', () => {
    expect(buildUvicornArgs('127.0.0.1', 8765)).toEqual([
      '-m',
      'uvicorn',
      'mvp.api.main:app',
      '--host',
      '127.0.0.1',
      '--port',
      '8765',
    ])
  })
})

describe('createBackendConfig', () => {
  it('defaults host/port/healthPath and derives healthUrl', () => {
    const cfg = createBackendConfig()
    expect(cfg.host).toBe(BACKEND_HOST)
    expect(cfg.port).toBe(BACKEND_PORT)
    expect(cfg.healthPath).toBe(BACKEND_HEALTH_PATH)
    expect(cfg.healthUrl).toBe(`http://${BACKEND_HOST}:${BACKEND_PORT}${BACKEND_HEALTH_PATH}`)
    expect(cfg.pollIntervalMs).toBe(500)
    expect(cfg.timeoutMs).toBe(90_000)
  })

  it('builds uvicorn args from the resolved host/port', () => {
    const cfg = createBackendConfig()
    expect(cfg.uvicornArgs).toEqual(buildUvicornArgs(cfg.host, cfg.port))
  })

  it('honors explicit overrides (port, healthUrl)', () => {
    const cfg = createBackendConfig({ port: 9000, healthUrl: 'http://x/health' })
    expect(cfg.port).toBe(9000)
    expect(cfg.healthUrl).toBe('http://x/health')
    expect(cfg.uvicornArgs).toContain('9000')
  })
})

describe('prodBackendConfig', () => {
  it('points the executable at the bundled backend.exe (no -m uvicorn)', () => {
    const cfg = prodBackendConfig('C:/app/resources')
    expect(cfg.backendCwd).toBe(path.join('C:/app/resources', 'backend'))
    if (process.platform === 'win32') {
      expect(cfg.pythonExecutable).toBe(path.join('C:/app/resources', 'backend', 'backend.exe'))
    } else {
      expect(cfg.pythonExecutable).toBe(path.join('C:/app/resources', 'backend', 'backend'))
    }
    expect(cfg.pythonExecutable).not.toBe('')
    // The PyInstaller exe launches uvicorn itself, so no module argv.
    expect(cfg.uvicornArgs).toEqual([])
    // FFmpegIO is pointed at the bundled binaries via MEDIA env vars (no mvp/src change).
    expect(cfg.spawnEnv.MEDIA_FFMPEG).toBe(path.join('C:/app/resources', 'backend', 'ffmpeg.exe'))
    expect(cfg.spawnEnv.MEDIA_FFPROBE).toBe(path.join('C:/app/resources', 'backend', 'ffprobe.exe'))
  })
})
