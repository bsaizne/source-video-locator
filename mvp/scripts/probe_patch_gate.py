# -*- coding: utf-8 -*-
"""patch 召回 v2 门控设计探针: 池外案例 + 对照正确段, 采集门控候选信号(研究侧, 零 runtime)。

信号: patch_top1(位置/分) / patch分@主定位 / CLS_sim@top1 / CLS_sim@主定位 / 偏移
用途: 找到能同时满足 [救回 p14/p26, 不采纳 t1r02/t1r14d/t2r07c, 对照组零接触] 的门控规则。
"""
import json
import os
import sys
from pathlib import Path

os.environ["SVL_DATA_DIR"] = r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data"
os.environ["MEDIA_FFMPEG"] = r"D:\claudework\benchmark\tools\ffmpeg.exe"
os.environ["MEDIA_FFPROBE"] = r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe"
os.environ.setdefault("SVL_DML_MODEL", r"C:/Users/Bsaizne/AppData/Local/SourceVideoLocator/models/dinov2_cls_384/dinov2_cls_384.onnx")
BENCH = Path(r"D:\claudework\benchmark")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))

import numpy as np  # noqa: E402
from app.locator_service import SourceLocatorService  # noqa: E402
from engine.localization.patch_rerank import PatchReranker, patch_score, resolve_patch_onnx, resolve_weights  # noqa: E402
from infrastructure.config import load_config  # noqa: E402

