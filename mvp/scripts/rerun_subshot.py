# -*- coding: utf-8 -*-
"""x"""
import json, os, sys, time
import numpy as np
from pathlib import Path
os.environ["SVL_DATA_DIR"] = "D:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data"
os.environ["SVL_DML_MODEL"] = "C:/Users/Bsaizne/AppData/Local/SourceVideoLocator/models/dinov2_cls_384/dinov2_cls_384.onnx"
os.environ["MEDIA_FFMPEG"] = "D:/claudework/benchmark/tools/ffmpeg.exe"
os.environ["MEDIA_FFPROBE"] = "D:/claudework/video-dedup-tool/.venv/Lib/site-packages/static_ffmpeg/bin/win32/ffprobe.exe"
BENCH = Path("D:/claudework/benchmark")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))
from app.locator_service import SourceLocatorService
from infrastructure.config import load_config
from engine.segment import ShotSegment
from domain import TimeSpan

CASES = {
  "2mkv": {"edited": "D:/video/1.mp4", "original": "D:/video/2.mkv"},
  "test1": {"edited": "D:/ProjectXIXI/test1/test1-ed.mp4", "original": "D:/ProjectXIXI/test1/test1-om.mkv"},
  "test2": {"edited": "D:/ProjectXIXI/test2/tset2-ed.mp4", "original": "D:/ProjectXIXI/test2/test2-om.mp4"},
  "test3": {"edited": "D:/ProjectXIXI/test3/test3-ed.mp4", "original": "D:/ProjectXIXI/test3/test3-om.mp4"},
}
class SubShotService(SourceLocatorService):
    def split_subshots(self, shots, thresh=0.5, min_sub=3):
        out = []
        for shot in shots:
            feats, times = shot.feats, shot.times
            if len(feats) < 6:
                out.append(shot); continue
            q = feats[:-1]/np.maximum(np.linalg.norm(feats[:-1],axis=1,keepdims=True),1e-8)
            r = feats[1:]/np.maximum(np.linalg.norm(feats[1:],axis=1,keepdims=True),1e-8)
            d = 1.0-np.sum(q*r,axis=1)
            cuts = [int(i+1) for i in range(len(d)) if d[i] > thresh]
            merged = []
            for c in cuts:
                if not merged or c-merged[-1] > 1: merged.append(c)
            if len(merged)+1 < min_sub:
                out.append(shot); continue
            bounds = [0] + merged + [len(feats)]
            for si in range(len(bounds)-1):
                a, b = bounds[si], bounds[si+1]
                if b-a < 1: continue
                out.append(ShotSegment(span=TimeSpan(float(times[a]), float(times[b-1])),
                                      feats=feats[a:b], times=times[a:b],
                                      card_ratio=shot.card_ratio))
        return out
    def locate(self, edited, original, **kw):
        from pathlib import Path as P
        edited = P(edited)
        self._ensure_session()
        bundle = self.build_original_index(original, **kw)
        shots = self.analyze_edited_video(edited, on_progress=kw.get("on_progress"), cancel_token=kw.get("cancel_token"))
        shots = self.split_subshots(shots)
        results = self._locate_features(shots, bundle, cfg=self.config.pipeline,
                                       on_progress=kw.get("on_progress"),
                                       cancel_token=kw.get("cancel_token"),
                                       edited=edited)
        from domain import ResultBatch
        return ResultBatch(original_video=str(bundle.meta.source_file),
                           edited_video=str(edited), results=results)
def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    cfg = load_config()
    srv = SubShotService(config=cfg)
    try:
        b = srv.backend
        print(f"BACKEND_SELECTED type={type(b).__name__} device={b.device_name()} dtype={b.device_type()}", flush=True)
    except Exception as e:
        print("BACKEND_SELECTED ERROR:", e, flush=True)
    for name, paths in CASES.items():
        if only and name != only: continue
        out = BENCH / "work" / f"rerun_{name}_subshot.results.json"
        print(f"\n=== {name} subshot ===", flush=True)
        t0 = time.monotonic()
        try:
            batch = srv.locate(paths["edited"], paths["original"])
            out.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
            n_high = sum(1 for r in batch.results if r.confidence.level.value == "HIGH")
            print(f"  {name}: {len(batch.results)} 段 HIGH={n_high} elapsed={time.monotonic()-t0:.1f}s", flush=True)
        except Exception as exc:
            import traceback; print(f"  {name} FAILED: {exc}", flush=True); traceback.print_exc()
    print("\nALL DONE", flush=True)
if __name__ == "__main__":
    main()
