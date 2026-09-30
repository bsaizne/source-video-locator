# ViT-B/14 全量索引 + 四片 runtime 回归 FINDINGS(2026-09-25)

> **GT 版本**:`ground_truth_v4.json`(2.mkv) + `ground_truth_test1/2/3.json`(verified-139)。
> **性质**:**产品级回归** —— 用生产 `SourceLocatorService` 全链路(两级切分+白闪守卫、事件扩池、patch v2 重排、text anchor),
> 只换 CLS backbone(ViT-S/14 → **ViT-B/14**),对四片跑真实 locate 并按三指标评估。**零 `mvp/src` 改动**(env + config + 研究侧 monkey-patch)。
> **产物**:`work/vitb_{2mkv,test1,test2,test3}.results.json` · `work/vitb_four_metrics.json` ·
> 脚本 `mvp/scripts/export_dml_model_vitb.py`(ONNX 导出)、`mvp/scripts/rerun_vitb_runtime.py`(harness)、
> `mvp/scripts/measure_four_results.py`、`mvp/scripts/diff_four_batches.py`(评估/逐案对照)。
> **对照批**:`work/rerun_{case}_perfopt.results.json`(2026-09-06 生产同路径批,本会话用同一评估器复核 = **117/139**);
> ViT-B 索引/查询 batch=1(实测 7.0 fps 最优;原 ViT-S 基线 batch=8)。
>
> **一句话结论**:**换 ViT-B 全量索引 = 无增益、轻微负向** —— 严格 **117 → 116/139(−1)**、场景级 **137 → 134/139(−3)**、
> 负例 4/9 持平;27 个 GT 案例发生翻转(严格口径 12 改善 / 13 退化)= 抖动而非系统性提升。
> 叠加成本(索引 ~1.8× 慢、特征存储 ×2、ONNX 资产 88→347MB)→ **「该不该换更大基座」产品级定论 = 不换**。

---

## 一、方法(可复现,零源码改动)

1. **导出研究侧 ViT-B CLS-768 ONNX**(`export_dml_model_vitb.py` → `work/vitb_asset/dinov2_cls_768.onnx` + `.data` + `asset.json`,合计 346.5MB):
   复用冻结模型类 `DinoV2Small(embed_dim=768, num_heads=12)` + `dinov2_vitb14_pretrain.pth`;
   **torch↔ONNX 校验 cos=1.000000、max|d|=1.1e-5**(输入名 `input`/输出名 `embedding`,与 DirectMLBackend 契约一致,图不含 L2);
2. **隔离数据目录**:`SVL_DATA_DIR=work/vitb_data` → 索引/编辑缓存/导出全部独立,**不碰产品与历史索引**;
3. **研究侧 FeatureStore 子类**(harness 内 monkey-patch `app.locator_service.FeatureStore`):
   `feature_version=handwritten_vitb14_cls_768d@1_l2+scn1+evt1`、index.json 的 `feature_model=dinov2_vitb14`、
   validate 接受 768 维(其余快检 size/duration/fps/hash 原样复用);
4. **后端**:`device.onnx_model=` ViT-B ONNX、`dml_batch_size=1`(实测 ViT-B DML 7.01 fps @batch1 > 5.9-6.1 fps @batch2-16)、`preferred=directml`;
   启动打印 `BACKEND_SELECTED type=DirectMLBackend device=directml dtype=amd model=dinov2_cls_768.onnx`;
5. 其余**全部走生产路径**(`srv.locate(edited, original)`,默认 config);索引 **1 fps**(与基线一致),4 部原片共 **31,117 帧**;
6. 评估:`measure_four_results.py` → `measure_shot_recall.evaluate`(严格/场景级±15s/负例误报/支撑 span),两侧同 GT 同评估器。

## 二、结果(四片三指标)

