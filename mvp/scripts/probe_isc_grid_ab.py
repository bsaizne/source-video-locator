# -*- coding: utf-8 -*-
"""ISC 宽扫网格抓帧（L1）整条 locate A/B —— test1（2026-10-03 续50 接线验收）。

唯一变量 = pipeline.grab_grid_decode（False=旧 grab_frames 窗解码 / True=select 网格抽取）。
两臂都跑完整 srv.locate()（DML 硬断言），输出 strip(result_id) 后逐字段比对 + 墙钟对比。

用法（venv 绝对路径 python，repo 根）:
  python mvp/scripts/probe_isc_grid_ab.py --case test1
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
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.locator_service import SourceLocatorService          # noqa: E402
from device.directml_backend import DirectMLBackend           # noqa: E402
from infrastructure.config import load_config                 # noqa: E402

OUT = BENCH / "work" / "isc_grid_ab"
CASES = {
    "2mkv": (r"D:\video\1.mp4", r"D:\video\2.mkv"),
    "test1": (r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv"),
    "test2": (r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4"),
    "test3": (r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4"),
}
VOLATILE = ("result_id",)


def strip(rows: list) -> list:
    out = []
    for r in rows:
        d = {k: v for k, v in r.items() if k not in VOLATILE}
        out.append(d)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="test1", choices=sorted(CASES))
    ap.add_argument("--force", action="store_true", help="忽略已有产物重跑")
    ap.add_argument("--force-on", action="store_true",
                    help="只重跑 on 臂（off 仍复用参照）；代码改动后必须用它，"
                         "否则会静默复用旧的 on 产物（2026-10-03 踩过）")
    ap.add_argument("--off-results", default=None,
                    help="off 臂复用已有结果批（默认取 work/isc_refine_arms/v2_{case}.results.json "
                         "= 现役默认批，续47 defaults_check 已证与当前配置逐位一致）")
    args = ap.parse_args()
    edited, orig = CASES[args.case]
    OUT.mkdir(parents=True, exist_ok=True)
    rep = {"case": args.case, "edited": edited, "source": orig, "arms": {}}

    ref_off = Path(args.off_results) if args.off_results else \
        (BENCH / "work" / "isc_refine_arms" / ("v2_%s.results.json" % args.case))

    for arm, grid_on in (("off", False), ("on", True)):
        res_p = OUT / ("%s_%s.results.json" % (arm, args.case))
        if arm == "off" and ref_off.exists() and not args.force:
            print("[off] 复用现役默认批 %s（不重跑 off 臂）" % ref_off, flush=True)
            rep["arms"]["off"] = {"wall_s": None, "results": str(ref_off), "reused": True,
                                  "note": "现役默认批（续47 defaults_check 逐位一致）"}
            continue
        cfg = load_config()
        cfg.pipeline.grab_grid_decode = bool(grid_on)
        cfg.pipeline.grab_window_decode = True
        srv = SourceLocatorService(config=cfg)
        assert isinstance(srv.backend, DirectMLBackend), \
            "必须 DirectMLBackend, 实际 %s" % type(srv.backend).__name__
        print("[%s] BACKEND=%s grab_grid_decode=%s isc_radius=%s"
              % (arm, type(srv.backend).__name__, cfg.pipeline.grab_grid_decode,
                 cfg.pipeline.isc_refine_scan_radius_s), flush=True)
        force_this = args.force or (args.force_on and arm == "on")
        if res_p.exists() and not force_this:
            print("[%s] 复用已有产物 %s" % (arm, res_p), flush=True)
            rep["arms"][arm] = {"wall_s": None, "results": str(res_p), "reused": True}
            continue
        t0 = time.monotonic()
        batch = srv.locate(edited, orig)
        wall = time.monotonic() - t0
        res_p.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1),
                         encoding="utf-8")
        rep["arms"][arm] = {"wall_s": round(wall, 1), "segments": len(batch.results),
                            "results": str(res_p), "reused": False}
        print("[%s] locate %.1fs (%d 段)" % (arm, wall, len(batch.results)), flush=True)

    a = Path(rep["arms"]["off"]["results"]) if rep["arms"].get("off") else None
    b = OUT / ("on_%s.results.json" % args.case)
    if a is not None and a.exists() and b.exists():
        off = json.loads(a.read_text(encoding="utf-8"))["results"]
        on = json.loads(b.read_text(encoding="utf-8"))["results"]
        so, sn = strip(off), strip(on)
        same_n = len(so) == len(sn)
        diffs = []
        if same_n:
            for i, (x, y) in enumerate(zip(so, sn)):
                if x != y:
                    diffs.append({"idx": i,
                                  "edited": x.get("edited_segment"),
                                  "off": x.get("original"), "on": y.get("original"),
                                  "conf_off": x.get("confidence"),
                                  "conf_on": y.get("confidence")})
        rep["compare"] = {"n_off": len(so), "n_on": len(sn),
                          "identical_after_strip": bool(same_n and not diffs),
                          "n_diff": len(diffs), "diffs": diffs[:20]}
        w0, w1 = rep["arms"]["off"].get("wall_s"), rep["arms"]["on"].get("wall_s")
        if w0 and w1:
            rep["speedup"] = round(w0 / w1, 3)
            print("\n=== A/B ===\noff %.1fs | on %.1fs | speedup %.3fx | 差异段 %d/%d"
                  % (w0, w1, w0 / w1, len(diffs), len(so)), flush=True)
        print("identical_after_strip =", rep["compare"]["identical_after_strip"], flush=True)
    (OUT / ("ab_%s.json" % args.case)).write_text(
        json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved %s" % (OUT / ("ab_%s.json" % args.case)))
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
