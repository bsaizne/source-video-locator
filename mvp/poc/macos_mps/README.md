# macOS Apple Silicon (MPS) Feasibility POC — H3

独立、可证伪的 **H3 (macOS Apple Silicon / PyTorch MPS)** 可行性验证。**只读复用**冻结
`DINOv2 ViT-S/14`（`mvp/src/device/dinov2_model.py` 的模型类 + `_imagenet_preprocess`），
**不修改任何生产源码**（不碰 `device/`、`CPUBackend`、`DirectMLBackend`、`FeatureStore`、
`engine`、`app`、UI）。产物全部在本目录。**未接入 MVP**。

> 本阶段（H3-0）只创建了仓库与 CI workflow；**H3 POC 尚未在真实 Apple Silicon 上运行**。
> 参见 `.github/workflows/h3-macos-mps.yml`（`workflow_dispatch` 手动触发）。

## 判定（verdict）

- **H3_MPS_GO**：MPS 实际启用、模型稳定、correctness 可接受、无关键 fallback、500 帧稳定、有实际性能价值。
- **H3_MPS_CONDITIONAL**：能运行，但存在部分 operator/CPU fallback 或性能收益有限。
- **H3_MPS_NO_GO**：MPS 不可用 / 关键算子不支持 / 不稳定 / 无实际性能收益。
- **H3_NOT_TESTED**：模型权重无法获取（`MODEL_DOWNLOAD_BLOCKED`）——**不伪造结果**。

判定阈值（POC 判据，非产品承诺）：`cos_mean >= 0.999`；`speedup_x > 1.2` 才有实际加速价值；
严重 CPU fallback 或 `cos_mean < 0.999` 或 500 帧不稳 → NO_GO。

## 运行

GitHub Actions（推荐，真实 Apple Silicon）：
- 手动触发 `.github/workflows/h3-macos-mps.yml`（`macos-15`，arm64）。
- 脚本自动：探测环境 → 下载并校验权重（size/sha256）→ CPU reference VS MPS →
  正确性（cos / absdiff / norm）→ 吞吐（3/8/32/128）→ 500 帧稳定性 → `results.json` + `results.md`。

本地（Windows/非 Apple Silicon，仅结构 selfcheck，**非 H3 结论**）：
```bash
python mps_poc.py --quick --out results.selfcheck.json
```
`--quick` 只验证 CPU reference 的 L2/shape/dtype 与**无 MPS 时的诚实降级**（不产出 MPS 指标）。

## 诚实性要求

- 必须确认 tensor/model **实际在 `mps`**（读取 `next(model.parameters()).device.type`），
  **不**把 `is_available()` 或"程序成功运行"等同"MPS 全程 GPU"。
- MPS 运行期间捕获的 `fallback / unsupported / cpu` warning 会如实记录在 `stability`。
- 权重下载后比对**大小 + sha256**（见 `mps_poc.py::_verify_weights`），失配 → `MODEL_DOWNLOAD_BLOCKED`，
  绝不静默使用错误权重。

## 文件

- `mps_poc.py` — 主线验证脚本（跨平台：macOS 跑 CPU vs MPS；非 macOS 诚实标注）。
- `.github/workflows/h3-macos-mps.yml` — CI workflow（手动触发）。
- `results.json` / `results.md` — CI 运行后生成的报告与 artifact。
