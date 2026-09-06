# PROJECT INDEX

## Module

### Name

benchmark — 视频片段反向定位引擎 Benchmark

### Path

D:\claudework\benchmark

### Description

对视频匹配/复制片段定位引擎做统一、可重复、真实素材 Benchmark，为 Windows+macOS 桌面软件（Edited→Original 片段定位提取）选型。**Phase 1~19 已全部完成（算法研究冻结，recall_B 7/7、连续镜头定位可靠、真蒙太奇 s4 为可接受难例）；现进入 MVP 产品化（Source Video Locator）。MVP Stage 1 编码已完成——后端核心（`mvp/src/`：media/domain/infrastructure/device CPU+DirectML/engine 全链）+ `app/SourceLocatorService` + 统一日志 `infrastructure/logging` + **FastAPI 桥 `mvp/api/`** + **Vue3+TS+Electron UI `mvp/ui/`（Mock/Http 双模式，HttpServiceAdapter 已切真实后端，Backend Connection 三态检测）**。当前待办 = WS 进度/取消/预览 → Electron 打包/真机验收 → 性能基准 + Confidence 标定。产品实现树在 `mvp/src/`（含 `mvp/tests/` + `mvp/scripts/smoke_*.py`）+ `mvp/api/`（含 `mvp/api/tests/`）+ `mvp/ui/`。**

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
| `mvp/src/media/ffmpeg/` | `FFmpegIO`（metadata/iter_frames/grab_frame/extract_clip/hash_file）+ ffprobe + `_runner`(subprocess 封装/MediaError) |
| `mvp/src/domain/` | 纯数据：`TimeSpan/Candidate/Confidence/Alternative/Result/IndexMeta/ExtractorConfig/IndexValidation/IndexProgress` + 枚举 |
| `mvp/src/infrastructure/` | `errors(LocatorError/ConfigError/DeviceError)`、`logging`、`paths`、`config(AppConfig/MediaConfig/PipelineConfig/ConfidenceConfig)` |
| `mvp/src/device/` | `DeviceBackend`(Protocol) + 冻结 DINOv2 backbone + `CPUBackend`(H1) + `DirectMLBackend`(H2 AMD) + `resolve_backend`(能力探测/CPU fallback) + `pick_best_available` + `export_dml_model`/模型资产 resolver |
| `mvp/src/engine/feature_store/` | `FeatureStore`(create/load/validate/invalidate/get_metadata/delete) + `IndexBundle` |
| `mvp/src/engine/common/`、`retrieval/`、`clustering/`、`ranking/`、`candidates.py` | cosine REUSE、Top-K 检索、连续性聚类、`v2_score` 排序、`produce_candidates` 编排 |
| `mvp/src/engine/localization/`、`confidence/` | 精定位 `finloc_window`(per-orig coverage + longest_run + montage `multi_island`) + `pipeline.localize_segment`(`RefinedSegment`) + `ConfidenceEngine`(score+三档+reasons+montage_flag) |
| `mvp/src/engine/segment/` | 无 GT 编辑侧查询单元切分：`ShotSegment` + `detect_shots`(局部 z-score + NMS + merge) + `adjacent_distances` |
| `mvp/src/app/` | 应用服务：`SourceLocatorService`(build_original_index/analyze_edited_video/locate/export_results/load_results) + `ProgressStage`/`ProgressEvent`/`CancellationToken` + `infrastructure/results_repo`(JSON 单文件批) |
| `mvp/api/` | **FastAPI 桥**：`app.py`(装配/路由/CORS/异常/session 中间件) + `main.py` + `schemas.py` + `dependencies.py`(AppContext/DI) + `routes/`(health/index/analysis/results) + `tests/test_api.py`(12 项) + `requirements.txt` |
| `mvp/ui/` | **Vue3+TS+Electron** 工作台：`src/services/`(ServiceAPI/Mock/Http/resolveService/types + `__tests__/` vitest 14 项) + `stores/`(session/analysis/results/projects) + `pages/`(Home/Projects/ProjectDetail/MediaLibrary/Analysis/Results/Settings) + `components/`(Fluent 自研 + BackendStatusIndicator 三态) |
| `mvp/tests/` | unittest 9 模块（media 6 + domain/infra 12 + device/feature_store 4 + retrieval/ranking 7 + localization/confidence 10 + segment 11 + locator_service 12 + directml 10 + logging 8）≈ 80 项 |
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
| `real/` | **真实素材**：`originals/2.mkv`（The Gorge 电影 7667s≈2.1h）+ `edited/1.mp4`（竖屏解说 126.8s）+ ground_truth.json（7 段，**不可修改**） |
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
