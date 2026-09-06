# Phase 24-2 · 局部 patch 级召回探针 M5 FINDINGS —— patch 特征作独立检索通道(召回层首次实测)
> ⚠️ **test4 数据错误(2026-09-01):** test4-ed.mp4 与 test4-om.mkv 为两部不同电影(81s竖屏 vs 71min横屏), 本文件中依赖 test4/t4r01 的结论全部作废(逻辑剔除, 详见 datasets/real/test4-INVALID.md)。

> 日期:2026-09-01 | 性质:**研究侧探针(零 runtime 改动, DML 双输出 ONNX, 918s)**
> 起因:用户拍板立项「patch 级召回」——E21/patch_rerank 都只在「CLS 已捞进池」的候选里做重排,
> patch **从未参与候选池构建**(召回层)。M5 首次实测:patch 级检索能否把失败族正确实例捞进候选池。
> 前置工程情报:项目 GPU 资产(DirectML ONNX)原本只导出 CLS;本探针新导出 **CLS+patch 双输出 ONNX**(研究侧临时资产 work/_patch_onnx_tmp/dinov2_cls_patch.onnx,
> 数值校验 CLS cos=1.0 / patch cos=1.000002, DML batch=1 17.98fps vs CPU torch 1.39fps ≈ **13× 提速**)——这是研究侧临时资产,不碰产品 models。
> 脚本:`mvp/scripts/research_patch_recall.py` | 数据:`work/patch_recall_results.json`

## 探针设计

- 每案例候选池 = **CLS top-200 ∪ 全索引均匀采样(~250 帧) ∪ 真值窗 ∪ 干扰窗**(混合池,~450-490 帧,包含真值);
- patch 打分 = E21 已验证的 **V3 指标**(每查询 patch 对候选帧 patch 的最大余弦, top-100 均值);
- 对照:CLS 全索引 best_rank(现有 features.npy) vs patch 混合池 best_rank/top-N/margin。
- **诚实口径**:混合池按构造**必然含真值**,故本探针测的是「真值若进入候选池,patch 能否把它排前 / 能否选中对实例」,
  不是「patch 从零在全索引捞真值」的召回成本。召回意义 = 进入候选池后的选中率,与 runtime 检索层直接相关。

## 结果

| 案例 | CLS 全索引 best_rank | patch 混合池 best_rank | top5/top10 | margin(true−dist) | 判定 |
|---|---|---|---|---|---|
| **p08** 兄弟机位 | 6 | **5** | 1/1 | +0.079 | ⚠️ 微改进(6→5) |
| **p08b** 兄弟机位 | **32** | **2** | 1/1 | +0.005 | ✅ **大胜(32→2)**,与 E21 一致 |
| **p26** 夜读 | 22 | 24 | 0/0 | **−0.050** | ❌ 无增益,干扰仍反超正确 |
| **p01** 易例(防回退) | 1 | 1 | 5/5 | — | ✅ 零回退 |
| **t3r12** 重复镜头 | 1 | 1 | 5/10 | +0.106 | ➖ 已 top-1,保持 |
| **t4r01** 同质滑梯 | 1 | 1 | 4/4 | +0.009 | ➖ 已 top-1,保持 |

## 关键发现

1. **patch 对「兄弟机位选对实例」有真实判别力(p08b 32→2)**:patch 最大匹配把正确机位(士兵特写 1048-1050)从 CLS 全局 32 名拉到混合池第 2,
   与 E21 实验结论一致——这不是新发现,而是**在含采样+干扰的更真实混合池里复现**。
2. **产品相关缺口**:runtime 检索 `retrieval_top_k=20`(冻结)——**p08b(CLS 32)与 p26(CLS 22)都超出 runtime 候选池**(不在 top-20),即 runtime 根本看不到它们。
   patch 能把 p08b 拉进池(32→2),但 **p26 无解**(patch 24, 干扰 sim 0.951 仍反超正确 0.900, margin −0.05)。
3. **p26 在 patch 层同样特征上限**:夜读/夜阳台在 CLS(混叠)与 patch(干扰反超)两层都不可分——印证 M1(M1b VLM 反向)/M3(CLIP 无判别)的结论,
   p26 维持「特征上限=已知局限」,patch 召回救不了它。
4. **易例零回退**:p01/t3r12/t4r01 全部保持 top-1,无 patch 引入的回归。

## 净结论

1. **patch 级信号 = 对「兄弟机位选对实例」有效, 对「夜读/同质」无效**。p08b 32→2 是真实、可复现、可在 runtime 落地的判别增益;
   p26 在 patch 层同样无解,失败族维持「特征上限=已知局限」的既有判定。
2. **若把 patch 召回 runtime 化**(宽候选池 + patch 评分),预期收益 = 兄弟机位族的一部分(p08b 型「CLS 池外但 patch 可分」)被救回,
   对 p26 无帮助。收益边界需用三指标回归实测(GT 中兄弟机位条目数有限,增益可能有限)。
3. **工程可落地性已验证**:DML 双输出 ONNX 18fps 且数值与 torch 一致——patch 召回/重排 runtime 化不再受「CPU 慢」或「资产只有 CLS」限制。
4. 探针零 runtime 改动;是否把 patch 召回接入 runtime 待用户拍板(接入须 bump feature_version + 三指标回归)。

## 相关产物

- 脚本:`mvp/scripts/research_patch_recall.py`;数据:`work/patch_recall_results.json`;
- 研究侧临时 ONNX:`work/_patch_onnx_tmp/dinov2_cls_patch.onnx`(CLS+patch 双输出,DML 校验通过;产物为研究侧,不入产品 models);
- 前置:E21(`phase21_probe_results.json`)/M1-M4(`semantic_signal/FINDINGS_M1/M2/M3/M4.md`)。