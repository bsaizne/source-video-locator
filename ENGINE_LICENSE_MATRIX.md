# 引擎 License 对比矩阵

> 来源：各仓库 README / LICENSE 文件实测（2026-08-23 核实）。

| 项 | VDF (videoduplicatefinder) | TransVCL | VCSL / VTA |
|---|---|---|---|
| **Repository** | github.com/0x90d/videoduplicatefinder | github.com/transvcl/TransVCL | github.com/alipay/VCSL |
| **License** | **AGPLv3** | **MIT** | **MIT** |
| 仓库根 LICENSE 文件 | 无（README 声明 AGPLv3） | 有 (MIT) | 有 (MIT) |
| **Commercial use** | 允许，但 AGPL 传染：衍生/链接作品须开源 | 允许（MIT 宽松） | 允许（MIT 宽松） |
| **Modification** | 允许，修改后须以 AGPL 提供源码 | 允许 | 允许 |
| **Redistribution** | 允许（同源 AGPL） | 允许 | 允许 |
| 部署形态 | 自包含 CLI/Web 二进制（.NET 自携带 runtime） | Python 源码 + 模型 | Python 源码 |
| 关键第三方依赖 | ffmpeg (GPL/LGPL), ONNX Runtime (MIT), DINOv2 (Apache-2.0), AcoustID.NET (LGPL 2.1) | PyTorch (BSD), torchvision (BSD) | PyTorch, tslearn, numba |

## 对商业桌面产品的含义

1. **VDF (AGPLv3)**：
   - 作为**独立进程**通过 CLI 调用（进程隔离），AGPL 传染性弱于库链接。
   - 若以**源码修改/库引用**方式集成，AGPL 要求整个衍生软件开源，与商业闭源产品冲突。
   - 命令行子进程集成（`Process.Start` + 解析 JSON）是规避 AGPL 传染的常见方式，但需法律确认。
   - **风险高**：AGPL 是最严格的开源协议之一（含 SaaS 场景）。

2. **TransVCL / VCSL (MIT)**：
   - 允许闭源商用、修改、再分发，无传染性。
   - **商业安全**，适合作为核心引擎直接集成。
   - 注意：TransVCL 引用的 LoFTR (Apache-2.0)、YOLOX (Apache-2.0) 同样宽松。

3. **辅助组件**：
   - ONNX Runtime (MIT)、DINOv2 (Apache-2.0) — 宽松，可商用。
   - AcoustID.NET (LGPL 2.1) — 若链接使用需动态链接；VDF 的 partial clip 指纹源于此。

## 结论

- **最商业友好**：VCSL/VTA (MIT)、TransVCL (MIT)。
- **有约束**：VDF (AGPLv3) — 工程上可行（进程隔离），但法律上需评估。
- 若产品闭源，**推荐 VCSL/自研核心 + 可选 VDF 子进程**。
