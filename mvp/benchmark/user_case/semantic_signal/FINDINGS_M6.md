# Phase 24-2 · GT 级 patch 召回覆盖探针 M6 FINDINGS —— 41 条 GT 的 CLS/patch 全索引召回统计

> 日期:2026-09-01 | 性质:**研究侧探针(零 runtime 改动, DML 双输出 ONNX, 6633s ≈ 110min)**
> 起因:用户拍板「跑完 41 条 GT 再决定 patch 召回 runtime 化值不值」——M5 只测了 6 个探针点, M6 扩到全量 GT,
> 统计到底有几条是「CLS 全索引 rank>20(runtime 候选池外)但 patch 能排进混合池 top-20」的。
> 脚本:`mvp/scripts/research_patch_recall_gt.py` | 数据:`work/patch_recall_gt_results.json`

## 探针设计

- 查询 = 每条 GT 正例编辑窗中点 ±0.4s 三帧 → CLS 均值 + patch 拼接;
- CLS 全索引 best_rank(免费, 现有 features.npy @ q_cls_mean);
- patch 混合池 = CLS top-200 ∪ 全索引均匀采样(~250) ∪ 真值窗, V3 patch 打分;
- 判定: CLS best_rank>20 且 patch 混合池 best_rank<=20 → RESCUE(runtime 漏掉但 patch 能捞进池)。

## 结果: RESCUE 1/41, CLS 池外 10 条中 patch 只救回 1 条

| 类别 | 数量 | 案例 |
|---|---|---|
| CLS 已在池内 | **31/41** | 全部易例(CLS best 1-12) |
| CLS 池外 → **patch 救回** | **1/41** | **p13**(峡湾直升机航拍: CLS 188 → patch **1**) ✅ |
| CLS 池外 → patch 未救回 | 9/41 | p05(178→159)/p10(63→127)/p20(465→23)/p23(96→41)/p24(2514→259)/p26(22→24)/p32(78→99)/p38(340→225)/p41(103→100) |

## 关键发现

1. **patch 召回在 GT 全量口径下只值 +1/41(p13)**: 41 条里 31 条 CLS 本来就在池内(patch 无增量), 10 条池外中
   patch 只救回 p13 一条(188→1)。这明显低于「≥2-3 条才值得 runtime 化」的门槛。
2. **已知难例全部未被 patch 救回**: p26 夜读(CLS 22→patch 24, 特征上限三形态再确认); p24(CLS 2514→patch 259);
   p41(CLS 103→patch 100); p10(CLS 63→patch 127)。
3. **⚠️ M5 的 p08b 32→2 与 M6 的 p38(同一目标区域 1048-1050, CLS 340→patch 225)矛盾**: 归因 = 查询帧选取不同
   (M5 用编辑 13.9s 三帧, M6 用 GT 编辑窗 [12.5,14.0] 中点 13.25s 三帧; 该编辑段是快剪瞭望塔/士兵特写交替,
   中点帧抓到的子镜头内容不同)——**patch 的「救回」对查询帧选取高度敏感, M5 的 32→2 高估了 patch 的稳定性**。
4. **p20 最接近救回(CLS 465→patch 23, 差 3 名进 top-20)**——patch 有弱信号但不足以过池线。

## 净结论

1. **patch 召回 runtime 化 = 不值(数据)**: 全量 GT 口径下只救 +1/41(p13), 且 M5 的正面信号(p08b 32→2)在更忠实于
   GT 的查询口径(M6 p38)下不复现——patch 召回信号不稳定。代价(patch 全索引 + bump feature_version + 全量重建 + runtime 复杂度)
   远大于收益。**方向与 M1-M4 同路径: 用数据关闭, 不 runtime 化。**
2. **p13 留档**: CLS 188→patch 1 是唯一被 patch 真实救回的 GT 正例(峡湾直升机航拍, 纯视觉、非多模态),
   未来若做「patch 作为弱加权第二召回通道」的折中, p13 型是其受益面——但收益仅 1/41, 当前不立项。
3. **失败族维持「特征上限=已知局限」**: p26(夜读)/p24(锯木女 1588-1598)/p41(夜阳台走位)/p38(兄弟机位)
   在 CLS 与 patch 双通道下均无解, 与 M1(M1b VLM 反向)/M3(CLIP 无判别)/M4(密度无增益)/M5(patch 重排无解)证据链闭合。
4. 零 runtime 改动;三指标 39/41 未动。

## 交接

- **patch 召回方向 = 关闭(有据)**: M6 全量 GT 显示仅 +1/41 且信号对查询帧敏感; M5 的 p08b 正面在 M6 p38 不复现。
  档案留证: 脚本 + 数据 + 本 FINDINGS, 与方向 A/C 归档并列。
- **工程情报保留**: DML 双输出 ONNX(CLS+patch) 18fps 数值一致(cos=1.0), 属研究侧临时资产 work/_patch_onnx_tmp/, 不碰产品 models;
  未来若真要做 patch 相关, 无需再验证 GPU 可行性。
- **护栏状态**: 2026-09-01 用户逐条拍板(解除13/保留15)已写入 6 处文档, 本次探针零 runtime, 与护栏无关。

## 相关产物

- 脚本:`mvp/scripts/research_patch_recall_gt.py`;数据:`work/patch_recall_gt_results.json`;
- 前置:M5(`semantic_signal/FINDINGS_M5.md`)/E21(`phase21_probe_results.json`)/M1-M4(`semantic_signal/FINDINGS_M1/M2/M3/M4.md`)。