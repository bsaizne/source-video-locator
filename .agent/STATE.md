# PROJECT STATE

## Project

视频片段反向定位引擎 Benchmark → **Source Video Locator MVP**（D:\claudework\benchmark）

> **项目状态：ALGORITHM_RESEARCH_FROZEN / MVP_DEVELOPMENT_ACTIVE（2026-08-25）**
> 算法研究已冻结收尾；进入 MVP 产品化（Source Video Locator）。研究结论见 `ARCHITECTURE_DECISION_PHASE20.md`；MVP 设计文档见 `mvp/docs/`。

> **硬件路线（2026-08-25 用户拍板锁定）**：H1 Windows CPU → H2 **Windows AMD GPU(DirectML)** → H3 macOS Apple Silicon(MPS) → H4 Windows NVIDIA(CUDA)。**不支持 macOS Intel**。`DeviceBackend` 必须保持可扩展——未来加 `CUDABackend` 不改上层 FeatureStore/Retrieval/Ranking/Localization/Confidence/UI。CUDA 不进当前实施阶段。
>
> **AMD GPU POC（`mvp/poc/amdgpu_onnx/`，独立、未接入 MVP）= `AMD_BACKEND_GO`**：RX 6750 GRE + ONNX Runtime DirectML + 冻结 DINOv2 ViT-S/14 CLS-384。15.15 fps，10.39× 加速，Top-1 邻居一致、embedding 数值稳定、500 帧无 NaN/norm 异常。
>
> **H2-Preflight（`h2_preflight.py`，2026-08-25）= `MEMORY_STABLE`**：2.mkv@0.5fps 建索引 3834/3834 帧全跑完，内存 278.5→336.8MB（+58.3MB，全部为首批~250帧一次性 warmup；之后 328–337MB 窄带波动，非线性增长），all_finite / norm=1.0，无 DML allocator 错误，全片 323.9s、11.84 fps。
>
> **H2 = `DirectMLBackend` 已正式接入并验证（2026-08-25）→ `H2_AMD_DIRECTML = IMPLEMENTED`**：
> `mvp/src/device/directml_backend.py`（`DeviceBackend` 实现，复用冻结 `_imagenet_preprocess`，ONNX+DML provider，numpy L2）+ `device/resolve_backend(preferred="auto")` 统一 resolver（能力探测 + 自动 CPU fallback + 明确日志 fallback_reason）+ `device/resolve_dml_model`/`asset_meta`（模型资产 resolver）+ `infrastructure.DeviceConfig`（preferred/onnx_model/dml_device_id/dml_batch_size）+ `mvp/scripts/export_dml_model.py`（从冻结模型重导出产品 ONNX 资产到 `<app_data>/models/dinov2_cls_384/` 含 `asset.json`）。
> 验证：全套 72 项测试过（含新增 `test_directml_backend.py` 10 项：A 类无 GPU→fallback/probe 结构/B 类 AMD 实机推理+CPU 正确性 cos>0.999+FeatureStore 完整兼容 create/load/validate/invalidate）；真实 2.mkv 生产索引构建 `smoke_directml_backend.py`：381.3s / 3834 帧 / 10.06 fps / `[3834,384] float32` / 内存 +53.4MB 稳定 / `IndexMeta.backend="directml" feature_version=...@0.5_l2`（与 CPU 同 schema，不复制 store）/ reload 0.002s。相比 H1 CPU ~3793.6s ≈ **9.95× 墙钟加速**（vs POC 324s 略高 +18%，因生产路径含文件哈希/持久化/探测开销）。**下一步 = UI（第 8 项，当前暂停）或继续按 roadmap**。

---

## Current Phase

**MVP 产品化 — Stage 1（编码）进行中**：已完成第 1~7 项 + **H2（Windows AMD GPU / DirectMLBackend 已接入并验证，`H2_AMD_DIRECTML=IMPLEMENTED`）**。**第 8 项 PySide6 UI 仍暂停**（用户重定向；此前已完成 DirectML POC→Preflight→接入）。算法研究 Phase 1~19 已冻结收尾。

