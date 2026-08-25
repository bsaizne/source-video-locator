# 视频片段反向定位引擎 Benchmark — 项目交接文档

> 生成日期：2026-08-24（v3，synthetic + real 三引擎实测完成，TransVCL 已实测）
> 用途：让新的 Claude 对话无缝继续开发本 benchmark 项目。
> 读这份文档 + `D:\VideoLocalization_Engine_Benchmark_Claude任务书.md`（任务书）即可接续。

---

## 1. 项目背景

目标（任务书第一阶段）：对三个候选视频匹配/复制片段定位引擎做统一、可重复、真实素材 Benchmark，最终决定哪个方案最适合后续开发 Windows + macOS 桌面软件（Edited Video → Original Video 片段定位提取工具）。

**已确认的关键决策（用户拍板）：**
- Dataset B 真实素材：**已由用户提供**（2.mkv 原片 + 1.mp4 解说，GT 已建，Phase 8 完成）
- 推进策略：严格按任务书顺序 VDF → TransVCL → VCSL，装不上如实标记 BLOCKED，不伪造结果
- 本轮不配置 macOS CI，先聚焦 Windows，报告标注"仅 Windows 实测"
- TransVCL：模型由用户手动下载（`D:\claudework\model_1.pth`/`model_2.pth`），CPU 推理已实测（结果见 §12）

---

## 2. 当前已完成的功能

| # | 功能 | 状态 |
|---|---|---|
| Phase 1 | 环境检查 + `environment.json` | ✅ 完成 |
| Phase 2 | **VDF 跑通**（CLI + partial-clip 检测 + adapter） | ✅ 完成，synthetic 已出结果 |
| Phase 3 | TransVCL 仓库 clone + 可行性调研 | ✅ 完成，**已实测**（模型已下载，CPU 推理跑通，见 §12） |
| Phase 4 | VCSL/VTA 最小实验 pipeline + adapter | ✅ 完成，synthetic 已出结果 |
| Phase 5 | 统一 Engine Adapter 抽象 + 3 个 adapter | ✅ 完成（VDF/VCSL/TransVCL 均可用） |
| Phase 6 | Dataset A 合成素材生成（A1~A12，14 个测试） | ✅ 完成 |
| Phase 7 | **三引擎跑 synthetic benchmark** | ✅ 完成，结果已聚合到 `benchmark_results.json` |
| Phase 8 | **真实视频 benchmark**（real 数据集：2.mkv 原片 + 1.mp4 解说，GT 7 段） | ✅ 完成，三引擎均已跑（结果见 §12） |
| Phase 9 | **报告生成** | ✅ 完成（`benchmark_report.md/.html`） |
| Phase 10 | License 矩阵 + 架构分析 | ✅ 完成（`ENGINE_LICENSE_MATRIX.md`、`MODEL_LICENSES.md`、`ARCHITECTURE_ANALYSIS.md`） |
| 其他 | ffprobe 8.0.1 已获取（VDF 关键依赖） | ✅ 就位 |

---

## 3. 当前未完成的功能

| # | 未完成项 | 原因 / 下一步 |
|---|---|---|
| Phase 11 | 最终技术选型（Q1~Q6 + 结论 A/B/C + 权重评分） | ✅ **已完成**（2026-08-24，见 §13 `TECHNOLOGY_SELECTION.md`） |
| Phase 2 (可选) | VDF 的 AI matching 功能（`--ai-matching`/`--ai-partial`） | 默认关闭（首次运行需下载 ~100MB ONNX/DINOv2）。如需测视觉 partial 可开 |

---

## 4. 当前项目技术栈

- **Python 3.13.14** — 复用 `D:\claudework\video-dedup-tool\.venv`（不是独立 venv！）
- **关键包**（已装）：opencv-python 5.0.0、numpy 2.5.2、imageio_ffmpeg 0.6.0（自带 ffmpeg）、static-ffmpeg 3.0、**torch 2.13.0+cpu**、**torchvision 0.28.0+cpu**、**pandas 3.0.5**、**loguru 0.7.3**（2026-08-24 新增，TransVCL 依赖）
- **TransVCL 模型**：`D:\claudework\model_1.pth` / `model_2.pth`（各 83MB，2026-08-24 用户下载，已用于实测）
- **ffmpeg**：`benchmark/tools/ffmpeg.exe`（7.1，从 imageio_ffmpeg 提取）
- **ffprobe**：`D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe`（8.0.1）
  - 注意：`engines/vdf/extracted/` 里也应有一份 ffprobe.exe（VDF 需要同目录或 PATH 找到）
- **VDF CLI**：`benchmark/engines/vdf/extracted/vdf-cli.exe`（4.1.x，自包含 .NET 二进制，无需 .NET SDK）
- **硬件**：Windows 11 Pro、AMD Ryzen 5 5600、16GB RAM、AMD RX 6750 GRE 10GB（**无 NVIDIA CUDA**，PyTorch 只能 CPU；AMD 卡无法用 CUDA 后端）
- **网络**：github.com / pypi.org 可达（但慢）；**Google Drive 连接失败**（但模型已由用户手动下载，绕过此限制）

