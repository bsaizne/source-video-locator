# -*- coding: utf-8 -*-
"""退化拒绝门影响面统计 + 旋钮分腿消融（2026-09-29 续31, 用户授权重开 B）。

DECISIONS 续21-E1 的纪律：凡「去重/唯一认领/跨段一致性」类竞品判据，移植前必须先以**影响面统计**
证明该伪影在我方架构下系统性存在。本脚本做三件续19 没做的事：

1. **影响面（与门的判据无关的口径）**：每个可回答段的「重复认领」发生率，以及被重复的段按
   GT 归属分桶（同 GT 行冗余 / 不同 GT 行但同源区 = 合法叙事复用 / 无 GT 归属 = 假定位）。
   ⇒ 回答「伪影是否系统性存在」以及「门要砍的对象到底有多少」。
2. **分腿消融**：`max_duplicate_scene_ratio`（拒识腿）与 `min_scene_coverage`（丢子 span 腿）
   各自单独开关 —— 续19 只测了两腿同开，无法区分「严格 −14」是腿一还是腿二造成的。
3. **反事实收益上界**：严格指标是 GT 侧「有没有 span 覆盖」，拒识永远不会新增 HIT ⇒
   该门的产品价值只能在 负例误报 / 无支撑定位 / 导出冗余 三个轴上，本脚本把三轴都量化。

零 runtime 改动、零 GPU（离线重放现有结果批）。子 span 丢弃腿在探针内模拟（「整段清空」
vs「全低则保留」两种形态），不改 `degradation_gate.py` 的冻结行为。

用法:
  PY="D:/claudework/video-dedup-tool/.venv/Scripts/python.exe"
  $PY mvp/scripts/probe_degradation_impact.py \
      --pattern "work/fastglobal_default_{case}.results.json" \
      --report work/degradation_impact_fastglobal_default.json
"""
from __future__ import annotations

import argparse
import io
import contextlib
import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

from domain import ResultBatch                                        # noqa: E402
from engine.localization.degradation_gate import apply_degradation_gate  # noqa: E402
from measure_shot_recall import evaluate, overlap_frac, result_spans  # noqa: E402

CASES = [
    ("2mkv", "datasets/real/ground_truth_v4.json"),
    ("test1", "datasets/real/ground_truth_test1.json"),
    ("test2", "datasets/real/ground_truth_test2.json"),
    ("test3", "datasets/real/ground_truth_test3.json"),
]

ARMS = {
    # (max_duplicate_scene_ratio, min_scene_coverage, allow_partial_subs)
    "off": (1.0001, 0.0, False),        # 两腿都不触发（ratio ≤ 1.0001 恒真；cover ≥ 0 恒真）
    "dup_only": (0.8, 0.0, False),      # 腿1：只开重复率拒识
    "subs_only": (1.0001, 0.2, True),   # 腿2：只开低覆盖子 span 丢弃（部分丢形态）
    "both_partial": (0.8, 0.2, True),   # 腿3：两腿同开，子 span 部分丢
    "both_allnone": (0.8, 0.2, False),  # 腿4：续19 形态（两腿同开，全低则整段子 span 清空）
}


def _answerable(r: dict) -> bool:
    if r.get("not_in_source") or r.get("failure_reason") or r.get("excluded") \
            or r.get("manual_override"):
        return False
    o = r["original"]
    return o["candidate_end"] - o["candidate_start"] > 0


def _union_len(intervals) -> float:
    """区间并集长度（去重，避免多段重复覆盖被累加成 >1）。"""
    total = 0.0
    cur = None
    for s, e in sorted(intervals):
        if e <= s:
            continue
        if cur is None:
            cur = [s, e]
            continue
        if s <= cur[1]:
            cur[1] = max(cur[1], e)
        else:
            total += cur[1] - cur[0]
            cur = [s, e]
    if cur is not None:
        total += cur[1] - cur[0]
    return total


def _gt_attribution(gt: dict, res: list) -> tuple[list, list]:
    """per-segment GT 归属：main span 命中的 GT 正例行 id；以及 GT 行 → 满足它的段下标。

    命中口径与 measure_shot_recall.evaluate 的严格判据一致（within / mid_in / cov≥0.4），
    编辑侧须与该 GT 行有交集。
    """
    seg_rows = [[] for _ in res]          # 段下标 -> [GT 行 id]
    row_segs = {p["id"]: [] for p in gt["positives"]}
    for p in gt["positives"]:
        e0, e1, o0, o1 = p["edited"][0], p["edited"][1], p["original"][0], p["original"][1]
        for i, r in enumerate(res):
            if not _answerable(r):
                continue
            re0, re1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
            if max(0.0, min(e1, re1) - max(e0, re0)) <= 0:
                continue
            a, b = r["original"]["candidate_start"], r["original"]["candidate_end"]
            within = (a >= o0 - 2.0) and (b <= o1 + 2.0)
            mid_in = a <= (o0 + o1) / 2 <= b
            cov = overlap_frac(o0, o1, a, b) >= 0.4
            if within or mid_in or cov:
                if p["id"] not in seg_rows[i]:
                    seg_rows[i].append(p["id"])
                if i not in row_segs[p["id"]]:
                    row_segs[p["id"]].append(i)
    return seg_rows, row_segs


