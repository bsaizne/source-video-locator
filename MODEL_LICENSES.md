# 模型 License 记录

> 所有模型来源、版本、下载地址、大小、License 记录。
> 更新于 2026-08-23。

| 模型 | 用途 | 来源 | 下载地址 | License |
|---|---|---|---|---|
| TransVCL model_1.pth | 复制片段定位（全监督） | TransVCL 官方 | `D:\claudework\model_1.pth`（83,412,059 字节，已下载） | 随 MIT 仓库发布 |
| TransVCL model_2.pth | 复制片段定位（弱半监督） | TransVCL 官方 | `D:\claudework\model_2.pth`（83,412,059 字节，已下载） | 同上 |
| DINOv2-small (ONNX int8) | 视觉嵌入（VDF AI matching） | Meta AI / Xenova | VDF ai-models-v1 release / HuggingFace | Apache-2.0 |
| ONNX Runtime | 推理引擎（VDF AI） | Microsoft | github.com/microsoft/onnxruntime/releases | MIT |
| ISC 特征 (VCSL) | 帧特征（VCSL benchmark） | ISC21 第一名方案 | VCSL 仓库 data/vcsl_features.txt | 随仓库 |
| testsrc2 / 合成视频 | Dataset A 测试原片 | — | 本机 ffmpeg 生成 | — |

## 下载状态（本机实测）

- TransVCL 两个模型：**已下载**（2026-08-24）。model_1 / model_2 各 83,412,059 字节。均从 Google Drive 经用户手动下载，存储于 `D:\claudework\`。
- VDF AI 组件（ONNX Runtime + DINOv2）：首次启用 AI matching 时自动下载（~100MB），本次未启用。

## 原则

- 不下载未知来源模型。
- 所有模型记录来源/版本/地址/大小/License。
- 若某模型无法获取，如实标记，不伪造测试结果。
