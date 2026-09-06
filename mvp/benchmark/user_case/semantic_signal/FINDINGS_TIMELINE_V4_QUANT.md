# 时序重排 v4 量化（2026-09-01 拍板执行序 ④，研究侧快）

> 起因: NEXT_STEPS ① ——「用 v4 GT 对 user_results 重跑 temporal_outlier_repair + seq_dp 的纠正判定,
> 数『修正前 MISS/part → 修正后 HIT』几条」, 直接量化时间轴先验的存量价值, 顺带重估 P3 悲观结论。
> 方法: ① 多版本结果批(v4 同口径)对比; ② 精确回滚实验(只还原带修复标记的段)。

## 一、多版本严格/场景命中（v4 GT，2.mkv 39 正例 / 4 负例）

| 版本 | mtime | 严格 | verified | loose | 场景(±15s) | 负例 FP |
|---|---|---|---|---|---|---|
| baseline_p21（Phase 21 前） | 08-29 17:17 | **29/39** | 28/36 | 1/3 | 35/39 | 2/4 |
| pre22a | 08-30 02:43 | **31/39** | 30/36 | 1/3 | 36/39 | 2/4 |
| pre24 | 08-30 14:41 | **33/39** | 32/36 | 1/3 | 36/39 | 2/4 |
| **current** | 08-30 14:49 | **32/39** | 31/36 | 1/3 | 36/39 | 2/4 |

- baseline_p21 → pre22a: **+2**（p26 part→HIT、p40 MISS→HIT）——Phase 21 场景指纹召回扩展层
  （场景表进索引 + 检索扩池 + seq_dp + text_anchor + patch_rerank）整体贡献，无法单拆 seq_dp。
- pre22a → pre24: **+2**（p16 part→HIT、p05 part→HIT）——时序离群修复(temporal_repair, s7 2400→1403)
  + s1 主定位 996→973（p05 命中 v4 正确窗 978-984）。
- pre24 → current: **−1**（p05 HIT→part）——s1 主定位 973→996 回到旧 GT 区（见 §三）。

## 二、精确回滚实验（只还原带 temporal_outlier_repair / conflict_rerank / sequence_rerank 标记的段）

- 当前结果批中带修复标记的段: **仅 s7**（`temporal_outlier_repair`, 修复前 2400-2402 → 修复后 1403-1405）。
- 回滚后: **严格 31/39**（vs current 32/39）；唯一差异 **p16: part → HIT**。
- **结论: temporal_outlier_repair 在 v4 下净纠正 = +1（p16）**。s7 为暗夜相似场景跨场景误配
  （2400s 夜读区 ↔ 1403s 铁丝网区），前后段定位彼此接近、本段远离两者 → 在前后段窗口内重定位拉回。

## 三、p05「pre24 HIT → current part」现象（非时序修复问题，诚实留痕）

- s1(ed 6.0-7.5) 主定位: pre22a=996-998 → pre24=973-979（命中 v4 正确窗 978-984）→ current=996-998（旧 GT 区）。
- 归属: s1 无任何修复标记——996→973 非 temporal_repair 产物（s1 不满足离群条件），
  973→996 亦非 conflict_rerank（无标记）。两处变化在 8 分钟内（14:41→14:49），疑似重跑
  非确定性或开关差异，非"时序类修复"的稳定贡献。
- 与 V4_MISS_RECHECK 的 p05 判定一致: **「修正后未跟上」**——旧 GT(996-998) 本就是算法检索产物,
  用户逐帧核实后正确窗前移到 978-984; 修正后算法检索结果不变 → 「严格」未命中。**非算法退化**。

## 四、对 P3 悲观结论的重估（TIMELINE_PRIOR §二）

- P3a 曾测「编辑序列与原片时间轴非 1:1」, p26 显示偏 1000s+（真值 2809 vs best_scene 1766）。
- GT 修正后 p26 正确位置 = 1768.2-1770.05, 恰在 best_scene 1766-1770 区域 → **完全符合时间轴顺序**。
- 时序修复的存量价值（v4 口径）: 严格 +1（p16）; 场景级口径下 current=36/39 已是
  p26/p40/p16 等被时序类机制（场景召回扩池 / 时序修复）拉回后的结果。
- **结论: 时间轴先验有真实但有限的存量价值（≥+1 严格，含 Phase 21 扩池后场景级 36/39 天花板）;
  单调弱先验进候选生成（NEXT_STEPS ②③）须先经 ⑥⑧ 验证（本次 +1 支持"离群修复"方向, 不支持"强制单调"）。**

## 相关产物
- 脚本: `mvp/scripts/research_timeline_v4_quant.py`（多版本对比）+ `research_timeline_v4_rollback.py`（精确回滚）
- 数据: `mvp/benchmark/user_case/user_results*.json` + `datasets/real/ground_truth_v4.json`
