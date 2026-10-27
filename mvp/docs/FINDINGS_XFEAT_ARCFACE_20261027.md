# FINDINGS — XFeat 起点精修 + SCRFD/ArcFace 替换（2026-10-27 续99）

> 口令「开始吧」，接续97待口令两项。先离线解混，再接线；smart render / HEVC 未动。
> 当前状态：ArcFace 已替换并通过门禁；XFeat 四片生产 A/B 已完成（严格 147→148、仅主 span
> 142→144、假阳 4→4、四片导出计划不变式全绿）。**2026-10-28 用户口令「1，翻默认」⇒
> `xfeat_start_enabled` 默认 True**（验收与边界见 §6；成本 ≈7~8s/行，已知未闭合、随翻默认接受）。

## 1. XFeat 离线实验

### 1.1 方法与判据

- 上游 `verlab/accelerated_features` commit `e92685f57f8318b18725c5c8c0bd28c7fe188d9a`，Apache-2.0。
- test1/2mkv/test2/test3 现役 dense 结果逐 GT 行取对应结果段；查询锚帧 = 结果编辑段起点
  `+min(0.25s, 段长×0.1)`。原片现役起点 ±4s@10fps，XFeat top_k=1024、MNN(cos>0.82)
  粗排前 5 + 现役点，再由 LighterGlue 复核。几何 = homography RANSAC 3px。
- 采纳门固定：matches≥12、inliers≥8、inlier_ratio≥0.20、较现役点 inliers 至少 +4；
  不满足则保留原起点。空关键点帧显式降级，不判负也不崩批。
- **GT 起点距离不是本实验的采纳尺**：多行 GT 是段/场景窗，读图证明数值更差时查询锚帧反而更准
  （例 t1r23）。主判据 = 全部实际改点逐张三联图（query / current / XFeat）判定锚帧对应；
  GT 距离只留作辅助，不用来推翻画面事实。

产物：`work/xfeat_probe_20261026/{probe.py,out_xfeat*.json,probe*.log,analyze.py,render_cases.py}`；
逐行裁决 `visual_review_{test1,2mkv,test2,test3}.json`，图 `sheet_{case}_*.jpg`（test1 图名 `sheet_all_*`）。

### 1.2 全部 117 个改点逐图结果

| 片 | 行级 更准/持平/更差 | 独立结果段 更准/持平/更差 |
|---|---|---|
| test1 | 26 / 3 / 3（32） | 20 / 2 / 3（25） |
| 2mkv | 12 / 21 / 2（35） | 12 / 19 / 1（32） |
| test2 | 10 / 9 / 1（20） | 9 / 6 / 1（16） |
| test3 | 8 / 22 / 0（30） | 8 / 20 / 0（28） |
| **合计** | **56 / 55 / 6（117）** | **49 / 47 / 5（101）** |

去重键 = `(edited_start, edited_end, current, guarded)`，由程序枚举，不手算。共享段包含
`t1r08a=t1g01`、`t2r05a=t2g04` 等，完整清单在各 visual_review JSON。

明确退化样例：test1 `t1r14a/t1r15/t1r19`（快速运动、人物姿态/遮挡变化）；
2mkv `p28`（`pg03` 同段，近景桌边人物变远）；test2 `t2r04b`（车侧近景变正前远景）。
这些不是“guard 已消灭”的反例，而是 runtime 回归锁；因此先 opt-in，不直接翻默认。

成本（离线同脚本、串行）：test1 44 行 353.15s（8.03s/行）；2mkv 43 行 303.21s（7.05s/行）；
test2 26 行 211.21s（8.12s/行）。只测了 GT 对应行，不代表全结果集总成本；生产成本以 A/B 为准。

## 2. SCRFD + ArcFace 解混与替换

### 2.1 只换嵌入判负，全栈成立

- 上游 `yakhyo/face-reidentification` commit `709b3903fc9503ddbec3436e712c08e4ce56ddbf`；
  官方 Release `det_2.5g.onnx` 3,292,009B + `w600k_mbf.onnx` 13,616,099B，CPUExecutionProvider。
