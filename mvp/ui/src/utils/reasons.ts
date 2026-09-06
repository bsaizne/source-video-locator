// Machine-readable reason keys (CONFIDENCE_DESIGN §4) → human text.
// Displayed in the Inspector; never as a probability.

const REASONS: Record<string, string> = {
  rank1: '最高排名候选',
  rankN: '非最高排名候选',
  high_query_coverage: '跨源高查询覆盖率',
  low_query_coverage: '低查询覆盖率——源部分重叠',
  stable_temporal_localization: '时间定位稳定',
  large_candidate_margin: '与下一候选有明显差距',
  low_candidate_margin: '与下一候选差距很小',
  multiple_similar_candidates: '找到多个相似候选',
  possible_montage: '疑似蒙太奇 / 多镜头源',
  dark_scene_semantic_confusion: '暗场景——语义特征可能歧义',
  source_window_anomaly: '源窗口宽度异常',
  finloc_unstable: '精定位不稳定',
  manual_override: '用户手动覆盖确认',
  no_candidates: '未找到候选',
  no_span: '未定位到区间',
  text_card_not_in_source: '黑底文字卡 / 片尾标识——非源片内容',
}

export function reasonText(key: string): string {
  return REASONS[key] ?? key.replace(/_/g, ' ')
}
