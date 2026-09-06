"""驱动 — 用硬化蒙太奇定位模块（MontageLocalizer）跑真实 12 段，产出 montage_localize.json。

验证模块在真实数据上复现 86% GT recall（确认重构无回归）。随后可调 research_gt_validate.py。

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/research_run_module.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))     # -> mvp/src
sys.path.insert(0, str(Path(__file__).resolve().parents[2]
                       / "mvp" / "benchmark" / "user_case" / "montage_research"))  # -> montage_research

from app import SourceLocatorService                  # noqa: E402
from media.ffmpeg import FFmpegIO                     # noqa: E402
from montage_localize import MontageLocalizer         # noqa: E402

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
EDIT = Path("D:/video/1.mp4")
ORIG = Path("D:/video/2.mkv")
APP_INDEX_ROOT = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index")
APP_MODEL = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/models/"
                 "dinov2_cls_384/dinov2_cls_384.onnx")
OUT = BENCH / "mvp" / "benchmark" / "user_case"
MRES = OUT / "montage_research"


def main() -> int:
    os.environ["SVL_DML_MODEL"] = str(APP_MODEL)
    svc = SourceLocatorService(ffmpeg=FFmpegIO(FFMPEG, FFPROBE),
                               index_root=APP_INDEX_ROOT, export_root=OUT)
    bundle = svc.build_original_index(ORIG)
    shots = svc.analyze_edited_video(EDIT)
    loc = MontageLocalizer()
    rows = []
    for idx, shot in enumerate(shots):
        r = loc.localize(shot.feats, shot.times, bundle)
        rows.append({
            "idx": idx,
            "edited": [round(shot.span.start, 2), round(shot.span.end, 2)],
            "mode": r.mode, "n_clusters": r.n_clusters,
            "dropped_weak": r.n_dropped_weak,
            "sub_spans": [{"edited_sub": s.edited_interval,
                           "edited_frames": s.edited_frames,
                           "cluster_frames": s.cluster_frames,
                           "span": list(s.original_span) if s.original_span else None,
                           "cover": s.cover, "best_sim": s.best_sim}
                          for s in r.spans],
        })
    MRES.mkdir(parents=True, exist_ok=True)
    (MRES / "montage_localize.json").write_text(
        json.dumps({"segments": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"module ran: {len(rows)} segments")
    return 0


if __name__ == "__main__":
    sys.exit(main())
