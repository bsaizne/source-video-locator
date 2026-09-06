# 暴力 top1 诊断结论：特征能否找到答案（2026-08-28）

> 触发：用户真实案例「清晰女性人像特写 → 定位到暗色 28:01-28:16 错原片」，怀疑特征本身判别力不足。
> 用户拍板：砍掉复杂 pipeline，写最小脚本 `单视频→逐帧→DINO embedding→暴力 cosine→top1 时间`，先证明特征能不能找到答案。允许多模态辅助。

## 方法

- 脚本 `mvp/scripts/verify_greedy_top1.py`（168 行，复用底层 `FFmpegIO.iter_frames`/`resolve_backend`/`embed_frames`/`cosine_similarity`，**跳过** clustering/ranking/finloc/confidence/montage）。
- 复用已建索引 `2__4c6d4ab2.idx`（7668 帧 @1fps, DirectML, 0 重建秒级）。
- 对每段编辑查询（GT 区间 / DIAGNOSIS 12 段），逐帧暴力最近邻，输出 top1 原片时间，取 median/主峰；抽出 top1 相似度最高帧对（编辑帧 | top1 原片帧）做多模态终核。

## 核心结论

### 1. 特征（CLS 暴力 top1）能找到答案 —— 用 corrected GT，6/7 命中

**关键坑**：原 `datasets/real/ground_truth.json` 的 `original_start/end` 大量错位（benchmark 已知问题）。`ground_truth_corrected.json` 是多模态视觉终核改正的。**用原 GT 测 = 0/7（纯假象），用 corrected GT 测 = 6/7**。

| edited | 原GT(错) | corrected GT 锚点 | 暴力 top1 median | 命中 |
|---|---|---|---|---|
| 19-21 | 6599.1 | 士兵/直升机 1296 | 1301 | ✅ |
| 26-29 | 6350.3 | 直升机绿谷 1342 | 1343 | ✅ |
| 28-30 | 6601.1 | 直升机 1342 | 1345 | ✅ |
| 30-32 | 1302.8 | 山脊士兵 1378 | 1376 | ✅ |
| 35-37.5 | 6349.8 | 雾山脊铁丝 1402 | 1403 | ✅ |
| 46-48.5 | 6598.1 | 混凝土bunker 1584 | 1584 | ✅ |

唯一 miss（6.5-10s）是 corrected 自标「最弱项/边界不确定」的段。

### 2. 多模态终核：top1 命中帧 = 编辑帧同镜头（铁证）

- seg01 牛排餐盘特写 → top1 同款餐盘 ✅
- seg02 直升机飞越绿谷 → top1 同款直升机绿谷 ✅
- seg06 混凝土bunker+森林+储油罐 → top1 完全同景 ✅
- seg00 瞭望塔bunker → top1 也是瞭望塔bunker（台词"There's another bunker"——corrected 此段存疑）

### 3. 用户 12 段：特征 top1 大多与产品定位一致 → 主因是 pipeline 聚合 / 置信，非特征

| seg | 产品定位 | 暴刀 top1 median | 判断 |
|---|---|---|---|
| s3 37-51 | 1550-1596 | 1571 | 特征对，pipeline 聚合+置信错 |
| s4 51.5-59 | 1668-1704 | 1682 | 特征对（多cluster 1601/1612/1683），蒙太奇被压成一条run |
| s5 59.5-62.5 | 1706-1710 | 1709 | 完全命中 ✅ |
| s10 121-122.5 | 2098-2104 | 2101 | 完全命中 ✅ |
| s11 123-126.5 | 7630-7660 | 7661 | **特征也命中片尾** → 确凿特征层上限 |

## 判定

- **特征能找到答案**：同一特征下，逐帧 top1 用 corrected GT 达 6/7，多模态确认 top1 帧=编辑帧同镜头；用户 12 段 top1 median 大多命中产品定位区间。
- **产品「对不上」的主因 = pipeline 聚合，不是特征**：`finloc longest_run` 把蒙太奇的 top1 分布压成一条连续 run（丢其余子镜头）；`clustering` 把多镜头聚成单候选；置信未标定（部分命中/相似外观仍标 HIGH）。暴力 top1 的**分布**（每帧最近邻）天然保有蒙太奇多镜头信息，产品却把它收窄成一条。
- **确凿的「特征层上限」活样本 = s11**（TikTok 水印 ↔ 电影片尾 logotype，黑底白字相似，CLS 把水印判为最像片尾 7661）。这类相似外观误配是特征无法用 CLS 轻易区分的，需第二信号（logotype 结构/时序/场景身份）。

## 建议方向（与「砍掉复杂 pipeline」直觉一致）

1. **定位改「暴力 top1 分布 + 时间聚类」**：逐帧 top1 的众数/多峰聚类输出多个原片区（而非 finloc 单 longest_run）。这天然覆盖蒙太奇多镜头，比 finloc 诚实、更对。研究 montage_localize（query-axis 聚类）已验证此方向有效。
2. **置信度标定**：对「top1 分布散（多峰=蒙太奇）/ 部分命中 / 相似外观」诚实降档到 LOW，别标 HIGH（解决 s3/s4/s11 类「自信答错」）。
3. **s11 类 logotype/文字卡片相似**：少数个案，需独立第二信号，属另立研究，不建议现阶段投入（低频）。

## 产物

- 脚本：`mvp/scripts/verify_greedy_top1.py`
- 结果：`mvp/benchmark/user_case/verify_greedy_corrected.json`
- 多模态接触表：`mvp/benchmark/user_case/verify_greedy/seg00..06_pair.jpg`

## 边界

诊断脚本，不进产品 runtime，不改任何产品算法语义。未改相似度/检索/排序/定位/置信语义、未改 GT、未做 sweep。
