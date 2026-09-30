# -*- coding: utf-8 -*-
"""诊断：6 条「单镜段/跨景」口袋行，我们输给竞品的机制是什么（2026-09-30）。

背景：6 行 GT 真时刻全在我方检索 top-20（t1r14c r1 / t2r06c r2 / p30 r3 / t3r02c r4 /
p34 r7 / p20 r8）⇒ 候选层有答案，决策层选错。本探针回答两个问题：

  Q1 单帧 CLS 能否分辨？—— ED 帧与我方落位帧 vs GT 窗帧的余弦差（差 ≈0 ⇒ 单帧信号盲）。
  Q2 序列投票能否分辨（竞品机制）？—— 对全片 1s 网格做逐镜偏移投票
     score(δ) = mean_i sim(ED帧i, 源帧@et_i+δ)，比较 score(δ_GT) / score(δ_OURS) /
     score(δ_竞品) 与全局 argmax。若投票峰在 GT ⇒ 信息在我方指纹里就有、只是决策层没用；
     若峰不在 ⇒ 1fps CLS 指纹本身分不开（真上限）。

零 runtime / 零 GT。产物 work/competitor_gap_diag.json。
Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_competitor_gap_diag.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", (r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
                                        r"\static_ffmpeg\bin\win32\ffprobe.exe"))
sys.path.insert(0, str(BENCH / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

import numpy as np  # noqa: E402

from app.locator_service import SourceLocatorService  # noqa: E402
from device.directml_backend import DirectMLBackend   # noqa: E402
from infrastructure.config import load_config          # noqa: E402
from media.ffmpeg import FFmpegIO                      # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

POCKETS = BENCH / "work" / "combo_pocket_retest_gt130" / "index.json"
ROWS = [("2mkv", "p20"), ("2mkv", "p30"), ("2mkv", "p34"), ("test1", "t1r14c"),
        ("test2", "t2r06c"), ("test3", "t3r02c")]
OURS = {"2mkv": "work/fastglobal_default_2mkv.results.json",
        "test1": "work/fastglobal_default_test1.results.json",
        "test2": "work/fastglobal_default_test2.results.json",
        "test3": "work/fastglobal_default_test3.results.json"}
ED_FPS, ED_MAX = 3.0, 15


def main() -> int:
    svc = SourceLocatorService(config=load_config())
    assert isinstance(svc.backend, DirectMLBackend), \
        f"必须 DirectMLBackend, 实际 {type(svc.backend).__name__}"
    print("BACKEND_SELECTED type=%s" % type(svc.backend).__name__, flush=True)
    fio = FFmpegIO(Path(os.environ["MEDIA_FFMPEG"]), Path(os.environ["MEDIA_FFPROBE"]))
    pockets = {(x["case"], x["id"]): x for x in
               json.loads(POCKETS.read_text(encoding="utf-8"))}

    out = []
    bundles = {}
    for case, pid in ROWS:
        pk = pockets[(case, pid)]
        e0, e1 = pk["gt_ed"]
        o0, o1 = pk["gt_og"]
        ours = pk["our_main_span"]
        comp = pk["proxy_span"]
        if case not in bundles:
            raw = json.loads((BENCH / OURS[case]).read_text(encoding="utf-8"))
            bundles[case] = (svc.store.load_index(Path(raw["original_video"])),
                             Path(raw["edited_video"]))
        b, ed = bundles[case]
        dur = e1 - e0
        n = max(3, min(ED_MAX, int(dur * ED_FPS)))
        ets = [e0 + dur * (i + 0.5) / n for i in range(n)]
        embs = []
        for et in ets:
            v = svc.backend.embed_frames([fio.grab_frame(ed, et)])[0]
            embs.append(v / max(1e-8, float(np.linalg.norm(v))))
        S = np.stack(embs) @ b.features.T                   # n_frames × N

        def vote_score(delta: float) -> float:
            """ED 帧序列在偏移 δ 下的平均对位相似度（1fps 索引最近邻）。"""
            vals = []
            for i, et in enumerate(ets):
                tgt = et + delta
                j = int(np.argmin(np.abs(b.times - tgt)))
                vals.append(float(S[i, j]))
            return float(np.mean(vals))

        # δ 网格：全片（1s 步长，索引 1fps 粒度）
        grid = np.arange(0.0, float(b.times[-1]), 1.0)
        scores = np.array([vote_score(d) for d in grid])
        k_best = int(np.argmax(scores))
        d_gt = (o0 + o1) / 2 - (e0 + e1) / 2
        d_ours = (ours[0] + ours[1]) / 2 - (e0 + e1) / 2 if ours else None
        d_comp = (comp[0] + comp[1]) / 2 - (e0 + e1) / 2
        # 排名：δ_GT / δ_ours / δ_comp 在网格里的名次
        rank = lambda d: int(np.sum(scores > vote_score(d))) + 1
        # 单帧分辨力：GT 窗帧 vs 我方落位帧 与各 ED 帧的平均余弦
        near = lambda t: int(np.argmin(np.abs(b.times - t)))
        sim_gt = float(np.mean([S[i, near(o0 + (o1 - o0) * (i + 0.5) / n)]
                                for i in range(n)]))
        sim_ours = (float(np.mean([S[i, near(ours[0] + (ours[1] - ours[0]) * (i + 0.5) / n)]
                                   for i in range(n)])) if ours else None)
        row = {"case": case, "id": pid,
               "gt_og": [o0, o1], "our_main": ours, "comp_span": comp,
               "vote": {"delta_best": round(float(grid[k_best]), 1),
                        "score_best": round(float(scores[k_best]), 4),
                        "score_gt": round(vote_score(d_gt), 4),
                        "score_ours": round(vote_score(d_ours), 4) if d_ours is not None else None,
                        "score_comp": round(vote_score(d_comp), 4),
                        "rank_gt_of_%d" % len(grid): rank(d_gt),
                        "rank_ours": rank(d_ours) if d_ours is not None else None,
                        "rank_comp": rank(d_comp)},
               "single_frame": {"sim_gt": round(sim_gt, 4),
                                "sim_ours": round(sim_ours, 4) if sim_ours is not None else None,
                                "gap_ours_minus_gt": (round(sim_ours - sim_gt, 4)
                                                      if sim_ours is not None else None)},
               "vote_prefers": ("GT" if rank(d_gt) <= rank(d_ours or 1)
                                else "OURS" if d_ours else "GT")}
        out.append(row)
        v = row["vote"]
        print("[%-5s %-7s] 投票峰 δ=%.0f (%.4f) | score GT=%.4f(rank %d) OURS=%.4f(rank %s) "
              "COMP=%.4f | 单帧 gap( ours-GT )=%s | 偏好=%s" % (
                  case, pid, v["delta_best"], v["score_best"], v["score_gt"],
                  v["rank_gt_of_%d" % len(grid)], v["score_ours"],
                  v["rank_ours"], v["score_comp"],
                  row["single_frame"]["gap_ours_minus_gt"], row["vote_prefers"]), flush=True)
    (BENCH / "work" / "competitor_gap_diag.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("产物: work/competitor_gap_diag.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
