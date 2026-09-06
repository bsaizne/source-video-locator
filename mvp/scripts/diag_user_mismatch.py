"""诊断脚本 — 复现用户真实定位失败（D:\\video\\1.mp4 -> 2.mkv）。

Mirror 打包 App 的生产路径：
  - index_root = App 数据目录的数据索引目录（复用已建的 2.mkv 索引，避免 ~350s 重建）
  - device    = DirectML（AMD GPU），复用 App 的 ONNX 模型（SVL_DML_MODEL）
  - edited fps = 2.0（App 后端 config 默认）
  - 导出 ResultBatch + 每段 edited/original 区间 + confidence/reasons/montage/failure_reason

运行（venv python）:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/diag_user_mismatch.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

from app import SourceLocatorService
from media.ffmpeg import FFmpegIO

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


def main() -> int:
    os.environ["SVL_DML_MODEL"] = str(APP_MODEL)
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    svc = SourceLocatorService(ffmpeg=FFmpegIO(FFMPEG, FFPROBE),
                               index_root=APP_INDEX_ROOT, export_root=OUT)
    dev = svc.device_settings()
    print("device:", json.dumps(dev, ensure_ascii=False))

    def prog(evt):
        print(f"    [{evt.stage.value}] {evt.current}/{evt.total} {evt.message}".rstrip())

    print(f"=== locate edited={EDIT.name} original={ORIG.name} ===")
    t1 = time.monotonic()
    batch = svc.locate(EDIT, ORIG, on_progress=prog)
    t_locate = time.monotonic() - t1
    print(f"locate elapsed={t_locate:.1f}s")

    path = svc.export_results(batch, out_dir=OUT, filename="user_results.json")
    print("exported:", path)

    rows = []
    for i, r in enumerate(batch.results):
        rows.append({
            "idx": i,
            "edited": [round(r.edited.start, 3), round(r.edited.end, 3)],
            "original": [round(r.original.start, 3), round(r.original.end, 3)],
            "confidence": r.confidence.level.value if r.confidence else None,
            "score": round(r.confidence.score, 4) if r.confidence else None,
            "reasons": list(r.confidence.reasons) if r.confidence else [],
            "montage_flag": r.montage_flag,
            "failure_reason": r.failure_reason,
            "candidate_rank": r.candidate_rank,
            "alternatives": [[round(a.interval.start, 3), round(a.interval.end, 3),
                              a.confidence_level.value if a.confidence_level else None]
                             for a in r.alternatives],
        })
    with open(OUT / "summary.json", "w", encoding="utf-8") as f:
        json.dump({"device": dev, "locate_elapsed_s": round(t_locate, 1), "segments": rows},
                  f, ensure_ascii=False, indent=2)

    counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for r in rows:
        counts[r["confidence"]] = counts.get(r["confidence"], 0) + 1
    print(f"\n=== segments={len(rows)} {counts} unresolved="
          f"{sum(1 for r in rows if r['failure_reason'])} ===")
    for r in rows:
        print(f"  [{r['idx']:2}] edited=({r['edited'][0]:6.1f},{r['edited'][1]:6.1f}) "
              f"orig=({r['original'][0]:7.1f},{r['original'][1]:7.1f}) "
              f"{r['confidence']:6} score={r['score']} mont={r['montage_flag']} "
              f"rank={r['candidate_rank']} fail={r['failure_reason']}")
    print("  reasons:")
    for r in rows:
        print(f"    [{r['idx']:2}] {r['reasons']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
