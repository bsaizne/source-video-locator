# 局部特征库手动安装教程（SuperPoint / DISK / ALIKED / LightGlue）

> 创建：2026-09-01 | 目的：为「现代局部特征探针」（区分失败族 p08/p08b/p26/test4/t3-r12 的局部空间结构证据）准备依赖与权重。
> 环境事实：本机 venv（D:/claudework/video-dedup-tool/.venv）pypi 可达、GitHub 可达；**HuggingFace 直连不可达、Google Drive 不可达、hf-mirror 超时**（2026-09-01 实测）→ 权重需手动下载后放入本地目录。

## 0. 核心结论（先读）

- 代码：**四个算法的实现 kornia 全都有**（`kornia.feature.SuperPoint / DISK / ALIKED / LightGlue`），`pip install kornia` 一次到位，无需逐个 clone 官方仓库。
- 权重：**全部在 HuggingFace**（见 §2 地址表）。本机 HF 不可达 → 手动下载 .pth 文件到 `work/local_feature_weights/`，探针从本地路径加载（绕开自动下载）。

## 1. 安装 kornia（代码，pypi 可达）

```powershell
# 在项目 venv 里装(注意必须用绝对路径 python):
& "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m pip install kornia
```

- 依赖 torch/cv2/numpy 已存在，kornia 会装 kornia_rs 等少量新包；装完 §4 验证。
- 若只想用其中一个（如 DISK），也可只装 `kornia`（它统一提供全部四个）。

## 2. 权重下载地址表（需手动下载）

> 本机无法直连 HF/GDrive，请在**能上网的另一台机器 / 手机热点 / 代理**下打开下列页面，下载文件后拷入 `D:/claudework/benchmark/work/local_feature_weights/`。

| 算法 | HuggingFace 仓库（Files 页里找权重） | 权重文件名（以仓库 Files 页实际为准） | 官方 GitHub（源码，备查） |
|---|---|---|---|
| SuperPoint | https://huggingface.co/magic-leap-community/superpoint | `superpoint_v1.pth`（官方）；kornia 用 `kornia/superpoint` 仓库（若有） | https://github.com/magicleap/SuperPointPretrainedNetwork |
| DISK | https://huggingface.co/kornia/disk | `disk-d2.pth`（D2 变体，推荐）| https://github.com/etrulla/disk |
| ALIKED | https://huggingface.co/kornia/aliked | `aliked-n16.pt`（推荐轻量） / `aliked-n32.pt` | https://github.com/Shiaoming/ALIKED |
| LightGlue | https://huggingface.co/kornia/lightglue | `superpoint_lightglue_v0.1_0.pth` / `disk_lightglue_v0.1_0.pth` / `aliked_lightglue_v0.1_0.pth` | https://github.com/cvg/LightGlue |

- **LightGlue 本身不是特征提取器，是匹配器**：需搭配一个特征器（SuperPoint/DISK/ALIKED）使用。若探针目标是「局部空间结构证据」，建议先只下 **DISK 或 ALIKED**（自足特征器，不依赖匹配器）。
- SuperPoint 官方权重也可在 magic-leap 的 GitHub Releases 找（GitHub 可达）：https://github.com/magicleap/SuperPointPretrainedNetwork/releases

## 3. 权重放置约定

```text
D:/claudework/benchmark/work/local_feature_weights/
  ├── superpoint_v1.pth      (SuperPoint, 可选)
  ├── disk-d2.pth            (DISK D2, 推荐首选)
  ├── aliked-n16.pt          (ALIKED n16, 可选)
  └── superpoint_lightglue_v0.1_0.pth  (LightGlue, 需配套特征器)
```

## 4. 离线加载示例（探针用，绕开自动下载）

```python
import torch
from kornia.feature import DISK
from kornia.feature import SuperPoint

weights_dir = r"D:/claudework/benchmark/work/local_feature_weights"

# DISK（torch.hub 权重 -> 手动 load_state_dict, 完全离线）:
disk = DISK()
sd = torch.load(weights_dir + "/disk-d2.pth", map_location="cpu", weights_only=True)
if isinstance(sd, dict) and "state_dict" in sd:
    sd = sd["state_dict"]
disk.load_state_dict(sd, strict=False)
disk.eval()

# SuperPoint（kornia 支持 weights 参数, 可传本地路径）:
sp = SuperPoint(weights=weights_dir + "/superpoint_v1.pth")

# 推理: 输入 [B,3,H,W] 归一化张量
# laf, res = disk(torch.tensor(frames_float32))   # DISK: laf=关键点, res={'descriptors':...}
```

## 5. 验证脚本

```python
# work/_lf_check.py —— 下载完权重后跑一下确认可加载
import torch
from pathlib import Path
from kornia.feature import DISK

wd = Path(r"D:/claudework/benchmark/work/local_feature_weights")
print("weights:", sorted(p.name for p in wd.glob("*.pth")) + sorted(p.name for p in wd.glob("*.pt")))
d = DISK()
sd = torch.load(wd / "disk-d2.pth", map_location="cpu", weights_only=True)
if isinstance(sd, dict) and "state_dict" in sd: sd = sd["state_dict"]
d.load_state_dict(sd, strict=False); d.eval()
x = torch.randn(1, 3, 480, 480)
with torch.no_grad():
    laf, res = d(x)
print("DISK OK: keypoints", laf.shape, "descriptors", res["descriptors"].shape)
```

## 6. 网络受限说明（诚实标记）

- 本机 pypi/GitHub 可达 → `pip install kornia` 可行；
- HF 直连 / Google Drive / hf-mirror 均不可达（2026-09-01 实测）→ 权重只能手动下载（另一台机器 / 手机热点 / 代理），放 §3 目录；
- 若你装完 kornia 后想先自动试一次（某些 kornia 版本权重在 GitHub release 也有镜像），可先跑 §5，失败再手动下——以 `BLOCKED` 如实标记为准。

## 7. 与项目探针的衔接

- 探针目标：用局部空间结构证据测「能否区分 p08/p08b/p26/test4/t3-r12」——即 FAILURE_TAXONOMY.md 的 A 类（召回失败）与 B 类（区分度失败）是否可被局部特征救回；
- 探针脚本约定：`mvp/scripts/research_local_feature.py`（待建），读取 §3 权重，对每个失败案例算「解说帧 vs 原片 top-100」的局部特征 GT rank；
- 判据沿用 Experiment X：GT 是否进 top-K / 是否被干扰压过（对照 M6 的 CLS/patch 基线）。