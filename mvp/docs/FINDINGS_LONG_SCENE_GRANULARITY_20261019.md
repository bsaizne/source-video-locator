# FINDINGS：长镜头内部定位粒度 — 我方 vs 竞品（2026-10-19，续75）

> ⚠️ **本文 §5 的「TopK 重排 = 最真实缺口」已被同日实验推翻** →
> `FINDINGS_TOPK_RERANK_OFFLINE_20261019.md`（单点精排 ≤1s 命中 26，TopK 裸 24、TopK+覆盖门 25）。
> 本文其余部分（参数对比、缺口规模、三条约束）仍然有效。
>
> 起因：竞品在「切分不可靠」上的应对策略是 `long_scene_*` 那套（承认切得粗，在长镜头内部
> 用关键帧+探针窗找精确起点）。本文量化我方对应链路的粒度与覆盖差距。**只读，零代码改动。**

## 0. 一句话

**我方有精排链路，粒度（10fps）与竞品同级；但竞品多两层我方没有的东西：**
**① TopK 重排（10 候选）② 长镜头局部 probe（3s 窗 / 1.5s 步长 / 最多 16 关键帧）。**
我方精排是**单点**的：只对已定位的起点在 ±4s 内重排一次，且只允许位移 ≤2s。

## 1. 我方现役链路（实测配置 = `load_config()` 真实生效值）

| 阶段 | 参数 | 值 | 作用 |
|---|---|---|---|
| 编辑侧采段 | `edited_segment_fps` | **2.0 fps** | 切镜头的粗采样 |
| 编辑侧密帧 | `seq_align.edit_fps` | **8.0 fps** | 给 DP 对齐用 |
| 全局锚定 | `fast_global_fps` | **3.0 fps** | 从 8fps 降采样，零额外解码 |
| 全局锚定宽窗 | `fast_global_wide_win_s` | 1.5 s | 宽窗支持判据 |
| **起点精排采样** | `dense_recheck_fps` | **10 fps** | 原片侧密集窗 |
| **精排窗** | `dense_recheck_margin_s` | **±4.0 s** | 起点前后各 4s |
| **最大位移** | `dense_recheck_max_shift_s` | **2.0 s** | 精排只允许移动起点 ≤2s |
| 精排增益门 | `dense_recheck_min_gain` | 0.04 | 相似度须提升 ≥0.04 才采纳 |

实现 = `_apply_dense_start_recheck`（`locator_service.py:815`）：只对**已定位主 span 的起点**
在 `span.start ± 4s` 内以 10fps 重新取原片帧 + embedding，取段内 3 个均匀代表帧做多帧
首段证据打分；采纳 = 增益 ≥0.04 且位移 ≤2s 且距离平局裁决。**只移起点、宽度保持。**

## 2. 竞品对应链路（常量块 + 实测取值）

| 项 | 竞品值 | 我方对应 | 差距 |
|---|---|---|---|
| 精排采样 | `offset_refine_dtw_sample_interval_seconds` = **0.1**（10fps） | `dense_recheck_fps` = 10 | **平手** |
| 精排方法 | **子序列 DTW**（动态规划路径） | 代表帧打分 + 增益门 | **竞品更强** |
| DTW 起点窗 | `offset_refine_dtw_start_window_radius_frames` = **30 帧** | `dense_recheck_margin_s` = ±4s | 我方窗更宽 |
| 起点窗最少增益 | `offset_refine_dtw_start_window_min_improvement` = **0.04** | `dense_recheck_min_gain` = 0.04 | **逐字相同** |
| DTW 最少分 | `offset_refine_dtw_min_score` = **0.55** | 无绝对分门 | 竞品多一道门 |
| DTW 采样上限 | `offset_refine_dtw_max_samples` = **64** | 无显式上限 | 竞品有界 |
| **TopK 重排** | `offset_refine_dtw_topk_rerank_enabled` = **True** | **无** | ⚠️ **关键缺口** |
| TopK 候选数 | `offset_refine_dtw_topk_rerank_max_candidates` = **10** | — | — |
| TopK 最少场景覆盖 | `offset_refine_dtw_topk_rerank_min_scene_coverage` = **0.8** | — | — |

**长镜头族（`feature_index.sampling`，我方完全没有对应物）：**

| 参数 | 值 | 语义（竞品 docstring 原文） |
|---|---|---|
| `long_scene_min_seconds` | **6.0** | 超过 6s 的场景算「长场景」 |
| `long_scene_keyframe_interval_seconds` | **1.0** | 长场景按 1s 间隔加样本 |
| `long_scene_max_keyframes` | **16** | 最多 16 个关键帧 |
| `long_scene_probe_window_seconds` | **3.0** | 局部 probe 窗 3s |
| `long_scene_probe_stride_seconds` | **1.5** | probe 步长 1.5s |

原文：「**普通场景均匀取帧，长原片场景按时间间隔和最大数量自适应增加样本**」
「按窗口与步长切分长场景，从现有逐帧特征聚合每个局部 probe」
「低内存模式：长镜头局部 probe 将在候选召回时按需生成，不常驻原片特征库」

⇒ 竞品的做法 = **长镜头不被当成一个整体**，而是切成 1.5s 步长、3s 窗的局部 probe 集合，
「长镜头里到底哪一段」于是有了比全局场景指纹更细的检索单元。

