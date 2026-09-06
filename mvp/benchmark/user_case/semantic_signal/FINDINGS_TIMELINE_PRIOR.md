# 单调弱先验进候选生成（NEXT_STEPS ②③，2026-09-02 拍板实施）——实测零触发

> 做法: 把「编辑序≈原片序」作为候选生成阶段的弱倾向（非仅事后修复）。对 Ambiguous 型段
> （>=2 保留证据簇）用前序段定位中点做时间轴锚点：primary 在带外(>ta_band_s=45s)且存在
> 带内竞争候选(cover 落差<=ta_max_cover_drop=0.10)时, 切换 primary 到带内候选。
> 逃生门: 唯一强候选/首段/前段未定位/primary 已在带内/全部带外 均不触发（真实回溯 8/29 不误伤）。

## 一、实现与回归

- 配置: `pipeline.timeline_prior_enabled`(True) + `ta_band_s`(45) + `ta_max_cover_drop`(0.10)。
- 代码: `locator_service._apply_timeline_prior` + `_locate_features` 接线（prev_mid 锚点维护 +
  tl_switched 留痕 reason `timeline_weak_prior`）。
- 单测 8 项（切换/逃生门全路径）；**全套 222 项全绿**（214 原 + 8 新增）。

## 二、真实数据重跑（新代码含 timeline_prior，复用现有索引）

用新代码重跑 2.mkv + test1-3 全部分析（结果批存 work/rerun_*_timelineprior.results.json），
再用新 GT（v4 + test1/2/3 正式版）跑三指标，新旧对比:

| case | 旧严格 | 新严格 | 旧场景 | 新场景 | 旧FP | 新FP |
|---|---|---|---|---|---|---|
| 2mkv | 32/39 | **32/39** | 36/39 | 36/39 | 2/4 | 2/4 |
| test1 | 32/43 | **32/43** | 38/43 | 38/43 | 0/1 | 0/1 |
| test2 | 9/20 | **9/20** | 10/20 | 10/20 | 0/1 | 0/1 |
| test3 | 31/37 | **31/37** | 34/37 | 34/37 | 2/3 | 2/3 |

**结论: timeline_prior 真实数据零触发 / 零影响（新旧三指标完全一致）。**

## 三、零触发原因分析（为什么没有带外 primary + 带内竞争候选）

用 2.mkv 29 段 montage 段（original_segments>=2）逐段检查 primary 与前序锚点距离:

- **大多数 montage 段的 primary 离前序锚点 >45s（带外）**（s1/s3/s6/s7/s9/s11/s12/s13/s14/s15/
  s17/s18/s20/s22/s24/s25/s27 等），但**带内不存在 cover 接近的竞争候选** → 无候选可切。
- **兄弟机位型错配（p08）恰恰相反**: primary 1048 离前段 1015 仅 33s（**带内**），真值 1108 离
  前段 93s（带外）——时间轴先验不仅不能纠 p08, 反而会把真值当"带外"排除。**先验对兄弟机位族
  结构性无效**（与 M8 邻接唯一性证伪呼应: 兄弟机位邻接同样貌）。
- 真实跳切段（s12 -1619s / s14 +1698s 等）本就全部带外 → 逃生门生效不误伤。
- 唯一历史离群修复案例（s7 temporal_repair 2400→1403）已在**事后**由 temporal_repair 处理,
  候选生成阶段先验没有独立增量。

## 四、结论（有据）

1. **单调弱先验在候选生成阶段 = 零增量（实测）**——当前特征架构下不存在"时间轴可纠但
   repair/conflict 未处理"的段; 时间轴先验的存量价值已由事后 temporal_repair(+1 p16)兑现。
2. 实现本身正确且安全（逃生门全绿, 零回归, 默认开零扰动）——作为**护栏保留**不关闭。
3. 与 NEXT_STEPS ⑧ 呼应: r10 由 conflict_rerank（几何重叠+内容证据）修复, 非时间轴先验。
4. **方向收窄**: 时间轴先验的进一步价值不在"候选生成弱先验", 而在已实现的"事后离群修复"
   + "时间轴→Ambiguity 降档"(②⑥ 已编码)。**不建议再投入候选生成级先验调参**（零信号）。
5. 保守化标定(⑦)仍是校准阶段正事——test1-3 全量 GT 已就绪可标。

## 相关产物
- 代码: `mvp/src/app/locator_service.py`(_apply_timeline_prior) + `infrastructure/config.py`
- 测试: `mvp/tests/test_timeline_prior.py`(8 项)
- 数据: `work/rerun_2mkv|test1|test2|test3_timelineprior.results.json`(新代码重跑)
- 评估: `mvp/scripts/eval_timeline_prior.py` + `rerun_timeline_prior.py`