- **YuNet 不变、只把 SFace 换 ArcFace**：正样本 p5=0.4967、负带 p95=0.6441、AUC=0.9552、
  p5−p95=−0.1474；同一人暗光样本 ci32 SFace 0.7516 → ArcFace 0.3632。故单点嵌入替换不成立。
- **SCRFD + ArcFace 全栈**：可判单脸正样本 11→23；up_single min/p5=0.6620/0.7890，
  负带 p95=0.2391，p5−p95=+0.5498，AUC=0.99986。旧 11 条逐条无低分回归，ci32 回到 0.6620。
  证明检测/对齐组合是承重因素，不能宣称“ArcFace 单独必然更强”。

产物：`work/arcface_probe_20261026/{probe.py,probe_scrfd.py,out_arcface_*.json,*log}`。

### 2.2 灰带来自现役近阈翻转读图

首版阈 0.51（全栈双带 p5/p95 中点 0.5141）在 302 行现役结果上可判 57→78，但有
`different→same` 一行和近阈可疑异人。逐图发现阈值两侧都存在不可硬判样本（test1#2 实际同人、
2mkv#67 疑似同人）⇒ 不加灰带会互造误标。落地 **阈值 ±0.10 一律 unknown**。

灰带后 302 行：

- 可判 **57→70**；`same↔different` 直接翻转 **0**；
- same→same 39、different→different 4；same→unknown 3、different→unknown 11；
- unknown→same 18、unknown→different 9、unknown→unknown 218。
- 覆盖提升与灰带保守性同时成立；近阈样本不再强行 same/different。

产物：`real_{case}.json`、`real_summary.json`、`eval_results*.log`、`flip_*.jpg`。

## 3. 产品接线（当前）

### 3.1 ArcFace（已替换）

- `engine/face_identity.py`：SCRFD 2.5G + ArcFace MobileFace、480 宽、两侧各 3 帧、质心 cos；
  仅两侧每帧均单脸才判，阈值 0.51 ±0.10 灰带 unknown；资产/推理失败仍整层/逐行降级。
- 不接定位、confidence、scenes 或自动导出判据。
- 资产安装 `install_face_models.py`；Windows 构建与包内资产锁已换成新两份 ONNX。

### 3.2 XFeat（2026-10-28 起默认开）

- `engine/xfeat_start.py` + `engine/xfeat_vendor/`（官方源码与 Apache LICENSE；仅相对导入、
  权重注入、强制 CPU 的适配改动）。`kornia>=0.8.3` 已声明。
- `PipelineConfig.xfeat_start_enabled=True`（2026-10-28 翻默认，见 §6）、`xfeat_start_margin_s=4.0`；挂点在全部定位修复后、
  人脸标注前。只移主 span 起点、宽度不变，不碰 confidence/子 span/alternatives；失败保留原起点。
- 资产安装 `install_xfeat_models.py`；Electron 注入、Windows 构建拷贝、包内两份权重锁已接。
- 未出包、未提交。**mac 不可直接 dispatch 本批**：工作流还需用户另行授权加入 kornia、
  XFeat 权重与新 SCRFD/ArcFace 资产；本批未改 CI。

## 4. 四片生产 A/B 与门禁

`rerun_toggle_ab.py xfeat_start_enabled` 已 ALL DONE；日志 `work/ab_xfeat_start.log`，stderr 空，
`BACKEND_SELECTED type=DirectMLBackend device=directml`。

| 片 | 生产改点 / 总行 | max shift | 严格 | 仅主 span | 假阳 | 导出不变式 |
|---|---:|---:|---|---|---|---|
| 2mkv | 56 / 84 | 3.45s | 43/43 → 43/43 | 42/43 → 42/43 | 3/4 → 3/4 | FAILED=0 |
| test1 | 36 / 55 | 3.52s | 42/44 → **43/44** | 41/44 → **42/44** | 0/1 → 0/1 | FAILED=0 |
| test2 | 36 / 67 | 3.98s | 25/26 → 25/26 | 23/26 → **24/26** | 0/1 → 0/1 | FAILED=0 |
| test3 | 70 / 103 | 3.65s | 37/37 → 37/37 | 36/37 → 36/37 | 1/3 → 1/3 | FAILED=0 |
| **合计** | **198 / 309** | — | **147→148** | **142→144** | **4→4** | **4 片全绿** |

