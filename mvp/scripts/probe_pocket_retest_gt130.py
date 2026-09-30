# -*- coding: utf-8 -*-
"""(E) 立项 · 按新 GT 重推「复现链独家命中」口袋测试集（2026-09-30，用户令，多模态复核）。

背景：续31 补二 的 14 条真口袋基于旧 GT；2026-09-30 GT 工单裁决已重锚定 12 行
（基线 严格 130 / 导出实得 107）⇒ 口袋测试集必须重推。本脚本完全复刻原口径：

  口袋 = 复现链截等长命中（caliber2，同粒度） && 我方主 span 截等长未 HIT。
  真口袋判定（每条三条证据，多模态）：
    A. 落窗算术：proxy 落位 mid_in GT窗 / cov≥0.4 / 间隙 0；窗口外 ≤2s = 容差类（剔除）
    B. 生产检索（独立证据）：ED 中帧 → 生产 CLS(DML 硬断言) → 原片 1fps top-20，
       GT 窗 / PROXY 窗 / OURS 窗各自的 rank（支持/不支持）
    C. 逐张读图：四格 GT_ED | GT_OG | PROXY | OURS（本脚本出图，人工读）

旧目录 `work/combo_pocket_visual/` 不覆盖（work 留痕铁律）；本批产物
`work/combo_pocket_retest_gt130/`。

Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_pocket_retest_gt130.py
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
SBOX = Path(r"D:\claudework\cutmatch-analysis\sandbox\out")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", (r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
                                        r"\static_ffmpeg\bin\win32\ffprobe.exe"))
sys.path.insert(0, str(BENCH / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

from diagnostics.contact_sheet import compose_sheet        # noqa: E402
from diagnostics.frame_sampler import ffmpeg_frame, fmt_ts  # noqa: E402
from measure_shot_recall import evaluate                    # noqa: E402
from measure_mainspan_caliber import truncate_main          # noqa: E402
from probe_combo_dual_caliber import caliber2, load_rows    # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OUT = BENCH / "work" / "combo_pocket_retest_gt130"
ROWS_PER_SHEET = 4
WIN_PAD = 1.0
TOPK = 20
CASES = [
    ("2mkv", "datasets/real/ground_truth_v4.json", "localization_2mkv.json",
     "work/fastglobal_default_2mkv.results.json", "D:/video/2.mkv", "D:/video/1.mp4"),
    ("test1", "datasets/real/ground_truth_test1.json", "localization_comboA_test1.json",
     "work/fastglobal_default_test1.results.json", None, None),
    ("test2", "datasets/real/ground_truth_test2.json", "localization_test2.json",
     "work/fastglobal_default_test2.results.json", None, None),
    ("test3", "datasets/real/ground_truth_test3.json", "localization_test3.json",
     "work/fastglobal_default_test3.results.json", None, None),
]
OLD_POCKETS = {("2mkv", "p02"), ("2mkv", "p03"), ("2mkv", "p20"), ("2mkv", "p30"),
               ("2mkv", "p34"), ("test1", "t1r14c"), ("test2", "t2r02a"),
               ("test2", "t2r05a"), ("test2", "t2r05b"), ("test2", "t2r06c"),
               ("test3", "t3r01"), ("test3", "t3r02c"), ("test3", "t3r05"),
               ("test3", "t3r26")}


def rank_in_window(times, pos_of_row, w0, w1):
    best = None
    for row, k in pos_of_row.items():
        t = float(times[row])
        if w0 - WIN_PAD <= t <= w1 + WIN_PAD:
            if best is None or k + 1 < best:
                best = k + 1
    return best


def _cell(video, t, cap, tag):
    if video is None or t is None:
        return None
    p = OUT / "frames" / f"{tag}.png"
    try:
        ffmpeg_frame(video, max(0.0, float(t)), p)
        return (str(p), [cap, fmt_ts(t)])
    except Exception:
        return None


def main() -> int:
    (OUT / "frames").mkdir(parents=True, exist_ok=True)
    # 检索证据（B）：生产同款 CLS + DML 硬断言
    from app.locator_service import SourceLocatorService  # noqa: E402
    from device.directml_backend import DirectMLBackend   # noqa: E402
    from infrastructure.config import load_config          # noqa: E402
    from media.ffmpeg import FFmpegIO                      # noqa: E402
    import numpy as np                                     # noqa: E402

    svc = SourceLocatorService(config=load_config())
    assert isinstance(svc.backend, DirectMLBackend), \
        f"必须 DirectMLBackend, 实际 {type(svc.backend).__name__}"
    print("BACKEND_SELECTED type=%s" % type(svc.backend).__name__, flush=True)
    fio = FFmpegIO(Path(os.environ["MEDIA_FFMPEG"]), Path(os.environ["MEDIA_FFPROBE"]))
    bundles, paths = {}, {}

    index, rows = [], []
    for case, gt_rel, loc_name, ours_rel, src_ovr, ed_ovr in CASES:
        gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
        raw = json.loads((BENCH / ours_rel).read_text(encoding="utf-8"))
        src = Path(src_ovr or raw["original_video"])
        ed = Path(ed_ovr or raw["edited_video"])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            m = evaluate(gt, truncate_main(raw)["results"])
        our_hit = {x["id"]: x["mark"] for x in m["per_pos"]}
        proxy = {x["id"]: x for x in caliber2(load_rows(SBOX / loc_name),
                                              gt["positives"], gt["negatives"])["per"]}
        if case not in bundles:
            bundles[case] = svc.store.load_index(src)
        b = bundles[case]
        for p in gt["positives"]:
            pid = p["id"]
            px = proxy.get(pid)
            if not (px and px["hit"] and our_hit.get(pid) != "HIT"):
                continue
            e0, e1, o0, o1 = p["edited"][0], p["edited"][1], p["original"][0], p["original"][1]
            det = px["detail"]                       # {qid,t0,t1} 复现链截等长落位
            pt0, pt1 = float(det["t0"]), float(det["t1"])
            best, om0, om1 = 0.0, None, None
            for r in raw["results"]:                 # 我方与该 GT 编辑窗重叠最多的段
                re0, re1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
                ov = min(e1, re1) - max(e0, re0)
                if ov > best:
                    best = ov
                    orig = r.get("original") or {}
                    if "candidate_start" in orig:
                        om0, om1 = orig["candidate_start"], orig["candidate_end"]
            # A. 落窗算术
            pmid = (pt0 + pt1) / 2
            mid_in = o0 <= pmid <= o1
            ov = max(0.0, min(pt1, o1) - max(pt0, o0))
            cov = ov / max(1e-9, o1 - o0)
            gap = max(o0 - pt1, pt0 - o1, 0.0)
            # B. 生产检索
            frame = fio.grab_frame(ed, (e0 + e1) / 2.0)
            emb = svc.backend.embed_frames([frame])[0]
            emb = emb / max(1e-8, float(np.linalg.norm(emb)))
            cos = b.features @ emb
            order = np.argsort(-cos)
            pos_of_row = {int(r): k for k, r in enumerate(order[:TOPK])}
            rk = {"gt": rank_in_window(b.times, pos_of_row, o0, o1),
                  "proxy": rank_in_window(b.times, pos_of_row, pt0, pt1),
                  "ours": (rank_in_window(b.times, pos_of_row, om0, om1)
                           if om0 is not None else None)}
            tag = f"{case}_{pid}"
            rows.append([
                _cell(ed, (e0 + e1) / 2, f"GT {pid} ED", f"{tag}_gt_ed"),
                _cell(src, (o0 + o1) / 2, f"GT {pid} OG", f"{tag}_gt_og"),
                _cell(src, pmid, f"PROXY {pt0:.1f}-{pt1:.1f}", f"{tag}_proxy"),
                _cell(src, ((om0 + om1) / 2 if om0 is not None else None),
                      f"OURS {om0:.1f}-{om1:.1f}" if om0 is not None else "OURS none",
                      f"{tag}_ours")])
            index.append({
                "case": case, "id": pid, "gt_ed": [e0, e1], "gt_og": [o0, o1],
                "proxy_span": [pt0, pt1], "our_main_span": [om0, om1],
                "our_mark": our_hit.get(pid),
                "arith": {"mid_in": mid_in, "cov": round(cov, 2), "gap_s": round(gap, 2)},
                "retrieval_rank": rk,
                "old_pocket": (case, pid) in OLD_POCKETS})
            print("[%-5s %-8s] mid_in=%s cov=%.2f gap=%.2f | rank GT=%s PROXY=%s OURS=%s" % (
                case, pid, mid_in, cov, gap, rk["gt"], rk["proxy"], rk["ours"]), flush=True)
    for i in range(0, len(rows), ROWS_PER_SHEET):
        chunk = rows[i:i + ROWS_PER_SHEET]
        sub = index[i:i + ROWS_PER_SHEET]
        cases = sorted({s["case"] for s in sub})
        out = OUT / f"pockets_retest_{i // ROWS_PER_SHEET + 1:02d}_{'-'.join(cases)}.png"
        compose_sheet(chunk, out,
                      "pockets retest GT130 %d-%d: GT_ED | GT_OG | PROXY | OURS"
                      % (i + 1, min(i + ROWS_PER_SHEET, len(rows))))
        print("[%s] %s (%d 行: %s)" % (cases, out.name, len(chunk),
              ", ".join(f"{s['case']}/{s['id']}" for s in sub)), flush=True)
    (OUT / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False),
                                    encoding="utf-8")
    print("\n口袋(复现链独家命中)共 %d 条; 旧 14 条中仍在 = %d; 产物 -> %s" % (
        len(index), sum(1 for x in index if x["old_pocket"]), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
