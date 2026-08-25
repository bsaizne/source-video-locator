# MVP Roadmap — Source Video Locator（H1 → H2 → H3）

> 阶段：MVP Design（Stage 0）。定义开发现顺序、里程碑、验收、性能基准、研究冻结护栏、项目状态标记。严格遵守 H1→H2→H3 硬件顺序，**不并行三平台**。

## 0. 项目状态

- **ALGORITHM_RESEARCH = FROZEN**（Phase 13–19 已冻结，见 MVP_ARCHITECTURE §8）
- **MVP_DEVELOPMENT = ACTIVE**
- Current Algorithm Baseline：DINOv2 ViT-S/14 CLS 384D / 0.5fps 索引 / 全局检索 / 聚类 / ExpA n_reps(=0.5) / per-orig coverage / longest_run finloc / Confidence / FFmpeg。
- Current Hardware Target：**PHASE H1 = Windows CPU**（第一优先级）。
- Current Known Limitations：见 §8。

## 1. 研究冻结护栏（贯穿全程）

- 不新增视觉 backbone / 不新增 VLM/LLM runtime / 不改相似度/检索/排序/定位/置信语义。
- 不进默认 runtime：17A/18/19 已证伪变体、patch/multi-scale、ORB-BOW、TransVCL、cut-aware、per-query 邻域投票。
- 不改 GT、不重跑研究 benchmark、不做大规模 sweep。
- 研究代码（experiments/diagnostics）保留，物理隔离在 mvp/src 之外；产品以"提取函数/公式"方式复用，不 import 研究脚本。
- 若未来真实用户数据证明某类失败明显影响产品价值 → **单独开启新的 Research Phase**（另立），不是在本 Phase 无限优化。

## 2. PHASE H1 — Windows CPU（第一优先级）

**目标**：Windows 10/11 x64、无独立 GPU 也能完整运行；DINOv2 CPU inference + Feature indexing + Localization + FFmpeg extraction 全链路在当前开发机真实跑通。

**开发顺序（Stage 1 起）**：
1. `media/ffmpeg`（FFmpegIO：metadata / seek / 抽帧 / clip extract）—— 生产级随机定位基础。
2. `domain`（Result/Candidate/Confidence/IndexMeta/Enums）+ `infrastructure`（配置/日志/错误模型/路径）。
3. `device/CPUBackend` + `engine/feature_store/FeatureStore`（index create/load/validate）+ `INDEX_SPEC` 落盘。
4. `engine/rank`（v2_score 提取）+ `engine/retrieval` + `engine/clustering`（从研究代码 REUSE/REFACTOR 提取）。
5. `engine/localization`（longest_run + montage 检测分支）+ `engine/confidence/ConfidenceEngine`。
6. `engine/segment`（edited shot 切分，定义查询单元，绕过 GT）。
7. `application service`（用例编排 + Result 持久化）。
8. **PySide6 UI**（Home→Index→Results→Export）+ 预览 + 手动修正 + 批量导出。
9. 打包（PyInstaller）+ 真机验收。

**H1 验收（acceptance）**：
- 端到端：给 Original + Edited → 产出候选 + Confidence + 预览 + 提取。
- 连续镜头段定位可靠（对应实测 IoU 0.5–0.75 段）；蒙太奇段标 LOW + montage flag，不输出伪精确边界。
- 索引复用生效（二次载入不重扫原片）。
- Confidence 三档可用（初版阈值，H1 后按 §7 标定）。
- 无 GPU 也能完整跑（CPU 主路径）。

**H1 性能基准（真实测，不虚构）**：对 10min / 60min / 120min 原片测 Index Build Time、Feature Extraction Time、Localization Time、Total Time、RAM、Disk、CPU utilization。无实机 → 标 NOT TESTED。

## 3. PHASE H2 — Windows AMD GPU（H1 稳定后）

**目标**：让 DINOv2 Feature Extraction 能在受支持的 AMD GPU 后端运行。考虑 ROCm/HIP、PyTorch AMD backend、GPU capability detection。

