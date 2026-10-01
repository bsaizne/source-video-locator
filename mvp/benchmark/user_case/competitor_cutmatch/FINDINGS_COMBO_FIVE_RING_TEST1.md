# FINDINGS — 竞品全流程组合探针（五环）单片先行 test1（2026-09-26 续10c）

> **GT 版本**（2026-10-01 补登记，批量执行）：现行 139 条 verified（ground_truth_v4.json + test1-3.json，2026-09-02 定案；2026-09-30 重锚定 12 行后仍为现行基准）（test1 43 条子集）。〔推断级：按成文日期推定，依据 GT_VERSION_REGISTER_PROPOSAL_20260928.md〕

> **定级**：代理复现（推断级），非竞品实测。依据 = `DECISIONS.md` 2026-09-26（用户拍板「竞品全流程组合探针」单片先行）
> + `FINDINGS_CAPABILITY_GAP.md`（差距组合链）。**纪律**：零 runtime / 不碰 GT / 复现产物标推断级 / 结论只写"口径差异"。
> **本文只回答一个问题：静态可复现的组合链（G1+G2+G3+G4[+G5]）在 test1 上，瓶颈在哪一环。**

## 0. 执行摘要

- **候选层（粒度无关口径）已饱和**：42/43 条 GT 内容出现在代理候选表 **top-1**（TN 场景粒度，median rank 1.0），
  与我方 oracle 天花板（全索引检索 rank1 38/43）同级 ⇒ **检索/排序层不是竞品链的瓶颈，也不是我方的瓶颈**（与我方 V5 分诊一致）。
- **位置层（span 截到查询等长后跑同款严格判据）只有 10/43**（不含争议 GT 9/41），
  显著低于我方 main-span-only 22/43 与完整基线 34/43 ⇒ **可复现组合链的瓶颈 = 「场景内位置精化」（span 起点锚定）**：
  span/查询时长比中位 10.9×，仅 2/31 行被 DTW 对齐到近查询等长，GT 内容距 span 起点中位 **14.9s**。
- **G5（路径一致性项，推断级最小近似）= 零增量零伤害**：continuity_tiebreak_bonus=0.02 从未翻转任何 GT 相关名次
  （top1-top2 差中位 0.10 ≫ 0.02）；offset 单调修复仅 6 行（≤1.5s 微移，无 GT 结果变化）。**竞品真实路径项语义仍在机器码（N1-N8），静态不可得。**
- **负例行为**：0/1 误报（t1r32 TikTok 水印正确拒绝，两臂一致）。
- **环境漂移检查**：本轮 four-ring 重跑 vs 已交付 `localization_test1.json` **35/35 行 matched/span 全一致**（numpy 2.2→2.5 无实质影响）。

## 1. 执行设置

| 项 | 内容 |
|---|---|
| 五环 | G1 每场景5关键帧+长场景加密 / G2 TN t050 全流程边界+段内单元 / G3 patch 0.55 主力 / G4 AKAZE strict / **G5 新增（本轮）** |
| 两臂 | **A = four-ring 重跑**（同环境基座）；**B = A + G5**。均复用 test1 特征缓存（源库 912s/关键帧 12s 免重提），每臂 ~650s CPU |
| 产物 | `cutmatch-analysis/sandbox/out/localization{_comboA,_comboG5}_test1.json`（+akaze_off+manifest，带后缀不覆盖交付物）；`run_localization.py` 增 `--g5`/`--out-suffix`（默认路径行为不变） |
| 评估 | `mvp/scripts/probe_combo_dual_caliber.py` → `work/combo_probe_test1.json`；出图 `mvp/scripts/probe_combo_flip_visual.py` → `work/combo_probe_review/`（12 张，已读 6 张关键张） |
| G5 实现 | G5a = 上一查询 winner 源场景相邻(\|Δ\|≤1)候选 combined +0.02 重排（并参与 matched 门）；G5b = 相邻查询同/邻 winner 场景内 span 起点倒序时单调修复。均为我方最小近似（manifest A26/A27 登记） |

## 2. 双口径数字（test1, GT 43 正例 + 1 负例）

