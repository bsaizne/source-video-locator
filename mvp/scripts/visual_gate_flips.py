# -*- coding: utf-8 -*-
"""退化拒绝门翻转段的逐图复核出图（2026-09-28 续19, T1-1 验收第三层）。

纪律（用户 2026-09-28）：**GT 不是唯一复核标准**——被门判为"重复认领"而拒识的段
是否真的答错，必须看画面。每张图两行：上=编辑段（查询）帧，下=被拒的原片 span 帧。
两行同内容 ⇒ 该拒是误伤；两行不同内容 ⇒ 该拒有道理。

用法:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/visual_gate_flips.py [case]
产出: work/gate_flips_visual/<case>_s<idx>_flip.png + index.json
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

from diagnostics.contact_sheet import compose_sheet        # noqa: E402
from diagnostics.frame_sampler import ffmpeg_frame, fmt_ts, pick_reps  # noqa: E402

BASE_PATTERN = "work/rerun_{case}_perfopt.results.json"
GT_OF = {"2mkv": "datasets/real/ground_truth_v4.json",
         "test1": "datasets/real/ground_truth_test1.json",
         "test2": "datasets/real/ground_truth_test2.json",
         "test3": "datasets/real/ground_truth_test3.json"}
OUT = BENCH / "work" / "gate_flips_visual"
MAX_PER_CASE = 8


def _gt_for(gt: dict, e0: float, e1: float):
    """编辑窗重叠最多的 GT 正例（仅作画面参照，不作判据）。"""
    best, best_ov = None, 0.0
    for p in gt["positives"]:
        ov = max(0.0, min(e1, p["edited"][1]) - max(e0, p["edited"][0]))
        if ov > best_ov:
            best, best_ov = p, ov
    return best if best_ov > 0 else None


def _row(tmp: Path, tag: str, idx: int, video: Path, a: float, b: float, label: str):
    cells = []
    for j, t in enumerate(pick_reps(a, b, 3)):
        p = tmp / f"{tag}_{label}_s{idx}_{j}.png"
        try:
            ffmpeg_frame(video, t, p)
            cells.append((str(p), [f"{label} {fmt_ts(t)}"]))
        except Exception:
            cells.append(None)
    return cells


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / "_frames"
    tmp.mkdir(exist_ok=True)
    ab = json.loads((BENCH / "work" / "degradation_gate_ab.json").read_text(encoding="utf-8"))
    idx_p = OUT / "index.json"
    if only and idx_p.exists():   # 单片重跑只替换该片记录，不覆盖其它片
        index = [x for x in json.loads(idx_p.read_text(encoding="utf-8")) if x["case"] != only]
    else:
        index = []
    for case_row in ab["cases"]:
        case = case_row["case"]
        if only and case != only:
            continue
        base_p = BENCH / BASE_PATTERN.format(case=case)
        if not base_p.exists():
            print("[%s] missing %s" % (case, base_p))
            continue
        raw = json.loads(base_p.read_text(encoding="utf-8"))
        video, original = Path(raw["edited_video"]), Path(raw["original_video"])
        gt = json.loads((BENCH / GT_OF[case]).read_text(encoding="utf-8"))
        rejected = [tuple(x) for x in case_row["rejected"]][:MAX_PER_CASE]
        for idx, ratio in rejected:
            r = raw["results"][idx]
            ed = r["edited_segment"]
            sp = r["original"]
            rows = [_row(tmp, case, idx, video, ed["start"], ed["end"], "QUERY"),
                    _row(tmp, case, idx, original, sp["candidate_start"],
                         sp["candidate_end"], "REJECTED")]
            g = _gt_for(gt, ed["start"], ed["end"])
            if g:
                rows.append(_row(tmp, case, idx, original, g["original"][0],
                                 g["original"][1], "GT"))
            out_p = OUT / ("%s_s%02d_flip.png" % (case, idx))
            compose_sheet(rows, out_p,
                          title=("%s seg%d ed %.1f-%.1f -> REJECTED %.1f-%.1f dup=%.2f "
                                 "(GT %s)%s" % (case, idx + 1, ed["start"], ed["end"],
                                                sp["candidate_start"], sp["candidate_end"], ratio,
                                                r.get("confidence"),
                                                "  GTwin %.1f-%.1f" % (g["original"][0],
                                                                       g["original"][1])
                                                if g else "")))
            index.append({"case": case, "seg_index": idx, "dup_ratio": ratio,
                          "edited": [ed["start"], ed["end"]],
                          "rejected_span": [sp["candidate_start"], sp["candidate_end"]],
                          "gt_window": g["original"] if g else None,
                          "image": str(out_p)})
            print("[%s] seg%d dup=%.2f -> %s" % (case, idx + 1, ratio, out_p.name))
    (OUT / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False),
                                    encoding="utf-8")
    print("总计 %d 张 -> %s" % (len(index), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
