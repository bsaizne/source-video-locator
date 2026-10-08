# PROJECT INDEX

## Module

### Name

benchmark — 视频片段反向定位引擎 Benchmark

### Path

D:\claudework\benchmark

### Description

对视频匹配/复制片段定位引擎做统一、可重复、真实素材 Benchmark，为 Windows+macOS 桌面软件（Edited→Original 片段定位提取）选型。**Phase 1~19 已全部完成（算法研究冻结，recall_B 7/7、连续镜头定位可靠、真蒙太奇 s4 为可接受难例）；现进入 MVP 产品化（Source Video Locator）。MVP Stage 1 编码已完成——后端核心（`mvp/src/`：media/domain/infrastructure/device CPU+DirectML/engine 全链）+ `app/SourceLocatorService` + 统一日志 `infrastructure/logging` + **FastAPI 桥 `mvp/api/`** + **Vue3+TS+Electron UI `mvp/ui/`（Mock/Http 双模式，HttpServiceAdapter 已切真实后端，Backend Connection 三态检测）**。当前状态（2026-10-08 续63 补九）= 生产现役基线严格 **136/139** · 导出实得 131 · 场景 138 · 负例 4/9；测试门禁 后端 **617** / API **124** / vitest **144** / app+desktop 双 typecheck `rc=0`；现役分发包 = **r17**（回滚档 r16，r15 待删口令）；竞品对标线：数据段挖穿 + **E 层（算法差集）全线关闭**（ordered_search M0 判负、索引密度判负），差集 TOP1 两条半边均已收口 = 成片渲染（续30 移植并真实验收）+ **退化判据（续31 分腿归因：拒识形态第四次确证维持默认关，安全形态 LOC-2002 重复认领告警已默认开）**；**竞品成品端到端从未实测=授权阻塞，立场不绕授权**。待办见 `.agent/STATE.md` Next Actions（六项立项已全结案：①②③④ 落地、⑤ 与 ⑥b 分别裁决搁置/判负、⑥a/c/d 未跑）；下一批候选三件 = ~~修复链腿边界埋点 / 支持档 proactor 噪声降噪 / 跳格锁改按最大值口径~~ **已全部做完（补九）**；新增观测面 = 一次 locate 落 12 行 `locate leg=`（进支持档，售后可按档复核进度卡在哪条腿），现役 r16 包**不含**这三件 ⇒ 进包等 r17 授权；降噪的证据 = 历史真档 485 条逐条判据回归 + **真进程注入三臂双臂对照**（`work/r17_noise/probe_inject.py` J0-J6 全 PASS）+ 单测 6 项，残留一项 = 本机七种客户端强关打法都没让 OS 真报出该形态（详见 STATE `Current Problem`）。近期关键文档（按新→旧）：`competitor_cutmatch/FINDINGS_DEGRADATION_LEGS_AND_DUP_CLAIM_WARN.md`（续31 分腿+LOC-2002）、`FINDINGS_VIDEO_RENDER_PORT.md`（续30 成片渲染）、`FINDINGS_ORDERED_SEARCH_M0.md`（续28 E 层闭合，勿重试依据）、`FINDINGS_SOURCE_MERGE_PORT.md`（续27/29 多原片）、`FINDINGS_CAPABILITY_MAP_20260928.md`（差集总表，**对标缺口先看这份**）、根目录 `PROJECT_AUDIT_20260928.md`。产品实现树在 `mvp/src/`（含 `mvp/tests/` + `mvp/scripts/smoke_*.py`）+ `mvp/api/`（含 `mvp/api/tests/`）+ `mvp/ui/`。**

### Related Documentation

