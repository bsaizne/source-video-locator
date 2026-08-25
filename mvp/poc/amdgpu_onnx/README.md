# AMD GPU Feasibility POC — DINOv2 ViT-S/14 CLS 384D (RX 6750 GRE)

独立、可证伪的 **H2 (Windows AMD GPU)** 可行性 POC。**只读复用** `mvp/src` 的冻结模型/预处理，
**不改任何生产源码**；产物全部在本目录。完成后**未接入 MVP**。

## 判定

> ## AMD_BACKEND_GO
>
> **DirectML 在 RX 6750 GRE 上真实运行、与 PyTorch CPU 数值一致、确实用 GPU、且性能远超 CPU（10.39×）；连续 500 帧稳定。**
> WinML 本机未装（未测）。附带一个需在 H2 验证的 caveat：见 §5 内存增长。

## 环境
- 运行时：`video-dedup-tool/.venv`（benchmark 复用的 venv），Python 3.13.14
- torch **2.13.0+cpu**(cpu-only), numpy 2.5.2, onnx 1.22.0, **onnxruntime-directml 1.24.4**
- GPU（WMI）：`['OrayIddDriver Device', 'AMD Radeon RX 6750 GRE 10GB']`（Oray = 远程虚拟显示驱动；
  唯一硬件 GPU = 6750 GRE）
- 权重：`work/dinov2_weights/dinov2_vits14_pretrain.pth`（裸 state_dict, 88MB）
- 模型：冻结 `DinoV2Small`（ViT-S/14, patch 14, embed 384, depth 12, heads 6, **tanh-GELU**）；
  forward = patch_embed → 12×Block → final LayerNorm → CLS token(`x[:,0]`, [B,384], float32, 未 L2)。

## 路线结果
| 引擎 | batch | fps | ms/frame | 相对 CPU |
|---|---|---|---|---|
| PyTorch CPU | 8 | 1.46 | 685.9 | 1.00× |
| ONNX Runtime CPU | 8 | 1.94 | 516.7 | 1.33× |
| **ONNX Runtime DirectML** | 8 | **15.15** | **66.0** | **10.39×** |
| ONNX Runtime DirectML | 1 | 8.93 | 112.0 | 6.12× |

（输入为 500 帧随机 BGR → 518×518；forward 计时不含共享的 preprocess 成本。）

## 正确性（vs PyTorch CPU，L2 归一后）——在阈值内
| 引擎 | cosine | max\|Δ\| | mean\|Δ\| | L2 norm | ok |
|---|---|---|---|---|---|
| ONNX CPU | 1.000000 | 4e-7 | 6e-8 | [1.0,1.0] | ✓ |
| ONNX DML | 0.999996 | 4.8e-4 | 1.1e-4 | [1.0,1.0] | ✓ |

- DML raw(CLS) vs CPU raw max|Δ|：0.0237（**未归一** raw 的差异；归一后骤降到 4.8e-4）
- **Top-1 邻居一致性：1.0**（DML 与 CPU 在索引里的最近邻完全一致）
- 全程 float32（无 fp16/量化降级）——差异纯来自 GPU 内核融合/调度顺序，非精度降档
- 逐帧 cosine 上界 0.999995 以上（cos_rowwise_min=0.999995，mean=0.999996）

## 稳定性（DirectML 500 帧）
- all_finite，**max_norm_dev = 0.0**（归一后 norm 严格 =1.0，无爆炸/塌缩）
- 进程内存：3889.3 → 4417.0 **+527.7MB**（见 §5 caveat）

## GPU 是否真的被用
- `session.get_providers()` → `['DmlExecutionProvider', 'CPUExecutionProvider']`（DML 激活）
- WMI 列出的唯一硬件 GPU = **AMD Radeon RX 6750 GRE 10GB**
- 15.15 fps vs CPU 1.46 fps（10.39×，远超静默 CPU fallback 会出现的 ≈1.33×）
- 说明：onnxruntime-directml 的 Python API 不直接暴露适配器名；证据 = provider 激活 + 唯一 GPU
  + 10× 性能 + 数值一致，足以判定非 CPU fallback。

## 结论与 H2 落点
**GO 的强度**：DirectML 是 Windows 上 AMD 的通用 GPU 通路，本次已验证其能跑通冻结 DINOv2 推理、
数值一致、显著加速、稳定。**接 H2 时**（本 POC 未接）应：
- 新建 `device/DMLBackend`（复用 `DeviceBackend` 协议；`embed_frames` 用 onnxruntime
  `DmlExecutionProvider` + numpy L2 + 同一 `_imagenet_preprocess`/batch；无 GPU → CPU fallback）。