## 3. 缺口规模（我方四片实测）

按竞品 `long_scene_min_seconds = 6.0` 这条线切我方四片真索引：

| 片 | 场景数 | 总时长 | ≥6s 场景数 | 占比 | 这些场景覆盖 | 时长占比 |
|---|---|---|---|---|---|---|
| 2mkv | 2102 | 7668s | 291 | 13.8% | 3357s | 43.8% |
| test1 | 913 | 8221s | 365 | **40.0%** | 6756s | **82.2%** |
| test2 | 1786 | 5051s | 125 | 7.0% | 1446s | 28.6% |
| test3 | 2754 | 10177s | 399 | 14.5% | 4410s | 43.3% |
| **合计** | **7555** | **31117s** | **1180（15.6%）** | | **约 16000s** | **约 51%** |

⇒ **约一半的原片时长落在「长场景」里**，而这些场景在我方是**一个检索单元**（一个场景指纹）。
竞品在同样的半片时长上会生成 ~16000 / 1.5 ≈ **1 万个局部 probe**（3s 窗 / 1.5s 步长）；
我方对应位置只有 **1180 个场景指纹**。**检索单元密度差约 8 倍。**

## 4. 但这不是简单「加 probe 就好」——三个必须说清的约束

1. **我方场景数已经远多于竞品**（7555 vs 竞品原片侧 TN 的 375 条/片量级）。
   竞品原片侧**根本不切镜头**，所以他们必须靠 probe 造检索单元；我方已经有 1fps 全片特征
   （`features.npy` 每帧一行）+ 场景表，**「检索单元」本来就在，只是没被当单元用**。
   ⇒ 缺口不在「没有细单元」，而在 **`evidence_localize` 只按场景池召回，不按帧级滑窗召回**。
2. **加 probe = 加索引时间与磁盘**。竞品那条原文就写明「低内存模式：长镜头局部 probe
   将在候选召回时按需生成，不常驻原片特征库」——**他们是按需生成，不是常驻**。
   我方若要抄，也必须走按需路径，否则四片索引会再涨一截。
3. **我方精排窗 ±4s 已比竞品 DTW 起点窗（±30 帧 ≈ ±1s）更宽**，
   所以「窗不够大」不是缺口；**真缺口是 TopK（10 候选）vs 单点**。

## 5. 结论与建议

| 缺口 | 竞品有 | 我方有 | 优先级判断 |
|---|---|---|---|
| 精排采样率 10fps | ✅ | ✅ | 无缺口 |
| 精排窗宽 | ±1s | **±4s（更宽）** | 无缺口 |
| 增益门 0.04 | ✅ | ✅ | 逐字相同 |
| **TopK 重排（10 候选）** | ✅ | ❌ | ⚠️ **已于同日判负**，见 `FINDINGS_TOPK_RERANK_OFFLINE_20261019.md` |
| **长镜头局部 probe** | ✅ | ❌ | 但缺口性质不同（见 §4.1） |
| 帧级检索单元 | 需 probe 造 | **已有 features.npy** | 我方底子更好 |

**建议（按性价比排序）：**

1. **先做 TopK 重排**（不增索引、不增磁盘、不增解码）：把 `_apply_dense_start_recheck`
   从「单点精排」改成「取 top-10 候选各自的 10fps 窗做 DTW/代表帧重排」。
   竞品 `topk_rerank_min_scene_coverage = 0.8` 说明他们的判据 = 候选必须覆盖 ≥80% 的场景帧。
   这是**纯算法改动**，可先用真索引离线验证收益，不必先改生产。
2. **帧级滑窗召回**（不建 probe，直接用现成 `features.npy` 做滑窗相似度）：
   对长场景在召回阶段改为「帧级滑窗 + NMS」，而不是「场景指纹点积」。
   代价 = 每段查询的召回成本从 `[S]` 点积变成 `[T]` 滑窗，需实测墙钟。
3. **不建议**照抄 `long_scene_probe_*` 的常驻实现（磁盘/索引时间代价），
   那条竞品自己也只在「低内存模式」下按需生成。

## 6. 复现

```powershell
$PY = 'D:\claudework\video-dedup-tool\.venv\Scripts\python.exe'
cd D:\claudework\benchmark
$env:PYTHONPATH='mvp/src;mvp'
& $PY -u work\probe_ls2.py   # 读我方真实生效的定位参数
& $PY -u work\probe_ls3.py   # 量长场景占比
```

## 7. 边界（如实）

- **零 `mvp/src` 改动**。本文只做对比与测量。
- 竞品参数值来自 `data/cutmatch_param_values.json`（**从 options 字典取到的实测值**，不是推断）；
  语义来自 `data/module_semantics_20261017.json` 的 docstring。**两份都是静态面，未做动态验证。**
- **未实测**「TopK 重排能否带来收益」——这正是 §5 建议 1 要先离线验证的原因。
  本文只指出「我方没有这一层」，**不等于「加上就有效」**。
- 竞品长场景 probe 的**实际生成条件**未确证（只知道参数名与取值，不知触发路径）；
  §4.1 的「我方底子更好」是**基于代码结构的判断**，不是实测结论。