def _spans_cover_same_source(gt: dict, row_a: str, row_b: str) -> float:
    """两条 GT 行的原片窗重叠比例（判「合法复用」还是「同一段被抢」）。"""
    rows = {p["id"]: p["original"] for p in gt["positives"]}
    a0, a1 = rows[row_a]
    b0, b1 = rows[row_b]
    inter = max(0.0, min(a1, b1) - max(a0, b0))
    return inter / max(1e-6, min(a1 - a0, b1 - b0))


def analyze(case: str, gt_rel: str, res_path: Path) -> dict:
    gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
    raw = json.loads(res_path.read_text(encoding="utf-8"))
    res = raw["results"]
    seg_rows, row_segs = _gt_attribution(gt, res)

    main = [(r["original"]["candidate_start"], r["original"]["candidate_end"])
            if _answerable(r) else None for r in res]
    per_seg = []
    for i, sp in enumerate(main):
        if sp is None:
            continue
        s, e = sp
        others = [sp2 for j, sp2 in enumerate(main) if j != i and sp2 is not None]
        dup_all = _union_len([(max(s, a), min(e, b)) for a, b in others
                              if min(e, b) - max(s, a) > 0]) / max(1e-6, e - s)
        dup_all = min(1.0, dup_all)
        rows = seg_rows[i]
        # 与我重叠 ≥0.8 的其它段，各自的 GT 归属
        partners = []
        e0_edit = res[i]["edited_segment"]["start"]
        e1_edit = res[i]["edited_segment"]["end"]
        for j, sp2 in enumerate(main):
            if j == i or sp2 is None:
                continue
            a, b = sp2
            ov = _union_len([(max(s, a), min(e, b))]) / max(1e-6, min(e - s, b - a))
            if ov >= 0.8:
                partners.append({"idx": j, "rows": seg_rows[j], "ov": ov, "src": [a, b],
                                 "edit": [res[j]["edited_segment"]["start"],
                                          res[j]["edited_segment"]["end"]]})
        if not partners:
            cls = "unique_correct" if rows else "unique_unsupported"
        elif not rows:
            cls = "duplicate_unsupported"      # 门的有效目标（重复 + 无 GT 归属）
        elif any(not p["rows"] for p in partners):
            cls = "shadowed_by_noise"          # 被无归属段重复认领
        elif all(set(p["rows"]) == set(rows) for p in partners):
            cls = "same_gt_redundant"          # 同 GT 行多次认领 = 产品可见冗余
        else:
            shared = [(_spans_cover_same_source(gt, r1, r2)
                       for r1 in rows for r2 in p["rows"] if r1 != r2)
                      for p in partners if p["rows"]]
            shared = [x for sub in shared for x in sub]
            cls = "legit_reuse" if shared and max(shared) >= 0.5 else "cross_gt"
        subs = [float(x.get("cover") or 0.0) for x in (res[i].get("original_segments") or [])]
        per_seg.append({"idx": i, "src": [s, e],
                        "edit": [res[i]["edited_segment"]["start"],
                                 res[i]["edited_segment"]["end"]],
                        "conf": res[i]["confidence"], "score": res[i]["confidence_score"],
                        "dup_all": round(dup_all, 3), "gt_rows": rows,
                        "class": cls,
                        "partners": [{"idx": p["idx"], "gt_rows": p["rows"],
                                      "edit": p["edit"], "src": p["src"],
                                      "overlap": round(p["ov"], 3),
                                      "edit_gap": round(min(abs(p["edit"][0] - e0_edit),
                                                             abs(p["edit"][1] - e1_edit)), 1)}
                                     for p in partners],
                        "n_subs": len(subs),
                        "subs_low": sum(1 for c in subs if c < 0.2),
                        "subs_all_low": bool(subs) and all(c < 0.2 for c in subs)})

    # ---- 分腿消融 ----
    gated_by_arm = {}
    metrics_by_arm = {}
    for arm, (mdup, mcov, partial) in ARMS.items():
        batch_res = json.loads(json.dumps(res))   # 深拷贝，逐臂独立
        batch = ResultBatch.from_dict(dict(raw, results=batch_res))
        # 拒识决策只依赖主 span（子 span 丢弃在其之前但不影响它），故两腿可分别模拟
        stats = apply_degradation_gate(batch.results, enabled=True,
                                       max_duplicate_scene_ratio=mdup,
                                       min_scene_coverage=mcov)
        for i in stats.rejected:
            batch_res[i]["original"] = {"candidate_start": 0.0, "candidate_end": 0.0}
            batch_res[i]["original_segments"] = []
            batch_res[i]["confidence"] = "LOW"
        subs_dropped = 0
        if mcov > 0:
            for i in range(len(batch_res)):
                if i in stats.rejected:
                    continue
                rows = batch_res[i].get("original_segments") or []
                if not rows:
                    continue
                keep = [x for x in rows if float(x.get("cover") or 0.0) >= mcov]
                if partial and rows and not keep:
                    continue          # 腿2/腿3：全低则整段保留，不让子 span 整体清空
                if len(keep) != len(rows):
                    subs_dropped += len(rows) - len(keep)
                    batch_res[i]["original_segments"] = keep
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            m = evaluate(gt, batch_res, label="%s/%s" % (case, arm))
        metrics_by_arm[arm] = {"strict": "%d/%d" % (m["strict_hit"], m["n_pos"]),
                               "scene": "%d/%d" % (m["scene_hit"], m["n_pos"]),
                               "fp": "%d/%d" % (m["fp"], m["n_neg"]),
                               "sup": "%d/%d" % (m["sup"], m["tot"]),
                               "per_pos": m["per_pos"], "offenders": m["offenders"]}
        gated_by_arm[arm] = {"rejected": [[i, round(stats.dup_ratios.get(i, 0.0), 3)]
                                          for i in stats.rejected],
                             "subs_dropped": subs_dropped,
                             "partial_subs": partial}
    return {"case": case, "results_path": str(res_path),
            "n_results": len(res), "n_answerable": len(per_seg),
            "segments": per_seg, "arms": gated_by_arm, "metrics": metrics_by_arm}