- **重新导出**冻结模型的 `.onnx`（本目录 `export_model/dinov2_cls_384.onnx` + 外部权重
  `.onnx.data` 88MB 必须**同目录打包**）。
- 在**真实特征管线**上做 CPU-vs-DML 数值一致性核验（非仅 CLS raw），并重跑 H1 性能基准
  （10/60/120min 原片）确认真实端到端加速。

## Caveat（GO 但需 H2 验证）
1. **内存增长**：500 帧 stability 循环内进程内存 +528MB。疑似 onnxruntime DML 执行栈 arena 预热/缓存
   （倾向于一次性分配后复用，非常见泄漏），但**未排除随帧数无界增长**。H2 须在完整建索引
   （如 2h@0.5fps≈3600 帧）上复测，确认无 unbounded host-memory 增长。
2. **输入为随机帧**：forward 成本真实（518×518），但 preprocess（cv2 cvtColor+resize）是**各引擎共享**
   的公共成本，未计入 forward fps；真实视频的 preprocess 对三者同样加价，相对加速比成立。
3. **WinML 未测**（本机无 `winml`/`windows.ai.machinelearning`）。DirectML 已覆盖 Windows-AMD，
   WinML 是另一可选通路，缺失不阻塞 H2 用 DirectML。
4. **tanh-GELU 语义**：本站点冻结模型用 `nn.GELU(approximate="tanh")`，与官方 checkpoint 训练时的
   exact GELU 不同。本 POC 以**本站点语义**为参考（与 `CPUBackend.embed_frames` 对齐），
   因此 DirectML/ONNX 与 CPU 的一致性成立；若担心与"官方 DINOv2 输出"有偏，需另行核验（不属于本 POC）。

## H2-Preflight — DirectML 长时索引稳定性（2026-08-25，`h2_preflight.py`）

完整真实原片 `datasets/real/originals/2.mkv`（1280×688, 7667.5s）@0.5fps 建索引 **3834/3834 帧全部跑完**。
用与 POC 相同的 ONNX graph / DirectML provider / preprocess / batch=8 / L2 归一。

| checkpoint frames | RSS(MB) | all_finite | norm_max |
|---|---|---|---|
| 256 | 328.85 | True | 1.0 |
| 504 | 328.91 | True | 1.0 |
| 1000 | 328.23 | True | 1.0 |
| 2000 | 334.43 | True | 1.0 |
| 3000 | 328.19 | True | 1.0 |
| 3834 | 336.82 | True | 1.0 |

- **起始 278.5 → 最终 336.8 MB（+58.3MB）**；峰值 336.82 MB
- **增长全部集中在首批 ~250 帧的一次性 jump**（278.5→~329 by frame 256 = DirectML arena warmup），
  之后在 328–337 MB 窄带内波动，**后续 3578 帧仅 ±几 MB，非线性增长**（interval ΔMB：+0.1/-0.7/+6.2/-6.2/+8.6，围绕噪声上下）
- 全片耗时 323.9s（含解码），平均 **11.84 fps**；全程 all_finite、norm=1.0、无 DML allocator 错误
- GPU VRAM：`NOT_AVAILABLE_VIA_ORT_DML`（onnxruntime-directml 无公开显存 query API；host RSS 为代理指标）

**Verdict：`MEMORY_STABLE`** — 内存增长后稳定，属 **warmup/cache overhead，可接受**；非无界线性增长。
→ 依据用户判定规则，**完整 3834 帧稳定 → AMD 后端正式进入 H2**（下一步接入 `DirectMLBackend`）。

## 复跑
```bash
TT="D:/claudework/video-dedup-tool/.venv/Scripts/python.exe"
"$TT" -m pip install onnx onnxruntime-directml onnxscript   # 一次性
"$TT" mvp/poc/amdgpu_onnx/export_onnx.py                    # 重导出 .onnx
"$TT" mvp/poc/amdgpu_onnx/bench.py --frames 500 --batch 8   # POC 基准
"$TT" mvp/poc/amdgpu_onnx/h2_preflight.py --batch 8         # H2-Preflight（长时稳定性）
```
产物：`report.json`/`report.md`（POC）、`report_h2.json`/`report_h2.md`（H2-Preflight）、
`export_model/dinov2_cls_384.onnx|.data`。