> **2026-08-26 — H3（macOS Apple Silicon / MPS）POC 完成 → `H3_MPS_GO`**（真实 Apple Silicon 验证通过，GitHub Actions 云端跑成功）。**repo**：`bsaizne/source-video-locator`（private→public；push 走 SSH——本机网络 HTTPS 443 被阻断、SSH 22/443 可达；DNS=小米路由 192.168.31.1 解析到 GitHub 20.205.243.x 段但 443 握手超时）。已 `git init` + 完整 `.gitignore`（排视频/权重/特征/第三方引擎/工具二进制/研究代码 `src/`/phase 报告/生成物/凭据/IDE）+ 入仓 `mvp/`、`.github/workflows/h3-macos-mps.yml`、`.agent/`、设计/研究结论文档；**含修复：`.gitignore` 无锚 `src/` 曾误忽略整个 `mvp/src`（致 CI checkout 缺 `device/dinov2_model.py`），已改 `/src/`**。**H3 POC = GO**：macOS 15.7.7 / arm64 / torch 2.13.0，`device_mps_actual=mps`（确认非 CPU fallback）、权重下载+sha256 通过、正确性 cos_mean=1.0 / max_abs_diff=6.3e-7 / mps norm deviation 1.19e-7、7.875× 加速（0.87→6.84 fps；batch=4 最佳 6.67；batch≥8 触发 `Invalid buffer size 5.37GiB` + 暴跌 2.83fps）、500 帧 all_finite 无异常无 fallback、峰值内存 ~1.07GB。**关键约束：MPS batch_size ≤4（推荐 4）**——未来正式 `MPSBackend` 必须遵守。CI workflow 已改 **workflow_dispatch-only**（手动；不 push 自动触发，避免每次 push 烧 macOS runner）。`mvp/src/device` 零改动；无 MPSBackend / UI / H4。POC 见 `mvp/poc/macos_mps/`。

---

## Current Task

1. **PySide6 UI**（Home→Index→Results→Export + 预览 + 手动修正 + 批量导出，消费 `SourceLocatorService`）。
2. 打包（PyInstaller）+ 真机验收 + **性能基准**（10/60/120min）+ **Confidence 标定**（`CONFIDENCE_DESIGN.md` 权重/阈值用真实数据校准）。

## Completed

