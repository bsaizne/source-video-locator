"""导入「代理复现」产物 → 我方评估口径 (2026-09-26).

输入(cutmatch-analysis 侧 RUNBOOK_CUTMATCH_PROXY_REPRO.md §3 规定):
  sandbox/out/localization.json  —— 每条编辑片段 -> 原片起止时间码(毫秒) + 评分
  sandbox/out/scene_split.json   —— 切点 + 场景区间(帧号 + 毫秒)
本脚本做两件事(零 mvp/src 改动; 不修改对方项目):
  1. --loc  -> 转成我方 results schema(work/proxy_<case>.results.json), 可直接喂
     measure_four_results.py --pattern 'work/proxy_{case}.results.json' 与 117/139 同口径对照;
  2. --scene-split -> 与某批我方边界做**几何对照**(±tol 匹配): 双方独有切点/匹配数/最近距离分位,
     输出 work/proxy_geom_<case>.json + .csv, 供人工/多模态逐条复核(不做自动"谁对"的判定)。

定级(必须遵守): 产物是「代理复现(推断级)」, 非竞品实测输出 ⇒ 结论一律写成"口径差异", 不写"竞品成绩"。
用法:
  python mvp/scripts/import_competitor_proxy.py --case 2mkv --loc <localization.json> \
      --scene-split <scene_split.json> --baseline-results work/rerun_2mkv_perfopt.results.json
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]

CASES = ["2mkv", "test1", "test2", "test3"]


def _conf(score: float) -> str:
    if score is None:
        return "MEDIUM"
    return "HIGH" if score >= 0.75 else ("MEDIUM" if score >= 0.50 else "LOW")


def _iter_v2(d: dict) -> list:
    """D 段 v2 schema: {schema: cutmatch-proxy-localization/v2, queries: [...]}。
    每查询: ed{start_ms,end_ms}, matched, not_in_source, source_span{start_ms,end_ms}|null,
    score, confidence, method, refined, candidates[...]. 展平成旧 matches 行。"""
    rows = []
    for q in d.get("queries", []):
        ed = q.get("ed") or {}
        sp = q.get("source_span") or {}
        cand = []
        for c in (q.get("candidates") or [])[:20]:
            cs = c.get("source_span") or {}
            cand.append({
                "rank": c.get("rank"), "channel": c.get("channel"),
                "source_start_ms": cs.get("start_ms"), "source_end_ms": cs.get("end_ms"),
                "score": c.get("score"), "akaze_inliers": c.get("akaze_inliers"),
                "akaze_score": c.get("akaze_score")})
        rows.append({
            "commentary_start_ms": ed.get("start_ms"), "commentary_end_ms": ed.get("end_ms"),
            "source_start_ms": sp.get("start_ms"), "source_end_ms": sp.get("end_ms"),
            "score": q.get("score", q.get("confidence")),
            "not_in_source": bool(q.get("not_in_source")) or not q.get("source_span"),
            "method": q.get("method"), "refined": q.get("refined"),
            "query_id": q.get("query_id"), "scene_index": q.get("scene_index"),
            "candidates": cand,
        })
    return rows


def import_localization(loc_path: Path, case: str, out: Path) -> dict:
    d = json.loads(loc_path.read_text(encoding="utf-8"))
    matches = d.get("matches") if isinstance(d.get("matches"), list) else _iter_v2(d)
    results = []
    for m in matches:
        c0 = float(m.get("commentary_start_ms") or 0) / 1000.0
        c1 = float(m.get("commentary_end_ms") or 0) / 1000.0
        s0 = float(m.get("source_start_ms") or 0) / 1000.0
        s1 = float(m.get("source_end_ms") or 0) / 1000.0
        sc = m.get("confidence", m.get("score"))
        results.append({
            "result_id": "proxy-%d" % len(results),
            "proxy_query_id": m.get("query_id"),
            "proxy_scene_index": m.get("scene_index"),
            "edited_segment": {"start": round(c0, 3), "end": round(c1, 3)},
            "original": {"candidate_start": round(s0, 3), "candidate_end": round(s1, 3)},
            "confidence": _conf(sc),
            "confidence_score": sc,
            "candidate_rank": 1,
            "alternatives": [],
            "proxy_candidates": m.get("candidates", []),
            "original_segments": [],
            "source": "proxy-repro",
            "not_in_source": bool(m.get("not_in_source", False) or (s1 - s0) <= 0.01),
            "excluded": False,
            "proxy_method": m.get("method"),
            "proxy_refined": m.get("refined"),
        })
    payload = {"schema_version": 1, "provenance": "proxy-repro(推断级) via cutmatch-analysis RUNBOOK",
               "original_video": d.get("source"), "edited_video": d.get("commentary"),
               "results": results}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved %s (%d 条结果)" % (out, len(results)))
    print("下一步: python mvp/scripts/measure_four_results.py --pattern '%s'" % out.as_posix().replace("2mkv", "{case}"))
    return payload


def our_boundaries(res_path: Path) -> list[float]:
    """我方编辑侧**切点**集合.

    约定: 切点 = 每段 start (>0.05s), **不用 end** —— 与对方 `cuts` 同义
    (对方 cuts 也不含 0 与片尾). 用 end 会把"片尾时刻"计入, 且在非链式分段
    (end_i != start_{i+1}, 如 TransNetV2 探针批) 下把段内收缩点误当切点.
    """
    res = json.loads(res_path.read_text(encoding="utf-8"))["results"]
    bs = set()
    for r in res:
        v = float(r["edited_segment"]["start"])
        if v > 0.05:
            bs.add(round(v, 2))
    return sorted(bs)


def _cut_times(d: dict) -> list[float]:
    """切点毫秒 -> 秒. 兼容两类送达格式:
    ① 单文件 {clip: payload} (v4 多片打包, 需 --clip 指定);
    ② 单条 {cuts: [...]}. cut 元素优先 time_ms, 退化到 frame/fps_rational.
    """
    fps = d.get("fps_rational")
    if isinstance(fps, str) and "/" in fps:
        num, den = fps.split("/")
        fps = float(num) / float(den)
    out = []
    for c in d.get("cuts", []):
        if c.get("time_ms") is not None:
            out.append(round(float(c["time_ms"]) / 1000.0, 3))
        elif c.get("frame") is not None and fps:
            out.append(round(float(c["frame"]) / float(fps), 3))
    return sorted(set(out))


def geometry(scene_split: Path, case: str, baseline: Path, tol: float, out_prefix: Path,
             clip: str | None = None) -> dict:
    d = json.loads(scene_split.read_text(encoding="utf-8"))
    if clip:
        if clip not in d:
            raise SystemExit("clip %r 不在 %s 中; 现有 = %s"
                             % (clip, scene_split.name, list(d.keys())))
        d = d[clip]
    theirs = _cut_times(d)
    fps_rational = d.get("fps_rational") if isinstance(d, dict) else None
    ours = our_boundaries(baseline)
    matched, t_only, o_only = [], [], []
    used = set()
    for t in theirs:
        best, bd = None, 1e9
        for j, o in enumerate(ours):
            if j in used:
                continue
            dist = abs(o - t)
            if dist < bd:
                best, bd = j, dist
        if best is not None and bd <= tol:
            matched.append({"theirs": t, "ours": ours[best], "dist_s": round(bd, 3)})
            used.add(best)
        else:
            t_only.append({"time": t, "nearest_ours": ours[best] if best is not None else None,
                           "dist_s": round(bd, 3) if best is not None else None})
    o_only = []
    for j, o in enumerate(ours):
        if j in used:
            continue
        best, bd = None, 1e9
        for t in theirs:
            dist = abs(o - t)
            if dist < bd:
                best, bd = t, dist
        o_only.append({"time": o, "nearest_theirs": best,
                       "dist_s": round(bd, 3) if best is not None else None})
    dists = sorted(m["dist_s"] for m in matched)
    def pct(p):
        return dists[min(len(dists) - 1, int(len(dists) * p))] if dists else None
    rep = {"case": case, "clip": clip, "fps_rational": fps_rational, "tol_s": tol,
           "n_theirs": len(theirs), "n_ours": len(ours),
           "matched": len(matched), "theirs_only": len(t_only), "ours_only": len(o_only),
           "match_dist_p50": pct(0.5), "match_dist_p90": pct(0.9),
           "theirs_only_list": t_only, "ours_only_list": o_only,
           "note": "代理复现(推断级); 谁是真切换需人工/多模态逐条复核, 本脚本不做自动判定"}
    (out_prefix.with_suffix(".json")).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    with out_prefix.with_suffix(".csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["side", "time_s", "nearest_other_s", "dist_s"])
        for m in matched:
            w.writerow(["matched", m["theirs"], m["ours"], m["dist_s"]])
        for x in t_only:
            w.writerow(["theirs_only", x["time"], x["nearest_ours"], x["dist_s"]])
        for x in o_only:
            w.writerow(["ours_only", x["time"], "", ""])
    print("saved %s{.json,.csv} | 匹配 %d / 仅他们 %d / 仅我方 %d (tol=%.1fs)"
          % (out_prefix, len(matched), len(t_only), len(o_only), tol))
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True, choices=CASES)
    ap.add_argument("--loc", help="对方 localization.json")
    ap.add_argument("--scene-split", help="对方 scene_split.json (支持单文件 {clip: payload})")
    ap.add_argument("--clip", help="scene_split 为多片打包时, 指定片名(如 1.mp4 / test1-ed.mp4)")
    ap.add_argument("--baseline-results", help="我方结果批(取编辑侧边界做几何对照)")
    ap.add_argument("--tol", type=float, default=0.5)
    ap.add_argument("--out-dir", default=str(BENCH / "work"))
    args = ap.parse_args()
    od = Path(args.out_dir)
    if args.loc:
        import_localization(Path(args.loc), args.case, od / ("proxy_%s.results.json" % args.case))
    if args.scene_split:
        if not args.baseline_results:
            print("--scene-split 需要 --baseline-results 才能做几何对照")
        else:
            geometry(Path(args.scene_split), args.case, Path(args.baseline_results),
                     args.tol, od / ("proxy_geom_%s" % args.case), clip=args.clip)
    return 0


if __name__ == "__main__":
    sys.exit(main())
