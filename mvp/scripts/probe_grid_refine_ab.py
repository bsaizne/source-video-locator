# -*- coding: utf-8 -*-
"""grid-refine A/B 探针（2026-10-05 续54）：精扫细化窗网格抽取 双臂验收。

判据：
  1. 零语义：on 臂与 off 臂 `strip(result_id)` 后**逐字段 0 差异**——fine_ts 走 select
     抽取（grab_grid_times，超集 + first_ge 配对）与 grab_frames 逐帧取帧应得**同帧**
     （续50 机制：300/300、90/90 逐字节；宽扫 coarse 已四片 A/B 验收同一契约）。
  2. 提速：on 臂墙钟 < off 臂（预期 isc_refine 阶段 -50% 级，全链 -15~20%）。

用法: D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_grid_refine_ab.py [--case test1]
输出: work/grid_refine_ab/{off,on}.results.json + ab_summary.json + 控制台摘要。
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
from infrastructure.config import load_config             # noqa: E402

OUT = BENCH / "work" / "grid_refine_ab"
CASES = {
    "test1": (r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv"),
    "2mkv": (r"D:\video\1.mp4", r"D:\video\2.mkv"),
}


def run_arm(case: str, refine_grid: bool, tag: str) -> dict:
    edited, orig = CASES[case]
    cfg = load_config()
    cfg.pipeline.isc_refine_grid_refine = refine_grid
    srv = LS.SourceLocatorService(config=cfg)
    t0 = time.monotonic()
    batch = srv.locate(edited, orig)
    wall = time.monotonic() - t0
    data = batch.to_dict() if hasattr(batch, "to_dict") else batch
    out = OUT / f"{tag}.results.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[%s] wall=%.1fs segments=%d -> %s" % (tag, wall, len(data.get("results", [])), out.name),
          flush=True)
    return {"wall_s": round(wall, 1), "segments": len(data.get("results", [])),
            "results_file": str(out)}


def strip(data: dict) -> dict:
    """剥离随机批次字段后拷贝（result_id 内嵌随机 UUID；同批字段保留）。"""
    import copy
    d = copy.deepcopy(data)
    d.pop("result_id", None)
    for r in d.get("results", []):
        r.pop("result_id", None)
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="test1", choices=sorted(CASES))
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"== grid-refine A/B on {args.case}（off 先行）", flush=True)
    off = run_arm(args.case, False, "off")
    on = run_arm(args.case, True, "on")

    d_off = json.loads((OUT / "off.results.json").read_text(encoding="utf-8"))
    d_on = json.loads((OUT / "on.results.json").read_text(encoding="utf-8"))
    s_off, s_on = strip(d_off), strip(d_on)
    n_diff = 0
    if s_off == s_on:
        print("[PASS] strip 逐字段 0 差异", flush=True)
    else:
        keys = set(s_off) | set(s_on)
        for k in sorted(keys):
            if s_off.get(k) != s_on.get(k):
                n_diff += 1
                print(f"  [DIFF] {k}", flush=True)
        # 逐段定位差异行
        r_off = {r.get("edited", {}).get("start"): r for r in s_off.get("results", [])}
        r_on = {r.get("edited", {}).get("start"): r for r in s_on.get("results", [])}
        for k in sorted(set(r_off) | set(r_on)):
            if r_off.get(k) != r_on.get(k):
                n_diff += 1
                print(f"  [DIFF] row edited.start={k}", flush=True)
    speedup = round(off["wall_s"] / max(on["wall_s"], 1e-9), 3)
    summary = {"case": args.case, "off": off, "on": on,
               "strip_identical": s_off == s_on, "n_diff_blocks": n_diff,
               "speedup": speedup,
               "created": time.strftime("%Y-%m-%d %H:%M:%S")}
    (OUT / "ab_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    print("SUMMARY %s" % json.dumps({k: summary[k] for k in
                                     ("strip_identical", "n_diff_blocks", "speedup",
                                      "off", "on")}, ensure_ascii=False), flush=True)
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