- `.agent/STATE.md` — **MVP 当前状态**（已完成/任务/决策/下一步；下一会话主要读这个）
- `.agent/TODO.md` — **MVP 待办**（P0 第 1~11 项）
- `.agent/DECISIONS.md` — **各阶段决策**（Phase 20、MVP Stage 1、UI 转向、FastAPI 桥、前端切真实后端）
- `PROJECT_HANDOFF.md` — 项目交接文档（全景，Phase 1~12；尾段新增 PART 2 到 Phase 19+MVP+前端切真实后端）
- `ARCHITECTURE_DECISION_PHASE20.md` — **Phase 20 最终算法架构决策**（研究收敛 + MVP 推荐 + 数据冲突）
- `mvp/docs/` — **MVP 产品化设计文档**（MVP_PRODUCT_SPEC / MVP_ARCHITECTURE / CONFIDENCE_DESIGN / INDEX_SPEC / DEVICE_BACKEND_SPEC / TECH_STACK_DECISION / THIRD_PARTY_NOTICES / MVP_ROADMAP）
- `TECHNOLOGY_SELECTION.md` — Phase 11 选型结论
- `benchmark_report.md` / `benchmark_report.html` — 三引擎实验报告
- `ENGINE_LICENSE_MATRIX.md` — VDF=AGPLv3、TransVCL/VCSL=MIT
- `MODEL_LICENSES.md` — 模型来源/License
- `ARCHITECTURE_ANALYSIS.md` — 跨平台集成分析（预判，待 Phase 12 修正）

---

## MVP 产品化实现树（mvp/src/，物理隔离于研究 src/）

| 路径 | 内容 |
|---|---|
| `mvp/src/media/ffmpeg/` | `FFmpegIO`（metadata/iter_frames/grab_frame/extract_clip/hash_file）+ ffprobe + `_runner`(subprocess 封装/MediaError/CREATE_NO_WINDOW) + **`source_merge.py`**（多原片入库前物理合并，续27）+ **`timeline_render.py`**（定位结果→成片，续30：CFR 逐段/中段 MOV+PCM/合并回退/帧数校验/停滞看门狗） |
| `mvp/src/domain/` | 纯数据：`TimeSpan/Candidate/Confidence/Alternative/Result/IndexMeta/ExtractorConfig/IndexValidation/IndexProgress` + 枚举 |
| `mvp/src/infrastructure/` | `errors(LocatorError/ConfigError/DeviceError)`、`logging`、`paths`、`config(AppConfig/MediaConfig/PipelineConfig/ConfidenceConfig)` |
| `mvp/src/device/` | `DeviceBackend`(Protocol) + 冻结 DINOv2 backbone + `CPUBackend`(H1) + `DirectMLBackend`(H2 AMD) + `resolve_backend`(能力探测/CPU fallback) + `pick_best_available` + `export_dml_model`/模型资产 resolver |
| `mvp/src/engine/feature_store/` | `FeatureStore`(create/load/validate/invalidate/get_metadata/delete) + `IndexBundle` |
| `mvp/src/engine/common/`、`retrieval/`、`clustering/`、`ranking/`、`candidates.py` | cosine REUSE、Top-K 检索、连续性聚类、`v2_score` 排序、`produce_candidates` 编排 |
| `mvp/src/engine/localization/`、`confidence/` | 精定位 `finloc_window`(per-orig coverage + longest_run + montage `multi_island`) + `pipeline.localize_segment`(`RefinedSegment`) + `ConfidenceEngine`(score+三档+reasons+montage_flag) + `degradation_gate.py`（竞品 results.validation：拒识门**默认关** + `min_scene_coverage` + 碎片告警 LOC-2001 + **`duplicate_claim_groups/warnings` 重复认领告警 LOC-2002**（续31 同构安全形态，只提示不删答案，默认开）） |
| `mvp/src/engine/segment/` | 无 GT 编辑侧查询单元切分：`ShotSegment` + `detect_shots`(局部 z-score + NMS + merge) + `adjacent_distances` |
| `mvp/src/app/` | 应用服务：`SourceLocatorService`(build_original_index/analyze_edited_video/locate/export_results/load_results) + `ProgressStage`/`ProgressEvent`/`CancellationToken` + `infrastructure/results_repo`(JSON 单文件批) |
| `mvp/api/` | **FastAPI 桥**：`app.py`(装配/路由/CORS/异常/session 中间件) + `main.py` + `schemas.py` + `dependencies.py`(AppContext/DI) + `routes/`(health/index/analysis/results) + `tests/test_api.py`(12 项) + `requirements.txt` |
| `mvp/ui/` | **Vue3+TS+Electron** 工作台：`src/services/`(ServiceAPI/Mock/Http/resolveService/types + `__tests__/` vitest 14 项) + `stores/`(session/analysis/results/projects) + `pages/`(Home/Projects/ProjectDetail/MediaLibrary/Analysis/Results/Settings) + `components/`(Fluent 自研 + BackendStatusIndicator 三态) |
| `mvp/tests/` | unittest（**2026-09-29 续31 实测全套 444 项**）：media / domain+infra / device+feature_store / retrieval+ranking / localization+confidence / segment / locator_service / directml / logging / flash_guard / twopass_flash / dense_start_check / offset_vote_prior / confidence_v2 / **degradation_gate(28)** / **source_merge(25)** / **timeline_render(29)** / **render_movie_service(16)** 等模块 |
| `mvp/scripts/review_progress_chain.py` | 进度链跳格复核（源码树记 on_progress，经产品自己的 `map_progress_stage`+`ProgressDebouncer` 换算；**按 pct 变化折叠**算停留；测量须独占设备） |
| `mvp/scripts/review_packaged_support_log.py` | 真实**支持档**事后复核（隔离链配对 / 会话账 / 腿标记 / ERROR 信噪比；`started==0` 判 N/A 不算 PASS） |
| `mvp/scripts/check_export_plan_invariants.py` | 导出计划四通道不变式常态守卫（4 片 × 4 通道，退出码可挂门槛） |
| `mvp/scripts/smoke_*.py` | 冒烟：media 23 / device+feature_store 25 / retrieval+ranking 6 / localization+confidence 9 / segment 6 |