逐字段差异锁：除 `result_id` 随机值和旧基线缺 `degenerate_warning` schema 外，
2mkv 首片只改变 56 个 `original.candidate_start` 与 face 标注；未改变 confidence、子 span、
alternatives 或其他定位字段。test1 唯一指标翻转 `t1r08c part→HIT`，test2 主 span 净 +1。

成本未闭合：四片 A/B 总 wall 10,661.2s，但基线来自历史批，不能按跨 run 方差宣称 XFeat 增量；
离线 GT 对应行为 7.05~8.12s/行，生产 309 行全量实际增量需同脚本双臂或历史同环境 wall 才能定。
因此本轮不翻默认。**2026-10-28 用户拍板翻默认开**（接受未闭合成本，见 §6）。

## 5. 已完成门禁

- 专项 **17 OK**（XFeat 5 + face 12，含真实硬样本 t1r14c=3135.94）。
- 后端全套 **758 OK(skipped=2)**；API **150 OK**；UI **166 passed**；双 typecheck rc=0。
- 四片生产三指标 + 导出计划不变式全绿（见 §4）。
- 未提交、未 push、未出包；mac 未更新且本批未改 CI。

## 6. 翻默认（2026-10-28，口令「1，翻默认」）

- **改动**：`PipelineConfig.xfeat_start_enabled` False → True（config 注释同步留档）；默认值锁
  `test_xfeat_start.test_default_on`（原 `test_opt_in_default_off`）断言 True。
- **默认路径同一性（承重前提，已核）**：A/B 腿 = `load_config()` 后 `setattr(pipeline,
  "xfeat_start_enabled", True)`；生产的唯一消费点 = `locator_service.py:1463` 的
  `getattr(config.pipeline, "xfeat_start_enabled", False)`；`load_config(path=None)` 返回纯默认、
  `settings.json` 只存 `device.preferred`、无其它覆盖源 ⇒ 翻默认后默认路径与 A/B 腿逐位同值。
  实测 `load_config().pipeline.xfeat_start_enabled=True`、`SourceLocatorService().config...=True`。
- **默认开态验收（对 A/B 四片产物，即默认开态）**：
  `check_export_plan_invariants.py --pattern "work/ab_xfeat_start_{case}.results.json"`
  ⇒ **FAILED=0**（4 片 × 4 通道）；`measure_four_results.py` 同脚本双臂复算：
  现役基线（dense_recheck 开 / xfeat 关，`work/ab_dense_recheck_{case}`）**147/150 · 142/150 · 假阳 4/9**
  → XFeat 开（`work/ab_xfeat_start_{case}`）**148/150 · 144/150 · 假阳 4/9**（与 §4 逐位一致）。
  另有代码漂移核对：A/B 产物之后 `mvp/src` 只有本次 config 改动。
  （注：`work/scn4_*` 旧批同脚本读数 146/141 不含 dense_recheck 默认开，不作本次对照基。）
- **门禁**：专项 5 OK（含真模型硬样本）· 后端 **758 OK(skipped=2)** · API **150 OK**。
- **成本**：≈7~8s/行（离线同脚本实测），随翻默认进入生产；未做同脚本双臂，**增量成本仍未闭合**。
- **边界**：只移主 span 起点、宽度不变，不碰 confidence/子 span/alternatives；资产缺失整层降级、
  单行失败保留原起点。现役 r29 包构建于 10-25，**不含 XFeat 代码与资产** ⇒ 本翻默认对 r29 无效，
  下次构建生效（`accept_packaged_bundle.py` 已有两份权重尺寸锁）。mac 侧仍需先授权改 workflow
  （kornia + XFeat 权重 + SCRFD/ArcFace 资产）。