- **2026-08-25 — `media/ffmpeg`（FFmpegIO）完成**：`mvp/src/media/ffmpeg/`（FFmpegIO + ffprobe + subprocess 封装）。禁用 cv2.CAP_PROP_POS_MSEC，改走 ffmpeg/ffprobe subprocess；`metadata`(format.duration 处理 MKV N/A)/`iter_frames`(流式 rawvideo pipe, 时间基采样, 不缩放)/`grab_frame`/`extract_clip`(精确重编码)/`hash_file`。冒烟 23 项 + unittest 6 项全过，真实 2h08m HEVC MKV 随机定位与帧精度验证通过。
- **2026-08-25 — `domain` + `infrastructure` 完成**：`mvp/src/domain/`（纯数据：TimeSpan/Candidate/Confidence/Alternative/Result + IndexMeta/ExtractorConfig/IndexValidation + 枚举，`to_dict()` 输出产品契约 JSON）+ `mvp/src/infrastructure/`（errors 模型 `LocatorError`/`ConfigError`、logging、paths 数据/index/export 目录、config `AppConfig`/`MediaConfig`/`PipelineConfig`/`ConfidenceConfig` + JSON 覆盖）。`MediaError` 已改为继承 `LocatorError` 统一错误模型。unittest 12 项 + media 复测全过。
- **2026-08-25 — `device/CPUBackend` + `engine/feature_store/FeatureStore` 完成**：`mvp/src/device/`（`DeviceBackend` Protocol + 冻结 DINOv2 backbone 提取 `dinov2_model.py` + `CPUBackend`(无 CUDA, 线程可配, ctypes 内存) + `pick_best_available`(H1 恒 CPU, 预留 H2/H3)）+ `mvp/src/engine/feature_store/`（`FeatureStore` create/load/validate/invalidate/get_metadata/delete, 按 INDEX_SPEC 落盘 `index.json`+`features.npy`+`times.npy`, 失效判定 size→duration→model/dim/fps/version→hash 硬检, `.stale` 隔离; `IndexBundle`）。device smoke 25 项 + FeatureStore/CPUBackend unittest 4 项全过; DINOv2 CPU 真推理 L2 norm=1.0。**`engine/segment` 当时未实现（属 roadmap 第 6 项，已于 2026-08-25 完成，见下）**。
- **2026-08-25 — `engine/retrieval` + `engine/clustering` + `engine/ranking` 完成**：`mvp/src/engine/common/similarity.py`(cosine REUSE)+`retrieval/`(retrieve_hits, 批量 Top-K K=20, orig_times[top_idx])+`clustering/`(_cluster_continuous 连续性感知 10/15/60s + _merged_ok + _bridges, build_candidates→domain.Candidate)+`ranking/`(v2_score = mean*sqrt(hit)*(0.5+0.5*cons)*n_reps^alpha alpha=0.5, rank_candidates)+`engine/candidates.py`(produce_candidates 编排)。**删除了 GT/benchmark/gid/实验路径/work 依赖**；`_dp_path`/`temporal_align`/`localize`/`edited_window_feats`/`_recall`(GT 依赖) 均 RESEARCH_ONLY 未进 runtime；`retrieval_top_k` config 占位 100 改为冻结 20；domain.Candidate 增加 `scene_div`(montage 指示)。retrieval smoke 6 项 + unittest 7 项全过。**注意：合成图案场景 CLS 易混淆，v2_score 会把非 GT 宽窗排前——冻结公式在真实影片数据(研究已验证)表现正常，属已知数据/模型属性**。
- **2026-08-25 — `engine/localization`(finloc longest_run + montage 检测分支) + `engine/confidence/ConfidenceEngine` 完成**：`mvp/src/engine/localization/`(finloc_window=per-orig max-over-query coverage + 3帧平滑 + mask(thresh=0.4 冻结) + longest_run→精确 span + multi_island 结构信号; pipeline.localize_segment=候选→finloc 最佳→回填 best_cover→confidence→RefinedSegment; montage/无 span/run 过短→original 退化候选窗范围)+`engine/confidence/confidence.py`(ConfidenceEngine.assess: rank/margin/n_reps/qcov/consistency/sim_std/scene_div + best_cover/span_stability/coverage_quality/multi_island→score+三档+reasons+hard_flags+montage_flag+alternatives)。**置信度权重/阈值全部为未标定占位**(CONFIDENCE_DESIGN §6)，已纳入 `ConfidenceConfig`(infrastructure/config.py, JSON 可覆盖)供 H1 标定；`engine/localization/__init__` 不 import 编排避免与 confidence 循环导入。禁 per-query argmax/voting/cut-aware/temporal align/改 similarity·ranking。researchnotes：synthetic v2_score 混淆使 smoke 的 top 候选非真值(已知属性, 见上文)；真值定位由 deterministic unittest 覆盖。localization/confidence unittest 10 项 + smoke 9 项全过；全套 46+ 项回归通过。
- **2026-08-25 — `engine/segment`（无 GT 编辑侧查询单元切分）完成**：`mvp/src/engine/segment/`（`ShotSegment` 模型 [span + feats + times 切片, 直接喂 produce_candidates/localize_segment] + `detect_shots` + `adjacent_distances` + `_merge_short`）。**算法**：相邻帧余弦距离 `d=1-cos`（复用冻结 cosine 语义, O(N) 点积）→ **局部 z-score 判别**（`z=(s-局部均值)/max(局部σ,floor)`，边界需 `z>=2` 且 `s>=cut_abs=0.30`——修正了"相对基线在 max() 下是死代码"缺陷，也正对应研究"绝对阈值 d 不可靠"证伪结论）+ **默认平滑窗=1**（不平滑保留单帧 cut 锐利尖峰，分析发现平滑窗 3 会拉平块边界 z≈1.15 漏检）+ NMS(min_gap=max(1,round(min_shot_s*fps))) + merge(过短段并入更弱边界一侧) + 无边界/单帧/空→回退整段 1 查询单元。**整体偏向下切分**（产品约束：过长可接受、过短/碎片化更危险）。`PipelineConfig` 平铺加 4 个占位字段 `seg_cut_abs/seg_z_thresh/seg_min_shot_s/seg_smooth`（3 个接线点 + JSON 覆盖验证通过）。segment unittest 11 项 + smoke(真 ffmpeg+DINOv2 3色多镜头) 结构不变式全过、输出诊断统计；全套 50 项回归通过。研究护栏：未改任何冻结算法、无 GT、未做 sweep、未重引入 Phase19 原片 cut-aware；多模态未触发（冒烟结构合法）。冒烟 3 纯色片段 CLS 混淆未切分=已知合成图案属性，非 segment 缺陷。
- **2026-08-25 — `app/SourceLocatorService`（application service：用例编排 + 失败隔离 + progress + cancellation + 错误翻译 + Result 汇总）完成**：`mvp/src/app/`（`models.py`：`ProgressStage`(7 阶段) + `ProgressEvent{stage,current,total,message}` + `CancellationToken`(threading.Event)；`locator_service.py`：`SourceLocatorService`(build_original_index / analyze_edited_video / locate / _locate_features / export_results / load_results；ffmpeg+backend+FeatureStore 惰性构建)）+ `infrastructure/results_repo.py`（`save_results/load_results` 单文件 `*.results.json` 批信封）+ `infrastructure/errors.py` +4（`IndexError/FeatureExtractionError/LocalizationError/ApplicationError` 均 `LocatorError` 子类）+ `domain/models.py` 增 `Result.failure_reason` + `Confidence/Alternative/Result.from_dict()`（对称 to_dict）+ `ResultBatch`(schema_version/original_video/edited_video/results[])。**编排**：locate(edited, original) = 原片 validate→(重)建→load + 编辑侧 iter_frames@2.0fps→embed_frames→detect_shots + 逐 segment produce_candidates→localize_segment→拼 `domain.Result`(edited=shot.span)。**失败隔离**：单 segment 抛错→unresolved(LOW + failure_reason + 日志 exception)+继续后续段；cancellation 抛 `ApplicationError` 不落入段级隔离。**健壮性**：确定性 unittest 12 项 + 全套回归 62 项通过；synthetic 端到端冒烟通过（a1 命中 HIGH、export/reload 往返、cancellation、失败隔离）；**修复 app 级 bug**：`_result_from_refined` 曾传 `shot` 而非 `shot.span` 致 `Result.edited` 被塞进 ShotSegment（已修）。**真素材首次完整管线跑通（§十，仅观察不调算法）**：2.mkv(1GB)索引 3834 帧/3793.6s + 1.mp4@2fps 254 帧→12 段/158.0s + 12 Results(HIGH5/MEDIUM1/LOW6, unresolved 0, candidate 485) + export/reload 往返 + cancellation + 失败隔离；total 3951.9s；peak_ram N/A（venv 无 psutil）。研究护栏：只编排不改冻结算法语义、无 GT、未 sweep。