---

## 核心源码（src/）

### 统一 runner 与工具

| 文件 | 用途 |
|---|---|
| `src/benchmark.py` | **主入口**。`--engine {vdf,transvcl,vcsl,dinov2_ta,transvcl_official,all}` × `--dataset {synthetic,real,all}`。逐 pair 跑引擎 → results/<engine>/<test>.json → 汇总 benchmark_results.json。⚠️ 覆盖式写入汇总 |
| `src/metrics.py` | 评估：`eval_pair` / `summarize` / `match_segments` / `load_ground_truth`（recall/precision/IoU/±0.5~2s/FP） |
| `src/report.py` | 报告生成 → benchmark_report.md/.html + report_summary.json（不写 benchmark_results.json） |
| `src/env_check.py` | 环境检测 → environment.json |
| `src/dataset_a.py` | synthetic A1~A12 素材 + GT 生成 |
| `src/orb_features.py` | ORB-BOW 256 维帧特征（`.npy` 缓存范式；TransVCL 旧版用，**已弃用于 Phase 12**） |

### Engine Adapters（src/adapters/，继承 base.py 的 `VideoLocalizationEngine`）

| 文件 | 引擎 | 状态 |
|---|---|---|
| `base.py` | 抽象基类（index_original/match/get_results + `_ok`/`_blocked`） | 核心 |
| `vdf.py` | VDF CLI（音频指纹 partial-clip） | ✅ 实测 |
| `vcsl.py` | 自研最小 pipeline（32x32 灰度 + 余弦 + Hough，**real 失效**） | ✅ 实测 |
| `transvcl.py` | TransVCL（ORB-BOW 特征，recall=0；Phase 12 弃用此特征源） | ✅ 实测 |
| `dinov2_ta.py` | **Phase 12 A**：DINOv2 vits14 + 单调 DP TA（0.5fps） | ✅ 已跑 real（recall=0，诊断中） |
| `transvcl_official.py` | **Phase 12 B**：官方 ISC21 特征 + TransVCL（1fps） | 代码就绪，待跑 |

### Phase 12 实验模块（src/experiments/）

| 文件 | 用途 |
|---|---|
| `dinov2_features.py` | DINOv2 vits14 手写 ViT-S/14 前向 + 0.5fps 采样 + 384 维 CLS 特征缓存 |
| `ta.py` | 自研单调 DP 时间对齐（余弦矩阵 → DP 路径 → cut_path → 片段合并） |
| `isc_features.py` | 官方 ISC21（isc_ft_v107）256 维特征 + 1fps 采样 |
| `failure_analysis.py` | 失败案例 A~J 十类分类 |

