# -*- coding: utf-8 -*-
"""性能旋钮同脚本双臂 A/B（2026-10-05 续55 通用件）。

用途：给「零语义提速」类改动出**干净口径**数字 —— off 臂 = 现役默认态、on 臂 = 指定旋钮值，
**同一脚本、同一条件、先后紧邻**（项目口径：提速只认同脚本双臂，跨 run 对照只作物级参考）。

判据：① `strip(result_id)` 后逐字段 0 差异（零语义）② 墙钟比（提速）。

用法（venv 绝对路径 python，repo 根）:
  python mvp/scripts/probe_perf_ab.py --case test1 --knob media.cluster_workers=4 --tag cluster4
  # 多次跑请换 --tag 或加 --force；既有产物默认拒覆盖（留痕）
输出: work/perf_ab/<tag>.{off,on}.results.json + <tag>.ab_summary.json
"""
from __future__ import annotations

import argparse
import copy
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

OUT = BENCH / "work" / "perf_ab"
CASES = {
    "test1": (r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv"),
    "test2": (r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4"),
    "test3": (r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4"),
    "2mkv": (r"D:\video\1.mp4", r"D:\video\2.mkv"),
}
VOLATILE = ("result_id",)


def apply_knob(cfg, dotted: str, raw_value: str) -> None:
    obj, *rest = dotted.split(".")
    cur = getattr(cfg, obj or "pipeline")
    for name in rest[:-1]:
        cur = getattr(cur, name)
    leaf = rest[-1]
    old = getattr(cur, leaf)
    if isinstance(old, bool):
        val = raw_value.lower() in ("1", "true", "on", "yes")
    elif isinstance(old, int) and not isinstance(old, bool):
        val = int(raw_value)
    elif isinstance(old, float):
        val = float(raw_value)
    else:
        val = raw_value
    setattr(cur, leaf, val)


def strip(data: dict) -> dict:
    d = copy.deepcopy(data)
    d.pop("result_id", None)
    for r in d.get("results", []):
        r.pop("result_id", None)
    return d


def run_arm(case: str, tag: str, knob: str | None, force: bool) -> dict:
    edited, orig = CASES[case]
    out_p = OUT / ("%s.%s.results.json" % (tag, "off" if knob is None else "on"))
    if out_p.exists() and not force:
        raise SystemExit("产物已存在，拒绝覆盖：%s（换 --tag 或加 --force）" % out_p)
    cfg = load_config()
    if knob:
        apply_knob(cfg, knob.split("=", 1)[0].strip(), knob.split("=", 1)[1].strip())
    srv = LS.SourceLocatorService(config=cfg)
    assert isinstance(srv.backend, DirectMLBackend), \
        "必须 DirectMLBackend, 实际 %s" % type(srv.backend).__name__
    print("[%s] BACKEND=%s %s cluster_workers=%s patch_refine_grid=%s grab_grid_decode=%s"
          % ("on" if knob else "off", type(srv.backend).__name__, knob or "(默认态)",
             cfg.media.cluster_workers, cfg.pipeline.patch_refine_grid,
             cfg.pipeline.grab_grid_decode), flush=True)
    t0 = time.monotonic()
    batch = srv.locate(edited, orig)
    wall = round(time.monotonic() - t0, 1)
    data = batch.to_dict() if hasattr(batch, "to_dict") else batch
    out_p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[%s] wall=%.1fs segments=%d -> %s"
          % ("on" if knob else "off", wall, len(data.get("results", [])), out_p.name), flush=True)
    return {"wall_s": wall, "segments": len(data.get("results", [])), "results": str(out_p)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="test1", choices=sorted(CASES))
    ap.add_argument("--knob", default=None, help="on 臂改动，形如 media.cluster_workers=4")
    ap.add_argument("--tag", default="ab", help="产物前缀（防覆盖留痕）")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if not args.knob:
        raise SystemExit("必须给 --knob name=value（off 臂无需 knob 时用 --knob 指 on 臂改动）")
    OUT.mkdir(parents=True, exist_ok=True)
    off = run_arm(args.case, args.tag, None, args.force)
    on = run_arm(args.case, args.tag, args.knob, args.force)
    s_off = strip(json.loads(Path(off["results"]).read_text(encoding="utf-8")))
    s_on = strip(json.loads(Path(on["results"]).read_text(encoding="utf-8")))
    n_diff = 0
    if s_off != s_on:
        for k in sorted(set(s_off) | set(s_on)):
            if s_off.get(k) == s_on.get(k):
                continue
            if k == "results":
                for i, (a, b) in enumerate(zip(s_off.get(k, []), s_on.get(k, []))):
                    if a != b:
                        n_diff += 1
                        print("  [DIFF] row %d edited=%s off=%s on=%s"
                              % (i, a.get("edited_segment"), a.get("original"),
                                 b.get("original")), flush=True)
            else:
                n_diff += 1
                print("  [DIFF] %s" % k, flush=True)
    summary = {"case": args.case, "knob": args.knob, "arms": {"off": off, "on": on},
               "strip_identical": s_off == s_on, "n_diff_rows": n_diff,
               "speedup": round(off["wall_s"] / max(on["wall_s"], 1e-9), 3),
               "created": time.strftime("%Y-%m-%d %H:%M:%S")}
    (OUT / ("%s.ab_summary.json" % args.tag)).write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print("SUMMARY identical=%s diff_rows=%d speedup=%s off=%.1fs on=%.1fs"
          % (summary["strip_identical"], n_diff, summary["speedup"],
             off["wall_s"], on["wall_s"]), flush=True)
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
