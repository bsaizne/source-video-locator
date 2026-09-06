"""多案例批跑(GT v3 时代泛化验证):对 D:/ProjectXIXI 的 test1-4 逐案例跑完整管线。

每案例导出 results 到 mvp/benchmark/user_case/cases/<case>_results.json,供逐镜头审计与
多模态裁决。运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/eval_cases.py [case ...]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "src"))

from app import SourceLocatorService
from infrastructure.config import load_config
from media.ffmpeg import FFmpegIO

FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
APP_INDEX_ROOT = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index")
OUT = BENCH / "mvp" / "benchmark" / "user_case" / "cases"

CASES = {
    "test1": (Path("D:/ProjectXIXI/test1/test1-ed.mp4"), Path("D:/ProjectXIXI/test1/test1-om.mkv")),
    "test2": (Path("D:/ProjectXIXI/test2/tset2-ed.mp4"), Path("D:/ProjectXIXI/test2/test2-om.mp4")),
    "test3": (Path("D:/ProjectXIXI/test3/test3-ed.mp4"), Path("D:/ProjectXIXI/test3/test3-om.mp4")),
    "test4": (Path("D:/ProjectXIXI/test4/test4-ed.mp4"), Path("D:/ProjectXIXI/test4/test4-om.mkv")),
}


def main() -> int:
    only = set(sys.argv[1:])
    OUT.mkdir(parents=True, exist_ok=True)
    import os
    # 可移植:旧机器硬编码路径存在才用,否则走默认解析(本机 %LOCALAPPDATA% 已带 DML 资产)
    index_root = APP_INDEX_ROOT if APP_INDEX_ROOT.exists() else None
    dml_model = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/models/"
                     "dinov2_cls_384/dinov2_cls_384.onnx")
    if dml_model.exists():
        os.environ["SVL_DML_MODEL"] = str(dml_model)
    cfg = load_config()
    cfg.pipeline.index_sampling_fps = 1.0
    svc = SourceLocatorService(config=cfg, ffmpeg=FFmpegIO(FFMPEG, FFPROBE),
                               index_root=index_root, export_root=OUT)
    for case, (ed, om) in CASES.items():
        if only and case not in only:
            continue
        print(f"\n===== {case} =====", flush=True)
        t0 = time.monotonic()
        try:
            batch = svc.locate(ed, om)
        except Exception as exc:
            print(f"{case} FAILED: {exc}", flush=True)
            continue
        svc.export_results(batch, out_dir=OUT, filename=f"{case}_results.json")
        from collections import Counter
        conf = Counter(r.confidence.level.value for r in batch.results)
        nis = sum(1 for r in batch.results if r.not_in_source)
        print(f"{case}: segments={len(batch.results)} conf={dict(conf)} "
              f"not_in_source={nis} elapsed={time.monotonic() - t0:.0f}s", flush=True)
    print("ALL CASES DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
