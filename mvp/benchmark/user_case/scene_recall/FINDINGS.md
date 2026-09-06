# Phase 21 场景指纹召回扩展层 — FINDINGS(2026-08-30)

> 交接执行单:场景表(索引侧)+ 证据扩池(检索后)+ 回归门槛 + 单测 + 收尾。
> 原型:`mvp/scripts/research_scene_retrieval.py`(p26 场景指纹 12→3);实验证据:`scene_retrieval_results.json`。

## 结论(TL;DR)

1. **场景表 + 扩池已产品化,默认开**(`scene_recall_enabled=True`)。帧级主定位/置信度与基线**逐段零漂移**;场景 span 只作附加子 span 与救回。2.mkv 严格召回 39/41(基线同口径 38/41,**+1 = p33 真救回**),负例 2/4 持平,p27 保住。
2. **两条硬教训(多模态/评测器实证)**:
   - 扩池帧并入同一证据池重聚类 → 簇桥接+均值稀释,25/29 段被改写、HIGH→LOW 塌陷(已废弃);
   - 场景 span 进重排器候选(seq DP 池 / text anchor 晋级窗)→ DP 全局路径改写(p27 主定位被挤到被证伪的 1859)+ OCR 巧合晋级错误位置(test2 s7 人物 A→人物 B、test1 s18/test3 s10 跳近黑画面)。
   - **定案:场景 span 不进任何重排器**(patch/DP/text anchor 一律不消费),仅 ①附加子 span(带 `from_scene_pool` 标记,UI 可识别)②帧级零证据时的救回主定位(诚实 LOW)。
3. **评测器 mid_in 规则 bug 修复**(`measure_shot_recall.py`):原式 `o0 <= GT中点 <= b` 漏了下界——任何 b≥GT中点的 span 都算"命中中点"(p08 的假 HIT 由此而来)。修复为 `a <= GT中点 <= b`;基线与新结果同口径重测。
4. p26(夜读)仍未解决:帧级有强错误簇(0.87)→ 非零证据,救回路径不触发;场景指纹 top-5 在该查询段上未把真值场景送进附加 span。特征上限问题依旧,需更强特征(Phase 21 遗留)。

## 实现(产品代码)

- **索引侧**(`engine/feature_store/feature_store.py`):`create_index` 落盘 `scenes.npy`([S,2] 起止秒,连续覆盖)+ `scene_feats.npy`([S,384] L2 场景指纹 = 场景内帧均值);`_build_scene_table` 用 `detect_shots(cut_abs=0.15, z_thresh=1.5, min_shot_s=3.0, smooth=1)`(research 验证口径);`feature_version` bump `+scn1` 触发自动重建;`validate_index` 纳入场景表存在性(缺失 → INVALID "scene table missing");`IndexBundle` 增 `scenes/scene_feats`(None=旧索引,扩池降级)。
  - 注:2.mkv 实测 699 场景(均值 11s);研究原型的 349 场景(均值 22s)来自其秒级量化去重伪影(`int(round(end))+1` 去重),非设计行为,未复刻。
  - 迁移:`mvp/scripts/backfill_scene_tables.py` 对既有 @1_l2 索引从缓存特征确定性派生场景表+更新版本(等价于重建,免 ~50min GPU 重 embed;5 个真实索引已回填)。
- **检索后扩池**(`engine/localization/evidence_localize.py`):
  - 帧级路径(聚类/门控/mode/primary/置信诊断)**逐行保持基线语义**;
  - 场景单元 = 查询均值 vs 场景指纹 top-`scene_top_k`(5) 场景,场景内帧(预算 `scene_max_expand_frames`=120,超长场景 linspace 截断);每场景独立过门(场景内帧均值 ≥ min_sim,≥min_frames)——**场景是扩池单元,不做时间重聚类**(实测时间相邻场景互相桥接);
  - 场景单元独立 finloc 精化(`_locate_cluster`,查询均值代表)→ `_gate_scene_spans`(与子 span 门同口径的严格门 + 与帧级保留 span/相互 IoU 去重 + 上限,**无保底**);
  - 帧级零证据时场景 span 晋级主定位(救回路径,mode=clean,诚实 LOW);
  - 配置:`scene_recall_enabled/scene_top_k/scene_max_expand_frames`(PipelineConfig,JSON 可覆盖)。
