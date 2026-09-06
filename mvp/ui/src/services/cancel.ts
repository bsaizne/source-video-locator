// Minimal cancellable token (mirrors the backend's CancellationToken).
// A token stays cancelled once cancelled; `raiseIfCancelled` lets long-running
// adapter work bail out between steps.

export interface CancelToken {
  readonly cancelled: boolean
  cancel(): void
  raiseIfCancelled(): void
}

export function createCancelToken(): CancelToken {
  let cancelled = false
  return {
    get cancelled() {
      return cancelled
    },
    cancel() {
      cancelled = true
    },
    raiseIfCancelled() {
      if (cancelled) throw new Error('operation cancelled')
    },
  }
}
