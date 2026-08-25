# TODO

## → 2026-08-25：算法研究冻结，进入 MVP 产品化（Source Video Locator）

- **研究阶段（Phase 1~19）已冻结收尾**。当前 = **ALGORITHM_RESEARCH_FROZEN / MVP_DEVELOPMENT_ACTIVE**。研究结论见 `ARCHITECTURE_DECISION_PHASE20.md`。
- **MVP Stage 0（设计文档）已完成**：`mvp/docs/` 8 份（MVP_PRODUCT_SPEC / MVP_ARCHITECTURE / CONFIDENCE_DESIGN / INDEX_SPEC / DEVICE_BACKEND_SPEC / TECH_STACK_DECISION / THIRD_PARTY_NOTICES / MVP_ROADMAP）。
- **MVP Stage 1（编码）待开始**：见下 P0。

## P0 — MVP Stage 1：Windows CPU（PHASE H1）开发顺序

1. ~~`media/ffmpeg`（FFmpegIO：metadata / seek / 抽帧 / clip extract）~~ — **DONE 2026-08-25**。生产级随机定位基础（禁 cv2.CAP_PROP_POS_MSEC）。`mvp/src/media/ffmpeg/`（FFmpegIO + ffprobe + _runner）。冒烟 23 项 + unittest 6 项过；真实 2h08m HEVC MKV 随机定位/帧精度验证通过。
2. ~~`domain`（Result/Candidate/Confidence/IndexMeta/Enums）+ `infrastructure`（配置/日志/错误模型/路径）~~ — **DONE 2026-08-25**。`mvp/src/domain/`（纯数据 + 枚举 + `to_dict()` 契约 JSON）+ `mvp/src/infrastructure/`（errors/logging/paths/config，JSON 覆盖）。`MediaError` 改继承 `LocatorError` 统一错误模型。test 12 项 + media 复测全过，未提前实现 engine。
3. ~~`device/CPUBackend` + `engine/feature_store/FeatureStore`（index create/load/validate，INDEX_SPEC 落盘）~~ — **DONE 2026-08-25**。`mvp/src/device/`（DeviceBackend Protocol + 冻结 DINOv2 backbone 提取 + CPUBackend 无CUDA + pick_best_available 预留 H2/H3）+ `mvp/src/engine/feature_store/`（FeatureStore create/load/validate/invalidate/get_metadata/delete，落盘 index.json+features.npy+times.npy，size→duration→model/dim/fps/version→hash 硬检失效，`.stale` 隔离）。device smoke 25 项 + unittest 4 项过；DINOv2 CPU 真推理 L2 norm=1.0。
4. ~~`engine/ranking`(v2_score) + `engine/retrieval` + `engine/clustering`（从研究代码 REUSE/REFACTOR 提取）~~ — **DONE 2026-08-25**。`mvp/src/engine/`：common/similarity(cosine REUSE)、retrieval/retrieve_hits(批量 TopK K=20)、clustering/continuity 10/15/60s + _merged_ok + _bridges、ranking/v2_score(mean*sqrt(hit)*(0.5+0.5*cons)*n_reps^0.5)、candidates.py(produce_candidates 编排)。删 GT/gid/benchmark/实验路径/work 依赖；`_dp_path`/`temporal_align`/`localize`/`_recall`=RESEARCH_ONLY 未进 runtime；config retrieval_top_k 100→冻结 20。retrieval smoke 6 项 + unittest 7 项过。（注：合成图案场景 CLS 易混淆，冻结公式在真实影片数据正常。）
5. ~~`engine/localization`（longest_run + montage 检测分支）+ `engine/confidence/ConfidenceEngine`~~ — **DONE 2026-08-25**。`mvp/src/engine/localization/`（finloc_window = per-orig max-over-query coverage + 3帧平滑 + mask(0.4 冻结) + longest_run → 精确 span；multi_island 结构检测；pipeline.localize_segment = 候选→finloc 最佳→回填 best_cover→confidence→RefinedSegment；montage/无 span/run 过短 → original 退化候选窗范围）+ `engine/confidence/confidence.py`（ConfidenceEngine.assess → score + HIGH/MEDIUM/LOW + reasons + hard_flags + montage_flag + alternatives）。置信度权重/阈值全部为未标定占位，纳入 ConfidenceConfig（infrastructure/config.py，JSON 可覆盖）供 H1 标定；`engine/localization/__init__` 不 import 编排避免循环导入。禁 per-query argmax/voting/cut-aware/temporal align/改 similarity·ranking。unittest 10 项 + smoke 9 项全过（synthetic v2_score 混淆使 smoke top 候选非真值，属已知数据/模型属性，真值定位由 deterministic unittest 覆盖）。
6. ~~`engine/segment`（edited shot 切分，定义无 GT 查询单元）~~ — **DONE 2026-08-25**。`mvp/src/engine/segment/`（`ShotSegment` 模型 + `detect_shots` + `adjacent_distances` + `_merge_short`）。相邻帧余弦距离 `d=1-cos`（复用冻结 cosine）→ **局部 z-score 判别**（`z>=2` 且 `s>=cut_abs=0.30`；弃"相对基线死代码"，正对研究"绝对阈值 d 不可靠"证伪）+ 默认平滑窗=1（保留单帧 cut 锐利尖峰）+ NMS(min_gap=max(1,round(min_shot_s*fps))) + merge(过短段并入更弱边界一侧) + 无边界/单帧/空→回退整段（现状行为）。整体偏向下切分（产品约束）。`PipelineConfig` 加 4 占位字段 `seg_cut_abs/seg_z_thresh/seg_min_shot_s/seg_smooth`（3 接线点 + JSON 覆盖验证过）。segment unittest 11 项 + smoke(真 ffmpeg+DINOv2 3色多镜头) 结构不变式全过、输出诊断统计；全套 50 项回归通过。研究护栏：未改冻结算法、无 GT、未 sweep、未重引入 Phase19 原片 cut-aware。冒烟 3 纯色 CLS 混淆未切分=已知合成图案属性。
7. ~~application service（用例编排 + Result 持久化）~~ — **DONE 2026-08-25**。`mvp/src/app/`（`models.py`：`ProgressStage`(7 阶段)+`ProgressEvent`+`CancellationToken`；`locator_service.py`：`SourceLocatorService`(build_original_index/analyze_edited_video/locate/_locate_features/export_results/load_results；ffmpeg+backend+FeatureStore 惰性构建)）+ `infrastructure/results_repo.py`（`save_results/load_results` JSON 单文件批 `*.results.json`）+ `infrastructure/errors.py` +4（`IndexError/FeatureExtractionError/LocalizationError/ApplicationError` 均 `LocatorError` 子类）+ `domain/models.py` 增 `Result.failure_reason`+`Confidence/Alternative/Result.from_dict()`+`ResultBatch`。编排：locate(edited,original)=原片 validate→(重)建→load + 编辑侧 iter_frames@2.0fps→embed_frames→detect_shots + 逐 segment produce_candidates→localize_segment→拼 `domain.Result`(edited=shot.span)。失败隔离：单 segment 抛错→unresolved(LOW+failure_reason+日志 exception)+继续后续段，cancellation 抛 `ApplicationError` 不落入段级隔离。unittest 12 项 + 全套回归 62 项通过；synthetic 端到端冒烟通过（a1 命中 HIGH、export/reload 往返、cancellation、失败隔离）；修复 app 级 bug（`_result_from_refined` 曾传 `shot` 而非 `shot.span`）。**真素材首次完整管线跑通（§十，仅观察不调算法）**：2.mkv 索引 3834 帧/3793.6s、1.mp4 12 段/254 帧、12 Results(HIGH5/MEDIUM1/LOW6, candidate 485)、export/reload 往返、cancellation、失败隔离、total 3951.9s；peak_ram N/A（venv 无 psutil）。研究护栏：只编排不改冻结算法语义、无 GT、未 sweep。
8. **PySide6 UI**（Home→Index→Results→Export + 预览 + 手动修正 + 批量导出）。
9. PyInstaller 打包 + 真机验收。
10. 性能基准（10/60/120min，Index Build / Feature Extraction / Localization / Total / RAM / Disk / CPU util）。
11. Confidence 标定（`CONFIDENCE_DESIGN.md` 权重/阈值用真实数据校准：HIGH 高 precision、LOW 高 recall-of-hard）。