FRAME_N = {"2mkv": 7668, "test1": 8221, "test2": 5051, "test3": 10177}
FILM_META = {
    "2mkv": (r"D:\video\1.mp4", r"D:\video\2.mkv"),
    "test1": (r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv"),
    "test2": (r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4"),
    "test3": (r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4"),
}
GT_FILE = {"2mkv": "ground_truth_v4.json", "test1": "ground_truth_test1.json",
           "test2": "ground_truth_test2.json", "test3": "ground_truth_test3.json"}

# 池外案例(film, gt_id)
POOL_MISS = [("2mkv", "p14"), ("2mkv", "p26"), ("test1", "t1r02"), ("test1", "t1r14d"),
             ("test2", "t2r05a"), ("test2", "t2r05b"), ("test2", "t2r07c")]
# 对照: 当前严格命中的 GT 条目
CONTROLS = [("2mkv", "p04"), ("2mkv", "p10"), ("2mkv", "p27"), ("2mkv", "p32"),
            ("test1", "t1r00"), ("test1", "t1r14a"), ("test1", "t1r27"),
            ("test2", "t2r00"), ("test2", "t2r06b"),
            ("test3", "t3r07"), ("test3", "t3r12"), ("test3", "t3r26")]


def main():
    cfg = load_config()
    srv = SourceLocatorService(config=cfg)
    rr = PatchReranker(resolve_weights(cfg.pipeline.patch_weights_path or None),
                       resolve_patch_onnx((cfg.pipeline.patch_onnx_model or "").strip() or None),
                       dml_device_id=cfg.device.dml_device_id)
    assert rr.ensure()
    print("patch device:", rr.device, flush=True)
    IDX = Path(os.environ["SVL_DATA_DIR"]) / "index"
    idx_by_film = {}
    for d in IDX.glob("*.idx"):
        try:
            f = np.load(d / "features.npy", mmap_mode="r")
            n = f.shape[0]
            if n in FRAME_N.values():
                idx_by_film[[k for k, v in FRAME_N.items() if v == n][0]] = (
                    np.asarray(f), np.load(d / "times.npy"))
        except Exception:
            continue

    def rep_times(a, b, n=3):
        return [round(a + (b - a) * (i + 0.5) / n, 2) for i in range(n)]

    def case_info(film, gid):
        gt = json.loads(Path("datasets/real", GT_FILE[film]).read_text(encoding="utf-8"))
        for p in gt["positives"]:
            if p["id"] == gid:
                return p
        raise KeyError(gid)

    def covering_main(film, p, res):
        e0, e1 = p["edited"]
        cands = [r for r in res
                 if min(e1, r["edited_segment"]["end"]) - max(e0, r["edited_segment"]["start"]) > 0]
        cands.sort(key=lambda r: -min(e1, r["edited_segment"]["end"]) + max(e0, r["edited_segment"]["start"]))
        r = cands[0]
        o = r["original"]
        return (o["candidate_start"] + o["candidate_end"]) / 2.0

    def measure(film, gid, use_uniform):
        p = case_info(film, gid)
        e0, e1 = p["edited"]; o0, o1 = p["original"]; om = (o0 + o1) / 2.0
        ed_vid, og_vid = FILM_META[film]
        res = json.loads(Path(f"work/rerun_{film}_perfopt.results.json").read_text(encoding="utf-8"))["results"]
        main_mid = covering_main(film, p, res)
        feats, times = idx_by_film[film]
        q_frames = [srv.ffmpeg.grab_frame(ed_vid, t) for t in rep_times(e0, e1)]
        q_patches = np.vstack([rr.frame_patches(f) for f in q_frames])
        q_cls_feats = srv.backend.embed_frames(q_frames)
        q_cls = q_cls_feats.mean(axis=0)
        q_cls /= max(float(np.linalg.norm(q_cls)), 1e-8)
        sims = feats @ q_cls
        top = set(int(i) for i in np.argsort(-sims)[:200])
        if use_uniform:
            top |= set(range(0, len(times), 20))
        # 保证主定位中点附近有池帧
        main_i = int(np.argmin(np.abs(times - main_mid)))
        top.add(main_i)
        gt_idx = set(int(i) for i in np.where((times >= o0 - 2.0) & (times <= o1 + 2.0))[0])
        pool = sorted(top)
        scored = []
        for i in pool:
            f = srv.ffmpeg.grab_frame(og_vid, float(times[i]))
            scored.append((patch_score(q_patches, rr.frame_patches(f)), i, float(times[i])))
        scored.sort(reverse=True)
        p_top1, i_top1, t_top1 = scored[0]
        p_main = next((s for s, i, t in scored if i == main_i), None)
        cls_top1 = float(sims[i_top1])
        cls_main = float(sims[main_i])
        in_gt = o0 - 2 <= t_top1 <= o1 + 2
        return {
            "id": gid, "gt_mid": round(om, 1), "main_mid": round(main_mid, 1),
            "top1_t": round(t_top1, 1), "top1_score": round(p_top1, 4),
            "patch_at_main": round(p_main, 4) if p_main is not None else None,
            "patch_margin": round(p_top1 - p_main, 4) if p_main is not None else None,
            "cls_at_top1": round(cls_top1, 4), "cls_at_main": round(cls_main, 4),
            "cls_margin": round(cls_top1 - cls_main, 4),
            "top1_offset": round(abs(t_top1 - main_mid), 1),
            "top1_in_gt": in_gt,
            "pool": len(pool),
        }

    print(f"{'case':10s}{'role':6s}{'top1_t':>8}{'main_mid':>9}{'off':>6}{'top1sc':>8}"
          f"{'patch@main':>11}{'p_margin':>9}{'cls@top1':>9}{'cls@main':>9}{'cls_mg':>8}{'in_gt':>6}", flush=True)
    for film, gid in POOL_MISS:
        m = measure(film, gid, use_uniform=True)
        m["id"] = gid
        print(f"{gid:10s}{'池外':6s}{m['top1_t']:>8}{m['main_mid']:>9}{m['top1_offset']:>6}"
              f"{m['top1_score']:>8}{m['patch_at_main']:>11}{m['patch_margin']:>9}"
              f"{m['cls_at_top1']:>9}{m['cls_at_main']:>9}{m['cls_margin']:>8}{str(m['top1_in_gt']):>6}", flush=True)
    for film, gid in CONTROLS:
        m = measure(film, gid, use_uniform=False)
        m["id"] = gid
        print(f"{gid:10s}{'对照':6s}{m['top1_t']:>8}{m['main_mid']:>9}{m['top1_offset']:>6}"
              f"{m['top1_score']:>8}{m['patch_at_main']:>11}{m['patch_margin']:>9}"
              f"{m['cls_at_top1']:>9}{m['cls_at_main']:>9}{m['cls_margin']:>8}{str(m['top1_in_gt']):>6}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
