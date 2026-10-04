# -*- coding: utf-8 -*-
"""L2 源片索引宽扫整条 locate A/B（2026-10-04 续52 接线验收）。

唯一变量 = pipeline.isc_l2_index_enabled（False=现役 v2 宽扫 / True=索引 matmul 粗排 +
top-5 ±4s 真帧精扫，索引 = work/isc_source_index/*.tp.isci.npz）。
off 臂复用当前代码 fresh 产物（grab_grid=True 时代，knob-off 与现役逐位同）；
on 臂跑完整 srv.locate()（DML 硬断言），strip(result_id) 逐字段比对 + 墙钟。

用法（venv 绝对路径 python，repo 根）:
  python mvp/scripts/probe_isc_l2_ab.py --case test1 [--force-on]
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

from app.locator_service import SourceLocatorService          # noqa: E402
from device.directml_backend import DirectMLBackend           # noqa: E402
from infrastructure.config import load_config                 # noqa: E402

OUT = BENCH / "work" / "isc_l2_ab"
IDX_DIR = BENCH / "work" / "isc_source_index"
CASES = {
    # case: (edited, orig, off 臂复用产物[当前代码 fresh，knob-off 逐位同现役])
    "2mkv": (r"D:\video\1.mp4", r"D:\video\2.mkv", OUT.parent / "isc_grid_ab" / "off_2mkv.results.json"),
    "test1": (r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv",
              OUT.parent / "isc_grid_ab" / "on_test1.results.json"),
    "test2": (r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4",
              OUT.parent / "isc_grid_ab" / "off_test2.results.json"),
    "test3": (r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4",
              OUT.parent / "isc_grid_ab" / "off_test3.results.json"),
}
VOLATILE = ("result_id",)


def strip(rows: list) -> list:
    return [{k: v for k, v in r.items() if k not in VOLATILE} for r in rows]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="test1", choices=sorted(CASES))
    ap.add_argument("--force", action="store_true", help="两臂都重跑")
    ap.add_argument("--force-on", action="store_true", help="只重跑 on 臂")
    ap.add_argument("--index-dir", default=None,
                    help="覆盖索引目录（缺省 = 入库目录 app_data/isc_index）")
    args = ap.parse_args()
    edited, orig, ref_off = CASES[args.case]
    OUT.mkdir(parents=True, exist_ok=True)
    rep = {"case": args.case, "edited": edited, "source": orig,
           "index": str(IDX_DIR / (Path(orig).stem + "@1.000fps.tp.isci.npz")), "arms": {}}

    for arm, l2_on in (("off", False), ("on", True)):
        res_p = OUT / ("%s_%s.results.json" % (arm, args.case))
        if arm == "off" and ref_off.exists() and not args.force:
            print("[off] 复用当前代码 fresh 批 %s" % ref_off.name, flush=True)
            rep["arms"]["off"] = {"wall_s": None, "results": str(ref_off), "reused": True,
                                  "note": "当前代码 fresh 批（knob-off 与现役逐位同；"
                                          "test2/test3 off 墙钟含 10-04 凌晨 GPU 争用）"}
            continue
        cfg = load_config()
        cfg.pipeline.isc_l2_index_enabled = bool(l2_on)
        if args.index_dir:
            cfg.pipeline.isc_l2_index_dir = args.index_dir   # 缺省 = 入库目录 data/isc_index
        srv = SourceLocatorService(config=cfg)
        assert isinstance(srv.backend, DirectMLBackend), \
            "必须 DirectMLBackend, 实际 %s" % type(srv.backend).__name__
        print("[%s] BACKEND=%s isc_l2_index_enabled=%s" % (arm, type(srv.backend).__name__, l2_on),
              flush=True)
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

    a = Path(rep["arms"]["off"]["results"])
    b = OUT / ("on_%s.results.json" % args.case)
    if a.exists() and b.exists():
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