---

## 第三方引擎（engines/）

| 目录 | 内容 |
|---|---|
| `vdf/` | vdf-cli.exe 4.1.x 自包含二进制 + ffmpeg/ffprobe（AGPLv3） |
| `transvcl/` | TransVCL 官方 clone + `run.py`（已 fork 改 CPU 支持）；模型在 `D:\claudework\model_1.pth`/`model_2.pth` |
| `vcsl-official/` | alipay/VCSL 官方 clone（VTA/DTW 参考实现，本机未用它跑结果） |
| `isc21/` | lyakaap/ISC21 官方 clone（`create_model('isc_ft_v107')` 输出 256 维，权重 GitHub release） |

---

## 数据（datasets/）

| 目录 | 内容 |
|---|---|
| `synthetic/` | 90s 合成原片 + A1~A12 编辑版 + ground_truth.json（17 段） |
| `real/` | **真实素材**：`originals/2.mkv`（The Gorge 电影 7667s≈2.1h）+ `edited/1.mp4`（竖屏解说 126.8s）。GT 版本口径（2026-08-28 修订）：`ground_truth.json`=**v1，已多模态证伪，仅留档不用于评估**；2.mkv 现行=`ground_truth_v4.json`（39 正/4 负，v3 41 条为逐帧确认基准） |
| `real/`（GT 正式版） | **ground_truth_v4.json**（2.mkv 39 正/4 负，基线 32/39）+ **ground_truth_test1.json**（43 正/1 负）+ **ground_truth_test2.json**（20 正/1 负）+ **ground_truth_test3.json**（37 正/3 负，含 r14/r15 加长版负例）——2026-09-02 用户逐段人工复核正式化 |
| `mvp/benchmark/user_case/gt_review/` | test1-3 GT 草案/工作表/时间轴清单/基准：`ground_truth_test1/2/3_draft.json` + `GT_BASELINE_test1-3.md` + `GT_REVIEW_WORKSHEET_test1-3.md` + `TIMELINE_CROSSCHECK_test1-3.md` + `FINDINGS_TEST1-3_GT_BUILD.md` |

---

## 运行结果（results/）

| 目录 | 内容 |
|---|---|
| `vdf/` | synthetic 13 ok + a9 error；real error |
| `vcsl/` | synthetic recall 76%（precision 25%）；real 0 |
| `transvcl/` | synthetic + real 均 recall 0（ORB-BOW 特征不匹配） |
| `dinov2_ta/` | **Phase 12 A**：real recall 0，total_pred 0（诊断中） |
| `optional/` | Candidate D 预留 |

---

## 运行时缓存（work/）

| 目录 | 内容 |
|---|---|
| `dinov2_feats/` | DINOv2 特征缓存 `{alias}@0.5fps.npy`（1=64帧, 2=3830帧，已生成） |
| `dinov2_weights/` | DINOv2 vits14 权重（88MB，已校验） |
| `isc21_weights/` | ISC21 isc_ft_v107 权重（401MB，已下载） |
| `isc_feats/` | ISC 特征缓存（**未生成**，等 B 首次运行） |
| `transvcl_feats/` | 旧 ORB-BOW 特征缓存 |
| `vdf_*` | VDF staging 残留 |
| `dbg_*.jpg` | GT 诊断对比帧（edited20s / orig1296 / orig6599 等） |
| `rerun_*_timelineprior.results.json` | ②③ 单调弱先验新代码重跑结果批（2mkv/test1/test2/test3，2026-09-02） |

---

## 重要入口速查

- 跑 A：`D:\claudework\video-dedup-tool\.venv\Scripts\python.exe src/benchmark.py --engine dinov2_ta --dataset real`
- 跑 B：同上，`--engine transvcl_official`
- 重建汇总：`--engine all`
- 读结果：`results/<engine>/metrics.json`
- 报告：`src/report.py`

---

## 竞品「代理复现」通道（`D:\claudework\cutmatch-analysis`，只读）

> 定级纪律：一切产出标注「**代理复现（推断级）**」，**不是竞品实测**；对比只写「口径差异」。

