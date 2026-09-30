# -*- coding: utf-8 -*-
"""conf_v2 移植验收分析：档位迁移 + 「病灶是否真被命中」交叉表。

三指标（严格/场景/负例）由 `measure_four_results.py` 单独核；本脚本回答它回答不了的两件事：

① **定位逐位一致性**：conf_v2 只改档位与 reasons，理论上不碰 span——实测证明（否则「零回退」只是假设）。
② **降档的真实价值**：每段按其编辑侧归属到 GT 正例并判 HIT/part/MISS，与档位做交叉表：
   - 收益侧 =「自信错答」HIGH ∧ MISS 的段数 OFF→ON 降了多少（2026-09-01 原型实验的老病灶：
     HIGH 档精度仅 5/13，错配多为 clean 单证据簇、margin 信号饱和 1.0）；
   - 代价侧 = GT 判 HIT 却被降档的段数；
   - 负例侧 = 落在负例编辑窗上的结果段其 OFF/ON 档位（沿用 measure_shot_recall 的 FP 定义）。

判定口径与 `measure_shot_recall.evaluate` 一致（within ±2s / GT 中点落 span 内 / 原片侧重叠 ≥0.4，
主 span 与子 span 都算）。**GT 只用于事后核对，不参与任何公式计算**（护栏保留项「不使用 GT 字段」）。

用法:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/analyze_conf_v2.py
产出: work/confv2_analysis.json（+ 控制台摘要）
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

from measure_shot_recall import overlap_frac, result_spans  # noqa: E402

CASES = [
    ("2mkv", "datasets/real/ground_truth_v4.json"),
    ("test1", "datasets/real/ground_truth_test1.json"),
    ("test2", "datasets/real/ground_truth_test2.json"),
    ("test3", "datasets/real/ground_truth_test3.json"),
]
OFF_PATTERN = "work/voteprior_{case}.results.json"      # 续11 现役基线批（conf_v2 关）
ON_PATTERN = "work/confv2_{case}.results.json"
MIN_ED_OVERLAP = 0.5
LEVELS = ("HIGH", "MEDIUM", "LOW")


def _owner(r: dict, gt: dict):
    """结果段归属到哪条 GT 正例：编辑侧重叠（按 GT 窗归一）≥0.5 且最大者。无则 None。"""
    re0, re1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
    best, best_ov = None, 0.0
    for g in gt["positives"]:
        g0, g1 = g["edited"]
        ov = overlap_frac(g0, g1, re0, re1)
        if ov >= MIN_ED_OVERLAP and ov > best_ov:
            best, best_ov = g, ov
    return best


def _verdict(r: dict, g) -> str:
    """结果段对其归属 GT 正例的判定：HIT / part / MISS / REJECT（正确拒绝）/ UNMATCHED。"""
    if r.get("not_in_source"):
        return "REJECT"
    if g is None:
        return "UNMATCHED"
    o0, o1 = g["original"]
    spans = result_spans(r)
    for _kind, a, b in spans:
        if ((a >= o0 - 2.0 and b <= o1 + 2.0) or (a <= (o0 + o1) / 2 <= b)
                or overlap_frac(o0, o1, a, b) >= 0.4):
            return "HIT"
    for _kind, a, b in spans:
        if o0 - 15.0 <= (a + b) / 2 <= o1 + 15.0:
            return "part"
    return "MISS"


def _spanset(batch: dict):
    """定位内容指纹（不含 uuid/置信字段），用于逐位一致性核对。"""
    return [(round(r["edited_segment"]["start"], 3), round(r["edited_segment"]["end"], 3),
             tuple((k, round(a, 3), round(b, 3)) for k, a, b in result_spans(r)))
            for r in batch["results"]]


def align_diag(results, raw_diag):
    """逐段诊断与结果批对齐（诊断按 assess 调用顺序产出，用编辑窗包含关系贪心匹配）。

    返回 ``[(result, diag_entry | None)]``；对齐不上记 None，不猜。
    """
    out, ptr, used = [], 0, set()
    for r in results:
        re0, re1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
        hit, j = None, ptr
        while j < len(raw_diag):
            iv = raw_diag[j].get("edited_interval")
            if j not in used and iv and iv[0] >= re0 - 0.6 and iv[1] <= re1 + 0.6:
                hit, ptr = raw_diag[j], j + 1
                used.add(j)
                break
            j += 1
        out.append((r, hit))
    return out


def owner_negative(r: dict, gt: dict):
    """该结果段是否压在 GT 负例编辑窗上（重叠≥0.5）；用于挑「产品上最想降档」的样本。"""
    re0, re1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
    best, best_ov = None, 0.0
    for n in gt["negatives"]:
        ov = overlap_frac(n["edited"][0], n["edited"][1], re0, re1)
        if ov >= MIN_ED_OVERLAP and ov > best_ov:
            best, best_ov = n, ov
    return best


def _neg_levels(batch: dict, gt: dict):
    """落在负例编辑窗（重叠≥0.5）上的结果段档位，按 (负例 id) -> [档位]。沿用 evaluate 的 FP 口径。"""
    rows = {}
    for n in gt["negatives"]:
        n0, n1 = n["edited"]
        got = []
        for r in batch["results"]:
            if r.get("not_in_source"):
                continue
            re0, re1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
            if overlap_frac(n0, n1, re0, re1) >= MIN_ED_OVERLAP:
                got.append(r["confidence"])
        rows[n["id"]] = sorted(got)
    return rows


def main() -> int:
    report = {}
    for case, gt_rel in CASES:
        off_p, on_p = BENCH / OFF_PATTERN.format(case=case), BENCH / ON_PATTERN.format(case=case)
        if not (off_p.exists() and on_p.exists()):
            print(f"[{case}] 缺批：{off_p.name} 或 {on_p.name}，跳过")
            continue
        off = json.loads(off_p.read_text(encoding="utf-8"))
        on = json.loads(on_p.read_text(encoding="utf-8"))
        gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))

        migration, cross_off, cross_on = Counter(), Counter(), Counter()
        hurt, cured = [], []
        for ro, rn in zip(off["results"], on["results"]):
            lo, ln = ro["confidence"], rn["confidence"]
            g = _owner(ro, gt)
            v = _verdict(ro, g)
            if lo != ln:
                migration[f"{lo}->{ln}"] += 1
            cross_off[f"{lo} / {v}"] += 1
            cross_on[f"{ln} / {v}"] += 1
            if v == "HIT" and lo != ln:
                hurt.append({"gt_id": g["id"], "downgrade": f"{lo}->{ln}",
                             "ed": [ro["edited_segment"]["start"], ro["edited_segment"]["end"]]})
            if v == "MISS" and lo == "HIGH" and ln != "HIGH":
                cured.append({"gt_id": g["id"], "downgrade": f"{lo}->{ln}",
                              "new_reasons": [x for x in rn["reasons"] if x not in ro["reasons"]]})

        diag_p = BENCH / "work" / ("confv2_diag_%s.json" % case)
        if not diag_p.exists():
            print(f"  ⚠️ 缺诊断文件 {diag_p.name}，score_v2 分布无法统计（不是「无降档」）")
        raw_diag = json.loads(diag_p.read_text(encoding="utf-8")) if diag_p.exists() else []
        v2 = [d["v2"] for d in raw_diag if d.get("v2")]
        scores = sorted(x["score"] for x in v2)

        # score_v2 到底有没有判别信息：按 GT 判定分组统计（诊断与 results 同序，每段一次 assess）
        by_verdict = {}
        for r, hit in align_diag(off["results"], raw_diag):
            s = (hit or {}).get("v2", {}).get("score") if hit else None
            by_verdict.setdefault(_verdict(r, _owner(r, gt)), []).append(s)
        vstat = {}
        for k, vals in sorted(by_verdict.items()):
            got = sorted(x for x in vals if x is not None)
            vstat[k] = {"n": len(vals), "aligned": len(got),
                        "median": got[len(got) // 2] if got else None,
                        "min": got[0] if got else None,
                        "below_gate": sum(1 for x in got if x < 0.6)}

        neg_off, neg_on = _neg_levels(off, gt), _neg_levels(on, gt)

        def _high_med(rows):
            return sum(1 for lv in rows.values() for x in lv if x in ("HIGH", "MEDIUM"))

        report[case] = {
            "identical_localization": _spanset(off) == _spanset(on),
            "segments": len(on["results"]),
            "migration": dict(migration),
            "cross_off": dict(cross_off),
            "cross_on": dict(cross_on),
            "HIGH_MISS_count": {"off": cross_off.get("HIGH / MISS", 0),
                                "on": cross_on.get("HIGH / MISS", 0)},
            "HIGH_part_count": {"off": cross_off.get("HIGH / part", 0),
                                "on": cross_on.get("HIGH / part", 0)},
            "cured_HIGH_MISS": cured,
            "hurt_true_HIT": hurt,
            "neg_high_or_medium": {"off": _high_med(neg_off), "on": _high_med(neg_on),
                                   "off_rows": neg_off, "on_rows": neg_on},
            "score_v2": {"n": len(scores), "min": scores[0] if scores else None,
                         "p25": scores[len(scores) // 4] if scores else None,
                         "median": scores[len(scores) // 2] if scores else None,
                         "p75": scores[3 * len(scores) // 4] if scores else None,
                         "max": scores[-1] if scores else None,
                         "below_gate": sum(1 for s in scores if s < 0.6)},
            "score_v2_by_verdict": vstat,
            "gate_hits": dict(Counter(r for d in _diag_reasons(diag_p) for r in d)),
        }
        r = report[case]
        print(f"\n=== {case}（{r['segments']} 段）===")
        print(f"  定位逐位一致: {r['identical_localization']}")
        print(f"  档位迁移: {r['migration'] or '无'}")
        print(f"  HIGH∧MISS（自信错答）: {r['HIGH_MISS_count']['off']} -> {r['HIGH_MISS_count']['on']}"
              f" | HIGH∧part: {r['HIGH_part_count']['off']} -> {r['HIGH_part_count']['on']}")
        print(f"  收益（HIGH∧MISS 被降档）: {len(r['cured_HIGH_MISS'])} 条 | "
              f"代价（HIT 被降档）: {len(r['hurt_true_HIT'])} 条")
        print(f"  负例上 HIGH/MEDIUM: {r['neg_high_or_medium']['off']} -> {r['neg_high_or_medium']['on']}")
        print(f"  score_v2: n={r['score_v2']['n']} min={r['score_v2']['min']} "
              f"median={r['score_v2']['median']} max={r['score_v2']['max']} "
              f"<0.6 共 {r['score_v2']['below_gate']}")
        print(f"  OFF 交叉表: {r['cross_off']}")
        print(f"  ON  交叉表: {r['cross_on']}")

    out = BENCH / "work" / "confv2_analysis.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {out}")
    return 0


def _diag_reasons(diag_p: Path):
    """从诊断文件取每段命中的低置信原因（列表的列表）。"""
    if not diag_p.exists():
        return []
    data = json.loads(diag_p.read_text(encoding="utf-8"))
    return [[x for x in d.get("new_reasons") or [] if x != "confidence_v2_downgraded"]
            for d in data]


if __name__ == "__main__":
    sys.exit(main())
