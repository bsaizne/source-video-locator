# 交接：蒙太奇段子镜头查询方向（2026-09-05，已结案 = runtime 不接入）

> 状态：**已结案（2026-09-05 会话二执行 §4 清单完毕）**。漂移触发判据修复后四片三指标
> 零变化（113→113/139），且「16/16 逐子救回」被证实为 oracle 口径（按 GT 挑子镜头）,
> runtime max-sim 采纳结构性选错 → 按 §4.4 接收为研究结论, runtime 不接入。
> 完整证据见 FINDINGS_SUBSHOT_QUERY.md「runtime 接入验证」章。以下原文留档。

## 0. 一句话结论

蒙太奇段（多镜头拼贴，如 test2 t2r02b = BOUGHT/THEN/CROP/WAS/WATERED 快速切换）**用整段
单均值查询会语义稀释**。**帧级距离突变可清晰识别子镜头**，**逐子镜头独立查询能救回**
（gap 从 15~2072s 缩到 <4s，16/16 零回退）。但**落地完整管线后**：无差别拆分→回退
（严格 34→31）；定向回退→未触发救回（p10 主定位漂移判据漏掉）。**触发判据是未解决核心障碍**。

## 1. 探针证据（可靠）

### 1.1 个体探针（research_subshot_query.py）—— t2r02b 救回
t2r02b（ed17.2-23.5, GT og2931 Jacob）6fps 帧级距离突变分离 6 子镜头。
段首子镜头 A（Jacob BOUGHT）独立查询 → **2934（GT 2931, sim 0.625）命中**；
整段均值 → 3303（洒水器, sim 0.537，Jacob 稀释）。

### 1.2 规模化验证（research_subshot_scale.py）—— 16/16 救回零回退
| 片 | 多镜头蒙太奇段 | 逐子改善 | 回退 |
|---|---|---|---|
| 2.mkv | 4 | 4 | 0 |
| test1 | 1 | 1 | 0 |
| test2 | 7 | 7 | 0 |
| test3 | 4 | 4 | 0 |
| 合计 | 16 | 16 | 0 |

代表性：test2 t2r07b 2072->1.1s / t2r03b 1849.7->0.3s / t2r05a 570.8->3.8s; 2.mkv p34 1069->5.0s / p10 92->0.0s。

### 1.3 多模态确认（本模型视觉）
t2r02b = BOUGHT(Jacob特写)/THEN(洒水器)/CROP/WAS(乡村房屋)/WATERED(洒水器)/BUT 快速蒙太奇。GT og2931=段首BOUGHT正确。整段均值稀释 Jacob。

## 2. 已实现代码（runtime 改造，含未解缺陷）

### 2.1 locator_service.py 新增
- `_subshot_relocalize(self, shot, bundle, dense, cfg)`（约 L967）：帧级距离突变拆子镜头，逐子 localize，取 best_sim 最高。返回 `(evidence, best_sim)`；不足 6 帧/子镜头<3 返回 `(None, -1.0)`。
- `_locate_features` 两处触发（约 L709/L719）：no_evidence 分支整段失败→子镜头回退；montage 弱命中（mode==montage and cur_sim<0.62）→回退，sub_sim>cur_sim 才采纳。

### 2.2 config.py 新增（PipelineConfig）
- `subshot_cut_thresh=0.5` / `subshot_enabled=True` / `subshot_min_sub=3` / `subshot_retry_min_sim=0.62`。

### 2.3 关键缺陷（未解决）
- **触发判据漏掉主定位漂移型**：p10（ed16.6-20.3）主定位 1144.5-1146.5 LOW（GT 1300-1302 偏 156s），montage 段，original_segments 有接近 GT 的 (1294.2,1308.8)/(1287,1316)，但主定位选 cover 最高的 1144，all_spans max sim 可能 >=0.62 → 不触发。
- 根因：用 `evidence.all_spans` 的 max sim 判整段弱，montage 段 all_spans 里有高 sim span 掩盖主定位漂移。应改用主定位 span best_sim 或 最佳span 与主定位 gap 大 判据。

## 3. 关键测量数据（regression baseline 对照）

### 3.1 基线批（无子查询, 精度版 twopass+flash）
4 片严格: 2.mkv(backup) 34/39, test1 34/43, test2 12/20, test3 32/37。（备份在 work/_backup_pre_subshot_rescue/）

### 3.2 无差别子镜头拆分（rerun_subshot.py 拆所有段）
2.mkv: 严格 **31/39**（34->31 回退 -3），段数 69->85。**证明无差别拆分不可行**。

### 3.3 定向子镜头回退（当前 locator_service 版, no_evidence+montage弱命中）
2.mkv: 严格 **34/39**（0 跌 0 涨）, p10 未救回（still 1144）——**判据未覆盖漂移型**。

## 4. 下一步执行清单（下个对话从这开始）

1. **修触发判据**：montage 触发改用「最佳span与主定位 gap 大」或「主定位 span best_sim < 子镜头最优 sim」判据（而非 all_spans max sim）。目标：救回 p10/p34 等主定位漂移型 montage 段，不伤害正确段。
2. 重跑四片（SVL_FORCE_RERUN=1 + SVL_DML_MODEL 指向真实 onnx）→ measure_shot_recall 对比基线批（work/_backup_pre_subshot_rescue/）。
3. 若严格净正且零回退 → 立项 runtime 化（加 config 开关；评估性能）。
4. 若收益有限（仅 16 段且判据难调）→ 接收为研究结论，runtime 不接入（FINDINGS 已记录）。

## 5. 避免的坑（教训）

- **无差别拆分所有段 = 回退**（拆坏原本正确整段）→ 必须条件触发。
- **触发判据不能只看 sim**——montage 段主定位漂移错位但 sim 不低，需看主定位 vs 候选 gap。
- **抽帧要密集采样**（避免抽错帧误判）。
- **路径用正斜杠**避免 \u 转义。

## 6. 相关产物

- 探针: research_subshot_query.py（个体）+ research_subshot_scale.py（规模化）+ rerun_subshot.py（无差别版已废弃）。
- FINDINGS: FINDINGS_SUBSHOT_QUERY.md（含规模化章）。
- 代码: locator_service._subshot_relocalize + config subshot_* 参数（含未解判据缺陷）。
- 数据: work/rerun_*_runtime_twopassflash.results.json（当前）+ _backup_pre_subshot_rescue/（基线）。
- 关联: FINDINGS_TEMPORAL_MONOTONICITY.md（附3 t2r02b 蒙太奇段单均值查询缺陷）。
---

## 7. §4 执行结果（2026-09-05 会话二, 结案记录）

1. 漂移触发判据（gap>15s & psim<0.62 + 合并采纳）已实现并四片重跑 → **三指标零变化**。
2. 机制三层阻断（漂移段早已 HIT / oracle 口径 / 近重复簇掩盖）全部实证, 见 FINDINGS。
3. 严格净正不成立 → 按 §4.4 接收为研究结论, **runtime 不接入**（代码已回退, 246 全绿）。
4. 若未来重开: 需要无 GT 的「正确子镜头选择信号」（正确子镜头 sim 未必最高）,
   例如编辑侧非外观信号; 现有证据不支撑继续投入。