## Current Problem

- None identified.

## Current Implementation

- `mvp/src/` 已构建模块树：`media/ffmpeg`（FFmpegIO）、`domain`、`infrastructure`、`device/`（CPUBackend）、`engine/feature_store`（FeatureStore）、`engine/common|retrieval|clustering|ranking`、`engine/candidates`、`engine/localization`（finloc + montage + pipeline）、`engine/confidence`（ConfidenceEngine）、`engine/segment`（ShotSegment + detect_shots）、`app/`（SourceLocatorService + ProgressStage/ProgressEvent/CancellationToken）。
- 测试：`mvp/tests/` 7 模块 61 项 unittest（media 6 / domain+infra 12 / device+feature_store 4 / retrieval+ranking 7 / localization+confidence 10 / segment 11 / locator_service 12）；`mvp/scripts/smoke_*.py` 冒烟（media 23 / device+feature_store 25 / retrieval+ranking 6 / localization+confidence 9 / segment 6 / locator_service 真素材+synthetic）全过。
- 冻结栈已贯通：FFmpegIO 抽帧 → CPUBackend(DINOv2 CPU) 特征 → FeatureStore 落盘索引 → retrieval/clustering/ranking 产出候选窗 → localization 精定位(最长连续 run + montage 检测) → confidence 三档置信 → **`app/SourceLocatorService` 逐个查询单元（`engine/segment`）串联整链并汇总 `domain.Result`，JSON 单文件批持久化**。**尚未接上 UI（第 8 项）**。

## Current Decision