## P1 — MVP 增强项（不阻塞 H1，属于 MVP 外）

- （需授权/条件触发）若产品域蒙太奇占比高 → s4 单类定向验证：DINOv2 稠密 + VCSL/VTA 序列对齐，判断能否分清"多-shot 同源"；成功才接入二级定位器。
- 场景身份模型（解 s0/s1 深 rank）——非外观第二信号。
- VDF 音频指纹辅助（AGPL，需法律确认，仅"音频不变"场景）。

## P2 — 硬件后续阶段（严格顺序，不并行）

> **硬件路线（2026-08-25 锁定）**：H1 CPU → H2 AMD GPU(DirectML) → H3 macOS MPS → H4 CUDA。**不支持 macOS Intel**。
> **H2 = `DirectMLBackend` 已接入并验证（`H2_AMD_DIRECTML = IMPLEMENTED`）**：resolver + CPU fallback + CPU/DML 正确性 + FeatureStore 兼容 + 真实 2.mkv 生产冒烟（381.3s/3834帧/~10 fps）全过。POC 证据见 `mvp/poc/amdgpu_onnx/`（保留不删）。H3/H4/UI 待后续。

- **PHASE H2 — Windows AMD GPU：✅ DONE（2026-08-25）**。`DirectMLBackend`（`mvp/src/device/directml_backend.py`）+ `resolve_backend` 自动选择/CPU fallback + 模型资产 resolver + `DeviceConfig` + `export_dml_model.py`。AMD 实机（RX 6750 GRE）：一致、10× 加速、内存稳定、FeatureStore 兼容。若未来某设备 DML 不稳则标 `AMD_GPU_BACKEND_BLOCKED` 继续 CPU（当前已自动 fallback，不影响 CPU MVP）。
- **PHASE H3 — macOS Apple Silicon**：`MPSBackend`（能力检测 + fallback）→ 一致性 + 性能基准 → 打包(.app/签名/公证) → 实机验收。**不支持 macOS Intel**。
- **PHASE H4 — Windows NVIDIA GPU (CUDA)**：未来 `CUDABackend`，无需改 Engine/FeatureStore/UI/AppService。不进当前实施阶段。

## Research Archive（研究阶段 TODO，已冻结，仅追溯）

- 历史研究任务（Phase 12~19）全部完成；见 `.agent/STATE.md → Research Archive`、`PROJECT_HANDOFF.md`、各 `benchmark_report_phase*.md`。
- 已关闭的待办：`--engine all` 重建 `benchmark_results.json`（需授权覆盖历史）；DINOv2+TA 成段（dinov2_ta total_pred=0，序列对齐 blocked，已归入"序列级需定向验证"）。

## 护栏（贯穿 MVP）

- 不新增 backbone/VLM、不改相似度/检索/排序/定位/置信语义、不改 GT、不重跑研究 benchmark、不把已证伪变体与 patch/multi-scale 引入 runtime、不做大规模 sweep。
- 研究代码（experiments/diagnostics/work/phase reports）保留；产品以"提取函数/公式"复用，不 import 研究脚本。
- 不为好看伪造结果；未测/不可用如实标 NOT TESTED / BLOCKED。
