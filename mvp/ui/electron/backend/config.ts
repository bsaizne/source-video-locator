// Backend connection + bundled-python spawn config for the Electron main process.
//
// Single source of truth for host / port / health path / poll timing — no magic
// strings scattered across manager / health / process. Kept intentionally free of
// any `electron` import so it stays unit-testable under Vitest's node environment.
//
// Dev mode: the developer runs `uvicorn mvp.api.main:app --port 8765` themselves;
// Electron only health-checks it. Prod (packaged) mode: Electron spawns the bundled
// python from `<resources>/backend/` (see resources/backend/README.md).
import * as path from 'node:path'

export const BACKEND_HOST = '127.0.0.1'
export const BACKEND_PORT = 8765
export const BACKEND_HEALTH_PATH = '/api/health'
export const HEALTH_POLL_INTERVAL_MS = 500
// 后端 PyInstaller 冷启动慢（加载 torch/onnx），慢机器可能 >30s。放宽到 90s，
// 否则用户在「正在初始化 AI 引擎」期间过早点构建索引会连不上后端（fetch failed）。
export const HEALTH_TIMEOUT_MS = 90_000

export interface BackendConfig {
  host: string
  port: number
  healthPath: string
  /** Full URL the renderer/health-check hits, e.g. http://127.0.0.1:8765/api/health */
  healthUrl: string
  pollIntervalMs: number
  timeoutMs: number
  /** Packaged (production) python executable; empty in dev (never spawned). */
  pythonExecutable: string
  /** Working directory for the spawned python (the bundled `backend/` dir). */
  backendCwd: string
  /** argv passed to python (uvicorn module invocation). */
  uvicornArgs: string[]
  /** Extra env vars applied to the spawned backend (merged over process.env).
   *  Prod uses this to point FFmpegIO at the bundled ffmpeg/ffprobe binaries. */
  spawnEnv: Record<string, string>
}

/** Build the exact uvicorn argv. Exported for tests (spawn-args correctness). */
export function buildUvicornArgs(host: string, port: number): string[] {
  return ['-m', 'uvicorn', 'mvp.api.main:app', '--host', host, '--port', String(port)]
}

/** Base config with all defaults resolved. Overrides only the fields you pass. */
export function createBackendConfig(overrides: Partial<BackendConfig> = {}): BackendConfig {
  const host = overrides.host ?? BACKEND_HOST
  const port = overrides.port ?? BACKEND_PORT
  const healthPath = overrides.healthPath ?? BACKEND_HEALTH_PATH
  return {
    host,
    port,
    healthPath,
    healthUrl: overrides.healthUrl ?? `http://${host}:${port}${healthPath}`,
    pollIntervalMs: overrides.pollIntervalMs ?? HEALTH_POLL_INTERVAL_MS,
    timeoutMs: overrides.timeoutMs ?? HEALTH_TIMEOUT_MS,
    pythonExecutable: overrides.pythonExecutable ?? '',
    backendCwd: overrides.backendCwd ?? '',
    uvicornArgs: overrides.uvicornArgs ?? buildUvicornArgs(host, port),
    spawnEnv: overrides.spawnEnv ?? {},
  }
}

/**
 * Bundle the ffmpeg/ffprobe binaries path resolution for a packaged backend.
 * FFmpegIO reads MEDIA_FFMPEG/MEDIA_FFPROBE env vars first (see media/ffmpeg/_runner),
 * so the main process just points them at the bundled binaries — no mvp/src change.
 */
function mediaEnv(backendDir: string): Record<string, string> {
  return {
    MEDIA_FFMPEG: path.join(backendDir, 'ffmpeg.exe'),
    MEDIA_FFPROBE: path.join(backendDir, 'ffprobe.exe'),
  }
}

/** Prod (packaged) config: the bundled PyInstaller onedir under `<resources>/backend/`.
 *  The `backend.exe` launcher starts uvicorn itself, so uvicornArgs is empty and we
 *  spawn it directly (no `python -m uvicorn`). */
export function prodBackendConfig(resourcesDir: string, overrides: Partial<BackendConfig> = {}): BackendConfig {
  const backendDir = path.join(resourcesDir, 'backend')
  const pythonExecutable =
    process.platform === 'win32'
      ? path.join(backendDir, 'backend.exe')
      : path.join(backendDir, 'backend')
  return createBackendConfig({
    ...overrides,
    pythonExecutable,
    backendCwd: backendDir,
    uvicornArgs: [],          // the exe runs uvicorn itself
    spawnEnv: mediaEnv(backendDir),
  })
}
