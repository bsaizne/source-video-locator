# Device Backend Spec — 统一推理后端（CPU / AMD GPU / MPS / 未来 CUDA）

> 阶段：MVP Design（Stage 0）。定义设备抽象、能力检测、GPU fallback、硬件阶段（H1/H2/H3）、CPU/GPU 一致性要求。**禁止在业务逻辑里写死 CPU/AMD/MPS/CUDA**——一切经 DeviceBackend。

## 1. DeviceBackend 接口

```python
class DeviceBackend(Protocol):
    def is_available(self) -> bool: ...                 # 该 backend 在本机是否可用
    def device_name(self) -> str: ...                   # "cpu" | "cuda:0" | "mps" | "rocm:0" | "AMD_GPU_BACKEND_BLOCKED"
    def device_type(self) -> Literal["cpu","amd","mps","cuda"]: ...
    def memory_info(self) -> dict: ...
    def load_feature_model(self) -> Any: ...            # DinoV2Small, .eval(), 已 `.to(device)`
    def embed_frames(self, bgr_frames: list[np.ndarray],
                     batch_size: int = 8) -> np.ndarray: ...   # [N,384] L2-norm
    def cleanup(self) -> None: ...
```

**业务层不得关心当前是 AMD、CPU 还是 MPS**，只拿到 `DeviceBackend`。

## 2. Backend 实现族

```
DeviceBackend
├── CPUBackend      # device_name="cpu", torch.set_num_threads
├── ROCmBackend     # 尝试 torch HIP/ROCm；失败 → 能力检测返回不可用 → fallback
├── MPSBackend      # torch MPS (macOS Apple Silicon)
└── CUDABackend     # 未来
```

- CPUBackend 是 H1 唯一要求；ROCm/MPS 是 H2/H3。
- 每个 backend `is_available()` 需做**运行时能力检测**（见 §3），不能假设"装了 torch 就能用 GPU"。

## 3. 能力检测（Capability Detection）

运行时检查（每个 backend 自行实现）：
1. GPU/加速器是否存在
2. 驱动是否可用
3. PyTorch backend 是否可用（`torch.backends.<x>.is_available()`）
4. 模型是否可加载到该设备
5. backend 是否支持当前 GPU（型号/能力级）

**AMD 特别注意**：当前设备 AMD Radeon RX 6750 GRE，其 ROCm/Windows 支持**不能假设成立**。若实机无法用稳定官方后端：
- 标记 `device_name = "AMD_GPU_BACKEND_BLOCKED"`，如实记录；
- **自动 CPU fallback**；
- 不为单台设备破坏整体工程。

**macOS**：Apple Silicon 优先 Metal/MPS/PyTorch MPS；必须实机测试，不因"代码理论上支持"就宣称可用；`is_available()` 不满足 → CPU fallback。

## 4. GPU fallback 规则（统一）

```
backend = pick_best_available()
if not backend.is_available():
    backend = CPUBackend()          # 兜底，永不因无 GPU 而不可用
```

- UI 显示实际选中 backend 与 device_name；无 GPU 也能完整运行（H1 核心）。
- fallback 是**自动且显式**的：记录 fallback 事件（日志），但功能不中断。

## 5. CPU/GPU 一致性（必须保证，允许差异要记录）

**GPU 只是加速，不能改变算法逻辑。** CPU/AMD/MPS 应尽量得到一致的：
- feature dimension（384）
- similarity 定义（L2 归一化余弦）
- candidate retrieval
- ranking
- localization
- confidence

**验证方法**：同一输入，CPU 与加速后端分别跑，逐帧比较特征（允许浮点极小差）。若出现明显数值差异（远超浮点容差），**必须记录**，不得默默接受。特征 L2 归一化后差异通常情况下极小。

> 一致性验收是 H2/H3 的准入前置：新 backend 上线前必须证明其数值与 CPU 基准一致性达标，否则视为 backend 问题。

## 6. 硬件路线（严格遵守顺序，不并行三平台）

**PHASE H1（第一优先级）— Windows CPU**
- Windows 10/11 x64；无独立 GPU 也能完整运行；DINOv2 CPU inference、feature indexing、localization、FFmpeg extraction。
- 本阶段是 MVP 基础版，须在当前开发机真实跑通。

**PHASE H2 — Windows AMD GPU**
- 目标：DINOv2 Feature Extraction 能在受支持的 AMD GPU 后端运行。重点考虑 ROCm/HIP、PyTorch AMD backend、GPU capability detection。
- **绝不说"所有 AMD GPU 都保证支持"**；必须能力检测，不可用则 CPU fallback。当前 6750 GRE 实机可用性需验证；不稳定则标记 BLOCKED 继续 CPU。
- H1 完成并稳定后才进入 H2。

**PHASE H3 — macOS Apple Silicon**
- 目标：Metal/MPS/PyTorch MPS；同样能力检测 + CPU fallback；Apple Silicon 实机测试。
- 不支持 macOS Intel（投入产出比不足）；不纳入 MVP。
- H2 完成基础支持后才进入 H3。

> 未来：可加 `CUDABackend`（NVIDIA），无需改 Localization Engine / UI / FeatureStore / Application Service。

## 7. 与业务层解耦

- FeatureStore.create_index / load_index 均注入 backend；Engine 只感知 `DeviceBackend`。
- 新增 backend = 新增一个 `device/<name>` 实现 + 能力检测 + 一致性验证；业务层零改动。
- `device_name()` 用于 UI 展示与日志，不作为分支逻辑键（除非统一 detection）。

## 8. 模型加载

- 使用冻结的**手写 DinoV2Small**（现有 `dinov2_features.py` 模型与前向，REUSE 不改）；权重为官方 pretrained state_dict（Apache-2.0 相关，见 THIRD_PARTY_NOTICES）。
- `load_feature_model()` 负责：加载权重 → `.eval()` → `.to(device)` → 返回可推理模型。模型缓存放在 backend 内部，业务层无感。
- 权重文件路径由基础设施配置（打包内嵌或首启下载），非研究 `work/dinov2_weights`。

## 9. 当前开发机事实（如实记录）

- 开发机：Windows 11 Pro，AMD Radeon RX 6750 GRE。
- **H1 目标 = CPU 跑通**；H2 的 AMD GPU 支持=**不确定/需实机验证**，不能默认 ROCm 可用。
- 若 6750 GRE 在 Windows 无稳定官方后端 → `AMD_GPU_BACKEND_BLOCKED`，H2 该设备标记 NOT SUPPORTED/未测试（诚实记录）。
