# -*- coding: utf-8 -*-
"""退化判据全量逐图复核出图（2026-09-29 续31，用户令「全部读一遍」）。

三套图，覆盖本批**每一条结论所依赖的样本**（不是抽查）：

A. **拒识腿实际拒识的段**（现役批 `dup_only` 臂）——每段一行：编辑帧 vs 它自己认领的原片 span 帧。
   同内容 ⇒ 该拒是误伤。并把**覆盖它的邻居**逐条并排，验证「相邻细段拼接铺满」这条机制。
B. **子 span 腿（`min_scene_coverage` 整段清空）翻掉的 GT 行**（test2 的 −5）——每行：
   GT 编辑窗帧 / GT 原片窗帧 / 被清掉的那条子 span 中帧。
C. **影响面统计里的全部重复对**（探针 partners ≥0.8 去重）——每行四格：
   段 i 编辑帧 / 段 i 原片帧 / 段 j 编辑帧 / 段 j 原片帧 ⇒ 直接看"是不是同一素材"。

数据源 = 探针产物 `work/degradation_impact_unionfix.json` + 现役结果批 JSON（只读）。
出图一律走 `src/diagnostics/frame_sampler.ffmpeg_frame`（项目口径：FFmpeg 精确 seek）。
零 runtime 改动、零 GT 改动。

Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/review_degradation_visual.py
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

from diagnostics.contact_sheet import compose_sheet                  # noqa: E402
from diagnostics.frame_sampler import ffmpeg_frame, fmt_ts, pick_reps  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

PROBE = BENCH / "work" / "degradation_impact_unionfix.json"
OUT = BENCH / "work" / "degradation_visual"
TMP = OUT / "frames"
CASES = ["2mkv", "test1", "test2", "test3"]
GT_OF = {"2mkv": "datasets/real/ground_truth_v4.json",
         "test1": "datasets/real/ground_truth_test1.json",
         "test2": "datasets/real/ground_truth_test2.json",
         "test3": "datasets/real/ground_truth_test3.json"}
ROWS_PER_SHEET = 4


def _load(case):
    raw = json.loads((BENCH / "work" / f"fastglobal_default_{case}.results.json")
                     .read_text(encoding="utf-8"))
    gt = json.loads((BENCH / GT_OF[case]).read_text(encoding="utf-8"))
    return raw, gt


def _cell(video, t, cap, tag):
    p = TMP / f"{tag}.png"
    try:
        ffmpeg_frame(video, t, p)
        return (str(p), [cap])
    except Exception as exc:                       # 解码失败留空格，不静默跳过整行
        return None                                # compose_sheet 用 None 画占位格


def _pair_cells(video, tag, ed_a, ed_b, om_a, om_b, label):
    """一段的两格：编辑侧中帧（编辑时间轴）+ 原片侧中帧（**原片时间轴**）。
    首版误把同一个窗口喂给两格 ⇒ 右列全错，已修。"""
    t_ed = pick_reps(ed_a, ed_b, 2)[0]
    t_om = pick_reps(om_a, om_b, 2)[0]
    return [_cell(video[1], t_ed, f"{label} ED {fmt_ts(t_ed)}", f"{tag}_ed"),
            _cell(video[0], t_om, f"{label} OM {fmt_ts(t_om)}", f"{tag}_om")]


def flush(rows, case, name, title, index):
    if not rows:
        return
    for i in range(0, len(rows), ROWS_PER_SHEET):
        chunk = rows[i:i + ROWS_PER_SHEET]
        part = i // ROWS_PER_SHEET + 1
        out = OUT / f"{case}_{name}_p{part}.png"      # 必须带 case，否则各片互相覆盖
        compose_sheet(chunk, out, title)               # 标题走 ASCII（默认 PIL 字体不渲中文）
        index.append({"sheet": out.name, "case": case, "set": name, "title": title,
                      "rows": len(chunk), "part": part})
        print("  [%s/%s] %s (%d 行)" % (case, name, out.name, len(chunk)), flush=True)


def main() -> int:
    TMP.mkdir(parents=True, exist_ok=True)
    probe = json.loads(PROBE.read_text(encoding="utf-8"))
    index = []
    for case in CASES:
        row = next((c for c in probe["cases"] if c["case"] == case), None)
        if row is None:
            continue
        raw, gt = _load(case)
        src = Path(raw["original_video"])
        ed = Path(raw["edited_video"])
        vids = (src, ed)
        segs = {s["idx"]: s for s in row["segments"]}
        print("\n===== %s =====" % case, flush=True)

        # ---- A. 拒识腿实际拒识的段 + 覆盖它的邻居 ----
        rows = []
        for i, ratio in row["arms"]["dup_only"]["rejected"]:
            s = segs[i]
            rows.append(_pair_cells(vids, f"A_{case}_s{i}_rej",
                                    s["edit"][0], s["edit"][1], s["src"][0], s["src"][1],
                                    f"REJ s{i} dup={ratio} gt={','.join(s['gt_rows']) or '-'}"))
            # 用全部可回答段重算「谁盖住了它」（探针 partners 只留 ≥0.8 的单一伙伴）
            others = [t for t in row["segments"] if t["idx"] != i
                      and min(t["src"][1], s["src"][1]) - max(t["src"][0], s["src"][0]) > 0]
            others.sort(key=lambda t: -(min(t["src"][1], s["src"][1])
                                        - max(t["src"][0], s["src"][0])))
            for o in others[:3]:
                ov = (min(o["src"][1], s["src"][1]) - max(o["src"][0], s["src"][0])
                      ) / max(1e-6, s["src"][1] - s["src"][0])
                rows.append(_pair_cells(vids, f"A_{case}_s{i}_by{o['idx']}",
                                        o["edit"][0], o["edit"][1], o["src"][0], o["src"][1],
                                        f"coverr s{o['idx']} src{o['src'][0]:.0f}-{o['src'][1]:.0f}"
                                        f" cov={ov:.2f} gt={','.join(o['gt_rows']) or '-'}"))
        flush(rows, case, "A_rejected", f"{case} A: rejected segs + covering neighbours", index)

        # ---- B. 子 span 腿（整段清空）翻掉的 GT 行 ----
        base = {p["id"]: p["mark"] for p in row["metrics"]["off"]["per_pos"]}
        dupm = {p["id"]: p["mark"] for p in row["metrics"]["dup_only"]["per_pos"]}
        allm = {p["id"]: p["mark"] for p in row["metrics"]["both_allnone"]["per_pos"]}
        subs_only = {p["id"]: p["mark"] for p in row["metrics"]["subs_only"]["per_pos"]}
        no_sub = []
        rows = []
        for p in gt["positives"]:
            rid = p["id"]
            mark = base.get(rid)
            if mark is None:
                continue
            lost = [arm for arm, m in (("allnone", allm), ("subs_partial", subs_only),
                                       ("dup_leg", dupm))
                    if m.get(rid) and m[rid] != mark]
            if not lost:
                continue
            e0, e1, o0, o1 = p["edited"][0], p["edited"][1], p["original"][0], p["original"][1]
            t_ed, t_om = pick_reps(e0, e1, 2), pick_reps(o0, o1, 2)
            cells = [_cell(ed, t_ed[0], f"GT {rid} ED {fmt_ts(t_ed[0])} lost:{','.join(lost)}",
                      f"B_{case}_{rid}_ed"),
                     _cell(src, t_om[0], f"GT {rid} OM {fmt_ts(t_om[0])}", f"B_{case}_{rid}_om")]
            # 找出「被整段清空」的子 span：cover<0.2 且罩住该 GT 原片窗 ≥40%（列全部候选，取前二）
            cands = []
            for ri, r in enumerate(raw["results"]):
                for sub in (r.get("original_segments") or []):
                    ov = min(o1, sub["candidate_end"]) - max(o0, sub["candidate_start"])
                    if ov / max(1e-6, o1 - o0) >= 0.4 and float(sub.get("cover") or 0) < 0.2:
                        cands.append((ri, sub))
            if cands:
                for k, (ri, sub) in enumerate(cands[:2]):
                    t = (sub["candidate_start"] + sub["candidate_end"]) / 2.0
                    cells.append(_cell(src, t,
                                       f"dropped s{ri} {fmt_ts(t)} cover={sub.get('cover'):.2f}",
                                       f"B_{case}_{rid}_sub{k}"))
            else:
                no_sub.append(rid)
                cells.append(None)     # 丢失发生在主 span 侧（无 cover<0.2 的子 span 可指）
            rows.append(cells)
        flush(rows, case, "B_subleg", f"{case} B: GT rows lost by sub-span leg + dropped subs", index)
        if no_sub:
            print("  [B] 无 cover<0.2 子 span 可指的 GT 行（丢失在主 span 侧）: %s" % no_sub,
                  flush=True)

        # ---- C. 影响面全部重复对 ----
        pairs = set()
        for s in row["segments"]:
            for p in s["partners"]:
                pairs.add((min(s["idx"], p["idx"]), max(s["idx"], p["idx"])))
        rows = []
        for i, j in sorted(pairs):
            a, b = segs.get(i), segs.get(j)
            if not a or not b:
                continue
            cells = _pair_cells(vids, f"C_{case}_{i}_{j}_a", a["edit"][0], a["edit"][1],
                                a["src"][0], a["src"][1],
                                f"s{i} gt={','.join(a['gt_rows']) or '-'}")
            cells += _pair_cells(vids, f"C_{case}_{i}_{j}_b", b["edit"][0], b["edit"][1],
                                 b["src"][0], b["src"][1],
                                 f"s{j} gt={','.join(b['gt_rows']) or '-'}")
            rows.append(cells)
        flush(rows, case, "C_pairs", f"{case} C: dup pairs (row = s_i ED|OM  s_j ED|OM)", index)

    (OUT / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False),
                                    encoding="utf-8")
    print("\n共 %d 张图 -> %s" % (len(index), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
