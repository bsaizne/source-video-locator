# FINDINGS — 方案 A「DINOv2 patch 稠密几何对应」可行性探针 = 判负，不进 runtime（2026-10-02）

> **GT 版本**：2026-10-01 续39 重锚定后 GT（ground_truth_v4 / test1/2/3，版本标记 gt-gap-review-20261001-r1）。
> 结果批 = 现役 r7 对应批 `work/spl_patch_arms/on_*.results.json`（两旋钮 ON，基线严格 133/139）。
> **定级**：探针（零 runtime、零 GT 修改、不 bump feature_version）。GPU 全程 DirectML 硬断言通过。

## 0. 结论（一句话）

patch 级稠密几何对应（mutual-NN + 仿射 RANSAC 内点率）**不能纠正错误定位**：在 6 条当前严格
未命中上 gt_is_peak 仅 1/6、margin 与噪声同量级 ⇒ **方案 A 判负，不进 runtime，不留通道**。

## 1. 动机与假设

根因（FINDINGS_DUAL_STACK / REDIG_20261001）：同场景内 2–7s 偏移与兄弟机位族的天花板 =
DINOv2 CLS/patch 余弦的**语义不变性**。现有 `patch_score`（patch_rerank.py:133）是
「每 query patch 对 source patch 最大余弦 top-100 均值」= 袋式匹配，**丢掉 argmax 落点**。

假设：利用被丢掉的落点做**稠密对应**——query patch i 的最近邻落在 source patch j → 位移向量；
同一瞬间画面（剪辑只做裁剪/缩放/平移）→ 位移场被单一仿射解释 → RANSAC 内点率高；
同场景偏几秒（前景移动）→ 位移场无法被单一仿射解释 → 内点率崩。
与已证伪的 AKAZE/ALIKED 稀疏单应（phase24_1/M7）是不同形态（稠密学习 patch vs 稀疏手工关键点）。

## 2. 方法（probe_patch_dense_corr.py）

- `dense_corr(Q,S)`：Sim=Q@S.T → mutual-NN 过滤（双向最近邻，nn≥0.45）→ 位移场 →
  `cv2.estimateAffinePartial2D(RANSAC, tol=2 patch)` → **inlier_ratio** 为主判据。
- 位置扫描：对每案例在 source 时间轴 [min(GT,main)-10s, max+10s] 步长 1s 扫描，
  每位置抓 1 帧，对 3 帧 query 各算 dense_corr 取均值，画 inlier_ratio 曲线。
- 判据：① GT 窗内分数 > 我方主定位处（margin>0.02）；② GT 处是全局峰（±1.5s）。
- 门槛（patch_v2 同规格）：MISS+POCKET 命中 ≥1/3 且对照组零反噬。

## 3. 测试集与口径警示

- MISS6（续39 当前严格未命中）：p14/p20/p34（2mkv）、t1r08c/t1r12a（test1）、t2r03b（test2）。
- POCKET8（**旧基线 127 时代**真口袋，probe_pocket_retest_gt130）：p02/p03/p20/p30/p34/t1r14c/t2r06c/t3r02c。
- CONTROL8（当前严格命中）：p04/p10/p32/t1r00/t1r27/t2r00/t3r07/t3r12。
- ⚠️ **口径警示**：POCKET8 基于旧基线；shot_split/patch_refine 默认开（续35）后其中
  p02(off=0.3s)/p03(0.7)/t1r14c(0.8) 在当前批已接近正确 ⇒ 不再是"未命中"案例，其 gt>main 无判别意义。
  干净的目标集 = MISS6。

## 4. 结果（20 案例，GPU DirectML，产物 work/patch_dense_corr/）

| 组 | gt>main | gt_is_peak |
|---|---|---|
| MISS6（当前真未命中） | 2/6 | **1/6** |
| POCKET6（去重后） | 3/6 | **0/6** |
| CONTROL8 | 7/8 | 5/8 |

