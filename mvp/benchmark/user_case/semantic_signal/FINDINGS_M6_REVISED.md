# M6 重算补充 FINDINGS —— v4 修正 GT 下 patch 召回 = 0 救回, 方向彻底关闭

> 日期: 2026-09-01 GT 重建专会话 | 性质: 研究侧重算(不改算法, 用修正 GT 重跑 M6 探针)
> 起因: GT v4 修正后, M6 原结论(基于 v3 错误 GT)作废, 用户拍板重算。
> 脚本: `mvp/scripts/research_patch_recall_gt.py --gt ground_truth_v4.json`(已加 --gt/--out/resume 参数)
> 数据: `work/patch_recall_gt_results_v4.json`(39 条完整) vs `work/patch_recall_gt_results.json`(v3, 41 条)

## 一、汇总对比: RESCUE 1/41 → 0/39, CLS 池外 10 → 0

| 指标 | v3(错误 GT, 41 条) | v4(修正 GT, 39 条) | 变化 |
|---|---|---|---|
| **RESCUE**(CLS 池外→patch 捞进) | **1**(p13) | **0** | ❌ 归零 |
| CLS 池外总数 | **10** | **0** | 全部消失 |
| 未救回 | 9 | 0 | — |
| CLS 已在池内 | 31 | **39/39** | 全覆盖 |

## 二、关键个案: v3 的 10 条「CLS 池外」几乎全是 GT 标错假象

| 条目 | v3 CLS best | v4 CLS best | v3 判定 | v4 判定 |
|---|---|---|---|---|
| **p05** | 178 | **1** | NOT_RESCUED | ✅ IN_POOL(池内直命中) |
| **p10** | 63 | **2** | NOT_RESCUED | ✅ IN_POOL |
| **p13** | 188 | **1** | **RESCUE(唯一救回)** | ✅ IN_POOL(CLS 直接命中) |
| **p20** | 465 | **8** | NOT_RESCUED | ✅ IN_POOL |
| **p23** | 96 | **1** | NOT_RESCUED | ✅ IN_POOL |
| **p24** | 2514 | **1** | NOT_RESCUED | ✅ IN_POOL |
| **p26** | 22 | **1** | NOT_RESCUED | ✅ IN_POOL |
| **p32** | 78 | **1** | NOT_RESCUED | ✅ IN_POOL |
| **p41** | 103 | **1** | NOT_RESCUED | ✅ IN_POOL |
| p38 | 340 | (已删, 与 p08 重复) | NOT_RESCUED | — |

→ **v3 的「CLS 池外」几乎全部是 GT 窗口标错位置**：算法 CLS 检索本来就能在正确位置命中(修正后 best_rank 1-8),
只是旧 GT 把正确窗标到了别处, 让「正确窗内帧」在错误位置找不到。
**p13 的「patch 唯一救回」也在修正后消失**——v4 下 p13 CLS best=1, patch 无增量。

## 三、净结论

1. **patch 召回 runtime 化 = 彻底不值(v4 口径 0/39 救回)**——比 v3 的「仅 +1/41」更极端:
   修正 GT 后 CLS 对全部 39 条正例直接命中池内, patch 第二通道零增量。
2. **方向关闭(有据, 双重证据)**: v3 1/41 + v4 0/39, 且 v3 的救回案例(p13)被证明是 GT 标错假象。
3. **M6 原 FINDINGS 中「RESCUE 1/41(p13)」结论作废**, 修正为「RESCUE 0/39, p13 为 GT 标错假象」。
4. **「失败族在 CLS/patch 双通道无解」结论需再修正**: v4 下失败族(修正后)只剩 runtime 未命中的
   p08(兄弟机位)/p36 + part 的 p05/p20/p34/p35/p41——这些是**定位精度/兄弟混淆**问题, 不是「召回层进不了池」。
5. 零 runtime 改动; 三指标以 v4 为准(32/39 严格)。

## 相关产物
- 脚本 `research_patch_recall_gt.py`(已参数化 + resume 支持) | 数据 `work/patch_recall_gt_results_v4.json`
- 对比脚本 `work/_m6_compare.py`
