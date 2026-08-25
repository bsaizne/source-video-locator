# Tech Stack Decision — MVP 技术栈（GUI / 语言 / 打包）

> 阶段：MVP Design（Stage 0）。基于**当前 Engine 实际依赖**（PyTorch/DINOv2/Python/FFmpeg）做 GUI 技术栈决策，不因"跨平台"字样盲目选 Avalonia。

## 1. 关键前提：Engine 是 Python/PyTorch

冻结算法栈 = DINOv2（PyTorch）→ 检索/聚类/排序（numpy）→ finloc（numpy）→ FFmpeg。**核心引擎是 Python 单进程 torch + numpy**。GUI 技术栈的核心问题是"如何把 UI 与这个 Python 引擎接起来"。

## 2. 候选对比

| | 方案 A：Python + PySide6 | 方案 B：.NET + Avalonia + Python Engine | 方案 C：Electron/Tauri + Python Engine |
|---|---|---|---|
| 与 Python 引擎耦合 | 同一进程，直接 `import`，零 IPC | 跨进程 (IPC/subprocess)，需序列化候选/特征/结果 | 跨进程，额外 IPC 层 |
| Windows CPU 部署 | 好（Qt + torch 本地进程） | 需打包 .NET + Python runtime 两套 | 更重（Node + Python + browser） |
| Windows AMD GPU | torch 进程内切换 backend，自然 | GPU backend 在 Python 子进程，UI 无关 | 同 B |
| macOS Apple Silicon | Qt + torch MPS 同一进程，好 | .NET 可跑 MPS？需 Python 子进程承载 | 重 |
| FFmpeg 集成 | subprocess 直调，成熟 | subprocess，UI 层再绕一层 | subprocess + Node 介入 |
| 打包 | PyInstaller（PySide6+DINOv2+torch，约 1.5–2GB） | .NET 自包含 + Python 环境，双份 | 更大 |
| 调试 | 单进程，断点直打 | 跨进程断点、序列化调试麻烦 | 最复杂 |
| License | PySide6=LGPL-3.0（商业可用，动态链接） | .NET=MIT（UI 侧），Python 引擎侧还是 PySide6/node | 混合 |
| 既有经验 | 用户已交付 PySide6 应用（bgremover MVP） | 无 | 无 |
| 复杂度 | **最低** | 中 | 高 |

## 3. 推荐：**方案 A — Python + PySide6**

**理由（依 Engine 实际依赖导出）：**
1. 引擎已是 Python/PyTorch；同一进程**免去 IPC/序列化/跨进程调试**，主流程简单、稳。
2. DINOv2 的 AMD/MPS/未来 CUDA backend 切换在进程内即可，UI 无需关心 GPU 落在哪。
3. FFmpeg 用 subprocess 直调，生产级随机定位可靠。
4. PySide6 = LGPL-3.0，动态链接对商业闭源产品友好（Qt 官方 LGPL 商用模式），比 AGPL 风险低很多。
5. 用户已有 PySide6 项目经验，开发成本最低。
6. macOS 上 Qt + torch MPS 天然可跑，跨平台诉求满足。

**不选 Avalonia / Electron 的核心理由**：它们只为"UI 本身"带来所谓跨平台/性能，但本项目 UI 很轻（表单+列表+预览），瓶颈全在 Python 引擎与 FFmpeg；跨进程反而增加耦合与调试成本。**"跨平台"不是选型的主导因素，引擎依赖才是。**

## 4. 技术栈选型明细

- **UI**：PySide6（Qt6，LGPL-3.0）
- **语言**：Python 3.11+（冻结）+ typed dataclass（domain）
- **数值/模型**：PyTorch（BSD）、numpy（BSD）、torchvision（BSD，未必用，因模型手写）
- **视频**：FFmpeg/ffprobe（subprocess，见 §6 license）
- **视觉回退/预览**：Qt 自带 image/opencv（Apache-2.0 或 Qt）——注意预览帧的显示键。
- **打包**：PyInstaller（先 H1 CPU 单机）→ 后续考虑 Briefcase/或平台原生安装器。
- **配置/持久化**：标准库 json + 轻量 SQLite（结果存档）。

## 5. 打包与更新

- **MVP 优先本地单机**：PyInstaller one-dir 打包，包含 DINOv2 权重（~80MB）+ torch（~2GB）+ 应用代码；真机验证启动、索引、定位、提取全流程。
- 权重与模型：随包分发或首启下载（需网络）；MVP 走随包分发，避免首启网络依赖。
- 更新：MVP 不做自动更新（单机 v1），格式化为"用户手动替换"；Roadmap 记录。
- 调试：开发用 `python -m app` 源码跑；发布用 PyInstaller 产物复测。

## 6. FFmpeg license 与提取精度（必须显式决策）

- FFmpeg 有 **GPL 与 LGPL** 两种构建。若商业闭源再分发，需用 **LGPL 构建**（动态链接、不 GPL 传染），或作为独立进程调用（AGPL/GPL 传染弱但仍有风险）。
- **提取精度与编码器**：`-ss`（在 `-i` 前）快但不精确（keyframe 对齐）；精准 seek 需 `-ss` 在 `-i` 后（慢）+ 重编码（libx264=GPL）。产出级提取需要**精确**起止。
- **决策建议**：MVP 用 LGPL FFmpeg 静态构建；提取用精确 seek + 重编码（或 `-c:v libx264` 仅当接受 GPL 编码器/或改用 LGPL 可用的编码器）；若必须 GPL 编码器，则需在 THIRD_PARTY_NOTICES 明确记录并做合规判断。**精确提取是产品价值点，不能因省事用 keyframe 对齐糊弄。**（此点需在 H1 实测确认 FFmpeg 构建的许可与编码器依赖后定稿。）

## 7. 跨平台策略

- H1：Windows CPU（唯一硬性交付）。
- H2：Windows AMD GPU（backend 能力检测 + CPU fallback）。
- H3：macOS Apple Silicon（Qt + torch MPS）；**macOS Intel 不支持**。
- 架构上 UI 层不写死平台分支，平台差异集中在 DeviceBackend + 打包配置。

## 8. 结论

**GUI = Python + PySide6**；Engine 单进程；FFmpeg 子进程；PyInstaller 打包。**原因：引擎是 Python/PyTorch，UI 极轻，跨进程无收益，单进程 + LGPL 是最稳、最省、可商业化的路线。**
