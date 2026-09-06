# -*- coding: utf-8 -*-
"""subshot drift 判据修复批 vs 基线批 三指标对比 + montage 段明细（研究侧评估）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
from measure_shot_recall import evaluate  # noqa: E402
from diag_subshot_trigger import FILMS, montage_spans  # noqa: E402

NEW_SUFFIX = "_subshotdrift.results.json"


def montage_table(res, verdict, pos):
    rows = []
    for i, r in enumerate(res):
        if not r.get("montage_flag"):
            continue
        ms = montage_spans(r)
        if not ms:
            continue
        from measure_shot_recall import overlap_frac
        p0, p1 = r["original"]["candidate_start"], r["original"]["candidate_end"]
        pmid = (p0 + p1) / 2.0
        best = max(ms, key=lambda s: (s["score"] or 0.0))
        bmid = (best["candidate_start"] + best["candidate_end"]) / 2.0
        e0, e1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
        gt_hit = None
        for ge0, ge1, go0, go1, gid in pos:
            if overlap_frac(ge0, ge1, e0, e1) >= 0.5:
                gt_hit = (gid, (go0 + go1) / 2.0)
                break
        gmid = gt_hit[1] if gt_hit else float("nan")
        v = verdict.get(gt_hit[0], "-") if gt_hit else "(neg/none)"
        rows.append(f"s{i:>3} ed{e0:7.1f}-{e1:6.1f} pmid{pmid:8.1f} bmid{bmid:8.1f} "
                    f"gap{abs(pmid-bmid):7.1f} psim{(best['score'] or 0):.3f} "
                    f"gt{gt_hit[0] if gt_hit else '-':>8} p_off{abs(pmid-gmid):7.1f} {v}")
    return rows


def main() -> int:
    tot = {"base": [0, 0, 0, 0], "new": [0, 0, 0, 0]}
    for label, gt_p, base_p in FILMS:
        gt = json.loads(Path(gt_p).read_text(encoding="utf-8"))
        base = json.loads(Path(base_p).read_text(encoding="utf-8"))["results"]
        new_name = base_p.name.replace("_runtime_twopassflash.results.json", NEW_SUFFIX)
        new_p = BENCH / "work" / new_name
        new = json.loads(new_p.read_text(encoding="utf-8"))["results"]
        eb = evaluate(gt, base)
        en = evaluate(gt, new, label=f"{label} NEW(subshot drift)")
        pos = [(p["edited"][0], p["edited"][1], p["original"][0], p["original"][1], p["id"])
               for p in gt["positives"]]
        vnew = {d["id"]: d["mark"] for d in en["per_pos"]}
        vbase = {d["id"]: d["mark"] for d in eb["per_pos"]}
        print(f"\n--- {label}: 严格 {eb['strict_hit']}->{en['strict_hit']} "
              f"场景 {eb['scene_hit']}->{en['scene_hit']} "
              f"负例 {eb['fp']}->{en['fp']} 支撑 {eb['sup']}/{eb['tot']}->{en['sup']}/{en['tot']} ---")
        for d in en["per_pos"]:
            if d["mark"] != vbase.get(d["id"]):
                print(f"  变化 {d['id']}: {vbase.get(d['id'])} -> {d['mark']}")
        print(f"--- {label} NEW montage 段明细 ---")
        for line in montage_table(new, vnew, pos):
            print(" ", line)
        tot["base"][0] += eb["strict_hit"]; tot["new"][0] += en["strict_hit"]
        tot["base"][1] += eb["scene_hit"]; tot["new"][1] += en["scene_hit"]
        tot["base"][2] += eb["fp"]; tot["new"][2] += en["fp"]
        tot["base"][3] += eb["sup"]; tot["new"][3] += en["sup"]
        tot["base"].append(0)
    npos = sum(len(json.loads(Path(g).read_text(encoding="utf-8"))["positives"]) for _, g, _ in FILMS)
    nneg = sum(len(json.loads(Path(g).read_text(encoding="utf-8"))["negatives"]) for _, g, _ in FILMS)
    print(f"\n===== 四片汇总: 严格 {tot['base'][0]}/{npos} -> {tot['new'][0]}/{npos} | "
          f"场景 {tot['base'][1]}/{npos} -> {tot['new'][1]}/{npos} | "
          f"负例 {tot['base'][2]}/{nneg} -> {tot['new'][2]}/{nneg} | "
          f"支撑 {tot['base'][3]} -> {tot['new'][3]} =====")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
