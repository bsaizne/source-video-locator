"""三条「纯数据判负/验收」结论的补读图复核（2026-09-30，交接铁律立后第一批）。

对象 = 历史复核台账里未做读图的三条：
  A. 续28 ordered_search 判负 —— 读它**顺序性独家回退**的 4 条（p03 / t3r05 / t3r13 / t3r29）：
     每行四格 ED | 基线截等长落位 | full 臂落位 | GT 窗，确认"锚点把合法复用段拖进后窗"是真回退
     还是 GT 窗侧问题（若后者，判负强度被高估）。
  B. 索引密度 2fps 探针判负 —— 读它生产严格的 4 项翻转（up p14/p30、down p08/p34）：
     每行四格 ED | 1fps 落位 | 2fps 落位 | GT 窗。
  C. 续27 多原片合并验收 —— 读**拼接点两侧**：merged@t vs original@t（t = join±1/±4s），
     确认 copy 合并没有重复/错位/黑帧（merged 时长比原片 +3.42s，必须查清这 3.4s 落在哪）。

零 runtime / 零 GT 改动。产物 `work/retro_review_visual/`。

Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/review_retro_three.py
"""
from __future__ import annotations

import io
import contextlib
import json
import os
import sys
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", (r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
                                        r"\static_ffmpeg\bin\win32\ffprobe.exe"))
sys.path.insert(0, str(BENCH / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

from diagnostics.contact_sheet import compose_sheet        # noqa: E402
from diagnostics.frame_sampler import ffmpeg_frame, fmt_ts  # noqa: E402
from measure_shot_recall import evaluate                    # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OUT = BENCH / "work" / "retro_review_visual"
GT_OF = {"2mkv": "datasets/real/ground_truth_v4.json",
         "test1": "datasets/real/ground_truth_test1.json",
         "test2": "datasets/real/ground_truth_test2.json",
         "test3": "datasets/real/ground_truth_test3.json"}
MERGED = (Path(os.environ["LOCALAPPDATA"]) / "SourceVideoLocator" / "merged"
          / "merged_2_1f8777435eff_copy.mkv")
JOIN = 3837.041          # part1 时长 = 合并时间轴上的拼接点


def _cell(video, t, cap, tag):
    p = OUT / "frames" / f"{tag}.png"
    try:
        ffmpeg_frame(video, max(0.0, float(t)), p)
        return (str(p), [cap, fmt_ts(t)])
    except Exception:
        return None


def _span_of(batch, gt_row, gt):
    """该 GT 行编辑窗对应的段主 span（取编辑侧重叠最大的段）。"""
    pos = next(p for p in gt["positives"] if p["id"] == gt_row)
    e0, e1 = pos["edited"]
    best, bo = None, 0.0
    for r in batch:
        re0, re1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
        ov = min(e1, re1) - max(e0, re0)
        if ov > bo:
            bo, best = ov, (r["original"]["candidate_start"], r["original"]["candidate_end"])
    return best, pos


def main() -> int:
    (OUT / "frames").mkdir(parents=True, exist_ok=True)

    # ---------- A: ordered_search 顺序性独家回退 4 条 ----------
    rows = []
    for case, rid in [("2mkv", "p03"), ("test3", "t3r05"), ("test3", "t3r13"),
                      ("test3", "t3r29")]:
        gt = json.loads((BENCH / GT_OF[case]).read_text(encoding="utf-8"))
        base_raw = json.loads((BENCH / f"work/fastglobal_default_{case}.results.json")
                              .read_text(encoding="utf-8"))
        full_raw = json.loads((BENCH / f"work/ordered_search_{case}_full.results.json")
                              .read_text(encoding="utf-8"))
        (b0, b1), _ = _span_of(base_raw["results"], rid, gt)
        (f0, f1), _ = _span_of(full_raw["results"], rid, gt)
        p = next(x for x in gt["positives"] if x["id"] == rid)
        e0, e1, o0, o1 = p["edited"][0], p["edited"][1], p["original"][0], p["original"][1]
        src, ed = Path(base_raw["original_video"]), Path(base_raw["edited_video"])
        rows.append([
            _cell(ed, (e0 + e1) / 2, f"{rid} ED", f"A_{rid}_ed"),
            _cell(src, (b0 + b1) / 2, f"BASE {b0:.0f}-{b1:.0f}", f"A_{rid}_base"),
            _cell(src, (f0 + f1) / 2, f"FULL {f0:.0f}-{f1:.0f}", f"A_{rid}_full"),
            _cell(src, (o0 + o1) / 2, f"GT {o0:.0f}-{o1:.0f}", f"A_{rid}_gt")])
    compose_sheet(rows, OUT / "A_ordered_search_regress.png",
                  "A ordered_search exclusive regressions: ED | BASE | FULL | GT")
    print("[A] A_ordered_search_regress.png (4 行)")

    # ---------- B: 密度探针 4 项翻转 ----------
    rows = []
    gt = json.loads((BENCH / GT_OF["2mkv"]).read_text(encoding="utf-8"))
    b1raw = json.loads((BENCH / "work/fastglobal_default_2mkv.results.json").read_text(encoding="utf-8"))
    b2raw = json.loads((BENCH / "work/fpsprod_2.results.json").read_text(encoding="utf-8"))
    src, ed = Path(b1raw["original_video"]), Path(b1raw["edited_video"])
    for rid in ["p14", "p30", "p08", "p34"]:
        (a0, a1), _ = _span_of(b1raw["results"], rid, gt)
        (c0, c1), _ = _span_of(b2raw["results"], rid, gt)
        p = next(x for x in gt["positives"] if x["id"] == rid)
        e0, e1, o0, o1 = p["edited"][0], p["edited"][1], p["original"][0], p["original"][1]
        rows.append([
            _cell(ed, (e0 + e1) / 2, f"{rid} ED", f"B_{rid}_ed"),
            _cell(src, (a0 + a1) / 2, f"1fps {a0:.0f}-{a1:.0f}", f"B_{rid}_f1"),
            _cell(src, (c0 + c1) / 2, f"2fps {c0:.0f}-{c1:.0f}", f"B_{rid}_f2"),
            _cell(src, (o0 + o1) / 2, f"GT {o0:.0f}-{o1:.0f}", f"B_{rid}_gt")])
    compose_sheet(rows, OUT / "B_density_flips.png",
                  "B 2fps density flips: ED | 1fps | 2fps | GT")
    print("[B] B_density_flips.png (4 行)")

    # ---------- C: 合并拼接点两侧 ----------
    orig = Path(b1raw["original_video"])
    rows = []
    for dt in (-4.0, -1.0, 1.0, 4.0):
        t = JOIN + dt
        rows.append([
            _cell(MERGED, t, f"MERGED join%+0.0fs" % dt, f"C_m{dt:+.0f}"),
            _cell(orig, t, f"ORIG   t%+0.0fs" % dt, f"C_o{dt:+.0f}")])
    rows.append([
        _cell(MERGED, JOIN - 0.1, "MERGED join-0.1", "C_m_pre"),
        _cell(MERGED, JOIN + 0.1, "MERGED join+0.1", "C_m_post"),
        _cell(orig, JOIN - 0.1, "ORIG join-0.1", "C_o_pre"),
        _cell(orig, JOIN + 0.1, "ORIG join+0.1", "C_o_post")])
    compose_sheet(rows, OUT / "C_merge_join.png",
                  "C merged-vs-original around join: MERGED | ORIG (same t)")
    print("[C] C_merge_join.png (5 行)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