| 片 | 基线 严格 / 场景 / 负例 / 支撑 | ViT-B 严格 / 场景 / 负例 / 支撑 | Δ严格 / Δ场景 |
|---|---|---|---|
| 2.mkv | 35/39 · 39/39 · 3/4 · 182/343 | **36/39** · 39/39 · 3/4 · 199/332 | **+1** / 0 |
| test1 | 34/43 · 42/43 · 0/1 · 109/220 | **35/43** · 40/43 · 0/1 · 101/203 | **+1** / **−2** |
| test2 | 14/20 · 19/20 · 0/1 · 71/229 | 14/20 · 19/20 · 0/1 · 77/233 | 0 / 0 |
| test3 | 34/37 · 37/37 · 1/3 · 230/349 | **31/37** · 36/37 · 1/3 · 220/309 | **−3** / **−1** |
| **合计** | **117/139 · 137/139 · 4/9 · 592/1141** | **116/139 · 134/139 · 4/9 · 597/1077** | **−1 / −3** |

### 逐案翻转(27 例;严格口径 12 改善 / 13 退化)

| 片 | 改善(→HIT) | 退化(HIT→part/MISS) |
|---|---|---|
| 2.mkv | p20, p30, p35 | p18(HIT→part), p41(HIT→part) |
| test1 | t1r02, t1r07a, t1r10b, t1r12a, t1r14b, t1r26 | t1r08a, t1r14a, t1r19(HIT→part);**t1r17, t1r18(HIT→MISS)** |
| test2 | t2r03b(MISS→HIT), t2r06a | t2r01a, t2r01c(HIT→part);t2r05a(part→MISS) |
| test3 | t3r03a | **t3r04c, t3r05, t3r06a, t3r16(HIT→part)**;t3r06b(part→MISS) |

### 失败集对比(MISS/part)

| 片 | 基线 | ViT-B |
|---|---|---|
| 2.mkv | p14, p20, p30, p35 | p14, p18, p41 |
| test1 | t1r02, t1r07a, t1r08b, t1r08c, t1r10b, t1r12a, t1r14d, t1r14b, t1r26 | t1r08a, t1r08b, t1r08c, t1r14a, t1r14d, t1r17, t1r18, t1r19 |
| test2 | t2r03b, t2r03c, t2r04a, t2r05a, t2r05b, t2r06a | t2r01a, t2r01c, t2r03c, t2r04a, t2r05a, t2r05b |
| test3 | t3r03a, t3r06b, t3r29 | t3r04c, t3r05, t3r06a, t3r06b, t3r16, t3r29 |

## 三、关键观察

1. **无一致增益,且最弱的一环更弱**:2.mkv/test1 各 +1,test2 持平,**test3 −3**;场景级 test1 −2、test3 −1。
2. **抖动而非提升**:27/139 案例翻转,改善与退化数量接近(12 vs 13)——同一管线下 backbone 更换带来的主要是"排序抖动",
   没有出现"某个失败族被整体救回"的模式。
3. **兄弟机位族(主定位层)未被解决**(与探针证据一致):
   p08 的编辑段 [12.6,14.3] 两侧都**靠子 span 枚举命中**(基线主 span 1061-1063 + 子 span 1106-1120;ViT-B 主 span 1034-1041 + 子 span 1108-1110),
   **主定位都落在兄弟机位区**(1017-1060),ViT-B 反而把置信档从 HIGH 降到 LOW。→ 与 `feature_upgrade_v4`(CLS rank 5-6)、`phase24_1_v4`(几何度量矛盾)一致。
4. **下游阈值随特征空间漂移**(换基座未重标定的必然后果):
   编辑侧切分段数 **2.mkv 69→66 / test1 41→37 / test3 67→60**(test2 54→54);
   置信档分布也变(2.mkv HIGH 46→40、LOW 11→17;test2 HIGH 28→34)——切分用的余弦距离阈值(z=1.5 / cut_abs=0.15)与置信度配置
   都是按 ViT-S 距离分布整定的,ViT-B 下不再最优。
5. **产品级结论与探针级结论收敛**:`feature_upgrade_v4`(局部窗口判别:两基座 5:4 互有胜负、失败族均不可分)+ 本次全量索引回归(严格 −1/场景 −3)
   → 「换更大基座」既无判别力增益,也无端到端收益。

