# -*- coding: utf-8 -*-
"""五环组合探针 同粒度化双口径评估(test1, 2026-09-26 续10c).

背景: TN 场景代理 span(时长比中位 ~8.7x)的装配效应已证伪严格指标单口径读数
(FINDINGS_PROXY_D_STAGE_REVIEW §2/§5)。本脚本按拍板设计做**同粒度化双口径**:

  口径1 候选层(粒度无关): 每条 GT 正例, 在覆盖其 ED 窗的查询行的候选表(每查询 top-20 源场景,
        按 combined 序)中找 GT 原片窗的最小名次(判据 = 候选场景 span 覆盖 GT 窗 >=30%)。
        回答「检索/排序层是否把 GT 内容排进来了」——与 span 粒度无关;
        拒识行(matched=False)的候选表同样计入 —— 把「找到了但被呈现门拒掉」与「根本没找到」分开。
  口径2 span 截到查询等长: matched 行主 span 截为 [span_start, span_start + ED窗时长],
        再跑与 measure_shot_recall.evaluate 完全相同的严格判据(within±2 / mid_in / cov>=0.4)。
        消除「大 span 装进 GT 窗」的装配效应。

参照系(硬编码, 出处 FINDINGS_PROXY_D_STAGE_REVIEW §1 表): 我方基线(完整批)严格 34/43 ·
场景 42/43 · 负例 0/1; main-span-only 基线 22/43。
检索天花板(oracle 口径, 出处 work/loc_retrieval_audit.json test1)单列参照。
争议 GT t1r08b/t1r12a(双侧独立定位同内容区、GT 窗画面与 ED 不符, 待用户裁决)双计: 含/不含。

用法:
  python mvp/scripts/probe_combo_dual_caliber.py \
      --loc-a cutmatch sandbox localization_comboA_test1.json \
      --loc-b ...localization_comboG5_test1.json [--delivered ...localization_test1.json] \
      --out work/combo_probe_test1.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
from measure_shot_recall import overlap_frac  # noqa: E402

GT_DEFAULT = BENCH / "datasets/real/ground_truth_test1.json"
CEILING = BENCH / "work/loc_retrieval_audit.json"
DISPUTED = ["t1r08b", "t1r12a"]  # GT 疑错线索(续10 §4), 指标双计
# 参照系(硬编码, 出处 FINDINGS_PROXY_D_STAGE_REVIEW §1)
REF_BASELINE = {"strict": "34/43", "scene": "42/43", "neg_fp": "0/1", "main_span_only": "22/43",
                "source": "我方生产管线 rerun_test1_perfopt.results.json(完整批) + main-span-only 口径(续9 预演)"}


def load_rows(loc_path: Path) -> list[dict]:
    """v2 localization -> 简化行: {qid, e0,e1(s), matched, s0,s1(s)|None, cands:[{rank,s0,s1,score,channel,bonus}]}"""
    d = json.loads(loc_path.read_text(encoding="utf-8"))
    rows = []
    for q in d.get("queries", []):
        ed = q["ed"]
        sp = q.get("source_span") or None
        cands = [{"rank": c["rank"],
                  "s0": c["source_span"]["start_ms"] / 1000.0,
                  "s1": c["source_span"]["end_ms"] / 1000.0,
                  "score": c.get("score"), "channel": c.get("channel"),
                  "bonus": c.get("continuity_bonus", 0.0)}
                 for c in (q.get("candidates") or [])]
        rows.append({"qid": q.get("query_id"), "matched": bool(q.get("matched")),
                     "e0": ed["start_ms"] / 1000.0, "e1": ed["end_ms"] / 1000.0,
                     "s0": (sp["start_ms"] / 1000.0) if sp else None,
                     "s1": (sp["end_ms"] / 1000.0) if sp else None,
                     "cands": cands, "smoothed": bool(q.get("g5_offset_smoothed"))})
    return rows


def caliber1(rows: list[dict], positives: list[dict]) -> dict:
    """候选层: GT 原片窗在候选表中的最小名次(任一覆盖该 GT ED 窗的查询行)。"""
    per = []
    for p in positives:
        e0, e1 = p["edited"]
        o0, o1 = p["original"]
        best = None  # (rank, qid, channel, row_matched)
        for r in rows:
            if min(e1, r["e1"]) - max(e0, r["e0"]) <= 0:
                continue
            for c in r["cands"]:
                if overlap_frac(o0, o1, c["s0"], c["s1"]) >= 0.3:
                    if best is None or c["rank"] < best[0]:
                        best = (c["rank"], r["qid"], c["channel"], r["matched"])
                    break
        per.append({"id": p["id"], "tier": p["tier"],
                    "rank": best[0] if best else None,
                    "qid": best[1] if best else None,
                    "channel": best[2] if best else None,
                    "row_matched": best[3] if best else None})
    ranks = [x["rank"] for x in per if x["rank"] is not None]
    n = len(positives)
    out = {"n": n,
           "top1": sum(1 for x in ranks if x == 1),
           "top3": sum(1 for x in ranks if x <= 3),
           "top20": len(ranks),
           "never": [x["id"] for x in per if x["rank"] is None],
           "median_rank": statistics.median(ranks) if ranks else None,
           "per": per}
    # 拒识分列: 候选层找到了但该行被呈现门拒掉(matched=False)
    out["found_but_rejected"] = [x["id"] for x in per if x["rank"] is not None and x["row_matched"] is False]
    return out


def caliber2(rows: list[dict], positives: list[dict], negatives: list[dict]) -> dict:
    """span 截到查询等长 + evaluate() 同款严格判据。"""
    per = []
    for p in positives:
        e0, e1 = p["edited"]
        o0, o1 = p["original"]
        mid = (o0 + o1) / 2.0
        best = None
        for r in rows:
            if min(e1, r["e1"]) - max(e0, r["e0"]) <= 0:
                continue
            if not (r["matched"] and r["s0"] is not None):
                continue
            t0, t1 = r["s0"], r["s0"] + (e1 - e0)   # 截到查询等长
            within = (t0 >= o0 - 2.0) and (t1 <= o1 + 2.0)
            mid_in = t0 <= mid <= t1
            cov = overlap_frac(o0, o1, t0, t1) >= 0.4
            if (within or mid_in or cov) and best is None:
                best = {"qid": r["qid"], "t0": round(t0, 2), "t1": round(t1, 2), "smoothed": r["smoothed"]}
        per.append({"id": p["id"], "tier": p["tier"], "hit": best is not None, "detail": best})
    fp_rows = []
    for n in negatives:
        e0, e1 = n["edited"]
        off = [r["qid"] for r in rows
               if r["matched"] and overlap_frac(e0, e1, r["e0"], r["e1"]) >= 0.5]
        fp_rows.append({"id": n["id"], "fp": bool(off), "qids": off})
    return {"n": len(positives), "strict_hit": sum(1 for x in per if x["hit"]),
            "per": per, "neg_fp": sum(1 for x in fp_rows if x["fp"]), "neg_detail": fp_rows}


def summarize(name: str, rows: list[dict], gt: dict) -> dict:
    pos, neg = gt["positives"], gt["negatives"]
    c1 = caliber1(rows, pos)
    c2 = caliber2(rows, pos, neg)
    out = {"arm": name, "c1": c1, "c2": c2}
    # 争议 GT 双计
    keep = [p for p in pos if p["id"] not in DISPUTED]
    out["c1_ex_disputed"] = caliber1(rows, keep)
    out["c2_ex_disputed"] = caliber2(rows, keep, neg)
    return out


def flips(sa: dict, sb: dict) -> dict:
    fa, fb = sa["c1"]["per"], sb["c1"]["per"]
    d1 = [{"id": x["id"], "A": x["rank"], "G5": y["rank"]} for x, y in zip(fa, fb) if x["rank"] != y["rank"]]
    ca, cb = sa["c2"]["per"], sb["c2"]["per"]
    d2 = [{"id": x["id"], "A": x["hit"], "G5": y["hit"], "A_span": x["detail"], "G5_span": y["detail"]}
          for x, y in zip(ca, cb) if x["hit"] != y["hit"]]
    sm = [x["id"] for x in sb["c2"]["per"] if x["detail"] and x["detail"].get("smoothed")]
    return {"c1_rank_changes": d1, "c2_hit_flips": d2, "g5_smoothed_entries": sm}


def semantic_drift(rows_a: list[dict], delivered: list[dict]) -> dict:
    """环境漂移检查: 本轮 four-ring 重跑 vs 已交付 localization_test1.json(逐行 matched/span 一致性)。"""
    diff = 0
    for x, y in zip(rows_a, delivered):
        same_span = (x["s0"] is None and y["s0"] is None) or (
            x["s0"] is not None and y["s0"] is not None and abs(x["s0"] - y["s0"]) < 0.02
            and abs(x["s1"] - y["s1"]) < 0.02)
        if x["matched"] != y["matched"] or not same_span:
            diff += 1
    return {"rows": len(rows_a), "delivered": len(delivered), "diff_rows": diff}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--loc-a", required=True, help="four-ring 重跑臂 localization JSON")
    ap.add_argument("--loc-b", required=True, help="five-ring(G5) 臂 localization JSON")
    ap.add_argument("--delivered", default=None, help="已交付 localization_test1.json(环境漂移检查, 可选)")
    ap.add_argument("--gt", default=str(GT_DEFAULT))
    ap.add_argument("--out", default=str(BENCH / "work/combo_probe_test1.json"))
    args = ap.parse_args()

    gt = json.loads(Path(args.gt).read_text(encoding="utf-8"))
    rows_a = load_rows(Path(args.loc_a))
    rows_b = load_rows(Path(args.loc_b))
    res = {"case": "test1", "loc_a": args.loc_a, "loc_b": args.loc_b,
           "reference": REF_BASELINE, "disputed_gt": DISPUTED}

    res["A_four_ring"] = summarize("A_four_ring_rerun", rows_a, gt)
    res["B_five_ring_g5"] = summarize("B_five_ring_g5", rows_b, gt)
    res["flips_A_vs_G5"] = flips(res["A_four_ring"], res["B_five_ring_g5"])

    if args.delivered and Path(args.delivered).exists():
        res["env_drift_check"] = semantic_drift(rows_a, load_rows(Path(args.delivered)))

    # 检索天花板参照(oracle 口径, 不与本探针同协议, 仅作候选层上界参照)
    if CEILING.exists():
        d = json.loads(CEILING.read_text(encoding="utf-8"))
        t1 = d.get("cases", {}).get("test1", {}).get("rows", [])
        ranks = [r.get("retrieval_rank") for r in t1 if r.get("retrieval_rank") is not None]
        res["ceiling_reference_oracle"] = {
            "note": "GT 引导查询点全索引检索名次(oracle 口径), 仅作候选层上界参照, 不与本探针同协议",
            "n": len(ranks), "rank1": sum(1 for x in ranks if x == 1),
            "rank_le3": sum(1 for x in ranks if x <= 3), "rank_le20": sum(1 for x in ranks if x <= 20)}

    Path(args.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")

    def brief(tag, s):
        c1, c2 = s["c1"], s["c2"]
        print("[%s] 候选层: top1 %d top3 %d top20 %d/%d (never=%s, 找到但被拒=%s, median rank %s)" % (
            tag, c1["top1"], c1["top3"], c1["top20"], c1["n"], c1["never"], c1["found_but_rejected"],
            c1["median_rank"]))
        print("        截查询等长严格: %d/%d · 负例误报 %d/%d | 不含争议GT: 候选 top20 %d/%d · 严格 %d/%d" % (
            c2["strict_hit"], c2["n"], c2["neg_fp"], len(c2["neg_detail"]),
            s["c1_ex_disputed"]["top20"], s["c1_ex_disputed"]["n"],
            s["c2_ex_disputed"]["strict_hit"], s["c2_ex_disputed"]["n"]))

    print("=" * 78)
    print("参照系: 我方基线严格 %s · 场景 %s · 负例 %s | main-span-only %s" % (
        REF_BASELINE["strict"], REF_BASELINE["scene"], REF_BASELINE["neg_fp"], REF_BASELINE["main_span_only"]))
    if "ceiling_reference_oracle" in res:
        c = res["ceiling_reference_oracle"]
        print("天花板参照(oracle): rank1 %d · <=3 %d · <=20 %d / %d" % (
            c["rank1"], c["rank_le3"], c["rank_le20"], c["n"]))
    brief("A four-ring 重跑", res["A_four_ring"])
    brief("B five-ring+G5", res["B_five_ring_g5"])
    f = res["flips_A_vs_G5"]
    print("-" * 78)
    print("G5 增量: 候选层名次变化 %d 处 %s" % (len(f["c1_rank_changes"]), f["c1_rank_changes"][:10]))
    print("        截等长严格翻转 %d 处: %s" % (len(f["c2_hit_flips"]),
          [("MISS->HIT" if x["G5"] else "HIT->MISS", x["id"]) for x in f["c2_hit_flips"]][:10]))
    print("        G5 offset 平滑修复 %d 条" % len(f["g5_smoothed_entries"]))
    if "env_drift_check" in res:
        print("环境漂移检查(重跑A vs 已交付): %s" % res["env_drift_check"])
    print("saved %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