---

## 5. 目录结构

```
D:\claudework\benchmark\
├── README.md                       # 项目说明
├── environment.json                # 环境实测数据
├── ENGINE_LICENSE_MATRIX.md        # 引擎 License 对比
├── MODEL_LICENSES.md               # 模型 License 记录
├── ARCHITECTURE_ANALYSIS.md        # 跨平台集成分析
├── benchmark_results.json          # 聚合汇总（三引擎）
├── benchmark_report.md / .html     # 报告（synthetic）
├── PROJECT_HANDOFF.md              # 本文档
├── engines/
│   ├── vdf/
│   │   ├── cli-win.zip             # VDF CLI 下载包（已解压）
│   │   └── extracted/              # vdf-cli.exe + ffmpeg.exe + ffprobe.exe
│   └── transvcl/                   # TransVCL 完整 clone
├── src/
│   ├── benchmark.py                # 统一 runner（入口）
│   ├── dataset_a.py                # Dataset A 生成器
│   ├── env_check.py                # 环境检测
│   ├── metrics.py                  # 评估指标
│   ├── report.py                   # 报告生成
│   ├── orb_features.py             # ORB-BOW 256 维帧特征（TransVCL adapter 用）【新增】
│   ├── transvcl_feasibility.md     # TransVCL BLOCKED 调研（已过时，见 §12）
│   └── adapters/
│       ├── base.py                 # 引擎抽象基类
│       ├── vdf.py                  # VDF adapter（已基于真实输出校准）
│       ├── transvcl.py             # TransVCL adapter（已重写为真实 CPU 推理）【重写】
│       └── vcsl.py                 # VCSL/VTA 最小 pipeline
├── datasets/
│   ├── synthetic/
│   │   ├── originals/source.mp4    # 90s 合成原片（6 场景）
│   │   ├── edited/                 # A1~A12 共 14 个编辑视频
│   │   └── ground_truth.json       # 17 个 ground truth 段
│   └── real/
│       ├── originals/2.mkv         # 真实原片（The Gorge 电影，1280×688，7667s≈2.1h）【用户提供】
│       ├── edited/1.mp4            # 竖屏解说视频（544×960，126.8s）
│       └── ground_truth.json       # 7 个 ground truth 段（ORB 定位 + 人工核对）
├── results/
│   ├── vdf/                        # ✅ synthetic 14 测试（13 ok + a9 error）+ real error + metrics.json
│   ├── transvcl/                   # ✅ synthetic 14 全跑完 + real 1（均 recall 0）+ metrics.json
│   └── vcsl/                       # ✅ synthetic 14 + real 1（real recall 0）+ metrics.json
├── tools/
│   └── ffmpeg.exe                  # 7.1（ffprobe 在 static_ffmpeg 目录）
├── work/                           # 运行时 staging（VDF staging / transvcl_feats 特征缓存 / pair csv）
│   └── transvcl_feats/             # TransVCL ORB-BOW 特征缓存（{alias}.npy）
├── report_summary.json             # report.py 输出（overall/transforms/fp）
└── logs/                           # benchmark 运行日志
```

---

## 6. 已创建文件清单及作用

