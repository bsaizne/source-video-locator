// Deterministic mock data used by MockServiceAdapter so the UI runs entirely
// standalone. The shape is identical to the real backend JSON (types.ts), so
// swapping in HttpServiceAdapter later requires no UI changes.

import type {
  AlternativeJson,
  BackendInfoJson,
  IndexMetaJson,
  IndexValidationJson,
  ResultBatchJson,
  ResultJson,
  ShotSegmentJson,
} from './types'

const ORIGINAL = 'Interstellar (2014).mkv'
const EDITED = 'trailer_compilation.mp4'

let seq = 0
function uid(): string {
  seq += 1
  return `mock-${String(seq).padStart(3, '0')}`
}

export function mockIndexMeta(): IndexMetaJson {
  return {
    index_version: 1,
    source_file: ORIGINAL,
    file_size: 1_073_741_824,
    duration: 8310,
    file_hash: 'sha256:3f1c...9e2a',
    feature_model: 'dinov2_vits14',
    feature_version: 'handwritten_vits14_cls_384d@0.5fps_l2',
    sampling_fps: 0.5,
    feature_dim: 384,
    num_frames: 4155,
    backend: 'cpu',
    created_at: '2026-08-26T10:14:00Z',
    device_machine_id: 'SVL-WORKSTATION',
    extractor: { normalize: 'l2', resize: '518x518', mean_std: 'imagenet', preprocess_sha: 'a1b2c3d4' },
  }
}

export function mockIndexValidation(): IndexValidationJson {
  return { status: 'VALID', reason: null }
}

// CPU is the guaranteed baseline (H1) — honest for the mock; the
// BackendStatusIndicator component still knows how to render all four kinds.
export function mockBackend(): BackendInfoJson {
  return { deviceName: 'cpu', deviceType: 'cpu', isAccelerator: false, fallback: false }
}

export function mockSegments(): ShotSegmentJson[] {
  const spans: Array<[number, number]> = [
    [3.1, 21.4],
    [28.6, 47.2],
    [61.0, 79.8],
    [95.4, 118.9],
    [133.2, 151.5],
    [170.0, 188.3],
    [201.7, 222.4],
    [247.1, 258.0],
  ]
  return spans.map(([start, end], i) => ({
    id: uid(),
    label: `片段 ${String(i + 1).padStart(2, '0')}`,
    span: { start, end },
    nq: Math.round((end - start) * 2),
  }))
}

function mkAlternative(candidate_start: number, candidate_end: number, confidence: AlternativeJson['confidence'], score: number): AlternativeJson {
  return { candidate_start, candidate_end, confidence, score }
}

interface ResultSeed extends Partial<ResultJson> {
  ed: [number, number]
  og: [number, number]
}

function mkResult(p: ResultSeed): ResultJson {
  return {
    result_id: p.result_id ?? uid(),
    edited_segment: { start: p.ed[0], end: p.ed[1] },
    original: { candidate_start: p.og[0], candidate_end: p.og[1] },
    confidence: p.confidence ?? 'LOW',
    confidence_score: p.confidence_score ?? 0,
    reasons: p.reasons ?? [],
    candidate_rank: p.candidate_rank ?? 1,
    alternatives: p.alternatives ?? [],
    original_segments: p.original_segments ?? [],
    source: p.source ?? 'auto',
    manual_override: p.manual_override ?? false,
    montage_flag: p.montage_flag ?? false,
    extracted_path: p.extracted_path ?? null,
    failure_reason: p.failure_reason ?? null,
    not_in_source: p.not_in_source ?? false,
    manual_timestamp: p.manual_timestamp,
    auto_result: p.auto_result,
  }
}

export function mockResultBatch(): ResultBatchJson {
  const results: ResultJson[] = [
    mkResult({
      ed: [3.1, 21.4], og: [5025, 5042],
      confidence: 'HIGH', confidence_score: 0.94, candidate_rank: 1,
      reasons: ['rank1', 'high_query_coverage', 'stable_temporal_localization'],
    }),
    mkResult({
      ed: [28.6, 47.2], og: [7180, 7199],
      confidence: 'HIGH', confidence_score: 0.88, candidate_rank: 1,
      reasons: ['rank1', 'high_query_coverage'],
    }),
    mkResult({
      ed: [61.0, 79.8], og: [1543, 1561],
      confidence: 'MEDIUM', confidence_score: 0.64, candidate_rank: 1,
      reasons: ['rank1', 'large_candidate_margin'],
      alternatives: [mkAlternative(2950, 2968, 'LOW', 0.42)],
    }),
    mkResult({
      ed: [95.4, 118.9], og: [4100, 4124],
      confidence: 'MEDIUM', confidence_score: 0.58, candidate_rank: 2, montage_flag: true,
      reasons: ['possible_montage', 'low_candidate_margin'],
      alternatives: [
        mkAlternative(6021, 6045, 'LOW', 0.39),
        mkAlternative(8100, 8124, 'LOW', 0.33),
      ],
    }),
    mkResult({
      ed: [133.2, 151.5], og: [2987, 3005],
      confidence: 'LOW', confidence_score: 0.41, candidate_rank: 3,
      reasons: ['dark_scene_semantic_confusion', 'low_candidate_margin'],
      alternatives: [mkAlternative(1055, 1073, 'LOW', 0.34)],
    }),
    // 非源片内容（TikTok 片尾/转场）——卡片守卫判定，不产出原片定位
    mkResult({
      ed: [190.5, 198.0], og: [0, 0],
      confidence: 'LOW', confidence_score: 0, candidate_rank: 1,
      reasons: ['text_card_not_in_source'],
      failure_reason: 'text_card_not_in_source',
      not_in_source: true,
    }),
    // A user-confirmed manual override — auto result preserved alongside.
    mkResult({
      ed: [170.0, 188.3], og: [4522, 4540],
      confidence: 'HIGH', confidence_score: 0.91, candidate_rank: 1,
      reasons: ['rank1', 'stable_temporal_localization'],
      source: 'manual', manual_override: true,
      manual_timestamp: '2026-08-26T10:42:00Z',
      auto_result: mkResult({
        ed: [170.0, 188.3], og: [4520, 4538],
        confidence: 'HIGH', confidence_score: 0.91, candidate_rank: 1,
        reasons: ['rank1', 'stable_temporal_localization'],
      }),
    }),
    // Segment failure isolation — unresolved.
    mkResult({
      ed: [201.7, 222.4], og: [0, 0],
      confidence: 'LOW', confidence_score: 0, candidate_rank: 1,
      reasons: ['no_candidates'], failure_reason: 'no_candidates',
    }),
    mkResult({
      ed: [247.1, 258.0], og: [6980, 6991],
      confidence: 'MEDIUM', confidence_score: 0.61, candidate_rank: 1,
      reasons: ['rank1', 'high_query_coverage'],
    }),
  ]
  return {
    schema_version: 1,
    original_video: ORIGINAL,
    edited_video: EDITED,
    results,
  }
}

export function mockIndexBuildSteps(total = 100): Array<{ stage: 'INDEX_BUILD'; current: number; total: number; message: string }> {
  return [
    { stage: 'INDEX_BUILD', current: 0, total, message: 'probing media' },
    { stage: 'INDEX_BUILD', current: 30, total, message: 'extracting frames @0.5fps' },
    { stage: 'INDEX_BUILD', current: 72, total, message: 'embedding DINOv2' },
    { stage: 'INDEX_BUILD', current: 100, total, message: 'writing index' },
    { stage: 'INDEX_BUILD', current: 100, total, message: 'index ready' },
  ]
}
