# 视频片段反向定位引擎 Benchmark

对候选视频匹配/复制片段定位引擎做统一、可重复、真实素材 Benchmark，
为后续开发 Windows + macOS 桌面软件（Edited Video → Original Video 片段定位）做技术选型。

## 候选引擎

| 引擎 | 定位 | 状态 |
|---|---|---|
| VDF (videoduplicatefinder) | 工程底座 | 见 results/vdf/ |
| TransVCL | 精确定位（深度学习） | BLOCKED：模型在 Google Drive 无法下载 |
| VCSL / VTA | 传统时间定位 | 最小实验实现，见 results/vcsl/ |

## 目录

```
benchmark/
├── environment.json        # 本机环境实测
├── ground_truth.json       # 合成 + 真实数据集 ground truth
├── benchmark_results.json  # 汇总结果
├── benchmark_report.md/html
├── ENGINE_LICENSE_MATRIX.md
├── MODEL_LICENSES.md
├── ARCHITECTURE_ANALYSIS.md
├── engines/                # 各引擎源码/二进制
├── datasets/               # synthetic/ + real/
├── results/                # 每引擎原始结果
└── src/                    # benchmark 框架
```

## 运行

```bash
# 环境
D:\claudework\video-dedup-tool\.venv\Scripts\python.exe src/benchmark.py --engine all --dataset synthetic

# 单引擎
... src/benchmark.py --engine vdf --dataset synthetic

# 生成报告
... src/report.py
```

## 依赖说明（本机）

- Python 3.13（复用 video-dedup-tool venv）
- ffmpeg 7.1（imageio_ffmpeg 自带 + gyan build）
- ffprobe（static-ffmpeg 下载）
- opencv-python 5.0 / numpy 2.5
- 无 NVIDIA GPU（AMD RX6750），深度学习引擎仅 CPU

## 测试数据集

- **synthetic/**: 人工可控原片（90s，6 个不同场景）+ A1~A12 编辑变换
- **real/**: 真实素材（用户提供）

## 结论

见 `benchmark_report.md`。所有结论基于实际实验结果，非 README 推断。
