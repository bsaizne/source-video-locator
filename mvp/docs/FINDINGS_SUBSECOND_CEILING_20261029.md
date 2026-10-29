# FINDINGS — 亚秒起点修正（matrixprofile 方向）：天花板 2 行，判负关闭（2026-10-29）

> 来源：调研 v2 批次2 的 `matrixprofile`（1D 互相关做亚秒修正）。批次2 当时未测，
> 2026-10-29 讨论「唯一还冲着 AP@0.5s 去的候选」时准备开，**先算上限，5 分钟判负**。

## 结论

**不做。** 亚秒（±0.05~0.1s）修正最多只能让 **2~5 行**跨过 0.5s 阈值，
而现役误差分布的大头是**多秒级**（36 行偏 >5s、18 行偏 2~5s）——插值打不到。

## 误差分布（现役默认批，四片 150 行，起点口径 = 主 span 起点 vs GT `original[0]`）

| \|err\| 区间 | 行数 |
|---|---|
| ≤0.5s | **51** |
| (0.5, 0.55] | **2** |
| (0.5, 0.6] | 5 |
| (0.5, 0.75] | 11 |
| (0.75, 1.0] | 14 |
| (1.0, 1.5] | 9 |
| (1.5, 2.0] | 11 |
| (2, 5] | 18 |
| >5s | **36** |
| 中位 | 1.00s |

推论：±0.05s 修正的天花板 = **(0.5, 0.55] 的 2 行**；±0.1s = (0.5, 0.6] 的 5 行。
AP@0.5s 最多从 0.447 挪到 ~0.46，属测量噪声量级。

## 为什么这不是"参数没调好"

亚秒修正的前提是「峰的位置对、只是落在网格的另一侧」。实测分布否证这个前提：
51 行已在 0.5s 内（插值无收益），**其余的多秒级误差是"选错位置"**（跨镜头/兄弟机位族，
见 `Known Issues`），不是网格量化问题。同一族的既有读数也一致：XFeat 起点精修改了 198 行、
严格仅 +1。

## 未做（如实）

- **dense 10fps 曲线落盘管道未建**：原本是该实验的前置（批次2 的 VQ2D 扩窗就因为曲线不落盘
  只能退到 1fps 代理）。既然天花板已判负，**不建**，避免为一个 2 行的收益加一条落盘路径。
- 若将来要动「0.5~2s 这 34 行」，需要的不是插值，而是**半秒尺度上的重判定**（新的判别信号），
  属另一类立项。

## 复现

```bash
# 误差分布（结果批 = work/ab_xfeat_start_<case>.results.json，GT = datasets/real/ground_truth_*.json）
D:/claudework/video-dedup-tool/.venv/Scripts/python.exe - <<'PY'
import json,numpy as np
S={'2mkv':('ground_truth_v4','ab_xfeat_start_2mkv'),'test1':('ground_truth_test1','ab_xfeat_start_test1'),
   'test2':('ground_truth_test2','ab_xfeat_start_test2'),'test3':('ground_truth_test3','ab_xfeat_start_test3')}
errs=[]
for c,(g,r) in S.items():
    gt=json.load(open('datasets/real/%s.json'%g,encoding='utf-8'))
    res=json.load(open('work/%s.results.json'%r,encoding='utf-8'))['results']
    for p in [x for x in gt['positives'] if x.get('tier')!='negative']:
        e0,e1=p['edited']; o0=p['original'][0]
        best=None
        for x in res:
            es=x['edited_segment']; ov=max(0,min(e1,es['end'])-max(e0,es['start']))
            if ov>0 and (best is None or ov>best[0]): best=(ov,x)
        cur=(best[1].get('original') or {}).get('candidate_start') if best else None
        if cur is not None: errs.append(abs(cur-o0))
e=np.array(errs); print(len(e), int((e<=0.5).sum()), int(((e>0.5)&(e<=0.55)).sum()), int(((e>2)).sum()))
PY
```
