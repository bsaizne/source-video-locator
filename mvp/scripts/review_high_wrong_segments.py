"""HIGH 档「主答案不覆盖其对应 GT 行」36 段的逐条裁决出图（2026-09-29 续31 补三，清单 2 前置）。

清单 2（conf_v2 换饱和判据）的对象盘点发现：段级口径下 HIGH 档错率 46~53%（对归属阈值不敏感），
但抽 6 段读图证明这是**混合靶子**——四桶混在一起：
  ① 同场景内偏移（真病灶，可分离则有价值）
  ② 兄弟机位/内容不可分（已知特征上限，置信信号救不了）
  ③ 真·不同内容错（最该被降档的一类）
  ④ GT 疑错/同源重复（我方帧与解说帧同镜头，GT 指向别处）

本脚本把全部对象段出成三格图（ED | OURS | GT）供逐条读图裁决，并导出 index.json
（含偏移秒数、GT 窗宽、段置信），读图结论按 index 回填。零 runtime / 零 GT 改动。

Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/review_high_wrong_segments.py
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
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

from diagnostics.contact_sheet import compose_sheet                    # noqa: E402
from diagnostics.frame_sampler import ffmpeg_frame, fmt_ts             # noqa: E402
from measure_shot_recall import overlap_frac                           # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OUT = BENCH / "work" / "highwrong_visual"
ROWS_PER_SHEET = 4
ATTRIB_FRAC = 0.95          # 段编辑窗 ≥95% 落在单一 GT 行内 ⇒ 归属无歧义
CASES = [
    ("2mkv", "datasets/real/ground_truth_v4.json", "work/fastglobal_default_2mkv.results.json"),
    ("test1", "datasets/real/ground_truth_test1.json", "work/fastglobal_default_test1.results.json"),
    ("test2", "datasets/real/ground_truth_test2.json", "work/fastglobal_default_test2.results.json"),
    ("test3", "datasets/real/ground_truth_test3.json", "work/fastglobal_default_test3.results.json"),
]


def covers(o0, o1, a, b) -> bool:
    """与 measure_shot_recall 的严格判据同款（within±2 / mid_in / cov>=0.4）。"""
    if b - a <= 0.01:
        return False
    return (a >= o0 - 2.0 and b <= o1 + 2.0) or a <= (o0 + o1) / 2 <= b \
        or overlap_frac(o0, o1, a, b) >= 0.4


def collect():
    items = []
    for case, gt_rel, ours_rel in CASES:
        pos = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))["positives"]
        raw = json.loads((BENCH / ours_rel).read_text(encoding="utf-8"))
        for i, r in enumerate(raw["results"]):
            if r["confidence"] != "HIGH":
                continue
            e0, e1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
            w = e1 - e0
            if w <= 0:
                continue
            cand = [p for p in pos
                    if (min(e1, p["edited"][1]) - max(e0, p["edited"][0])) / w >= ATTRIB_FRAC]
            if len(cand) != 1:
                continue
            p = cand[0]
            a, b = r["original"]["candidate_start"], r["original"]["candidate_end"]
            o0, o1 = p["original"]
            if covers(o0, o1, a, b):
                continue                      # 主答案对得上，不是对象
            off = (a - o1) if a > o1 else ((o0 - b) if b < o0 else 0.0)
            items.append({"case": case, "seg": i, "gt_row": p["id"], "gt_tier": p["tier"],
                          "ed": [round(e0, 2), round(e1, 2)],
                          "ours": [round(a, 2), round(b, 2)],
                          "gt_og": [round(o0, 2), round(o1, 2)],
                          "offset_s": round(off, 2),
                          "gt_width_s": round(o1 - o0, 2),
                          "span_width_s": round(b - a, 2),
                          "score": round(r["confidence_score"], 3),
                          "n_subs": len(r.get("original_segments") or []),
                          "montage": bool(r.get("montage_flag")),
                          "src": raw["original_video"], "edf": raw["edited_video"],
                          "bucket": None})    # 读图后回填
    return items


def main() -> int:
    (OUT / "frames").mkdir(parents=True, exist_ok=True)
    items = collect()
    by_case = {}
    for it in items:
        by_case[it["case"]] = by_case.get(it["case"], 0) + 1
    print("对象段 = %d  分布 %s" % (len(items), by_case))

    def cell(video, t, cap, tag):
        p = OUT / "frames" / f"{tag}.png"
        try:
            ffmpeg_frame(video, max(0.0, float(t)), p)
            return (str(p), [cap, f"t={fmt_ts(t)}"])
        except Exception:
            return None

    rows, meta_chunk, part = [], [], 0
    for it in items:
        src, edf = Path(it["src"]), Path(it["edf"])
        e0, e1 = it["ed"]
        a, b = it["ours"]
        o0, o1 = it["gt_og"]
        tag = f"{it['case']}_s{it['seg']}"
        rows.append([
            cell(edf, (e0 + e1) / 2, f"{it['case']} seg{it['seg']} ED {e0:.1f}-{e1:.1f}",
                 tag + "_ed"),
            cell(src, (a + b) / 2, f"OURS {a:.0f}-{b:.0f} off{it['offset_s']:+.1f}s",
                 tag + "_ours"),
            cell(src, (o0 + o1) / 2, f"GT {it['gt_row']}({it['gt_tier']}) {o0:.0f}-{o1:.0f}",
                 tag + "_gt")])
        meta_chunk.append(it)
        if len(rows) == ROWS_PER_SHEET:
            part += 1
            _flush(rows, meta_chunk, part)
            rows, meta_chunk = [], []
    if rows:
        _flush(rows, meta_chunk, part + 1)

    (OUT / "index.json").write_text(json.dumps(items, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
    print("清单与元数据 -> %s（bucket 字段读图后回填）" % (OUT / "index.json"))
    return 0


def _flush(rows, meta, part):
    out = OUT / f"sheet_p{part}.png"
    label = " / ".join("%s s%d→%s" % (m["case"], m["seg"], m["gt_row"]) for m in meta)
    compose_sheet(rows, out, "HIGH but main span misses GT: ED | OURS | GT   rows: " + label)
    print("  [%s] %d 行" % (out.name, len(rows)), flush=True)


if __name__ == "__main__":
    sys.exit(main())
