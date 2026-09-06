// Time display helpers for the UI. Seconds are floats (backend uses absolute
// seconds). Edited spans are typically short (MM:SS.tenths); original spans
// can be hours (H:MM:SS). Shown as clock values, never as probability.

function pad(n: number, width = 2): string {
  return String(Math.floor(n)).padStart(width, '0')
}

/** e.g. 15.24 -> "00:15.2" ; 8310 -> "02:18:30.0" */
export function formatClock(seconds: number, withTenths = true): string {
  const safe = Number.isFinite(seconds) ? Math.max(0, seconds) : 0
  const totalTenths = Math.round(safe * 10)
  const tenths = totalTenths % 10
  const totalSec = Math.floor(totalTenths / 10)
  const s = totalSec % 60
  const m = Math.floor(totalSec / 60) % 60
  const h = Math.floor(totalSec / 3600)
  const base = h > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`
  return withTenths ? `${base}.${tenths}` : base
}

/** Edited spans use tenths precision (short clips). */
export function formatEdited(seconds: number): string {
  return formatClock(seconds, true)
}

/** Original spans often exceed an hour; keep them whole-second. */
export function formatOriginal(seconds: number): string {
  return formatClock(seconds, false)
}

/** Human duration, e.g. 8310 -> "2h 18m 30s". */
export function formatDuration(seconds: number): string {
  const safe = Number.isFinite(seconds) ? Math.max(0, seconds) : 0
  const s = Math.round(safe)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const parts: string[] = []
  if (h) parts.push(`${h}h`)
  if (m) parts.push(`${m}m`)
  parts.push(`${sec}s`)
  return parts.join(' ')
}

/** Byte count to human string. */
export function formatBytes(n: number): string {
  if (!Number.isFinite(n) || n <= 0) return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  let v = n
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v.toFixed(v >= 10 ? 0 : 1)} ${units[i]}`
}