## 四、成本对照

| 项 | ViT-S(基线) | ViT-B(本次) | 倍数 |
|---|---|---|---|
| DML 前向吞吐(batch=1, 518²) | ~13-14 fps | **7.01 fps** | ~2× |
| 四片索引墙钟(31,117 帧 @1fps) | ~47 min(按生产记录 ~11 fps 估算) | **~82 min**(实测:2mkv 21 / test1 21 / test2 13 / test3 27 min) | ~1.8× |
| features.npy 合计 | **47.8 MB**(11.8+12.6+7.8+15.6) | **95.8 MB**(23.6+25.3+15.5+31.3) | 2.0× |
| ONNX 资产 | 88.3 MB | **346.5 MB** | 3.9× |
| 四片 locate 墙钟 | ~54 min | ~55 min(2mkv 15.3 / test1 11.8 / test2 15.6 / test3 ~12) | ~1× |

## 五、边界(诚实声明)

- **这是一次「只换 backbone、下游阈值未重标定」的测试**:切分/最短镜头/置信度参数均为 ViT-S 口径,
  段数与置信档因此系统性漂移(§三.4)。严格公平的比较需要在 ViT-B 上重新标定这些参数并重跑基线——**另一项工作,且当前无证据表明值得**。
- **patch 重排两侧同为 ViT-S**:`resolve_patch_onnx` 回退到 repo `work/_patch_onnx_tmp/dinov2_cls_patch.onnx`(DML 双输出 ViT-S),
  即 CLS=ViT-B / patch=ViT-S 混合口径;该配置对两侧完全一致,但若正式换基座需一并换 patch 资产。
- **batch 口径**:ViT-S 基线 batch=8(生产默认)、ViT-B batch=1(实测最优)。已实测 DML batch 不变性:同帧集 batch1 vs batch8
  **cos=1.00000000、max|d|≤1.1e-6**(ViT-S 1.1e-6 / ViT-B 6.5e-7)→ 不构成对照偏置。
- **单次运行,无重复采样**:±1~3/139 的差异与 27 例翻转说明该量级差异**在管线抖动范围内**;
  本结论的强度在于"没有正向信号",而非"精确的 −1"。
- harness 通过 monkey-patch FeatureStore 支持 768 维索引;**若正式接入 ViT-B,需要把 dim/model 参数化进 `mvp/src`(索引 schema/validate/asset 解析)并补回归测试**——本次刻意不改源码。
- 未测 DINOv2-L/H、DINOv3(许可证另议);未测 ViT-B 全量索引 + 重新整定后的配置。

## 六、净结论与建议

1. **「该不该换更大基座(ViT-S→ViT-B)」= 不换(产品级定论,有据)**:
   端到端三指标无增益且场景级退化(116 vs 117 / 134 vs 137),成本翻倍级上升;
2. 该结论与 `FINDINGS_FEATURE_UPGRADE_V4.md`(探针级:无一致增益、失败族均不可分)**一致**,不再是"仅凭探针外推";
3. **基座路线正式关闭**(原结论"无增益"成立,但依据从"探针零增益 + p08b 恶化(后证为 GT 假象)"换成
   "探针无一致增益 + **全量索引端到端回归无收益**");
4. **保留复用价值**:本 harness(`rerun_vitb_runtime.py` + `measure_four_results.py` + `diff_four_batches.py`)是
   「一键换 backbone 做四片回归」的工具,未来 H4(CUDA)/DINOv3/其他 backbone 评估可直接复用(只需换 ONNX 与 feature_version);
5. **待拍板**:①是否把该 harness 固化为 `mvp/scripts/eval_backbone_swap.py`(含文档);②是否将本结论写入 `ARCHITECTURE_DECISION_PHASE20.md` 的"基座路线"附录。

> 执行者:AI 助手(2026-09-25)｜ 依据:ViT-B ONNX(torch↔onnx cos=1.000000) + 四片真实 locate 结果 + 同 GT 同评估器对照批(117/139 已复核)
