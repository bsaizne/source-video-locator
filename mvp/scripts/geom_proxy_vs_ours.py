# -*- coding: utf-8 -*-
"""代理复现(推断级) 场景切分 × 我方编辑侧切点 —— 几何对照 (判卷侧 §4.2).

输入(只读对方目录, 不写入对方任何文件):
  D:\\claudework\\cutmatch-analysis\\sandbox\\out\\scene_split_t{030,040,050,060}.json
  (单文件多片 {clip: payload}; payload.cuts[i] = {frame, time_ms, prob})

对照基线(我方):
  runtime = 现行生产「两级切分 + 白闪守卫」 work/rerun_<case>_runtime_twopassflash.results.json
  tn      = TransNetV2 探针(同源模型, 不同实现)  work/tn_<case>.results.json

输出: work/proxy_geom_<case>_<batch>_t0XX.{json,csv}
      work/proxy_geom_summary.json  (含 匹配/独有清单/阈值稳定性/我方分段链式性)
定级: 「代理复现(推断级)」≠ 竞品实测; 本脚本不做"谁是真切换"的自动判定。
"""
from __future__ import annotations
import importlib.util, json, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BENCH = Path(r"D:\claudework\benchmark")
WORK = BENCH / "work"
PROXY = Path(r"D:\claudework\cutmatch-analysis\sandbox\out")

spec = importlib.util.spec_from_file_location("icp", str(BENCH / "mvp" / "scripts" / "import_competitor_proxy.py"))
icp = importlib.util.module_from_spec(spec); spec.loader.exec_module(icp)

CASES = {
    "2mkv":  ("1.mp4",        "rerun_2mkv_runtime_twopassflash.results.json",  "tn_2mkv.results.json"),
    "test1": ("test1-ed.mp4", "rerun_test1_runtime_twopassflash.results.json", "tn_test1.results.json"),
    "test2": ("tset2-ed.mp4", "rerun_test2_runtime_twopassflash.results.json", "tn_test2.results.json"),
    "test3": ("test3-ed.mp4", "rerun_test3_runtime_twopassflash.results.json", "tn_test3.results.json"),
}
THRESHOLDS = ["030", "040", "050", "060"]
TOL = 0.5


def proxy_cuts(clip: str, th: str) -> list[float]:
    d = json.loads((PROXY / ("scene_split_t%s.json" % th)).read_text(encoding="utf-8"))[clip]
    return icp._cut_times(d)


def chaining(res_name: str) -> dict:
    """我方分段链式性: end_i 是否 == start_{i+1}. 非链式 ⇒ 用 end 当切点会虚增. """
    res = json.loads((WORK / res_name).read_text(encoding="utf-8"))["results"]
    res = sorted(res, key=lambda r: float(r["edited_segment"]["start"]))
    bad = sum(1 for a, b in zip(res, res[1:])
              if abs(float(a["edited_segment"]["end"]) - float(b["edited_segment"]["start"])) > 0.05)
    return {"n_results": len(res), "nonchained_pairs": bad,
            "chained": bad == 0,
            "unique_boundaries_both_ends": len({round(float(r["edited_segment"][k]), 2)
                                                 for r in res for k in ("start", "end")
                                                 if float(r["edited_segment"][k]) > 0.05})}


summary = {"provenance": "proxy-repro(推断级) vs benchmark 侧编辑切点; tol=%.1fs" % TOL,
           "cut_convention": "切点 = 各段 start (>0.05s); 与对方 cuts 同义(不含 0 与片尾)",
           "cases": {}}
rows = []
for case, (clip, base_rt, base_tn) in CASES.items():
    entry = {"clip": clip, "batches": {}, "proxy_cuts_by_threshold": {th: len(proxy_cuts(clip, th)) for th in THRESHOLDS}}
    sets = [set(proxy_cuts(clip, th)) for th in THRESHOLDS]
    core = set.intersection(*sets)
    union = set.union(*sets)
    entry["proxy_cut_stability"] = {
        "stable_all_4": len(core), "union": len(union),
        "stable_ratio": round(len(core) / max(len(union), 1), 4)}

    for batch, base_name in (("runtime", base_rt), ("tn", base_tn)):
        entry["batches"][batch] = {"baseline": base_name, "chaining": chaining(base_name), "thresholds": {}}
        for th in THRESHOLDS:
            prefix = WORK / ("proxy_geom_%s_%s_t%s" % (case, batch, th))
            rep = icp.geometry(PROXY / ("scene_split_t%s.json" % th), case,
                               WORK / base_name, TOL, prefix, clip=clip)
            keep = {k: rep[k] for k in ("tol_s", "n_theirs", "n_ours", "matched",
                                        "theirs_only", "ours_only", "match_dist_p50", "match_dist_p90")}
            # 给代理独有切点标注「四阈值稳定出现」次数
            all_sets = sets
            for x in rep["theirs_only_list"]:
                x["stable_in_n_thresholds"] = sum(1 for s in all_sets
                                                  if any(abs(x["time"] - c) <= 0.02 for c in s))
            keep["theirs_only_list"] = rep["theirs_only_list"]
            keep["ours_only_list"] = rep["ours_only_list"]
            entry["batches"][batch]["thresholds"][th] = keep
            rows.append((case, batch, th, keep["n_theirs"], keep["n_ours"], keep["matched"],
                         keep["theirs_only"], keep["ours_only"]))

    summary["cases"][case] = entry

(WORK / "proxy_geom_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                              encoding="utf-8")

print()
print("| case | 对照批 | 阈值 | 代理切点 | 我方切点 | ±%.1fs 匹配 | 仅代理 | 仅我方 |" % TOL)
print("|---|---|---|---|---|---|---|---|")
for c, b, t, nt, no, m, to, oo in rows:
    print("| %s | %s | 0.%s | %d | %d | %d | %d | %d |" % (c, b, t[1:], nt, no, m, to, oo))

print()
print("=== 我方分段链式性 (非链式 ⇒ 段 end 不是切点) ===")
for case, e in summary["cases"].items():
    for b, bd in e["batches"].items():
        ch = bd["chaining"]
        print("%-6s %-8s n_results=%-4d 非链式对=%-4d 链式=%-5s (start∪end 唯一点=%d)" % (
            case, b, ch["n_results"], ch["nonchained_pairs"], ch["chained"], ch["unique_boundaries_both_ends"]))

print()
print("=== 代理侧阈值稳定性 ===")
for case, e in summary["cases"].items():
    s = e["proxy_cut_stability"]
    print("%-6s 切点 %s | 四阈值共有 %d / 并集 %d (稳定 %.1f%%)" % (
        case, e["proxy_cuts_by_threshold"], s["stable_all_4"], s["union"], 100 * s["stable_ratio"]))