### 结论文档（`mvp/benchmark/user_case/competitor_cutmatch/`）

- `FINDINGS_DEGRADATION_GATE_AB.md` — 竞品 results.validation 两条硬停门的我方移植与实测否决（−14/−12/±0，含逐图证据）。
- `FINDINGS_CAPABILITY_MAP_20260928.md` — 竞品 137 模块（103 叶子）× 我方实现穷举对齐表 A–F + 最终差集 TOP8。**对标缺口先看这份。**
- `FINDINGS_VIDEO_RENDER_PORT.md` — 续30 成片渲染移植：blob #138 字节确证清单 + 我方口径（紧凑拼接/原片音轨）+ **中段 AAC 造成 59 处接缝拉伸的实测结论与 PCM 解法** + 真实验收数字与覆盖缺口。
- `FINDINGS_SOURCE_MERGE_PORT.md` — 续27 多原片合并（竞品 video.concat）移植与验收；§4 含续29 UI 入口接线状态。
- `FINDINGS_ORDERED_SEARCH_M0.md` — 续28 ordered_search 第二套复现 M0 五轮判负（含伪影修复后消融）+ 索引密度 2fps 判负；**勿重试**依据。
- `SPEC_VS_IMPL_20260928.md` — 我方规格 vs 实现断链清单（A1–A5 已修 / G1–G9 在册）。

- `FINDINGS_PROXY_B_STAGE_REVIEW.md` — B 段判卷侧复核：帧数裁决（197,106）、模型字节级同一、ed 四片几何对照、**44/44 盲判全量裁决**、两条异议撤回。
- `FINDINGS_CUTMATCH_POSTPROCESS_REPLAY.md` — 后处理规则**逐帧复现确证（24/24）** + 换切点探针 + 对 FINDINGS/11 的答复。
- `FINDINGS_QUERY_UNIT_SWAP.md` — **D 段前置对照①**：查询单元换成竞品 t050 → 四片 −10/−15 + 多模态复审机制。
- `REVIEW_PROMPT_FOR_EXECUTOR_D.md` — D 段提示词复核/回执（7 条 P0 + 5 条口径混杂 + 7200→1800 更正 + P0-8）。
- `INTEL_REQUESTS_CUTMATCH.md` — 对执行方的需求与逐轮回执（§G/§H/§I）。

### 脚本

- `mvp/scripts/import_competitor_proxy.py` — 对方 `localization.json` → 我方 results schema；`--scene-split` 几何对照。
- `mvp/scripts/geom_proxy_vs_ours.py` — 代理切分 × 我方边界几何对照（4 片 × 4 阈值 + 稳定性 + 链式性）。
- `mvp/scripts/visualize_proxy_disputes.py` / `probe_qu_flip_visual.py` — 盲判图 / 翻转例多模态对照图。
- `mvp/scripts/replay_cutmatch_postprocess.py` — 后处理规则重放对拍（24/24）。
- `mvp/scripts/verify_cutmatch_profile_pairing.py` / `reconcile_cutmatch_bindings.py` — 常量绑定独立复核与系统对账。
- `mvp/scripts/proxy_query_unit_run.py` — 「只换查询单元」的定位对照 harness（四片 GPU）。
- `mvp/scripts/replay_degradation_gate.py` — 退化拒绝门/覆盖门槛**离线重放双臂**（同批同 GT 同判据，零 GPU）。
  ⚠️ 续31 起必须带 `--report <新文件名>`：输出路径曾硬编码，跑新批次会覆盖历史留痕。
- `mvp/scripts/probe_degradation_impact.py` — 重复认领**影响面统计 + 五臂分腿消融**（续31；拒识腿/子 span 腿
  分离、宽窄 span 与 GT 归属分桶、并查集分组），零 GPU 离线重放。
- `mvp/scripts/accept_duplicate_claim_warning.py` — LOC-2002 真实导出冒烟（四片 EDL 开关两侧逐字节比对）
  + 每条告警点名段的左右对照图（ffmpeg 精确 seek），产物 `work/dupwarn_accept/`。
