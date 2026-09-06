// resolveFor / resolveService switching tests (vitest, node env).
// Verifies the Mock/HTTP adapter selection, including the explicit mode default.
import { describe, it, expect } from 'vitest'
import { resolveFor } from '../resolveService'
import { MockServiceAdapter } from '../MockServiceAdapter'
import { HttpServiceAdapter } from '../HttpServiceAdapter'

describe('resolveFor', () => {
  it('defaults to MockServiceAdapter for undefined mode', () => {
    expect(resolveFor(undefined)).toBeInstanceOf(MockServiceAdapter)
  })

  it('uses MockServiceAdapter for mock mode', () => {
    expect(resolveFor('mock')).toBeInstanceOf(MockServiceAdapter)
  })

  it('uses HttpServiceAdapter for http mode', () => {
    expect(resolveFor('http')).toBeInstanceOf(HttpServiceAdapter)
  })

  it('passes the base URL through to HttpServiceAdapter', () => {
    expect(resolveFor('http', 'http://127.0.0.1:8765')).toBeInstanceOf(HttpServiceAdapter)
  })
})
