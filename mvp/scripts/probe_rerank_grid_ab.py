# -*- coding: utf-8 -*-
"""主循环重排窗网格抽取 A/B（2026-10-06 续55 下一刀）。

唯一变量 = ``pipeline.rerank_grid_grab``（默认 False）＝ locate 主循环里两处源片重排窗
抓帧改走 grab_grid 网格抽取：① patch v2 近场池（±30s@4s 均匀网格，other 桶主力）
② 字牌锚定源窗（每窗 4 个均匀点）。off/on **同脚本紧邻双臂**（跨 run 方差 ±18%，纪律
＝提速数字只认同脚本双臂）。

判据：① strip(result_id) 后**逐字段 0 差异**（网格 = 同帧契约，`%.6f` 修复后 micro
1200/1200 逐字节同帧）② 墙钟下降（other 桶 294.4s=22%，4s 步长下管道量 ÷~100）。

用法: D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_rerank_grid_ab.py [--case test2|test3|2mkv]
输出: work/rerank_grid_ab/{off,on}.results.json + ab_summary.json
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

OUT = BENCH / "work" / "rerank_grid_ab"
CASES = {
    "test1": (r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv"),
    "test2": (r"D:\ProjectXIXI\test2\test2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mkv"),
    "test3": (r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mkv"),
    "2mkv": (r"D:\ProjectXIXI\2mkv\1.mp4", r"D:\ProjectXIXI\2mkv\2.mkv"),
}


def strip(data: dict) -> dict:
    d = copy.deepcopy(data)
    d.pop("result_id", None)
    for r in d.get("results", []):
        r.pop("result_id", None)
    return d


def run_arm(knob: bool, edited: str, orig: str, out_p: Path) -> float:
    cfg = load_config()
    cfg.pipeline.rerank_grid_grab = knob
    srv = LS.SourceLocatorService(config=cfg)
    assert isinstance(srv.backend, DirectMLBackend), \
        "必须 DirectMLBackend, 实际 %s" % type(srv.backend).__name__
    print("[%s] BACKEND=%s rerank_grid_grab=%s grab_grid_decode=%s grab_window_decode=%s"
          % ("on" if knob else "off", type(srv.backend).__name__, knob,
             cfg.pipeline.grab_grid_decode, cfg.pipeline.grab_window_decode), flush=True)
    t0 = time.monotonic()
    batch = srv.locate(edited, orig)
    wall = round(time.monotonic() - t0, 1)
    out_p.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print("[%s] wall=%.1fs segments=%d" % ("on" if knob else "off", wall,
                                           len(batch.results)), flush=True)
    return wall


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="test1", choices=sorted(CASES))
    args = ap.parse_args()
    edited, orig = CASES[args.case]
    OUT.mkdir(parents=True, exist_ok=True)

    off_wall = run_arm(False, edited, orig, OUT / "off.results.json")
    on_wall = run_arm(True, edited, orig, OUT / "on.results.json")

    s_off = strip(json.loads((OUT / "off.results.json").read_text(encoding="utf-8")))
    s_on = strip(json.loads((OUT / "on.results.json").read_text(encoding="utf-8")))
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
    summary = {"case": args.case, "knob": "rerank_grid_grab",
               "off": {"wall_s": off_wall, "results": str(OUT / "off.results.json")},
               "on": {"wall_s": on_wall, "results": str(OUT / "on.results.json")},
               "strip_identical": identical, "n_diff_blocks": n_diff,
               "speedup": round(off_wall / max(on_wall, 1e-9), 3),
               "created": time.strftime("%Y-%m-%d %H:%M:%S")}
    (OUT / "ab_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    print("SUMMARY %s" % json.dumps({k: summary[k] for k in
                                     ("case", "strip_identical", "n_diff_blocks", "speedup",
                                      "off", "on")}, ensure_ascii=False), flush=True)
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