def flips_of(base: dict, arm: dict) -> list:
    return [{"id": b["id"], "from": b["mark"], "to": a["mark"]}
            for b, a in zip(base["per_pos"], arm["per_pos"]) if b["mark"] != a["mark"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pattern", default="work/fastglobal_default_{case}.results.json")
    ap.add_argument("--report", default="work/degradation_impact.json")
    args = ap.parse_args()

    report = {"arms_definition": {k: {"max_duplicate_scene_ratio": v[0],
                                      "min_scene_coverage": v[1],
                                      "allow_partial_subs": v[2]} for k, v in ARMS.items()},
              "cases": []}
    for case, gt_rel in CASES:
        rp = BENCH / args.pattern.format(case=case)
        if not rp.exists():
            print("MISSING results: %s" % rp)
            continue
        row = analyze(case, gt_rel, rp)
        report["cases"].append(row)
        base = row["metrics"]["off"]
        cls_count = {}
        for s in row["segments"]:
            cls_count[s["class"]] = cls_count.get(s["class"], 0) + 1
        hi_dup = [s for s in row["segments"] if s["dup_all"] >= 0.8]
        print("\n########## %s (%d 段, 可回答 %d) ##########" % (
            case, row["n_results"], row["n_answerable"]))
        print("  重复认领发生率 dup_all>=0.8: %d/%d 段  分类: %s" % (
            len(hi_dup), row["n_answerable"], cls_count))
        for arm in ("dup_only", "subs_only", "both_partial", "both_allnone"):
            m = row["metrics"][arm]
            fl = flips_of(base, m)
            print("  [%-12s] 严格 %s | 场景 %s | 负例 %s | 支撑 %s | 拒识 %d 丢子span %d%s" % (
                arm, m["strict"], m["scene"], m["fp"], m["sup"],
                len(row["arms"][arm]["rejected"]), row["arms"][arm]["subs_dropped"],
                ("  翻转 " + ",".join("%s:%s->%s" % (f["id"], f["from"], f["to"])
                                      for f in fl)) if fl else ""))
        for s in hi_dup:
            print("    dup=%.2f seg%-3d ed%.1f-%.1f src%.0f-%.0f %s(%.2f) gt=%s class=%s "
                  "subs=%d(低%d,全低=%s)" % (
                      s["dup_all"], s["idx"], s["edit"][0], s["edit"][1], s["src"][0],
                      s["src"][1], s["conf"], s["score"],
                      ",".join(s["gt_rows"]) or "-", s["class"],
                      s["n_subs"], s["subs_low"], s["subs_all_low"]))
            for p in s["partners"]:
                print("        伙伴 seg%-3d ed%.1f-%.1f src%.0f-%.0f ov=%.2f 编辑间隔=%.1fs gt=%s" % (
                    p["idx"], p["edit"][0], p["edit"][1], p["src"][0], p["src"][1],
                    p["overlap"], p["edit_gap"], ",".join(p["gt_rows"]) or "-"))
        for arm in ("dup_only", "both_allnone", "both_partial"):
            for i, ratio in row["arms"][arm]["rejected"]:
                print("      [%s] 拒识 seg%d dup=%.2f" % (arm, i, ratio))

    out = BENCH / args.report
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n产物: %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