| 文件 | 作用 |
|---|---|
| `src/benchmark.py` | 统一 runner。`--engine vdf/vcsl/transvcl/all` + `--dataset synthetic/real/all`。逐 pair 跑引擎、保存原始结果、汇总指标到 `benchmark_results.json`。**是主入口**。⚠️ 每次运行会**覆盖** `benchmark_results.json`，只保留本次引擎/数据集的汇总（跑 `--engine all` 才能三引擎都进汇总）。 |
| `src/dataset_a.py` | 生成合成原片 + A1~A12 编辑版 + ground_truth.json。原片=6 个 15s 不同场景（不同底色+几何图案+不同音频音调）。 |
| `src/env_check.py` | 生成 `environment.json`（OS/CPU/GPU/RAM/磁盘/工具链/包版本）。已运行。 |
| `src/metrics.py` | 评估指标：localization accuracy（±0.25/0.5/1/2s）、temporal IoU(0.5/0.7/0.9)、Recall、Precision、False Positives、summarize 聚合。 |
| `src/report.py` | 读 results/*/ + ground_truth，生成 `benchmark_report.md/.html` + `report_summary.json`。含总体表（synthetic/real 分数据集）、按变换类型表、FP 示例、人类可读 PASS/WARN/FAIL 日志（recall>0 才标 PASS）。⚠️ **不写** `benchmark_results.json`（那是 benchmark.py 的专属输出，避免覆盖）。 |
| `src/orb_features.py` | **ORB-BOW 256 维帧特征提取**（TransVCL adapter 用）。cv2 抽帧 → ORB 描述子 → kmeans 256 词 codebook → L1 归一化 BOW 直方图。 |
| `src/transvcl_feasibility.md` | TransVCL 早期 BLOCKED 调研记录（模型下载不了）。**已过时**——模型已下载并实测，见 §12。 |
| `src/adapters/base.py` | `VideoLocalizationEngine` 抽象基类（index_original/match/get_results + `_ok`/`_blocked`）。 |
| `src/adapters/vdf.py` | **已基于真实输出校准**（非猜测）。解析 VDF 4.1.x JSON：顶层数组 → `Items[]` → 找 `Flags` 含 "PartialClip" 的项 → 读 `PartialClipOffset`（HH:MM:SS）。AI 默认关闭。 |
| `src/adapters/transvcl.py` | **已重写为真实 CPU 推理**（2026-08-24）：ORB-BOW 特征 → 缓存 → 调 run.py（subprocess）→ 解析 JSON。见 §12 的负面结论。 |
| `src/adapters/vcsl.py` | 最小实验 pipeline：cv2 1fps 提帧 → 32x32 灰度特征 → 余弦相似度矩阵 → Hough voting over offsets → 聚类合并。非官方 VCSL 实现，结果标注"minimal experimental"。 |
| `engines/transvcl/run.py` | **FORK 修改**（2026-08-24）：支持 `--device cpu/mps`、去 `.cuda()`、`--device` 类型改 str、输出解析改 `rsplit`。见 §10.4。 |
| `ENGINE_LICENSE_MATRIX.md` | VDF=**AGPLv3**、TransVCL=MIT、VCSL=MIT。VDF 对商业闭源产品有传染性风险。 |
| `MODEL_LICENSES.md` | 模型来源/License 记录。TransVCL 模型**已下载**（`D:\claudework\model_1.pth`/`model_2.pth`）。 |
| `ARCHITECTURE_ANALYSIS.md` | 跨平台集成分析。推荐"自研核心(MIT) + 可选 VDF 子进程"架构。 |
| `README.md` | 项目说明 + 运行方式。 |

---

## 7. 数据模型结构

### ground_truth.json
```json
{
  "video_pair": "synthetic_source",
  "segments": [
    {
      "test": "a1",
      "edited_start": 0.0,
      "edited_end": 5.0,
      "original_start": 20.0,
      "original_end": 25.0,
      "transform": "direct crop",
      "extra": {}
    }
  ]
}
```

### 引擎统一输出（adapter 返回，存 results/<engine>/<test>.json）
```json
{
  "engine": "VDF",
  "video_pair": "a1",
  "segments": [
    {
      "edited_start": 0.0,
      "edited_end": 5.2,
      "predicted_original_start": 120.4,
      "predicted_original_end": 125.8,
      "score": 0.93,
      "confidence": "high"
    }
  ],
  "runtime_seconds": 31.2,
  "index_seconds": 20.0,
  "search_seconds": 10.0,
  "verification_seconds": 1.2,
  "status": "ok" | "blocked" | "error",
  "note": "..."
}
```

### benchmark_results.json（benchmark.py 聚合，engine × dataset）
```json
[
  {"engine":"vdf","dataset":"synthetic","recall":0.46,"precision":0.46,"iou_0_5":0.46,"blocked":true,...},
  {"engine":"transvcl","dataset":"synthetic","recall":0.0,"precision":0.0,"blocked":false,...},
  {"engine":"vcsl","dataset":"synthetic","recall":0.76,"precision":0.25,"iou_0_5":0.76,"blocked":false,...},
  {"engine":"vdf","dataset":"real","status":"no-ok","blocked":true},
  {"engine":"transvcl","dataset":"real","recall":0.0,"blocked":false},
  {"engine":"vcsl","dataset":"real","recall":0.0,"blocked":false}
]
```
⚠️ 注意：`benchmark_results.json` 由 `benchmark.py` 独家写入（6 行 engine×dataset 汇总）。`report.py` **不再写这个文件**，而是写 `report_summary.json`（overall/transforms/false_positives），避免互相覆盖（2026-08-24 修复）。

---

## 8. 已实现的重要业务逻辑

### 8.1 合成原片设计（dataset_a.py）
- 6 个 15s 场景，每个：不同底色（color 源）+ 移动的 testsrc2 前景（overlay 动画）+ **不同的几何图案**（drawbox/drawgrid）+ **不同音调音频**（sine 不同频率）
- 用 concat demuxer 拼成 90s 原片
- **关键教训**：最初只有底色不同，导致 32x32 灰度特征无法区分场景，VCSL 产生大量假阳性。加了 distinct 几何图案后才可区分。这模拟了真实影片"不同场景内容不同"的性质。

### 8.2 VCSL 最小 pipeline（vcsl.py）
1. cv2 读视频，按 `fps=1` 间隔抽帧（step = round(fps/1.0)）
2. 每帧转灰度 → resize 32x32 → 展平 → L2 归一化作为特征
3. 查询帧特征 × 参考帧特征 = 余弦相似度矩阵 `[Nq, Nr]`
4. 对每个查询帧，取 top_k=5 个最高分参考帧（>0.85），累计"偏移量 = 参考时间 - 查询时间"
5. 偏移量聚类（容忍 1s），取 ≥min_hits=3 的簇为候选片段
6. **核心端点估计**：用中位数附近 2s 内的密集投票帧估计起止，剔除漂移离群点
7. 合并重叠片段（gap<3s 且原片间隔<5s 合并）

**实测结果（synthetic）**：Recall 76.2%、Precision 25.5%、IoU@0.5=76%、mean start err=0.94s、mean end err=2.04s。**高召回低精度**——能找到大部分真实片段但产生大量 FP（59 预测中 46 个 FP）。对镜像(a9)、变速鲁棒性差。

### 8.3 VDF adapter（vdf.py）——**已实测校准**
- 用 staging 目录把原片和编辑片复制为 source.mp4/edited.mp4 再跑 `vdf-cli scan-and-compare`
- 关键参数：`--partial-clip-detection --partial-clip-min-ratio 0.02`（音频指纹）；AI 默认关闭
- `_parse`（已验证）：VDF 4.1.x JSON 输出是**顶层数组**，每元素是一个 duplicate 组，含 `Items[]`（成员文件）。对每个 item 检查 `Path` 是否含 edited 文件名 → `Flags` 含 "PartialClip" → 读 `PartialClipOffset`（"HH:MM:SS"）作为原片起始，用编辑片时长推终点
- **已知局限**：partial-clip 每组只报一个 offset，**多片段编辑(A10)会被折叠成单组**；这是 VDF 行为限制，不是解析 bug

**实测结果（synthetic，音频指纹版）**：Recall 46.2%、Precision 46.2%、IoU@0.5=46%、mean start err=1.5s、mean end err=0.77s、avg runtime 1.3s。
- ✅ 命中：a1 直接裁剪、a6 调色、a12 组合攻击、a8 变速(0.8/1.2/1.5x) 全部 recall=1.0
- ❌ 未命中：a2 缩放、a3 竖屏、a4 字幕、a5 Logo、a7 重编码（audio partial-clip 对画面型变换+音频不变的场景应仍匹配，但实测 0%——可能是 staging 目录内两文件音频指纹相似度或阈值问题，**值得复查**）
- ❌ a10 多段拼接、a11 转场 recall=0（单组 offset 限制，符合预期）
- ⚠️ a9 镜像 → error（"no parseable duplicates"）

**实测结果（real，"解说套电影"）**：**error（no parseable duplicates）**。音频指纹对竖屏解说嵌入横屏电影失效——解说叠加人声/重混音，音频指纹无法与原片匹配。这是音频指纹方案的**本质局限**（§12.3）。

### 8.4 TransVCL adapter（transvcl.py）——**2026-08-24 实测**
- ORB-BOW 256 维帧特征（`src/orb_features.py`）：cv2 抽帧(fps=2) → ORB 描述子 → kmeans 256 词 codebook（从原片学）→ L1 归一化 BOW 直方图 → `[T,256]` npy
- 特征缓存 `work/transvcl_feats/{alias}.npy`（原片缓存，多 edited 复用）
- 调 run.py（subprocess，`--device cpu --inference-batch 1`），解析 JSON（坐标=特征帧序号，/fps 转秒）
- **结果：synthetic + real 全部跑通但 recall=0**（ORB-BOW 与官方 VCSL/ISC 特征分布不匹配，输出全低置信度噪声）。见 §12.2

### 8.5 评估指标（metrics.py）
- IoU-based 贪心匹配（每个 GT 配最优预测，IoU≥0.5）
- 统计 start/end 误差、各容差精度、IoU 通过率、Recall/Precision、FP/漏检

### 8.6 报告生成（report.py）
- 已产出 synthetic + real 合并报告。总体表（synthetic/real 分数据集）+ 按变换类型表 + FP 示例 + PASS/WARN/FAIL 日志（recall>0 才标 PASS）
- 输出 `benchmark_report.md/.html` + `report_summary.json`（**不覆盖** benchmark.py 的 `benchmark_results.json`）

### 8.7 real 数据集构建（2026-08-24）
- 原片 `datasets/real/originals/2.mkv`（The Gorge 电影，1280×688，23.976fps，**7667.5s ≈ 2.1h**）；编辑片 `datasets/real/edited/1.mp4`（竖屏解说，544×960，29fps，126.8s，视频含缩小的电影画面 + 黑边）
- **GT 建立方式**：半自动——先 32x32 粗扫 top 位置，再用 **ORB 特征点匹配**复核（ORB 内点数>20 才可信），人工核对配对图后聚类引用段。GT 7 段，置信度 weak/ok 记录在 `extra.confidence`。详见记忆"benchmark-real-material-lesson"
- **关键教训**：32x32 灰度特征在"解说套电影"上系统性失效（黑边/暗部误判），GT 中所有位置都经 ORB + 人工核对确认，不能用 32x32 结果当 GT

---

## 9. 下一步开发计划（严格顺序）

### STEP 1：Phase 11 最终技术选型（唯一剩余大项）
synthetic + real 数据已齐（见 §12），可基于实测数据完成：
- 按权重打分（Accuracy 35 / Robustness 20 / Speed 15 / Long-video 10 / Integration 10 / Cross-platform 5 / License 5）
- 回答任务书 Q1~Q6 + 结论 A（最佳纯算法）/ B（最佳工程底座）/ C（最佳组合架构）
- 所有结论必须引用实验数据（`benchmark_report.md` + §12 表）
- **关键数据点**：VCSL 思路在 synthetic 高召回但 real 失效（32x32 弱特征）；VDF 音频指纹对"解说套电影"失效；TransVCL 在非官方特征下无有效输出

### STEP 2（可选）：改进候选方案再测
- VCSL 换 ORB/强特征（记忆教训：32x32 在 real 失效，ORB 已人工验证有效）
- VDF 复查 a2~a5/a7 的 recall=0（降 `--partial-clip-similarity` 阈值）
- 若要继续 TransVCL：需升级为稠密 CNN 特征（接近官方 ISC 分布），复杂度高

### STEP 3：产出最终交付物
- 更新 `ARCHITECTURE_ANALYSIS.md`（用 real 数据修正）
- 更新 `README.md`（运行方式 + 最终选型结论）
- 生成最终报告

---

## 10. 开发注意事项

### 10.1 环境相关
- **Python 用**：`D:\claudework\video-dedup-tool\.venv\Scripts\python.exe`（不是 python/python3，bash PATH 里没有）
- **ffmpeg 用**：`benchmark/tools/ffmpeg.exe`（7.1）
- **ffprobe 用**：`video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe`（8.0.1）；**VDF 目录里也有一份**（`engines/vdf/extracted/ffprobe.exe`）
- **VDF 报 "Cannot find FFmpeg/FFprobe"**：把 ffmpeg.exe + ffprobe.exe 放到 `engines/vdf/extracted/` 同目录，或加到 PATH
- **无 CUDA**：PyTorch 只能 CPU（AMD 卡无 CUDA 后端；ROCm 仅 Linux，未采用）。TransVCL CPU 推理已实测。macOS MPS 可行但**未实测**（无 Apple Silicon Mac）
- **网络慢且不稳定**：大文件下载用 `curl -C -`（断点续传）+ `--retry`，多次迭代续传
- **bash 中文乱码**：VDF 输出是 GBK，用 `iconv -f GBK -t UTF-8` 转码查看

### 10.2 编码问题
- **Windows 下 ffmpeg 的 drawtext fontfile 转义**：`fontfile=C\\\\:/Windows/Fonts/arial.ttf`（双反斜杠+转义冒号），text 内空格用 `\\ `，避免单引号
- filter_complex 里 drawbox 和 drawtext 之间必须用**逗号**分隔（不是冒号）
- 写文件统一 `encoding="utf-8"`

### 10.3 不伪造结果的铁律
- 引擎装不上/模型下不了 → 标记 `status: blocked` + note 说明原因，不填假数据
- 报告标注"仅 Windows 实测"，不能声称双平台验证

### 10.4 已知坑 / 待复查项
- **VDF 对 a2 缩放/a3 竖屏/a4 字幕/a5 Logo/a7 重编码 recall=0%**——这些是纯画面变换且音频通常不变，理论上 audio partial-clip 应能匹配。可能原因：staging 目录内 source.mp4/edited.mp4 的音频指纹相似度未达阈值，或 VDF 把这些对当"同文件不同版本"处理。**待复查**（可降 `--partial-clip-similarity` 阈值再测，Phase 11 可选）
- VCSL 是"最小实验实现"，Precision 只有 25%，结果要注明不是官方 VCSL benchmark
- `benchmark.py` 里 `Tee` 重定向 stdout 到日志文件，运行完记得看日志
- **`benchmark.py` 每次运行覆盖 `benchmark_results.json`**——要三引擎汇总必须跑 `--engine all`，不要单独跑单引擎后看汇总。⚠️ `report.py` 写的是 `report_summary.json`（不同的文件），**不会**破坏 `benchmark_results.json`（2026-08-24 修复）
- `results/vcsl/` 和 `results/vdf/` 已有结果文件，重新跑会覆盖（可复现）
- `tools/` 里下载残留已清理；`engines/vcsl-main.tar.gz` 之前删不掉（被占用），可手动确认删除
- VDF 的 AI 功能（--ai-matching）首次运行会下载 ~100MB 组件（ONNX Runtime + DINOv2），网络慢时可能很慢；默认关闭
- **TransVCL 已实测但无有效输出**（2026-08-24）：ORB-BOW 特征与官方 VCSL/ISC 预训练分布不匹配，输出全低置信度噪声（conf<0.07），recall=0。**结论：TransVCL 需官方特征才能工作**，见 §12.2
- **run.py fork 修改点**：① `--device` 类型 int→str；② device 解析支持 cpu/mps；③ `.cuda()`→`.to(device)`；④ 输出块号解析 `split("_")[0:2]`→`rsplit("_",2)`（否则带下划线文件名崩溃）。见 `engines/transvcl/run.py` 的 `[FORK]` 注释
- **TransVCL 特征缓存**：`work/transvcl_feats/{alias}.npy`（alias 去掉点/横线，如 `a8_1.5`→`a8_1_5`）。重新跑不同数据集会复用缓存

### 10.5 数据一致性
- synthetic ground_truth 有 17 段，对应 14 个测试（a10 3段、a11 2段、a8 3个变体各1段）
- GT 与 edited 文件已核对一致（无缺文件）

---

## 11. 交付物清单（当前状态）

```
benchmark/
├── README.md                    ✅
├── environment.json             ✅
├── datasets/real/ground_truth.json  ✅ (7 段，2026-08-24)
├── benchmark_results.json       ✅ (3 引擎 × 2 数据集 = 6 行汇总)
├── benchmark_report.md/.html    ✅ (synthetic + real 合并)
├── ENGINE_LICENSE_MATRIX.md     ✅
├── MODEL_LICENSES.md            ✅ (TransVCL 模型已登记下载)
├── ARCHITECTURE_ANALYSIS.md     ⏳ (预判，待 Phase 11 用 real 数据修正)
├── results/vdf/                 ✅ (synthetic 13 ok + a9 error; real error)
├── results/transvcl/            ✅ (synthetic 14 全跑完 recall 0; real recall 0)
├── results/vcsl/                ✅ (synthetic 14; real recall 0)
├── src/orb_features.py          ✅ (新增)
├── report_summary.json          ✅ (report.py 输出，新增)
└── logs/                        ✅
```

---

## 12. 三引擎实测结果（synthetic + real，2026-08-24）

> 数据来源：`benchmark_results.json` + `benchmark_report.md`。仅 Windows 实测。

### 12.1 汇总表

| 数据集 | 引擎 | Precision | Recall | IoU@0.5 | Avg Runtime(s) | 备注 |
|---|---|---|---|---|---|---|
| synthetic | VDF | 46.2% | 46.2% | 0.46 | 1.1 | a9 镜像 error |
| synthetic | TransVCL | 0% | 0% | 0.00 | 4.9 | 特征不匹配，无有效输出 |
| synthetic | VCSL | 25.5% | 76.2% | 0.76 | 0.7 | 高召回低精度，FP 多 |
| real | VDF | — | — | — | 26.0 | **error**（音频指纹对解说套电影失效） |
| real | TransVCL | 0% | 0% | 0.00 | 4.9 | 同 synthetic，特征不匹配 |
| real | VCSL | 0% | 0% | 0.00 | — | **32x32 弱特征在真实素材失效** |

### 12.2 TransVCL 关键结论（本次新增实测）

- **CPU 推理跑通**：改 run.py 支持 `--device cpu` 后，synthetic 14 个 pair + real 全部运行无崩溃，不再 BLOCKED。
- **但 ORB-BOW 特征与官方 VCSL/ISC 预训练分布严重不匹配**：低阈值诊断（conf-thre=0.01）显示模型输出全为低置信度噪声（conf 0.035~0.066），查询区间固定、参考均匀铺满——模型把两个序列当不相关输入。
- **结论**：TransVCL 只有在**官方 ISC/VCSL 特征**下才能工作（论文 65%+）。本项目用 ORB-BOW 喂入属预期失败，**如实记录，不伪造**。
- 若要真正跑出 TransVCL 成绩，需升级为稠密 CNN 帧特征（ResNet/ML-GoogLeNet 256 维），复杂度高，本轮未做（用户决策：如实记录负面结果）。
- macOS MPS 后端可行但**未实测**（无 Apple Silicon Mac）。

### 12.3 real 数据集（"解说套电影"）三引擎表现

- **VDF**：`no parseable duplicates`（error）。音频指纹对"竖屏解说套横屏电影"失效——解说音频叠加人声/重新混音，与原片音频指纹无法匹配。这是音频指纹方案的**本质局限**。
- **VCSL**：recall=0（32x32 灰度特征失效）。正是记忆里"benchmark-real-material-lesson"记录的教训：竖屏嵌入+黑边让 32x32 灰度把暗部/黑边误判，top 匹配全错。**需换 ORB/强特征**（ORB 人工核对已确认有效）。
- **TransVCL**：recall=0（特征不匹配，同 synthetic）。

### 12.4 初步倾向（Phase 11 待正式打分）

- **VCSL 思路（视觉特征 + 时间对齐）方向正确**，但 32x32 弱特征必须升级（ORB/DINOv2/CLIP + temporal re-ranking，即任务书 Candidate D）。
- **VDF 作为音频指纹补充有价值**（synthetic 变速/调色/组合 robust），但对重混音频的解说场景失效。
- **TransVCL** 依赖官方特征 + 高算力，跨平台部署重（torch + 特征管线），本 benchmark 下无有效输出。
- License 上 VCSL/TransVCL 都是 MIT，VDF 是 AGPLv3（商业传染风险）。

**下一轮**：完成 Phase 11 正式选型（§9 STEP 1），用上述数据按权重打分。

---

## 13. Phase 11 最终选型结果（2026-08-24）

> 详细文档：`TECHNOLOGY_SELECTION.md`（本文件旁）。按任务书 §36 权重（Accuracy 35/Robustness 20/Speed 15/Long-video 10/Integration 10/Cross-platform 5/License 5）打分，全部基于实测数据。

### 13.1 加权总分

| 引擎 | Accuracy(35) | Robust(20) | Speed(15) | Long(10) | Integ(10) | Cross(5) | Lic(5) | **加权总分** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| VCSL 思路 | 4.5 | 6.0 | 8.5 | 5.5 | 6.5 | 6.0 | 9.0 | **6.00** |
| VDF | 4.6 | 4.0 | 8.0 | 6.0 | 7.5 | 7.0 | 3.0 | **5.46** |
| TransVCL | 1.0 | 1.0 | 4.0 | 3.5 | 4.5 | 4.5 | 9.0 | **2.63** |

### 13.2 Q1~Q6 摘要

- **Q1** 最容易找到对应位置：synthetic 上 VCSL（76% recall）> VDF（46%）> TransVCL（0%）；**real 上三者全失败**。
- **Q2** 最鲁棒：VCSL 覆盖 9/14 变换最广；VDF 仅"音频不变"场景；real 全败。
- **Q3** 长原片：未跑 10/60/120min 梯度；2.1h real 数据点 VDF error、VCSL/TransVCL 无有效结果 → 无优胜者。
- **Q4** 最快：VCSL 0.7s > VDF 1.2s > TransVCL 5.0s（CPU）。
- **Q5** 最易集成：VDF（自包含 CLI，除 AGPL 风险）> VCSL（轻依赖，license 安全）> TransVCL（torch 重）。
- **Q6** 最终选型：**B（混合）**，不是纯 A 也不是纯 C。

### 13.3 三个结论

- **结论 A（最佳纯算法引擎）**：当前无合格引擎（real 全败）。最有潜力 = **VCSL 思路**（视觉+时间对齐方向对，只差特征）。
- **结论 B（最佳工程底座）**：**VDF**（工程最省，license 风险）/ **VCSL 自研底座**（license 安全，需投入开发）。
- **结论 C（最佳组合架构，推荐）**：**自研视觉定位核心（VCSL 思路升级：ORB→DINOv2/CLIP + temporal re-ranking + SSIM/ORB 精排去 FP）+ VDF 音频指纹辅助（子进程 AGPL 隔离）+ FFmpeg 提取**。

### 13.4 落地含义

- **不进入 GUI 开发**（任务书 §43："所有方案都不够准确 → 先研究特征 + re-ranking"）。
- 下一步 = §9 STEP 2：**升级 VCSL 特征（ORB/DINOv2）+ 加 temporal consistency re-ranking，在 real 数据集复测，直到 real recall > 0**。
- 可选复查：VDF `--partial-clip-similarity` 阈值 + `--ai-matching`。
- TransVCL 列为研究参考，不作为第一版底座（特征不匹配，真实上限未测出）。

---

# PART 2（2026-08-25）：Phase 13–19 研究收敛 + MVP 产品化交接

> 本部分是 PART 1（Phase 1~12）的续章，记录 DINOv2 路线从 13 到 19 的收敛、Phase 20 架构决策，以及转入 MVP 产品化的交接。**研究已冻结，MVP 开发已激活。**

## A. 研究阶段收尾（Phase 13~19）

**采用的技术路线**：Phase 11 结论 C —— 自研视觉定位核心（VCSL 思路：ORB→**DINOv2** + temporal re-ranking）。Phase 13~19 实际执行并收敛。

**冻结后的核心能力（corrected Segment GT，`datasets/real/ground_truth_corrected.json`）**：
- Candidate Recall：**recall_B = 7/7**（7 段正确区全部进入候选窗）——"哪段原片"问题已解决。
- Candidate Ranking：ExpA `n_reps`(α=0.5) rerank 修好 s2（rank 2→1）；s0/s1 深 rank6/5（相似场景混淆）。
- Fine Localization（连续镜头）：s0 0.571 / s1 0.647 / s2 0.5 / s3 0.75 / s6 0.75 —— 可靠。
- Multi-shot Montage（唯一硬伤）：**s4 0.333**（2–2.5s 编辑跨 3–4 个来源 shot）+ s5 0.455 & 反向跨段风险。

**关键阶段**：
- 13A/B/C：连续轨迹达成（s6 0.75/s1 0.632）；证原片 0.5fps 非瓶颈；证 gap tolerance 近无效、expanded query 有害。
- 14A/14A.1：全局 candidate retrieval（s0 被召回、869s 巨窗消除、7/7 正确区浮现）+ clustering 连续性修正（≤60s 无巨窗；gap 参数非杠杆）。
- 14C：edited query density —— **召回杠杆是查询窗口 span（pad 0→±4s，3/7→6/7）而非 fps**；更高 fps 反略伤 finloc。
- 15（Agent 视觉诊断，`src/diagnostics/`）：s2/s4=C 特征判别失败、s3=E GT 边界、s0/s1=B 相似场景混淆、s6=F 证据不足(已解)、s5=B 干净命中；贯穿主因="暗色+人物+军事纹理"语义混淆。
- 16A：corrected GT 复核收紧 s2/s3/s4 → **recall_B 7/7**（s3 由 miss 变命中）。
- 16B：ExpA `n_reps`(α=0.5) 采纳；ExpB patch / ExpC multi-scale 无净收益不采纳。16B.1 多模态复盘（s4 瓶颈=shot-based temporal localization，非查不到）。
- 17A / 18 / 19：finloc 三方向（multi-segment / 邻域投票 / cut-aware coverage）**均"修好 s4 却伤 3–5 段"→ 全部不采纳**；三轮一致证明 **per-orig 覆盖是对的**，round 级 cut 切分在 0.5fps 下不可行。

## B. Phase 20 架构决策（ARCHITECTURE_DECISION_PHASE20.md）

**最终推荐**：**不启动新的算法研究阶段。** P0 = 把已验证栈直接产品化；P1（仅当产品域蒙太奇占比高才做）= s4 单类定向验证（DINOv2 稠密 + VCSL/VTA 序列对齐），成功才接入二级定位器。**MVP READY = YES（有条件，版本一）**。
- **s4 判为可接受困难边界案例**（非必须攻克核心）。
- **sequence-level model（VCSL/VTA）引入条件**：①frame-level 优化到顶（已满足）②产品域蒙太奇占比高（需产品决策）③s4 单类定向验证正面（未满足）。TransVCL 的 0-recall 是"ORB-BOW 特征喂错"非其真实上限，但也不因其推荐。
- **4 条须显式指出的数据冲突**：s4 根因诊断（15 判 C 特征 vs 16B.1 判 temporal localization 主）、"s4 需序列级"vs"序列级在此数据 blocked"、s5 改好的稳健性（coverage 信号巧合）、召回 7/7 与 s0/s1 深 rank 的矛盾（Top-K=20 掩盖外观缺陷）。

## C. MVP 产品化（已激活）

- **产品**：Source Video Locator（本地 Edited→Original 来源定位与提取）。定位与边界见 `mvp/docs/MVP_PRODUCT_SPEC.md`。
- **Stage 0 设计文档已完成（`mvp/docs/` 8 份）**：MVP_PRODUCT_SPEC / MVP_ARCHITECTURE / CONFIDENCE_DESIGN / INDEX_SPEC / DEVICE_BACKEND_SPEC / TECH_STACK_DECISION / THIRD_PARTY_NOTICES / MVP_ROADMAP。
- **技术栈**：Python + PySide6（LGPL），Engine 单进程 torch/numpy，FFmpeg 子进程，PyInstaller。
- **硬件路线**：H1 Windows CPU（第一优先级）→ H2 Windows AMD → H3 macOS Apple Silicon。6750 GRE 的 ROCm/Windows 可用性**需实机验证**，不稳标 `AMD_GPU_BACKEND_BLOCKED` 继续 CPU。
- **关键落差点（无 GT 运行时）**：研究用 GT 窗口定义查询段，产品**无 GT** → 新增 `engine/segment` 做 edited shot 切分（产品胶水，不改冻结算法）。
- **研究代码处理**：REUSE（手写 ViT-S/14 模型+预处理+前向、longest_run、cosine_similarity、检索/聚类算法、v2_score）/ REFACTOR（feature extraction 入 DeviceBackend、narrow 去 GT/TransVCL 依赖、检索/聚类 I/O 去 benchmark 全局）/ REWRITE（frame 采样→FFmpeg、FFmpeg 工具集中化、FeatureStore、ConfidenceEngine、engine/segment）/ RESEARCH_ONLY（ta._dp_path、query_density_14c 整脚本、17A/18/19、patch/multi-scale、ORB-BOW/TransVCL/VDF）。

## D. 下一会话从哪继续

1. 读 `.agent/STATE.md`（研究冻结回顾 + MVP 当前状态）+ `ARCHITECTURE_DECISION_PHASE20.md`（研究结论）。
2. 读 `mvp/docs/`（8 份设计，为 Stage 1 编码的规格）。
3. **MVP Stage 1 起点**：`media/ffmpeg`（FFmpegIO：metadata/seek/抽帧/clip extract）→ `domain` + `infrastructure`；随后 CPUBackend+FeatureStore → ranking/retrieval/clustering（从研究提取）→ localization+confidence → engine/segment → app service → PySide6 UI → 打包验收 → 性能基准 + Confidence 标定（详见 `mvp/docs/MVP_ROADMAP.md §2`）。
4. **研究护栏**：不改冻结算法/GT、不新增 backbone/VLM、不重跑研究 benchmark、不把已证伪变体与 patch/multi-scale 引入 runtime、不做大规模 sweep。
