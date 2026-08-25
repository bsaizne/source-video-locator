# Agent Project Instructions

## Context Management

Before starting work:

1. Read `.agent/STATE.md`.
2. Read `.agent/TODO.md`.
3. Read `.agent/INDEX.md` only when necessary.
4. Do not read `.agent/archive/` unless explicitly required.
5. Do not read the entire project automatically.

## Working Rules

- Treat source code as the source of truth.
- Do not copy large code blocks into context documents.
- Do not rewrite completed work without a reason.
- Respect existing architectural decisions.
- Check `.agent/DECISIONS.md` before reversing an important decision.
- Update project state after major milestones.

## Checkpoint

When the conversation becomes large or before switching to a new Agent conversation:

Run:

```bash
agent-context checkpoint
```

The checkpoint should update:

- STATE.md
- TODO.md
- DECISIONS.md when necessary
- CHANGELOG.md
- INDEX.md when necessary

## Resume

When starting a new Agent conversation:

Run:

```bash
agent-context resume
```

Only load the minimum information required to continue the project.

---

## Project: 视频片段反向定位引擎 Benchmark

> 目标：对视频匹配/复制片段定位引擎做统一、可重复、真实素材 Benchmark，决定哪个方案适合后续 Windows + macOS 桌面软件（Edited Video → Original Video 片段定位提取）。本阶段不做 GUI、不做最终产品。

### 关键文档（按优先级读）

- `.agent/STATE.md` / `.agent/TODO.md` — 当前状态与待办
- `PROJECT_HANDOFF.md` — 项目交接文档（历史全景，含 Phase 1~12 进展）
- `TECHNOLOGY_SELECTION.md` — Phase 11 选型结论（VCSL 思路 6.00 > VDF 5.46 > TransVCL 2.63）
- `benchmark_report.md` / `benchmark_report_phase12.md`（Phase 12 报告，生成中）— 实验数据
- `ENGINE_LICENSE_MATRIX.md` — VDF=AGPLv3（传染风险）、TransVCL/VCSL=MIT
- `datasets/real/ground_truth.json` — real GT 7 段（**不得修改**，见约束）

### 运行 / 测试命令

- 统一 runner（主入口）：
  ```bash
  # 三引擎旧汇总（会覆盖 benchmark_results.json，注意只保留本次引擎）
  .venv/Scripts/python.exe src/benchmark.py --engine all --dataset real
  # 单引擎（Phase 12 新增引擎）
  .venv/Scripts/python.exe src/benchmark.py --engine dinov2_ta --dataset real
  .venv/Scripts/python.exe src/benchmark.py --engine transvcl_official --dataset real
  ```
- 报告生成：`python src/report.py`（写 benchmark_report.md/.html + report_summary.json；**不写** benchmark_results.json）
- 环境检测：`python src/env_check.py` → `environment.json`
- 合成数据生成：`python src/dataset_a.py` → synthetic A1~A12
- **Python 必须用绝对路径**：`D:\claudework\video-dedup-tool\.venv\Scripts\python.exe`（bash PATH 里没有 python/pip）
- **ffmpeg**：`tools/ffmpeg.exe`；**ffprobe**：`..\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe`
- **无测试框架、无 CI**。验证靠真实数据复测（跑 benchmark 后看 results/<engine>/metrics.json 的 recall 等指标）。

### 重要目录

- `src/` — 统一 runner + 评估 + 报告 + adapter
- `src/adapters/` — 各引擎适配器（base.py 抽象 + vdf/vcsl/transvcl/dinov2_ta/transvcl_official）
- `src/experiments/` — Phase 12 新增：DINOv2 特征、ISC 特征、TA 对齐、失败分析
- `engines/` — 第三方引擎仓库（vdf 二进制 / transvcl clone / vcsl-official clone / isc21 clone）
- `datasets/` — synthetic（A1~A12）+ real（2.mkv 原片 + 1.mp4 解说，GT 7 段）
- `results/` — 各引擎运行结果（dinov2_ta / transvcl / vcsl / vdf / optional）
- `work/` — 运行时缓存（dinov2_feats / isc_feats / dinov2_weights / isc21_weights / transvcl_feats 等）
- `.agent/` — 本上下文档案

### 禁止误改的边界

- **`datasets/real/ground_truth.json` 不可修改**（任务书铁律：不为好看改 GT）
- **现有 `results/vdf|vcsl|transvcl/` 历史结果** 不覆盖（Phase 12 新结果放独立目录）
- `src/benchmark.py` 每次运行会覆盖 `benchmark_results.json`——要三引擎汇总必须 `--engine all`；Phase 12 引擎结果单独存，不进旧三引擎汇总
- 不伪造结果：装不上/模型下不了/特征失败 → 如实标记 `status: blocked` / `BLOCKED` / `NETWORK_BLOCKED`
- 不做 GUI / 不删 benchmark / 不研究音频指纹 / 不淘汰 TransVCL（需官方特征才能评估）
- 网络限制：github/pypi/download.pytorch.org 可达（慢）；Google Drive / HuggingFace / dl.fbaipublicfiles.com 直连可能失败（DINOv2 权重用带 `dinov2_vits14/` 子路径的 URL 可下）

### 上下文更新约定

- 大阶段完成后更新 `.agent/STATE.md` + `TODO.md`（+ CHANGELOG.md）
- 关键决策（如选型、实验路线）记入 `.agent/DECISIONS.md`
- Phase 12 实验完成前不宣布 TransVCL 失败、不宣布 DINOv2 是最终方案