- 第 1~4 项关键决策：FFmpegIO 走 ffmpeg/ffprobe subprocess（禁 cv2 CAP_PROP_POS_MSEC；mkv 用 format.duration）；clip 提取 = `-ss before -i` 重编码 libx264（精确，非 stream copy）；采样时间基 `t=i/fps`（不复刻研究帧索引基）；FeatureStore 落盘 `<stem>__<hash8>.idx/{index.json,features.npy,times.npy}`、失效判定 size→duration→model/dim/fps/version→hash 硬检、旧索引转 `.stale` 隔离；`retrieval_top_k`=20(冻结)；`v2_score` alpha=0.5(冻结)；domain.Candidate 增 `scene_div`（montage 指示）、`best_cover` 留占位由 finloc 回填。
- 第 6 项 `engine/segment` 关键决策：`ShotSegment` 放 **engine 层**（domain 禁 numpy；先例 `Hits`/`LocalizationResult`）；切分**判别用局部 z-score**（非裸绝对阈值——研究 Proof 绝对 d 不可靠；相对基线 `max(cut_abs, cut_rel*base)` 是死代码已弃），`cut_abs` 仅作下限安全垫；**默认平滑窗=1**（不平滑保留单帧 cut，平滑会把单帧边界拉平致漏检）；**整体偏向下切分**（产品约束：过长可接受、过短/碎片化更危险），NMS+merge+min_shot_s 保底；切分参数是**产品化占位**（非冻结 finloc 阈值），已入 `PipelineConfig.seg_*` 供 H1 标定，**不做 sweep**；segment 属产品胶水，**不触碰任何冻结算法**。
- **第 7 项 application service 关键决策**：shot 切分 + per-segment 循环放 **app service 层**（按 STATE.md Next Actions 复用 `detect_shots`/`produce_candidates`/`localize_segment`，不新建 engine 层 `LocalizationEngine` 类）；**失败隔离**——单 segment 异常 → unresolved(LOW + `failure_reason` + 日志 exception) + 后续段继续，cancellation 抛 `ApplicationError` 不落入段级隔离；**ffmpeg/backend/FeatureStore 惰性构建**（纯编排路径不强制解析二进制）；**Progress** 7 阶段 `ProgressStage`+`ProgressEvent` 逐事件回调；**Cancellation** `CancellationToken`(threading.Event) 在 index build/extract/segment loop/export 检查；**错误模型** 补 `IndexError/FeatureExtractionError/LocalizationError/ApplicationError`（均 `LocatorError` 子类，GUI `except LocatorError` 即可）；**持久化（用户拍板）** JSON 单文件批 `schema_version/original_video/edited_video/results[]`（`*.results.json` 落 `paths.export_root()`），复用 `Result.to_dict()/from_dict()` 保留 auto/manual 双轨，`Result.failure_reason` 收窄失败段；**不用 SQLite**。修复 app 级 bug：`_result_from_refined` 曾传 `shot` 而非 `shot.span` 致 `Result.edited` 塞进 ShotSegment。
- **注意（交接必读）**：检索单元测试用合成图案数据，`v2_score` 会把覆盖更宽的非 GT 窗口排在真 GT 区之前——这是**冻结公式 + 合成图案 CLS 语义混淆**的已知属性；研究在**真实影片**数据上 v2_score 正确分离（研究已验证）。真实用户场景是 film 内容，非合成图案；若真实数据同样混淆，应属 Confidence 显式降险情形（第 5 项），**不是 retrieval 改动**，也不回退冻结公式。

## Next Actions

- **H3 CI 触发（用户手动）**：GitHub Actions → H3 macOS MPS POC → Run workflow（真实 Apple Silicon CPU vs MPS；H3 verdict = GO/CONDITIONAL/NO_GO；产物 results.json/.md artifact）。H3 尚不接入 `mvp/src/device`（POC 阶段）。
- **第 8 项**：PySide6 UI（Home→Index→Results→Export + 预览 + 手动修正 + 批量导出），消费 `SourceLocatorService`（`build_original_index` / `locate` / `export_results` / `load_results` + `ProgressStage` 进度条 + `CancellationToken` 取消），结果卡片用 `domain.Result`（edited/original/confidence/alternatives/montage_flag/failure_reason）。
- 之后：第 9 项 打包验收 + 性能基准 + Confidence 标定。
- **研究护栏（贯穿）**：不新增 backbone/VLM、不改相似度/检索/排序/定位/置信语义、不改 GT、不重跑研究 benchmark、不把已证伪变体与 patch/multi-scale 引入 runtime、不做大规模 sweep。仅当真实用户数据证明某类失败显著影响产品价值，才另立新的 Research Phase。

---

## Important Constraints

- None recorded.

## Known Issues

- None known.

## Last Updated

2026-08-25 23:42
