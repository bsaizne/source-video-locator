// Spawn wrapper around the bundled python (uvicorn) process.
//
// Pure Node: the only `node:child_process` import is the default `spawn`, which is
// swappable via the `spawnFn` parameter so tests never launch a real process.
import { spawn, type ChildProcess, type SpawnOptions } from 'node:child_process'
import type { BackendConfig } from './config'

/** Handle to a running backend process — the only surface manager/main touch. */
export interface BackendProcessHandle {
  readonly pid: number | undefined
  /** Graceful stop (SIGTERM via child.kill). Synchronous — no lingering await. */
  stop(): void
  readonly exited: Promise<void>
}

export type LogFn = (line: string) => void
export type SpawnFn = (command: string, args: string[], opts: SpawnOptions) => ChildProcess

/** The exact spawn invocation for a config. Exported for tests (args correctness).
 *  Returns the merged env: the config's spawnEnv overlays the parent environment so the
 *  child inherits PATH etc. and still gets FFmpegIO's MEDIA_FFMPEG/MEDIA_FFPROBE
 *  (prod) pointing at the bundled binaries. */
export function buildSpawnCommand(config: BackendConfig): {
  command: string
  args: string[]
  cwd: string
  env: NodeJS.ProcessEnv
} {
  return {
    command: config.pythonExecutable,
    args: config.uvicornArgs,
    cwd: config.backendCwd,
    env: { ...process.env, ...config.spawnEnv },
  }
}

/** Spawn the backend with piped stdio, forwarding every stdout/stderr line to `onLog`.
 *  Line-buffered: the `BACKEND_LISTEN <host> <port>` announcement must survive chunk
 *  boundaries, so raw chunks are split on newlines and complete lines are forwarded. */
export function spawnBackendProcess(
  config: BackendConfig,
  onLog: LogFn,
  spawnFn: SpawnFn = spawn,
): BackendProcessHandle {
  const { command, args, cwd, env } = buildSpawnCommand(config)
  const child = spawnFn(command, args, {
    cwd,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true, // suppress the console window for the console-subsystem backend
  })

  const forwardLines = (stream: NodeJS.ReadableStream | undefined): void => {
    if (!stream) return
    let buf = ''
    stream.on('data', (chunk: unknown) => {
      buf += String(chunk)
      const lines = buf.split(/\r?\n/)
      buf = lines.pop() ?? ''
      for (const line of lines) if (line) onLog(line)
    })
    stream.on('end', () => {
      if (buf) {
        onLog(buf)
        buf = ''
      }
    })
  }
  forwardLines(child.stdout ?? undefined)
  forwardLines(child.stderr ?? undefined)

  const exited = new Promise<void>((resolve) => {
    child.once('exit', () => resolve())
  })

  return {
    get pid() {
      return child.pid
    },
    stop() {
      child.kill()
    },
    exited,
  }
}
