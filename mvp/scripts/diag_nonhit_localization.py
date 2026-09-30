"""非 HIT 案例的定位层机制分诊 —— "查询单元稀释" vs "候选池/选择" (2026-09-26).

输入: 四片 perfopt 结果批 + GT + work/loc_retrieval_audit.json(检索天花板 rank).
对每个非 HIT 正例输出:
  * 运行期覆盖 GT 编辑段的编辑侧结果段(数量 / 总长 / 最长段) 与其相对 GT 编辑段长的倍率;
  * 运行期结果 span 是否有任何一个落在 GT 原片窗 ±TOL 内(即"池/选择是否已经把答案给出来了");
  * 分诊标签:
      ANSWER_PRESENT_BUT_UNMARKED -> 运行期 span 已落在 GT 窗内(仅判据/标记问题)
      QUERY_UNIT_DILUTED         -> 查询单元远长于 GT 编辑段(>=2x), 且无 span 落在窗内
      POOL_OR_SELECTION          -> 查询单元粒度接近 GT, 但运行期未把窗内答案给出
零 runtime 改动, 纯结果文件计算(秒级).

用法:
  python mvp/scripts/diag_nonhit_localization.py [--tol 0.5] [--ratio 2.0] [--out work/nonhit_diag.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]

CASES = [
    ("2mkv", "datasets/real/ground_truth_v4.json", "work/rerun_2mkv_perfopt.results.json"),
    ("test1", "datasets/real/ground_truth_test1.json", "work/rerun_test1_perfopt.results.json"),
    ("test2", "datasets/real/ground_truth_test2.json", "work/rerun_test2_perfopt.results.json"),
    ("test3", "datasets/real/ground_truth_test3.json", "work/rerun_test3_perfopt.results.json"),
]


def ov(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def spans(r):
    out = [("main", r["original"]["candidate_start"], r["original"]["candidate_end"])]
    for s in r.get("original_segments") or []:
        out.append(("sub", s["candidate_start"], s["candidate_end"]))
    return [x for x in out if x[2] - x[1] > 0.01]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tol", type=float, default=0.5)
    ap.add_argument("--ratio", type=float, default=2.0, help="查询单元倍率阈值(查询单元稀释判据)")
    ap.add_argument("--audit", default=str(BENCH / "work" / "loc_retrieval_audit.json"))
    ap.add_argument("--out", default=str(BENCH / "work" / "nonhit_diag.json"))
    args = ap.parse_args()

    rank_by = {}
    ap_p = Path(args.audit)
    if ap_p.exists():
        ad = json.loads(ap_p.read_text(encoding="utf-8"))
        for c, blk in ad["cases"].items():
            for row in blk["rows"]:
                rank_by["%s/%s" % (c, row["id"])] = (row["mark"], row["retrieval_rank"])

    rows, tally = [], {}
    for case, gt_rel, res_rel in CASES:
        gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
        res = json.loads((BENCH / res_rel).read_text(encoding="utf-8"))["results"]
        for p in gt["positives"]:
            e0, e1 = [float(x) for x in p["edited"]]
            o0, o1 = [float(x) for x in p["original"]]
            gt_ed = max(1e-6, e1 - e0)
            segs = []
            answer_present = False
            for i, r in enumerate(res):
                rs, re = r["edited_segment"]["start"], r["edited_segment"]["end"]
                if ov(rs, re, e0, e1) <= 0:
                    continue
                segs.append((i, rs, re, re - rs))
                for kind, a, b in spans(r):
                    if a <= o1 + args.tol and b >= o0 - args.tol:
                        answer_present = True
            if not segs:
                continue
            max_len = max(s[3] for s in segs)
            ratio = max_len / gt_ed
            mark, rank = rank_by.get("%s/%s" % (case, p["id"]), (None, None))
            if mark == "HIT":
                continue
            label = ("ANSWER_PRESENT_BUT_UNMARKED" if answer_present else
                     ("QUERY_UNIT_DILUTED" if ratio >= args.ratio else "POOL_OR_SELECTION"))
            tally[label] = tally.get(label, 0) + 1
            rows.append(dict(case=case, id=p["id"], mark=mark, retrieval_rank=rank,
                             gt_edited=[e0, e1], gt_orig=[o0, o1],
                             n_segments=len(segs), max_seg_len=round(max_len, 2),
                             ratio=round(ratio, 2),
                             dims="%s" % ("+".join("%.1f-%.1f" % (s[1], s[2]) for s in segs[:4])),
                             label=label))
            print("  %-8s %-8s mark=%-5s rank=%-5s seg=%d maxlen=%7.1fs GTed=%5.1fs ratio=%5.1fx  %s" % (
                case, p["id"], mark, rank, len(segs), max_len, gt_ed, ratio, label), flush=True)

    print("\n" + "=" * 90)
    for k, v in sorted(tally.items(), key=lambda x: -x[1]):
        print("  %-30s %d" % (k, v))
    print("  总计非 HIT: %d (阈值 ratio>=%.1f)" % (sum(tally.values()), args.ratio))
    Path(args.out).write_text(json.dumps({"tol": args.tol, "ratio": args.ratio,
                                          "tally": tally, "rows": rows},
                                         ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
