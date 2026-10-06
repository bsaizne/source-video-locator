# -*- coding: utf-8 -*-
"""stable 排序零差异回归（2026-10-06 续58 CI 修复的生产不变性证明）。

变更 = `_clusters`/L2 宽扫的 `np.argsort` 加 `kind="stable"`（跨平台平局确定性，
macOS CI 5 失败根因修复）。真实嵌入 sims 为连续浮点 ⇒ 精确平局概率为零 ⇒ 预期四片
**逐字节零差异**。对照 = `work/defaults_flip_ab/<case>/on.results.json`（同代码态
默认旋钮臂；本变更不改任何旋钮/阈值/采样）。

Run: D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_stable_sort_regress.py [--case test1]
输出: work/stable_sort_regress/<case>.results.json + summary.json
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
os.environ.setdefault("SVL_DATA_DIR", r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", (r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
                                        r"\static_ffmpeg\bin\win32\ffprobe.exe"))
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.locator_service import SourceLocatorService  # noqa: E402
from device.directml_backend import DirectMLBackend  # noqa: E402
from infrastructure.config import load_config  # noqa: E402
from rerun_fast_global import CASES, _Progress  # noqa: E402

OUT = BENCH / "work" / "stable_sort_regress"


def strip(data: dict) -> dict:
    d = copy.deepcopy(data)
    d.pop("result_id", None)
    for r in d.get("results", []):
        r.pop("result_id", None)
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default=None, choices=sorted(CASES))
    args = ap.parse_args()
    cases = [args.case] if args.case else list(CASES)
    OUT.mkdir(parents=True, exist_ok=True)
    srv = SourceLocatorService(config=load_config())
    assert isinstance(srv.backend, DirectMLBackend), \
        "必须 DirectMLBackend, 实际 %s" % type(srv.backend).__name__
    summary = {}
    for case in cases:
        paths = CASES[case]
        print("[stable %s] defaults-only BACKEND=%s" % (case, type(srv.backend).__name__),
              flush=True)
        t0 = time.monotonic()
        batch = srv.locate(paths["edited"], paths["original"], on_progress=_Progress())
        wall = round(time.monotonic() - t0, 1)
        out_p = OUT / ("%s.results.json" % case)
        out_p.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1),
                         encoding="utf-8")
        ref_p = BENCH / "work" / "defaults_flip_ab" / case / "on.results.json"
        s_new = strip(json.loads(out_p.read_text(encoding="utf-8")))
        s_ref = strip(json.loads(ref_p.read_text(encoding="utf-8")))
        identical = s_ref == s_new
        n_flip = 0
        if not identical:
            for i, (a, b) in enumerate(zip(s_ref.get("results", []), s_new.get("results", []))):
                if a != b:
                    n_flip += 1
                    print("  [DIFF] %s row %d" % (case, i), flush=True)
        summary[case] = {"wall_s": wall, "strip_identical": identical, "n_diff_rows": n_flip}
        print("SUMMARY[stable %s] wall=%.1fs identical=%s diffs=%d"
              % (case, wall, identical, n_flip), flush=True)
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    print("ALL_DONE all_identical=%s" % all(v["strip_identical"] for v in summary.values()),
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
