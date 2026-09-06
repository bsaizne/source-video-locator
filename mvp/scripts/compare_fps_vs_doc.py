"""采样率重跑批 vs 文档基线批 四片三指标对比（2026-09-05）。

用法: python compare_fps_vs_doc.py <fps>
doc 批 = mvp/benchmark/user_case/user_results.json + cases/*_results.json（文档基线, 2fps）
<fps> 批 = work/rerun_<case>_<fps>fps.results.json
输出: work/compare_<fps>fps_vs_doc.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
from measure_shot_recall import evaluate  # noqa: E402

PAIRS = [
    ("2mkv",  "datasets/real/ground_truth_v4.json",
     "mvp/benchmark/user_case/user_results.json",          "2mkv"),
    ("test1", "datasets/real/ground_truth_test1.json",
     "mvp/benchmark/user_case/cases/test1_results.json",   "test1"),
    ("test2", "datasets/real/ground_truth_test2.json",
     "mvp/benchmark/user_case/cases/test2_results.json",   "test2"),
    ("test3", "datasets/real/ground_truth_test3.json",
     "mvp/benchmark/user_case/cases/test3_results.json",   "test3"),
]


def load_res(p: Path) -> list[dict]:
    data = json.loads(Path(p).read_text(encoding="utf-8"))
    return data["results"] if isinstance(data, dict) and "results" in data else data


def main() -> int:
    fps = sys.argv[1] if len(sys.argv) > 1 else "4"
    run_suffix = f"rerun_{fps}fps" if "." not in fps else f"rerun_{fps}fps"
    rows = []
    print("=" * 100)
    for name, gt_p, doc_p, case in PAIRS:
        gt = json.loads((BENCH / gt_p).read_text(encoding="utf-8"))
        doc_res = load_res(BENCH / doc_p)
        run_p = BENCH / "work" / f"rerun_{case}_{fps}fps.results.json"
        if not run_p.exists():
            print(f"[{name}] MISSING {run_p.name}, skip")
            continue
        run_res = load_res(run_p)
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rd = evaluate(gt, doc_res, label=f"{name}-doc")
            rr = evaluate(gt, run_res, label=f"{name}-{fps}fps")
        def fmt(r):
            return (f"严格 {r['strict_hit']}/{r['n_pos']} 场景 {r['scene_hit']}/{r['n_pos']} "
                    f"负例 {r['fp']}/{r['n_neg']} 支撑 {r['sup']}/{r['tot']}")
        rows.append({"name": name, "doc": fmt(rd), f"run{fps}": fmt(rr),
                     "doc_per_pos": {p["id"]: p["mark"] for p in rd["per_pos"]},
                     "run_per_pos": {p["id"]: p["mark"] for p in rr["per_pos"]}})
        print(f"[{name}] doc : {fmt(rd)}")
        print(f"[{name}] {fps}fps: {fmt(rr)}")
        dp = rows[-1]["doc_per_pos"]; rp = rows[-1]["run_per_pos"]
        for pid in sorted(set(dp) | set(rp), key=lambda s: (len(s), s)):
            a, b = dp.get(pid, "-"), rp.get(pid, "-")
            if a != b:
                print(f"    {pid}: {a} -> {b}")
        print("-" * 100)
    out = BENCH / "work" / f"compare_{fps}fps_vs_doc.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
