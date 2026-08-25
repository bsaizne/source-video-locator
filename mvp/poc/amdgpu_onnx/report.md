# AMD GPU Feasibility POC — Result

- 模型: DINOv2 ViT-S/14 CLS 384D (frozen)
- 硬件: ['OrayIddDriver Device', 'AMD Radeon RX 6750 GRE 10GB']
- 输入: 960x540 -> 518x518 x 500 帧, batch=8
- torch 2.13.0+cpu (cpu-only), torch_threads=12
- WinML: winml / windows.ai.machinelearning: NOT_INSTALLED

## Perf (frames/s)
| engine | batch | fps | ms/frame |
|---|---|---|---|
| PyTorch CPU | 8 | 1.46 | 685.92 |
| ONNX CPU | 8 | 1.94 | 516.74 |
| ONNX DirectML | 8 | 15.15 | 66.02 |
| ONNX DirectML | 1 | 8.93 | 111.95 |

Speedup vs CPU(torch): **10.39x** (batch=1: 6.12x)

## Correctness (vs PyTorch CPU, L2 后)
- ONNX CPU: cosine=1.0, max|Δ|=4e-07, mean|Δ|=6e-08, l2norm∈[1.0,1.0]
- ONNX DML: cosine=0.999996, max|Δ|=0.0004795, mean|Δ|=0.00010803, l2norm∈[1.0,1.0]
- DML raw vs CPU raw max|Δ|: 0.0237243
- Top-1 neighbor agreement (DML vs CPU): 1.0

## Stability (DML 500 frames)
- all_finite max_norm_dev=0.0 mem_growth_mb=527.7

## GPU actually used?
- providers: ['DmlExecutionProvider', 'CPUExecutionProvider']
- GPU WMI: ['OrayIddDriver Device', 'AMD Radeon RX 6750 GRE 10GB']

## Verdict
**runs, correct, GPU used, speedup>=1.5x, stable**
- checks: ['+correctness', '+gpu_used', '+stability', '+speed>=1.5x', '+batch1_speed']
