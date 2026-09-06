# ① p28/p36 召回层深漏验证 FINDINGS —— 两条都不是召回层问题, 均为定位/选择问题(2026-09-04)

> 性质: 研究侧验证(零 runtime 改动, 用 rerun 批 + 全索引检索链复现)
> 起因: V4_MISS_RECHECK 判 p28/p36 为「真漏/召回层未覆盖」, 需验证是否候选池(top-20)问题。
> 结论: **两条的正确帧都在 CLS top-20 池内(M6 v4: p28 rank 5 / p36 rank 2), 非召回层问题;
> p28 已被新管线修复(HIT), p36 是定位/选择层问题(机制已复现)。**

## 一、p28 —— rerun 批已 HIT, 旧「深漏 800s」是旧结果批快照

- rerun_2mkv_timelineprior.results.json: ed 86.0-89.0 → original **1828-1840**(LOW), 覆盖 GT 1833.15-1836,
  measure 判 **HIT**(s19 main 1828-1840)。M6 v4: cls_best_rank_full=5、patch=1、IN_POOL。
- V4_MISS_RECHECK 的「main[1828-1840] 全在 1800-2050、差 800s」基于 **旧 user_results.json**(pre-时序修复),
  新管线(temporal_repair/conflict_rerank/重跑批)已把该段修正到正确区。**p28 从剩余真漏移除。**

## 二、p36 —— 正确帧在池内(rank 2/3), 但被「单帧簇门槛 + scene 回退漏选」两级淘汰

### 2.1 检索层: 正确帧明确进池
- 全索引 CLS top-25: 2042(rank 3, sim 0.729)、2043(rank 5, 0.712)——top-20 内; M6 v4: cls=2/patch=1。

### 2.2 定位层机制(EvidenceLocalizer 复现): 两级淘汰
- 查询 = ed 110-111.5 段 2fps 3 帧; 帧级 argmax 各自分散: frame→1856 / **2042** / 2829;
  → 2042 是其中一帧的 argmax(单例簇), 但 cluster_by_gap 后每簇仅 1 帧, **过不了 min_frames=2 门槛**,
     sig 为空 → 走 scene 回退(mode=clean via scene_units);
- scene 回退: 查询均值 qf 的 scene_top-5 = 297(0.763)/235(0.757)/216(0.685)/217(0.614)/228(0.605)
  —— **正确 scene 232[2034-2044](含 2042-2043.4)不在 top-5**(其 sim 更低, 未显示), scene 回退也不含正确区;
- 最终 spans: 1869-1884(cover 0.543)/2060-2065(0.278)/2829-2834(0.216), primary=1869-1884(cover 最高)
  → runtime 主定位 2060.5-2062.5(frame_precision moment 命中该区), GT 2042-2043.4 差 ~18.5s(略超 ±15s 场景级线)。

## 三、判定与影响

1. **p36 不是召回层失败**(检索池有正确帧), 是「查询帧 argmax 分散→单例簇被 min_frames 门掉 +
   scene 回退 top-5 未含正确 scene」的**定位/选择层问题**。
2. **已证伪的假设**: V4_MISS_RECHECK「p28/p36 = 召回层未覆盖(top-20 池外)」不成立——M6 v4 已证明
   39/39 全部进池; 本验证进一步确认两条剩余 MISS 的正确帧也进池。**2.mkv 无召回层缺口。**
3. **剩余问题焦点转移**: 2.mkv 真漏只剩 **p36**(定位选择)与 **p08**(兄弟机位特征上限, 已知);
   p28 已修复。p36 的可修方向 = ①scene 回退扩到含正确 scene(当前 top-5 全错区, 需更多 scene 或
   更高 min_sim); ②单帧簇门槛放宽(1 帧簇若 best_sim 显著高可保留)——均属算法侧改动, 按护栏需评估
   收益后再立项(仅 1 条 GT 的收益, 低 ROI)。
4. 零 runtime 改动; 三指标 v4 基线不受影响(研究验证)。

## 相关产物

- 数据: work/rerun_2mkv_timelineprior.results.json(p28 HIT 行) + work/patch_recall_gt_results_v4.json(p28/p36 行)
- 复现: 本会话脚本(检索链 + EvidenceLocalizer 复现, 未入库)