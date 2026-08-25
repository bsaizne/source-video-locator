# 跨平台与集成架构分析

> 本机实测平台：Windows 11 Pro (x64)。macOS 未实测，以下为代码/依赖分析推断，标注"推断"。

## 1. 各引擎集成形态

| 引擎 | 形态 | Windows | macOS (Apple Silicon) |
|---|---|---|---|
| VDF | 自包含 CLI 二进制（.NET self-contained） | ✅ 实测可运行（`vdf-cli.exe`，无需 .NET SDK） | 官方提供 `CLI-osx-arm64.tar.gz`，**推断**可运行（.NET 8 self-contained） |
| TransVCL | Python 源码 + PyTorch 模型 | ⚠️ 需 CPU/GPU torch，模型下载受阻 | ⚠️ MPS 支持（torch mac），但模型同样下载受阻 |
| VCSL | Python 源码（cv2/opencv） | ✅ 实测可运行（最小 pipeline） | ✅ **推断**可运行（opencv 跨平台） |

## 2. 依赖对比

| 依赖 | VDF | TransVCL | VCSL |
|---|---|---|---|
| 运行时 | 无（自包含） | Python 3.8+ / PyTorch (~2GB) | Python 3.6+ / opencv / numpy |
| ffmpeg | 必需（ffmpeg + ffprobe，需捆绑分发） | 特征提取需 ffmpeg | 可选（cv2 可直接读） |
| 预训练模型 | 可选（AI matching 时 ~100MB 自动下载） | **必需**（Google Drive，本机受阻） | 无 |
| GUI 捆绑 | 官方提供 GUI/Web | 需自建 | 需自建 |

## 3. 集成到桌面软件（Windows + macOS）的难度

### VDF（AGPLv3）
- **方式**：`Process.Start("vdf-cli", ...)` 子进程调用 + 解析 JSON 输出。进程隔离可弱化 AGPL 传染（需法律确认）。
- **优点**：跨平台二进制现成、无需自带运行时、官方已有 GUI/Web 可参考。
- **缺点**：AGPL 许可风险高；输出是"整文件一个 offset"粒度，多片段/转场定位能力弱（实测 A10/A11 recall 0）。
- **打包**：需捆绑 ffmpeg.exe + ffprobe.exe 到 app 目录。

### TransVCL（MIT）
- **方式**：Python 子进程 / 内嵌。需先提取帧特征再推理。
- **优点**：许可宽松；论文级精度。
- **缺点**：依赖重（PyTorch）、模型获取受阻、无 GPU 时 CPU 推理慢；特征提取管道需自行构建（本机未跑通）。

### VCSL / VTA 思路（MIT）
- **方式**：可整体用 Python（或 C++/Rust 重写）实现。特征 + 相似度矩阵 + VTA 对齐。
- **优点**：许可宽松；无重依赖；实测 CPU 快（0.6s/测试）；可直接集成。
- **缺点**：本机实现是"最小实验版"（Precision 25%），需改进特征（DINOv2/CLIP）与对齐算法（DTW/HV）才能达到论文水平。

## 4. 推荐架构（推断）

对 Windows + macOS 本地 GUI 桌面软件，**最务实的路径**：

```
自研核心（Python 或 Rust，MIT 友好）
  ├── 帧特征提取（DINOv2/CLIP，Apache/MIT）  ← 关键升级点
  ├── 相似度矩阵 + 时间对齐（VTA: HV/DTW）    ← 复用 VCSL 思路
  └── 结果验证（SSIM 精排，去 FP）
      ↓
可选 VDF 子进程（AGPL，若需要音频指纹补充）
```

理由：
1. **许可**：AGPL 的 VDF 作为产品底座有法律风险；MIT 的 VCSL 思路可自研。
2. **跨平台**：Python/opencv 全平台一致；Rust 更易打包。
3. **精度**：VDF 实测对多片段/转场无力；VCSL 思路有提升空间。
4. **速度**：VCSL 实测 0.6s/测试（CPU），足够交互式使用。

> 最终结论需等 Phase 8 真实视频数据 + Phase 11 综合评分，本文件为架构预判。
