# HANDOFF — bug1（text_anchor CJK）四片生产 A/B（2026-10-29 自动跑批）

> 口径：同代码、同索引缓存、同 GT；两臂仅 `text_anchor_enabled` 不同。
> 指标 = `measure_shot_recall.evaluate`（严格 / 仅主 span=导出实得 / 场景 / 假阳）。

## 逐片

| 片 | 臂 | 严格 | 仅主span | 场景 | 假阳 | n_pos |
|---|---|---|---|---|---|---|
| 2mkv | on | 43 | 42 | 43 | 3 | 43 |
| 2mkv | off | 43 | 42 | 43 | 3 | 43 |
| test1 | on | 43 | 42 | 44 | 0 | 44 |
| test1 | off | 43 | 42 | 44 | 0 | 44 |
| test2 | on | 25 | 24 | 25 | 0 | 26 |
| test2 | off | 25 | 24 | 25 | 0 | 26 |
| test3 | on | 37 | 36 | 37 | 1 | 37 |
| test3 | off | 37 | 36 | 37 | 1 | 37 |

## 池化

| 臂 | 严格 | 仅主span | 场景 | 假阳 |
|---|---|---|---|---|
| on | 148/150 | 144/150 | 149 | 4 |
| off | 148/150 | 144/150 | 149 | 4 |

## 增量（on − off）

- 严格 +0 · 仅主 span +0 · 假阳 +0

**建议（未执行，需口令）**：持平：默认不动，等用户裁决是否保留该腿

## 产物

- `work/close_20261029/bug1ab/{on,off}_{case}.results.json`
- `work/close_20261029/bug1ab/compare.json`
- 日志 `work/close_20261029/bug1ab/run.log`
