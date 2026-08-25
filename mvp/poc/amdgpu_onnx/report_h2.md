# H2-Preflight — DirectML 长时索引稳定性

- 源: D:\claudework\benchmark\datasets\real\originals\2.mkv (1280x688, 7667.5s)
- batch=8  目标帧=3834  完成帧=3834
- completed_all_frames=True
- GPU VRAM: NOT_AVAILABLE_VIA_ORT_DML

## checkpoint
| frames | RSS(MB) | fps | 上一批ms | all_finite | norm_max |
|---|---|---|---|---|---|
| 256 | 328.8515625 | 11.66 | 668.57 | True | 1.0 |
| 504 | 328.9140625 | 11.44 | 660.07 | True | 1.0 |
| 1000 | 328.234375 | 11.57 | 652.45 | True | 1.0 |
| 2000 | 334.43359375 | 11.73 | 663.31 | True | 1.0 |
| 3000 | 328.19140625 | 11.87 | 685.03 | True | 1.0 |
| 3834 | 336.8203125 | 11.9 | 181.21 | True | 1.0 |

## interval 增量
| 区间帧 | ΔMB | MB/1000帧 |
|---|---|---|
| 248 | 0.1 | 0.25 |
| 496 | -0.7 | -1.37 |
| 1000 | 6.2 | 6.2 |
| 1000 | -6.2 | -6.24 |
| 834 | 8.6 | 10.35 |

## 汇总
- 起始 RSS 278.49609375 MB | 峰值 336.8203125 MB | 最终 336.8203125 MB
- 增长 58.32421875 MB
- 全片耗时 323.9 s | 平均 fps 11.84 | 平均 batch 585.11 ms
- 后半程斜率 2.05 MB/1000帧 vs 整体 2.23 MB/1000帧

## Verdict
**MEMORY_STABLE** — warmup/cache overhead (one-time arena jump, then flat)
