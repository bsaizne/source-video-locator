"""18 条 GT 复核工单的自动判别（2026-09-30 续32，交接铁律第一批补复核的第二件）。

背景：续31 补三 读图裁决出 18 段「ED 帧与我方落位匹配、与 GT 原片窗不匹配」（④ 桶），
但④有两种解释：(a) GT 真标错；(b) 同一镜头在原片出现两次（解说复用），GT 选了另一处。
本脚本用**生产同款检索**自动区分，不需要人工逐帧：

  ED 中帧 → 生产 DINOv2 CLS（DirectML 硬断言）→ 原片 1fps 索引 top-20
  - OURS 窗内行在 top-20 且 GT 窗内行不在   ⇒ **GT 疑错**（ED 的同镜头在我方落点）
  - 两者都在 top-20                          ⇒ **同源重复**（镜头两处，GT 选了他处；我方也对）
  - 两者都不在                               ⇒ **工单无效**（ED 帧属插入/变换镜头，索引无同镜头）
  - 只有 GT 在、OURS 不在                    ⇒ **推翻读图**（我方落点才是错的）

零 runtime / 零 GT 改动。产物 `work/gt_tickets_retrieval.json`。

Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_gt_tickets_retrieval.py
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
sys.path.insert(0, str(BENCH / "mvp" / "src"))

import numpy as np  # noqa: E402

from app.locator_service import SourceLocatorService  # noqa: E402
from device.directml_backend import DirectMLBackend   # noqa: E402
from infrastructure.config import load_config          # noqa: E402
from media.ffmpeg import FFmpegIO                     # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

TICKETS = BENCH / "work" / "highwrong_visual" / "GT_REVIEW_TICKETS.json"
OUT = BENCH / "work" / "gt_tickets_retrieval.json"
TOPK = 20
WIN_PAD = 1.0          # 窗两侧各放 1s 容差（索引 1fps）
SRC_OF_CASE = {"2mkv": "work/fastglobal_default_2mkv.results.json",
               "test1": "work/fastglobal_default_test1.results.json",
               "test2": "work/fastglobal_default_test2.results.json",
               "test3": "work/fastglobal_default_test3.results.json"}


def _rank_in_window(times: np.ndarray, pos_of_row: dict,
                    w0: float, w1: float) -> int | None:
    """top-20 里落在 [w0-pad, w1+pad] 的行的最小名次；不在 top-20 即视为未召回。"""
    best = None
    for row, k in pos_of_row.items():
        t = float(times[row])
        if w0 - WIN_PAD <= t <= w1 + WIN_PAD:
            if best is None or k + 1 < best:
                best = k + 1
    return best


def main() -> int:
    tickets = json.loads(TICKETS.read_text(encoding="utf-8"))
    svc = SourceLocatorService(config=load_config())
    assert isinstance(svc.backend, DirectMLBackend), \
        f"必须 DirectMLBackend, 实际 {type(svc.backend).__name__}"
    print("BACKEND_SELECTED type=%s" % type(svc.backend).__name__, flush=True)
    io = FFmpegIO(Path(os.environ["MEDIA_FFMPEG"]), Path(os.environ["MEDIA_FFPROBE"]))

    bundles, paths = {}, {}
    rows_out = []
    for tk in tickets:
        case = tk["case"]
        if case not in bundles:
            raw = json.loads((BENCH / SRC_OF_CASE[case]).read_text(encoding="utf-8"))
            bundles[case] = svc.store.load_index(Path(raw["original_video"]))
            paths[case] = (Path(raw["original_video"]), Path(raw["edited_video"]))
        b = bundles[case]
        src, ed = paths[case]
        e0, e1 = tk["ed"]
        o0, o1 = tk["gt_og"]
        a0, a1 = tk["ours"]
        frame = io.grab_frame(ed, (e0 + e1) / 2.0)
        emb = svc.backend.embed_frames([frame])[0]
        emb = emb / max(1e-8, float(np.linalg.norm(emb)))
        cos = b.features @ emb
        order = np.argsort(-cos)
        pos_of_row = {int(r): k for k, r in enumerate(order[:TOPK])}
        gt_rank = _rank_in_window(b.times, pos_of_row, o0, o1)
        our_rank = _rank_in_window(b.times, pos_of_row, a0, a1)
        top1_t = float(b.times[int(order[0])])
        if our_rank is not None and gt_rank is None:
            verdict = "GT 疑错"
        elif our_rank is not None and gt_rank is not None:
            verdict = "同源重复"
        elif our_rank is None and gt_rank is not None:
            verdict = "推翻读图(我方落点才错)"
        else:
            verdict = "工单无效(ED 帧无同镜头)"
        rows_out.append({**tk, "top1_src_t": round(top1_t, 1),
                         "gt_rank_top20": gt_rank, "ours_rank_top20": our_rank,
                         "verdict": verdict})
        print("%-6s %-8s top1=%7.1fs  GT窗rank=%-4s OURS窗rank=%-4s => %s" % (
            case, tk["gt_row"], top1_t, gt_rank, our_rank, verdict), flush=True)

    from collections import Counter
    c = Counter(r["verdict"] for r in rows_out)
    print("\n裁决分布: %s" % dict(c))
    OUT.write_text(json.dumps(rows_out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("产物: %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
