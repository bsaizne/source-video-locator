# -*- coding: utf-8 -*-
"""续54 窗 spawn 合并四片回归验收（零语义 + 墙钟）。

合并（`_preembed_mids` / metadata 缓存）**无旋钮、直接生效** ⇒ test1 之外的三片必须
自证零语义。参照臂 = `work/isc_l2_ab/on_<case>.results.json`（续52-G 常态链复验臂，
= 续54 改动之前的现役默认态产物）。

判据：
  1. 零语义：新臂与参照臂 strip(result_id) 后逐行 0 差异。
  2. 提速：新臂墙钟 / 参照臂墙钟（参照数字含 10-04 夜间 GPU 争用，口径 ±10%）。

用法（venv 绝对路径 python，repo 根）:
  python mvp/scripts/probe_spawn_consolidation_regress.py [--case all]   # all = test2/test3/2mkv
输出: work/spawn_consolidation_regress/{case}.results.json + regress_summary.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
os.environ.setdefault("SVL_DATA_DIR", r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE",
                      r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app import locator_service as LS                     # noqa: E402
from device.directml_backend import DirectMLBackend       # noqa: E402
from infrastructure.config import load_config             # noqa: E402

OUT = BENCH / "work" / "spawn_consolidation_regress"
REF = BENCH / "work" / "isc_l2_ab"
CASES = {
    "test2": (r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4"),
    "test3": (r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4"),
    "2mkv": (r"D:\video\1.mp4", r"D:\video\2.mkv"),
    # test1 已在续54 用同脚本双臂 + 三方 strip 验收，此处仅保留入口
    "test1": (r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv"),
}
ALL_PENDING = ["test2", "test3", "2mkv"]
VOLATILE = ("result_id",)


def strip(rows: list) -> list:
    return [{k: v for k, v in r.items() if k not in VOLATILE} for r in rows]


def load_ref(case: str, ref_dir: Path, ref_pat: str) -> dict:
    return json.loads((ref_dir / (ref_pat % case)).read_text(encoding="utf-8"))


def ref_wall(case: str, ref_dir: Path, ref_pat: str):
    """参照臂墙钟：isc_l2_ab 用 ab_<case>.json；regress 目录用 regress_summary.json。"""
    ab_p = ref_dir / ("ab_%s.json" % case)
    if ab_p.exists():
        ab = json.loads(ab_p.read_text(encoding="utf-8"))
        return ab.get("arms", {}).get("on", {}).get("wall_s")
    summ = ref_dir / "regress_summary.json"
    if summ.exists():
        rep = json.loads(summ.read_text(encoding="utf-8"))
        for c in rep.get("cases", []):
            if c.get("case") == case:
                return c.get("wall_s")
    return None


def run_case(case: str, force: bool, patch_grid: bool = False,
             tag: str = "", ref_dir: Path = None, ref_pat: str = "on_%s.results.json") -> dict:
    ref_dir = ref_dir or REF
    edited, orig = CASES[case]
    res_p = OUT / ("%s%s.results.json" % (tag, case))
    ref = load_ref(case, ref_dir, ref_pat)
    rep = {"case": case, "reference": str(ref_dir / (ref_pat % case)),
           "ref_wall_s": ref_wall(case, ref_dir, ref_pat),
           "ref_segments": len(ref["results"]),
           "patch_refine_grid": patch_grid}
    if res_p.exists() and not force:
        print("[%s] 复用已有产物 %s" % (case, res_p.name), flush=True)
        new = json.loads(res_p.read_text(encoding="utf-8"))
        rep.update({"wall_s": None, "reused": True})
    else:
        cfg = load_config()
        cfg.pipeline.patch_refine_grid = bool(patch_grid)
        srv = LS.SourceLocatorService(config=cfg)
        assert isinstance(srv.backend, DirectMLBackend), \
            "必须 DirectMLBackend, 实际 %s" % type(srv.backend).__name__
        print("[%s] BACKEND=%s l2=%s grid=%s grid_refine=%s patch_grid=%s"
              % (case, type(srv.backend).__name__, cfg.pipeline.isc_l2_index_enabled,
                 cfg.pipeline.grab_grid_decode, cfg.pipeline.isc_refine_grid_refine,
                 cfg.pipeline.patch_refine_grid), flush=True)
        t0 = time.monotonic()
        batch = srv.locate(edited, orig)
        rep["wall_s"] = round(time.monotonic() - t0, 1)
        new = batch.to_dict() if hasattr(batch, "to_dict") else batch
        res_p.write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")
        print("[%s] locate %.1fs (%d 段)" % (case, rep["wall_s"], len(new["results"])), flush=True)

    s_ref, s_new = strip(ref["results"]), strip(new["results"])
    diffs = []
    if len(s_ref) == len(s_new):
        for i, (a, b) in enumerate(zip(s_ref, s_new)):
            if a != b:
                diffs.append({"idx": i, "edited": a.get("edited_segment"),
                              "ref": a.get("original"), "new": b.get("original"),
                              "conf_ref": a.get("confidence"), "conf_new": b.get("confidence")})
    rep["compare"] = {"n_ref": len(s_ref), "n_new": len(s_new),
                      "identical_after_strip": bool(len(s_ref) == len(s_new) and not diffs),
                      "n_diff": len(diffs), "diffs": diffs[:20]}
    if rep.get("wall_s") and rep["ref_wall_s"]:
        rep["speedup_vs_ref"] = round(rep["ref_wall_s"] / rep["wall_s"], 3)
    print("[%s] strip 差异 %d/%d identical=%s speedup(vs ref)=%s"
          % (case, rep["compare"]["n_diff"], rep["compare"]["n_ref"],
             rep["compare"]["identical_after_strip"], rep.get("speedup_vs_ref")), flush=True)
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="all", choices=["all"] + sorted(CASES))
    ap.add_argument("--force", action="store_true", help="重跑已存在产物")
    ap.add_argument("--patch-grid", action="store_true",
                    help="本臂开 pipeline.patch_refine_grid（网格抽取）")
    ap.add_argument("--tag", default="", help="产物文件名前缀（禁止覆盖既有臂留痕）")
    ap.add_argument("--ref-dir", default=None, help="参照臂目录（缺省 work/isc_l2_ab）")
    ap.add_argument("--ref-pat", default="on_%s.results.json",
                    help="参照臂文件名模板（regress 目录用 '%%s.results.json'）")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    ref_dir = Path(args.ref_dir) if args.ref_dir else REF
    cases = list(ALL_PENDING) if args.case == "all" else [args.case]
    reps = [run_case(c, args.force, patch_grid=args.patch_grid, tag=args.tag,
                     ref_dir=ref_dir, ref_pat=args.ref_pat) for c in cases]
    summary = {"cases": reps,
               "all_identical": all(r["compare"]["identical_after_strip"] for r in reps),
               "created": time.strftime("%Y-%m-%d %H:%M:%S")}
    summ_name = "regress_summary%s.json" % ("_" + args.tag.strip("_") if args.tag else "")
    (OUT / summ_name).write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
    print("SUMMARY all_identical=%s" % summary["all_identical"], flush=True)
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