逐案例 margin（GT−main）：MISS 组 −0.13 ~ +0.20（多数 <0.1）；POCKET 组 −0.06 ~ +0.07。
inlier_ratio 绝对值整体仅 0.15–0.47，相邻位置抖动 ±0.1–0.2 ⇒ margin 淹没在噪声里。
异常：t2r03b 我方主定位=0s（candidate_start/end=0，完全未定位）GT=3570s，off=3570.7。

## 5. 逐张读图确证（curves/*.png，3 张代表）

- **p10（control，gt_is_peak=True）**：峰在 GT 窗内，但红竖线（ours main）就在峰旁（off=0.0）
  ⇒ control 的"成峰"是**同义反复**（定位已对时 main≈GT），非 dense_corr 独立挑出 GT。
- **p20（miss，off=7s）**：GT 窗处 inlier≈0.17，与邻域噪声（0.12–0.22）同水平，**无判别峰**；
  全局峰在远离 GT 的 1545s。margin=0.018≈0。
- **p02（pocket，off=0.3s）**：GT 窗与 main 重合，GT 处反而是低谷（0.19 vs 邻域 0.43），
  margin=0.067 是噪声。

## 6. 失效机理（设计时预警的陷阱，实测确认）

**背景主导稀释**：同场景偏几秒时，**静止背景的 patch 仍对齐**（相机没动）→ 内点率不降；
前景错位只占少数 patch → 被背景稀释 ⇒ GT 处分数与错误位置无显著差异。
dense_corr 只在「整帧对齐」（control，main≈GT）时给高分，**不能把正确位置从错误位置中挑出来**
——而这恰是纠正定位所需的能力。⇒ 假设不成立。

## 7. 裁决与下一步

- **方案 A 判负**：门槛未达（MISS gt_is_peak 1/6 << 要求；margin 噪声级）。不进 runtime、不留通道。
- 与 REDIG_20261001 一致：该族上限是**特征判别力**，换锚定/对应形态（袋式→稠密几何）仍不突破。
- 下一步候选（待用户拍板）：
  - **方案 B**：正交预训练 backbone 集成（非 DINOv2 同族；ViT-B 同族已证 −1 无增益，B 需先探针）。
  - **接受现状**：严格 133/139 已接近该素材/该 GT 上限，剩 6 条为特征上限族 + 1 条未定位（t2r03b）。
  - ~~t2r03b 主定位=0s 是产品缺陷线索（完全未定位却出 0s 而非 unresolved）~~ →
    **2026-10-02 查证更正（本会话自我更正留痕）**：0s 只是 unresolved 的 `Result.original`
    默认占位（models.py:173），导出（exporters.py:114-117 双重 skip）/渲染（ResultsPage:407 跳过）/
    UI（「未定位」徽标 ResultTable.vue:45-48）全部正确过滤或标记，**非用户可见缺陷**。
    真实根因（`probe_t2r03b_diag.py`）：检索 OK（GT 区 top-20 rank1-2、sim≤0.63）→ 2fps 仅 2 帧
    无显著簇 → dense retry(8fps) 有 1 簇但 cover=0.062 / bsim=0.413 被弱簇门(0.30/0.45)丢弃；
    窄窗豁免（edited<1.2s 放宽弱簇门）可过弱簇门（primary→3570-3571=GT 区），但
    **dense_retry_min_sim=0.62 门仍挡**（0.413<0.62；降门会放回 test4 假定位 0.53-0.60）
    ⇒ **证据本身太弱（0.9s 窄段/GT 0.57s/cover 0.062），不可救**，接受为未命中。
    窄窗豁免已**回退**（对目标案例无收益 + 引入窄段假子 span 风险）；仅保留
    `reasons.ts` 补 `no_evidence` 中文映射（原缺该 key 致 UI 显示英文技术串；vitest 138 + 双 typecheck 绿）。

## 8. 产物

- 脚本 `mvp/scripts/probe_patch_dense_corr.py`；stdout `work/probe_patch_dense_corr_stdout.log`
- `work/patch_dense_corr/{index.json, curves/*.png(20), sheets/*.png(20)}`
