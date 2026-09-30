# -*- coding: utf-8 -*-
"""「输出/展示层换切点」可行性量化: 用对方 probs.npy 对我方现行切点做自检。

三问: ① 已裁决为真的我方切点处 TN prob 是否是峰? ② 6 处已裁决假切点是否天然被峰值规则剔除?
      ③ 峰值规则给出的切点数 vs 交付切点数(粒度)。
锚点只用**已裁决**的 44 例(不套 GT)。输出 work/cut_swap_probe.json
"""
import json, sys
import numpy as np
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
B = Path(r"D:\claudework\benchmark")
PROXY = Path(r"D:\claudework\cutmatch-analysis\sandbox\out")
WORK = B / "work"
CASES = {"2mkv": ("1.mp4", 29.0, "rerun_2mkv_runtime_twopassflash.results.json"),
         "test1": ("test1-ed.mp4", 30.0, "rerun_test1_runtime_twopassflash.results.json"),
         "test2": ("tset2-ed.mp4", 30.0, "rerun_test2_runtime_twopassflash.results.json"),
         "test3": ("test3-ed.mp4", 28.0, "rerun_test3_runtime_twopassflash.results.json")}

def our_bounds(name):
    d = json.loads((WORK / name).read_text(encoding="utf-8"))["results"]
    return sorted({round(float(r["edited_segment"]["start"]), 2) for r in d if float(r["edited_segment"]["start"]) > 0.05})

def f_of(t, fps):
    return int(round(t * fps))

def is_peak(prob, i, k=3):
    lo, hi = max(0, i - k), min(len(prob), i + k + 1)
    seg = np.nan_to_num(prob[lo:hi], nan=-1.0)
    return bool(prob[i] >= seg.max() - 1e-6)

verd = json.loads((WORK / "proxy_blind_disputes" / "verdicts_44_enriched.json").read_text(encoding="utf-8"))
ours_true = {(v["case"], round(v["ours_s"], 2)) for v in verd if v["ours_v"] == "cut"}
ours_false = {(v["case"], round(v["ours_s"], 2)) for v in verd if v["ours_v"] == "nocut"}
ours_unsure = {(v["case"], round(v["ours_s"], 2)) for v in verd if v["ours_v"] == "unsure"}

res = {"note": "TN probs 在我方现行切点上的表现(锚点=已裁决 44 例)", "cases": {}}
agg = {"true": [], "false": [], "unsure": []}
print("| 片 | 我方切点 | 其中已裁决 | 真/假/未定 | 真处 TNprob 中位数 | 假处 TNprob | 假处是否局部极大 |")
print("|---|---|---|---|---|---|---|")
for case, (clip, fps, resname) in CASES.items():
    prob = np.load(PROXY / ("%s.probs.npy" % clip))
    ours = our_bounds(resname)
    rows = []
    for t in ours:
        f = f_of(t, fps)
        key = (case, round(t, 2))
        tag = "true" if key in ours_true else ("false" if key in ours_false else ("unsure" if key in ours_unsure else None))
        p = float(prob[min(f, len(prob) - 1)])
        pk = is_peak(prob, min(f, len(prob) - 1), 3)
        rows.append({"t": t, "frame": f, "tag": tag, "tn_prob": round(p, 4), "is_peak_k3": pk,
                     "peak_gt_05": bool(pk and p > 0.5)})
        if tag:
            agg[tag].append(p)
    tp = [median for median in [np.median([r["tn_prob"] for r in rows if r["tag"] == "true"])] if True]
    fp = [r for r in rows if r["tag"] == "false"]
    res["cases"][case] = {"clip": clip, "n_ours": len(ours), "bounds": rows}
    print("| %s | %d | %d | %d/%d/%d | %s | %s | %s |" % (
        case, len(ours), sum(1 for r in rows if r["tag"]),
        sum(1 for r in rows if r["tag"] == "true"), len(fp), sum(1 for r in rows if r["tag"] == "unsure"),
        ("%.3f" % tp[0]) if tp else "-",
        ", ".join("%.3f" % r["tn_prob"] for r in fp) if fp else "-",
        ", ".join(str(r["is_peak_k3"]) for r in fp) if fp else "-"))

def stat(v):
    return {"n": len(v), "median": round(float(np.median(v)), 4), "min": round(float(np.min(v)), 4),
            "max": round(float(np.max(v)), 4), "lt_05": int(sum(1 for x in v if x < 0.5))} if v else {"n": 0}
print()
print("TN prob 汇总: 已裁决真切换处", stat(agg["true"]))
print("             已裁决假切点处", stat(agg["false"]))
print("             未定处        ", stat(agg["unsure"]))
print()
print("== 峰值规则(prob>th 且 k 邻域内最大, 再按 min_gap 合并)切点数 vs 交付切点数 ==")
print("| 片 | 交付 t030/t040/t050/t060 | 峰值 th=0.5 k=2 | k=3 | k=5 | 峰值 th=0.3 k=3 |")
print("|---|---|---|---|---|---|")
from importlib.util import spec_from_file_location, module_from_spec
spec = spec_from_file_location("rp", str(B / "mvp" / "scripts" / "replay_cutmatch_postprocess.py"))
rp = module_from_spec(spec); spec.loader.exec_module(rp)
for case, (clip, fps, resname) in CASES.items():
    prob = np.load(PROXY / ("%s.probs.npy" % clip))
    delivered = [len(json.loads((PROXY / ("scene_split_t%s.json" % th)).read_text(encoding="utf-8"))[clip]["cuts"])
                 for th in ("030", "040", "050", "060")]
    counts = {}
    for k in (2, 3, 5):
        idx = [i for i in range(len(prob)) if np.nan_to_num(prob[i], nan=-1) > 0.5 and is_peak(prob, i, k)]
        items = [[i, i] for i in idx]
        merged = rp.merge_by_cut_gap(items, 8)
        counts["th05_k%d" % k] = len(merged)
    idx = [i for i in range(len(prob)) if np.nan_to_num(prob[i], nan=-1) > 0.3 and is_peak(prob, i, 3)]
    counts["th03_k3"] = len(rp.merge_by_cut_gap([[i, i] for i in idx], 8))
    print("| %s | %s | %d | %d | %d | %d |" % (case, "/".join(map(str, delivered)),
        counts["th05_k2"], counts["th05_k3"], counts["th05_k5"], counts["th03_k3"]))
res["aggregate"] = {"true": stat(agg["true"]), "false": stat(agg["false"]), "unsure": stat(agg["unsure"])}
(WORK / "cut_swap_probe.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print()
print("saved work/cut_swap_probe.json")