**开发顺序**：
1. `device/ROCmBackend`（能力检测 → 可用则 GPU / 不可用则 CPU fallback）。
2. 一致性验证（与 CPU 基准对比 feature/retrieval/ranking/localization/confidence）。
3. 性能基准（同 H1 指标，若实机可用）。
4. UI 显示实际 backend + device_name；记录 fallback。

**关键原则**：
- **绝不说"所有 AMD GPU 都保证支持"**；必须能力检测。
- 当前设备 AMD Radeon RX 6750 GRE 的 ROCm/Windows 支持**不能假设成立**；需实机验证。
- 若 6750 GRE 在 Windows 无稳定官方后端 → 标记 `AMD_GPU_BACKEND_BLOCKED`，如实记录，继续 CPU。**不为单台设备破坏整体工程。**

**H2 验收**：AMD backend 可用则数值一致性达标 + 性能优于/等价 CPU；不可用则正确 fallback + 如实记录。

## 4. PHASE H3 — macOS Apple Silicon（H2 基础后）

**目标**：Metal/MPS；PyTorch MPS backend；能力检测 + CPU fallback；Apple Silicon 实机测试。

**不支持 macOS Intel**（投入产出比不足，不纳入 MVP）。

**开发顺序**：
1. `device/MPSBackend`（能力检测 → MPS 或 fallback）。
2. 一致性验证 + 性能基准（3 平台同指标）。
3. 打包配置（macOS）（.app / 签名 / 公证，若需）。
4. 实机验收。

**H3 验收**：MPS 可用则数值一致 + 性能达标；不可用则 fallback + 记录；**不因"代码理论支持"就宣称 macOS 可用**。

## 5. 整体里程碑

| | M1 | M2 | M3 |
|---|---|---|---|
| 内容 | H1 端点+定位+置信+提取跑通 | H1 UI+预览+手修+导出+打包 | H2 AMD / H3 Apple Silicon（依次） |
| 验收 | 连续镜头定位可靠、索引复用、无 GPU 完整跑 | 端到端 GUI 可用、打包真机通过 | AMD/MPS（可用则）一致性+性能达标 / 不可用则正确 fallback+记录 |

## 6. Confidence 标定（H1 后独立任务）

- 用 real 7 段（corrected GT）+ 人工标注扩展集（连续 + montage）。
- 校准 `CONFIDENCE_DESIGN.md` 的权重/阈值；目标 HIGH 高 precision、LOW 高 recall-of-hard。
- 记录每档 precision/recall 口径。

## 7. 性能基准汇总表（3 平台）

| 指标 | H1 Win CPU | H2 Win AMD | H3 macOS AS |
|---|---|---|---|
| Original 时长 | 10 / 60 / 120min | 同 | 同 |
| Index Build Time | 实测 | 实测(若可用) | 实测(若可用) |
| Feature Extraction Time | 实测 | 实测 | 实测 |
| Localization Time | 实测 | 实测 | 实测 |
| Total Time | 实测 | 实测 | 实测 |
| RAM / Disk / CPU util | 实测 | 实测 | 实测 |
| No hardware | NOT TESTED | NOT TESTED | NOT TESTED |

## 8. 当前已知限制（作为产品明示）

1. 连续镜头定位是当前 MVP 主能力；复杂 montage 是低置信场景。
2. s4 代表当前已知困难边界案例（多-shot montage）。
3. DINOv2 CLS 对某些同类暗场景存在语义混淆（置信可能虚高 → 显式降险）。
4. Confidence 不得仅依赖 cosine。
5. Windows AMD GPU 后端是否可用必须实机验证。
6. macOS Apple Silicon 必须实机验证。
7. macOS Intel 不支持。

## 9. 暂停/停止条件（按用户指示）

- Stage 0（设计文档）完成后**停止**：不写完整 GUI、不打包、不改核心算法、不新增实验、不改 GT、不重跑研究 benchmark、不新增模型。
- 本 Roadmap 之后的 Stage 1 编码从 §2 的 H1 开发顺序第 1 项开始（`media/ffmpeg` + `domain`）。
