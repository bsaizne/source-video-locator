# Third-Party Notices — Source Video Locator

> 阶段：MVP Design（Stage 0）。记录所有 runtime 依赖与直接引用代码的 License 信息，逐项核对 Source/Model/Weight/Commercial/Redistribution/Modification。**仅供设计决策参考；正式合规以各仓库实际 LICENSE 文件为准，发布前需法律确认。**

## 1. 依赖清单与 License 概览

| 组件 | 用途 | Source License | Model/Weight License | Commercial use | Redistribution | Modification | 备注 |
|---|---|---|---|---|---|---|---|
| DINOv2 (facebookresearch/dinov2) | 特征 backbone（ViT-S/14） | Apache-2.0 | **权重需确认**（官方分发；一般认为 Apache-2.0，但发布前核对） | ✅ | ✅（保留 notice） | ✅ | **本项目用手写 ViT**，引用其模型结构与权重；不 import 其全部代码 → 依赖更少 |
| PyTorch | 推理框架 | BSD-3-Clause | n/a | ✅ | ✅ | ✅ | torch 2.13 CPU 已装 |
| torchvision | 图像/变换（或未用） | BSD-3-Clause | n/a | ✅ | ✅ | ✅ | 模型手写，可能不依赖 |
| numpy | 数值 | BSD-3-Clause | n/a | ✅ | ✅ | ✅ | |
| opencv-python | 帧读取（预处理用） | Apache-2.0 | n/a | ✅ | ✅ | ✅ | 生产用关键帧仍走 FFmpeg；opencv 用于帧预处理 |
| PySide6 | GUI | **LGPL-3.0** | n/a | ✅（动态链接） | ✅ | ✅ | 商用友好；需遵守 LGPL（不静态链接 Qt，或保留可替换性） |
| FFmpeg / ffprobe | metadata/seek/抽帧/提取 | **GPL 或 LGPL（构建二选一，需确认）** | n/a | ⚠️ 见下 | ⚠️ 见下 | ⚠️ | **关键决策**：商业再分发需 LGPL 构建；提取编码器若用 GPL(libx264) 有合规考量 |
| PyInstaller | 打包 | GPL-2.0（含 bootloader 例外） | n/a | ✅（bootloader 例外允许分发） | ✅ | ✅ | 打包分发一般不传染 |
| Python 标准库 | 运行 | PSF | n/a | ✅ | ✅ | ✅ | |

## 2. 逐项 License 明细

### DINOv2
- **Source**：Apache-2.0（仓库 LICENSE）。
- **Model/Weight**：官方发布 pretrained 权重；许可证一般与 Apache-2.0 一致，但**需在发布前提权核对**（有的权重遵循其 model card 附加条款）。本 MVP 随包分发权重，需保留归属声明。
- **Commercial/Redistribution/Modification**：开源允许；商业可用；**保留版权/许可声明**，勿移除。

### FFmpeg（重要，需显式决策）
- **Source License**：FFmpeg 本身 LGPL-2.1+ 或 GPL-2.0+（取决于构建配置是否启用 GPL-only 组件）。
- **对商业桌面产品的含义**：
  - 若选择 **LGPL 构建**：动态链接使用，传染性弱 → 商业闭源可用；需遵守 LGPL（动态库、允许替换、保留许可）。
  - 若选择 **GPL 构建**：集成到闭源产品再分发会触发 GPL 传染，不适合商业闭源。
  - **MVP 建议**：使用 **LGPL 静态/动态构建**，通过子进程或动态链接调用；明确在 NOTICES 记录构建来源与配置。
- **提取编码器**：`-c:v libx264` 为 GPL；若产品需要重编码提取，需评估 GPL 编码器合规，或寻找 LGPL 兼容途径（如使用 `-c copy`、或纯 LGPL 编码器、或接受 `-c copy` 的 keyframe 边界取舍）。**此点需 H1 实测确认 FFmpeg 构建与编码器依赖后定稿。**

### PySide6
- **License**：LGPL-3.0（Qt for Python）。
- **Commercial**：允许闭源商用，但需遵守 LGPL（动态链接 Qt 库，不静态合并，保留可替换性与许可声明）。
- 对商业风险远低于 AGPL；是 MVP 可接受的 GUI 层。

### PyTorch / torchvision / numpy / opencv-python
- 均为宽松开源（BSD/Apache），商业可用、可再分发、可修改；保留版权声明。

### VDF (videoduplicatefinder)
- **License：AGPLv3**。**不放入最终 MVP runtime**（除非完成专门许可审查并做出架构决定）。本 MVP 的默认 runtime 不含 VDF；VDF 仅作为"未来可选音频指纹辅助模块"，且只能以独立进程 + 法律确认的方式接入，不可库链接。**本 MVP 规避 VDF AGPL。**

## 3. 直接引用代码 / 模型归属声明

- **DINOv2 手写模型**（源自 `src/experiments/dinov2_features.py` 的 `DinoV2Small`）：结构来自 facebookresearch/dinov2（Apache-2.0），权重官方预训练。

## 4. 待办 / 发布前需确认（H1 里程碑）

- [ ] DINOv2 权重正式 License（model card / 官方仓库）核对。
- [ ] FFmpeg 构建选择：LGPL vs GPL；随包分发方式；record 构建来源与 configure 参数。
- [ ] 提取编码器合规（libx264=GPL 的处理）。
- [ ] PySide6 / Qt 的 LGPL 动态链接合规确认。
- [ ] 是否有 import 其他研究代码（REUSE 需保留原始许可声明，尤其 DINOv2 结构与 DINOv2 权重）。

## 5. 原则

- 所有第三方依赖保留各自 LICENSE/NOTICE 文本（随包分发 LICENSE 目录）。
- 不引入 VDF AGPL（除非专门审查 + 架构决定）。
- 不引入未核对许可的权重/模型。
- 所有 License 判断以实际开源文件为准；此表为设计期参考，**不构成正式法律意见**。