- `mvp/scripts/review_degradation_visual.py` — 退化判据**全量**逐图复核出图（A 拒识段+覆盖邻居 /
  B 子 span 腿翻掉的 GT 行+被清掉的子 span / C 全部重复对），产物 `work/degradation_visual/`（16 张）。
- `mvp/scripts/probe_combo_caliber_all_cases.py` — **竞品整套四环链 × 四片双口径对照**（续31 补二）：
  R1 完整 span / R2 截查询等长 / R3 候选层名次 / R4 我方截等长 / R5 我方完整口径，
  产物 `work/combo_caliber_all_cases.json`。
- `mvp/scripts/probe_combo_pocket_visual.py` — 「复现链同粒度独家命中」逐条四格出图
  （GT_ED | GT_OG | PROXY | OURS），产物 `work/combo_pocket_visual/`。
- `mvp/scripts/review_high_wrong_segments.py` — 段级「HIGH∧主 span 不覆盖 GT」对象段三格出图
  （ED | OURS | GT）供逐条裁决，产物 `work/highwrong_visual/`（含 GT 复核工单 JSON）。
- `mvp/scripts/probe_gt_tickets_retrieval.py` — GT 工单自动判别：ED 帧 → 生产 CLS（DML 硬断言）→
  原片 1fps 索引 top-20，分 GT 疑错/同源重复/推翻读图/无效四类，产物 `work/gt_tickets_retrieval.json`。
- `mvp/scripts/review_retro_three.py` — 历史纯数据判负的补读图复核出图（ordered_search 回退 /
  密度翻转 / 合并拼接点两侧），产物 `work/retro_review_visual/`。
- `mvp/scripts/probe_split_patch_timing.py` / `rerun_split_patch_arms.py` / `time_full_locate_optimized.py`
  — 续34：两旋钮段耗时归因（monkey-patch 计时，不重跑整条 locate）/ 生产路径双臂四片复跑 /
  整条 locate A/B。产物 `work/spl_patch_timing/*`、`work/spl_patch_arms/*`。
- `mvp/scripts/attr_packaged_headless.py` — **打包态归因 harness（续36）**：以与 Electron 完全相同的
  env（release 通道 + 会话令牌 + 随机端口 + 包内 ffmpeg/模型 + 同一 `SVL_DATA_DIR` 复用索引）直接起
  包内 `backend.exe`，无 UI/无预览/无观察，轮询 `/api/tasks/{id}` 记录 (时刻,stage,message) + 轮询延迟 +
  后端进程 CPU。第 4 参 `mode=venv` = 用同一 harness 起源码树 `run_backend.py`（分离冻结包 vs 服务形态）。
  产物 `work/pkg_attr/{headless,venvhttp}_<case>.{events.csv,summary.json,results.json}`。
- `mvp/scripts/attr_env_phase_table.py` — 把 E2E 打包日志 / 各臂 events 折成同一张阶段耗时表（缺臂少列，不编数）。
- `mvp/scripts/attr_lab_arm_timestamped.py` — 给 venv 直跑臂加 elapsed 时间戳（rerun 产物先留痕再重跑）。
- `mvp/scripts/accept_packaged_bundle.py` — **包体验收（续36 新增，重打后必跑）**：patch 资产在位 +
  sha256 + 合成冒烟 `patch reranker device=dml` + 耗时阈值 + 出结果；对未修包实测 `FAILED=5`。
- `mvp/scripts/visual_gate_flips.py` — 被拒段逐图复核出图（QUERY / REJECTED / GT 三行）。
- `mvp/scripts/bench_perf_tiers.py` — 10/60/128min 三档性能实测（硬断言 DirectMLBackend）。
- `mvp/scripts/blind_sidechannel.py` — 盲判帧差旁证（跨点帧差 / 同侧基线）。

### 数据（`work/`）

- `proxy_geom_*.json` / `proxy_geom_summary.json` · `proxy_blind_disputes/`（44 张盲判图 + 答案键 + `verdicts_44.csv`）
- `replay_postprocess.json` · `binding_reconciliation.json` · `cut_swap_probe.json`
- `proxy_qu_*.results.json`（四片实验批）· `_four_{base,pqu}.json` · `qu_flip_visual/*.png`