| 口径 | A four-ring | B five-ring+G5 | 参照系 |
|---|---|---|---|
| **候选层 top-1 / top-3 / top-20** | 42 / 42 / 42（never: t1r08c*） | 同 A（**名次变化 0 处**） | 我方 oracle 天花板 rank1 38/43, ≤20 43/43（不同协议, 仅参照） |
| **候选层「找到但被拒」** | 1（t1r14e） | 同 A | D 段复核: 复现弱点=蒙太奇段拒识（p10 型） |
| **span 截查询等长 严格** | **10/43**（不含争议 GT 9/41） | 同 A（**翻转 0 处**） | 我方 main-span-only **22/43** · 完整基线 **34/43**（场景 42/43） |
| 负例误报 | 0/1 | 0/1 | 基线 0/1 |

\* t1r08c 的 never 是**口径伪影**：其 GT 编辑窗为零宽 [33,33]，与任何查询行 ED 交集恒空（V5 已知零宽案例），非检索失败。

**两臂逐 GT 条目零翻转** ⇒ 下文判读全部适用于 five-ring（G5 在该近似形式下不改变任何结论）。

## 3. 判读（有据，逐图复核）

1. **「找得对、锚不准」**：候选层饱和 + 位置层 10/43 的组合只有一种解释——组合链把 GT 内容**归到了正确的 TN 场景**
   （top-1），但**场景内的位置只由起点窗(±30帧)/offset(±2帧)/DTW 门决定**，DTW 采纳率低（仅 2/31 行 span≈查询等长），
   内容中位落在 span 起点右侧 14.9s 处。读图证实：t1r02（游泳场景，截窗早 ~11s 同场景）、t1r04（甲板区域，截窗早 ~7s）、
   t1r17（暗室盾戏，截窗早 ~21s）——**全部同场景同内容区，0 内容性错位**（与 D 段复核结论一致），错的是锚点。
2. **与我方口径对照必须同粒度**：全 span 口径下复现 test1 严格 41/43（装配效应），截等长后 10/43——再次证明
   **TN 场景 span 的装配效应可被任何"重叠式"判据兑现**（续10 §2 的结论在单指标上重现）。公平读数 = 本文件双口径 + 我方双参照。
3. **G5 零增量的机制**：0.02 加分 ≪ top1-top2 差中位 0.101 ⇒ 只可能翻转"差 <0.02"的近平局（test1 无 GT 相关案例）；
   offset 平滑修的是已近乎单调序列的 ≤1.5s 抖动。**这不证伪竞品的路径项**——其真实形式（目标函数权重/作用范围/与
   ordered_search 的耦合）在机器码里；本结论只覆盖"公开信息可复现的最小近似"。
4. **端到端差距的落点（有界推断）**：用户实测竞品成品更好 + 本轮"检索层同级饱和、可复现位置层弱于我方" ⇒
   竞品成品的端到端优势**只能来自可复现层之外**：① 位置/边界精化（`commentary_boundary_refine_*` 9 项 A18 未实现、
   2fps 精确模式主档 A19、ordered_search A17）；② TN 边界的**展示层质量**（G7，几何正确性）；③ 我方尚未复现的工程环节。
   **本探针不能证实/证伪竞品成品**——它只划定了"静态可复现部分"的水平线。

## 4. 对我方路线的含义（待拍板，不在本探针权限内）

- **「细切点当子 span」前置条件已被本次量化**：竞品链证明"检索层饱和 + 位置层弱"时，细切点最有价值的用法是
  **展示层边界（G7）**而非定位（与 FINDINGS_QUERY_UNIT_SWAP / A1 方向一致）。
- 若继续追位置层：方向应是「无 GT 的场景内锚点信号」（DTW 采纳门之外的第二信号），而不是调 top-k/权重（已饱和）。
- G5 若要再测，前置 = 执行方机器码逆向给出 `select_scene_match_path` 目标函数（N1-N8），当前 blocked，不重复投入。

## 5. 产物清单

- 复现侧（外部仓，用户已授权直改）：`sandbox/run_localization.py`（+`--g5`/`--out-suffix`，默认路径不变）+
  `out/localization_comboA_test1.json` / `localization_comboG5_test1.json`（各配 akaze_off + manifest，A26/A27 假设登记）
- 判卷侧：`mvp/scripts/probe_combo_dual_caliber.py`（双口径评估）+ `mvp/scripts/probe_combo_flip_visual.py`（出图）+
  `work/combo_probe_test1.json` + `work/combo_probe_review/`（12 张：G5 平滑 8 + 一致抽样 4；已读 6 张关键张）
- 未竟：93 张 D 段对照图未裁部分（非阻塞）/ 2mkv A 桶 17 张 / G5 真实语义（等机器码）/ 出图脚本中文桶名在
  cv2.imwrite 下乱码（已手工改名，待修）