- **app 层**(`app/locator_service.py`):场景 span → `original_segments` 附加段,`domain.OriginalSegment` 增 `from_scene_pool`(序列化对称;UI types.ts 镜像);**text anchor 晋级窗跳过 `from_scene_pool`**;patch/DP 池不消费(场景 span 不进 `all_spans`,救回段除外)。

## 回归门槛(同环境+同口径:场景关对照 vs 场景开,均为今日 DirectML 跑批)

| 指标 | 场景关(对照,scene_recall_enabled=False) | 场景开(最终) |
|---|---|---|
| 严格召回 | 38/41 (verified 34/37) | **39/41 (verified 35/37)** |
| 场景级(±15s) | 39/41 | 39/41 |
| 负例误报 | 2/4 | 2/4 |
| 有支撑 span | 52/64 (81%) | 90/136 (66%) |
| 主定位/置信 | — | **逐段一致(2.mkv 29 段、test1-4 对照零漂移)** |

- 对照组与 08-29 基线数字完全一致(38/41、52/64)→ 管线可复现;**+1 = p33**(ed102.5-112 → GT og2044-2054):s21 新增场景子 span **2043-2053** 落入 GT±2 → 从"场景级 part"升级严格 HIT,纯由场景扩展贡献。
- MISS 不变:p08、p26。
- 门槛 ③ "≥37/41 不回退" ✓;"p27 型不被翻车" ✓(s18 主定位保持 1809-1811);test3 s1 / test4 s0/s6/s9 的 no_evidence 段获场景救回(诚实 LOW)。达标 → **默认开**。
- 诚实代价:新增 ~30 个无 GT 支撑的场景子 span(支撑率 81%→66%);它们是 LOW 质量附加候选(带 `from_scene_pool` 标记),换取救回通道与 p33 类收益。
- **环境漂移事件(重要,影响未来基线对比)**:本阶段发现 venv 内 `onnxruntime` 1.29.0(纯 CPU)覆盖了 `onnxruntime-directml` 1.24.4 的同名包文件(疑 08-29 装 rapidocr-onnxruntime 时引入)→ DirectML 失效静默回退 CPU。已恢复 `onnxruntime-directml==1.24.4`(DML provider 回归,rapidocr 兼容已验证)。教训:**跨日基线对比必须核对后端日志 `backend selected=directml`**,特征数值微差足以翻转边缘决策(本次 test1-4 相对 08-29 文件基线的 34 处主定位漂移全部由该事件导致,scene-off 对照复现同样漂移、scene-on vs scene-off 零漂移)。
- 过程版本留档:`user_results_scene_v1_churn.json`(池混聚,废弃)、`user_results_scene_v2.json`/`v3_textanchor.json`(重排器消费场景 span,废弃)、`user_results_sceneOFF_control.json`(同环境对照)、`cases/test2_sceneOFF_control.json`、`cases/_scene_v3_*`。

## test1-4 泛化(最终跑批 scene_cases_run2.log + 对照)

- 汇总档位与 08-29 基线逐案例一致(test1 33段 H28/L5/NIS2;test2 9段 H3/L6/NIS1;test3 34段 H24/M3/L7/NIS1;test4 18段 H3/M1/L14)。
- **场景扩展主定位零漂移**:scene-off 对照 vs scene-on,四案例主定位/置信 **0 差异**;新增 = 附加场景子 span(+276)与 no_evidence 段场景救回(test3 s1 / test4 s0/s6/s9 → LOW 结果)。
- 相对 08-29 文件基线的 34 处主定位差异 = **onnxruntime 环境漂移**(scene-off 对照完全复现,见上),与场景扩展无关;该批差异未逐段多模态裁决(属环境回归课题,非本阶段范围)。
- 抽检(`spotcheck_mains.jpg`,9 样本,v3 版本):发现 text anchor 按 OCR 巧合晋级场景 span 的风险路径 → 加入"场景 span 不参与主定位改写"护栏(重排器一律不消费);最终版本主定位=帧级基线,无需再抽检。

## 遗留

- p26 类(帧级强错误簇)非扩池可解:需更强特征或场景身份主信号(研究结论不变)。
- 场景子 span 的 UI 展示(InspectorPanel 标注"场景候选")= 后续 UI 轮;`from_scene_pool` 字段已透传。
- 无支撑子 span 增多(81%→66%)可接受性待用户反馈;可调 `scene_top_k`/门控收紧。
