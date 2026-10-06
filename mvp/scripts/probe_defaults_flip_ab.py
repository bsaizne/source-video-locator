# -*- coding: utf-8 -*-
"""三旋钮翻默认前置：联合双臂四片回归（2026-10-06 续57 口令「翻」）。

唯一差量 = 三个待翻旋钮**联合**打开：
  off = 现役默认（patch_refine_grid=False · rerank_grid_grab=False · cluster_workers=1）
  on  = patch_refine_grid=True  · rerank_grid_grab=True  · cluster_workers=4

三旋钮各自已在 test1 上做过「同脚本紧邻双臂」零语义验证（1.068× / 1.132× / 1.071×，
strip 逐字节 0 差异）；本探针补**三片联合**证据（单片形状不能外推成套结论——续55 教训），
加 test1 联合 on 臂对照今晚 off 臂 ⇒ 四片零语义。任何联合差异将逐旋钮拆臂归因。

用法: D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_defaults_flip_ab.py [--cases test1,test2,test3,2mkv]
输出: work/defaults_flip_ab/<case>/{off,on}.results.json + summary.json
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

OUT = BENCH / "work" / "defaults_flip_ab"
CASES = {
    "test1": (r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv"),
    # ⚠️ 真实文件名：test2 剪辑片就是拼错的 "tset2-ed.mp4"；2mkv 在 D:\video\
    "test2": (r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4"),
    "test3": (r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4"),
    "2mkv": (r"D:\video\1.mp4", r"D:\video\2.mkv"),
}
# test1 off 臂复用今晚 rerank_grid_ab off（同代码态 + 同默认旋钮，已 strip 验证过 on 差异）
REUSE_OFF = {"test1": BENCH / "work" / "rerank_grid_ab" / "off.results.json"}


def strip(data: dict) -> dict:
    d = copy.deepcopy(data)
    d.pop("result_id", None)
    for r in d.get("results", []):
        r.pop("result_id", None)
    return d


def run_arm(knobs_on: bool, edited: str, orig: str, out_p: Path) -> float:
    cfg = load_config()
    if knobs_on:
        cfg.pipeline.patch_refine_grid = True
        cfg.pipeline.rerank_grid_grab = True
        cfg.media.cluster_workers = 4
    srv = LS.SourceLocatorService(config=cfg)
    assert isinstance(srv.backend, DirectMLBackend), \
        "必须 DirectMLBackend, 实际 %s" % type(srv.backend).__name__
    print("[%s] BACKEND=%s patch_refine_grid=%s rerank_grid_grab=%s cluster_workers=%s"
          % ("on " if knobs_on else "off", type(srv.backend).__name__,
             cfg.pipeline.patch_refine_grid, cfg.pipeline.rerank_grid_grab,
             cfg.media.cluster_workers), flush=True)
    t0 = time.monotonic()
    batch = srv.locate(edited, orig)
    wall = round(time.monotonic() - t0, 1)
    out_p.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print("[%s] wall=%.1fs segments=%d" % ("on " if knobs_on else "off", wall,
                                           len(batch.results)), flush=True)
    return wall


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="test1,test2,test3,2mkv")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {}
    for case in args.cases.split(","):
        case = case.strip()
        edited, orig = CASES[case]
        cdir = OUT / case
        cdir.mkdir(parents=True, exist_ok=True)
        off_p = cdir / "off.results.json"
        reused = False
        if case in REUSE_OFF and REUSE_OFF[case].exists():
            import shutil
            shutil.copyfile(REUSE_OFF[case], off_p)
            off_wall = -1.0
            reused = True
            print("[%s][off] 复用 %s" % (case, REUSE_OFF[case].name), flush=True)
        else:
            off_wall = run_arm(False, edited, orig, off_p)
        on_wall = run_arm(True, edited, orig, cdir / "on.results.json")
        s_off = strip(json.loads(off_p.read_text(encoding="utf-8")))
        s_on = strip(json.loads((cdir / "on.results.json").read_text(encoding="utf-8")))
        identical = s_off == s_on
        n_diff = 0
        if not identical:
            for k in sorted(set(s_off) | set(s_on)):
                if s_off.get(k) != s_on.get(k):
                    if k == "results":
                        for i, (a, b) in enumerate(zip(s_off.get(k, []), s_on.get(k, []))):
                            if a != b:
                                n_diff += 1
                                print("  [DIFF] %s row %d edited=%s"
                                      % (case, i, a.get("edited_segment")), flush=True)
                    else:
                        n_diff += 1
                        print("  [DIFF] %s %s" % (case, k), flush=True)
        summary[case] = {"strip_identical": identical, "n_diff_blocks": n_diff,
                         "off_reused": reused, "off_wall_s": off_wall, "on_wall_s": on_wall,
                         "speedup": round(off_wall / max(on_wall, 1e-9), 3) if off_wall > 0 else None}
        print("SUMMARY[%s] %s" % (case, json.dumps(summary[case], ensure_ascii=False)),
              flush=True)
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    print("ALL_DONE all_identical=%s" % all(v["strip_identical"] for v in summary.values()),
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
