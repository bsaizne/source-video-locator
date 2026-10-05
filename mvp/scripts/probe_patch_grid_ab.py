# -*- coding: utf-8 -*-
"""patch 精排窗网格抽取 A/B（2026-10-05 续54 补二）。

唯一变量 = ``pipeline.patch_refine_grid``（默认 False）。
off 臂 = 复用 ``work/grid_refine_ab/off.results.json``（续54 合并后现役代码、默认旋钮全默认态，
墙钟 1287.3s）；on 臂 = 现役代码 + 本旋钮 True。

判据：① strip(result_id) 后**逐字段 0 差异**（网格抽取 = 同帧契约，micro 实测 120/120
逐字节同帧）② 墙钟下降（micro 单窗 2.28×，patch 窗桶 172.4s）。

用法: D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_patch_grid_ab.py [--force-off]
输出: work/patch_grid_ab/on.results.json + ab_summary.json
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

OUT = BENCH / "work" / "patch_grid_ab"
EDITED = r"D:\ProjectXIXI\test1\test1-ed.mp4"
ORIG = r"D:\ProjectXIXI\test1\test1-om.mkv"
REF_OFF = BENCH / "work" / "grid_refine_ab" / "off.results.json"
REF_OFF_WALL = 1287.3


def strip(data: dict) -> dict:
    d = copy.deepcopy(data)
    d.pop("result_id", None)
    for r in d.get("results", []):
        r.pop("result_id", None)
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-off", action="store_true", help="重跑 off 臂（默认复用续54 臂）")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    off_p = OUT / "off.results.json"
    if args.force_off or not off_p.exists():
        cfg = load_config()
        cfg.pipeline.patch_refine_grid = False
        srv = LS.SourceLocatorService(config=cfg)
        assert isinstance(srv.backend, DirectMLBackend), type(srv.backend).__name__
        t0 = time.monotonic()
        batch = srv.locate(EDITED, ORIG)
        off_wall = round(time.monotonic() - t0, 1)
        off_p.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1),
                         encoding="utf-8")
        print("[off] 重跑 wall=%.1fs" % off_wall, flush=True)
    else:
        off_wall = REF_OFF_WALL
        import shutil
        shutil.copyfile(REF_OFF, off_p)
        print("[off] 复用续54 现役臂 %s (wall=%.1fs)" % (REF_OFF.name, off_wall), flush=True)

    cfg = load_config()
    cfg.pipeline.patch_refine_grid = True
    srv = LS.SourceLocatorService(config=cfg)
    assert isinstance(srv.backend, DirectMLBackend), \
        "必须 DirectMLBackend, 实际 %s" % type(srv.backend).__name__
    print("[on] BACKEND=%s patch_refine_grid=%s grab_grid_decode=%s"
          % (type(srv.backend).__name__, cfg.pipeline.patch_refine_grid,
             cfg.pipeline.grab_grid_decode), flush=True)
    t0 = time.monotonic()
    batch = srv.locate(EDITED, ORIG)
    on_wall = round(time.monotonic() - t0, 1)
    on_p = OUT / "on.results.json"
    on_p.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
    print("[on] wall=%.1fs segments=%d" % (on_wall, len(batch.results)), flush=True)

    s_off = strip(json.loads(off_p.read_text(encoding="utf-8")))
    s_on = strip(json.loads(on_p.read_text(encoding="utf-8")))
    identical = s_off == s_on
    n_diff = 0
    if not identical:
        for k in sorted(set(s_off) | set(s_on)):
            if s_off.get(k) != s_on.get(k):
                if k == "results":
                    for i, (a, b) in enumerate(zip(s_off.get(k, []), s_on.get(k, []))):
                        if a != b:
                            n_diff += 1
                            print("  [DIFF] row %d edited=%s" % (i, a.get("edited_segment")),
                                  flush=True)
                else:
                    n_diff += 1
                    print("  [DIFF] %s" % k, flush=True)
    summary = {"case": "test1", "knob": "patch_refine_grid",
               "off": {"wall_s": off_wall, "results": str(off_p),
                       "reused": not args.force_off},
               "on": {"wall_s": on_wall, "results": str(on_p),
                      "segments": len(batch.results)},
               "strip_identical": identical, "n_diff_blocks": n_diff,
               "speedup": round(off_wall / max(on_wall, 1e-9), 3),
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
