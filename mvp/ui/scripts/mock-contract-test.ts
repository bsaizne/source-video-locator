// MockServiceAdapter contract test — exercises the ServiceAPI flow end to end
// against the in-memory adapter and asserts the ResultBatchJson shape matches
// the backend wire contract (types.ts) exactly.
//
// Run:  npx esbuild scripts/mock-contract-test.ts --bundle --platform=node
//        --format=cjs --outfile=/tmp/mock-test.cjs && node /tmp/mock-test.cjs
import { MockServiceAdapter } from '../src/services/MockServiceAdapter'
import { createCancelToken } from '../src/services/cancel'
import type { ResultBatchJson } from '../src/services/types'

function assert(cond: unknown, msg: string): asserts cond {
  if (!cond) throw new Error(`ASSERT FAIL: ${msg}`)
}

async function main(): Promise<void> {
  const svc = new MockServiceAdapter()
  const stages: string[] = []
  svc.onProgress((e) => stages.push(e.stage))

  // Index Service
  const status = await svc.buildIndex('movie.mkv')
  assert(status.indexMeta?.feature_model === 'dinov2_vits14', 'indexMeta.feature_model')
  assert(status.indexMeta?.feature_dim === 384, 'indexMeta.feature_dim')
  assert(status.validation.status === 'VALID', 'validation.status')
  assert(status.backend.deviceType === 'cpu', 'backend.deviceType')

  // Analysis Service
  const analysis = await svc.analyzeEdited('clip.mp4')
  assert(analysis.segments.length > 0, 'segments non-empty')
  assert(typeof analysis.segments[0].span.start === 'number', 'segment span.start')

  // Result Service (locate)
  const batch: ResultBatchJson = await svc.locate('clip.mp4', 'movie.mkv')
  assert(batch.schema_version === 1, 'schema_version')
  assert(batch.results.length === 9, 'results count')
  const r = batch.results[0]
  assert(r.edited_segment && typeof r.edited_segment.start === 'number', 'edited_segment.start')
  assert(r.original && typeof r.original.candidate_start === 'number', 'original.candidate_start (asym key)')
  assert(typeof r.confidence === 'string', 'confidence flattened to top level')
  assert(typeof r.confidence_score === 'number', 'confidence_score top level')
  assert(['HIGH', 'MEDIUM', 'LOW'].includes(r.confidence), 'confidence in enum')
  assert(Array.isArray(r.reasons), 'reasons array')
  assert(Array.isArray(r.alternatives), 'alternatives array')

  const manual = batch.results.find((x) => x.manual_override)
  assert(manual?.auto_result != null, 'manual override preserves auto_result')
  assert(manual?.source === 'manual', 'manual override source')

  // Export
  const { path } = await svc.exportResults(batch, { filename: 'export' })
  assert(path.endsWith('.results.json'), 'export path')

  // Progress stages observed across the locate flow
  const seen = new Set(stages)
  assert(seen.has('INDEX_BUILD'), 'saw INDEX_BUILD')

  // Cancellation token semantics
  const t = createCancelToken()
  assert(!t.cancelled, 'token starts uncancelled')
  t.cancel()
  assert(t.cancelled, 'token cancelled')
  let threw = false
  try {
    t.raiseIfCancelled()
  } catch {
    threw = true
  }
  assert(threw, 'raiseIfCancelled throws after cancel')

  console.log('PASS: mock ServiceAPI contract OK')
  console.log('  results:', batch.results.length)
  console.log('  confidence levels:', batch.results.map((x) => x.confidence).join(','))
  console.log('  stages observed:', [...seen].join(' -> '))
}

main().catch((e) => {
  console.error((e as Error).message)
  process.exit(1)
})
