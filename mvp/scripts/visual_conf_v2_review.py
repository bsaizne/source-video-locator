# -*- coding: utf-8 -*-
"""conf_v2 多模态复核出图：把「指标说了什么」与「画面里是什么」并排摆出来。

纪律（用户 2026-09-28）：**GT 不是唯一复核标准**，最终要逐张读图。本脚本只负责产图，
判读由模型逐张看图完成；图证与 GT 判据冲突时以图证为准（本项目已多次出现 GT 窄窗假象
与场景 span 装配效应导致的指标误读）。

挑样原则 = 专挑能推翻或证实结论的少数样本，不做全量图海：
  HIGHorMISS / HIGHorpart —— 现行档位判 HIGH 但 GT 不认（老病灶「自信错答」）
  v2gate                 —— score_v2 < 0.6（新公式认为不稳，看画面到底可不可疑）
  neg                    —— 压在 GT 负例窗上的段（产品上最该降档的一类）
  sanityHIT              —— 每片 2 条 GT 判 HIT 的段，作正面参照基准

每张图三行：编辑段帧 / 定位到的原片帧 / GT 真值窗帧（仅参照，非判据）。

用法:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/visual_conf_v2_review.py [case]
产出: work/confv2_visual/<case>_r<idx>_<tag>.jpg
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

from diagnostics.contact_sheet import compose_sheet  # noqa: E402
from diagnostics.frame_sampler import ffmpeg_frame, fmt_ts, pick_reps  # noqa: E402

from analyze_conf_v2 import (CASES, OFF_PATTERN, ON_PATTERN, align_diag,  # noqa: E402
                             owner_negative, _owner, _verdict)

OUT = BENCH / "work" / "confv2_visual"
MAX_PER_CASE = 16
PRIORITY = {"v2gate": 0, "neg": 1, "HIGHor": 2, "sanityHIT": 3}


def _prio(tag: str) -> int:
    for k, v in PRIORITY.items():
        if tag.startswith(k):
            return v
    return 9


def _row(tmp: Path, tag: str, idx: int, video: Path, a: float, b: float):
    cells = []
    for j, t in enumerate(pick_reps(a, b, 3)):
        p = tmp / f"{tag}_r{idx}_{['a', 'b', 'c'][j]}.png"
        try:
            ffmpeg_frame(video, t, p)
            cells.append((str(p), [f"{tag} {fmt_ts(t)}"]))
        except Exception:
            cells.append(None)
    return cells


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / "_frames"
    tmp.mkdir(exist_ok=True)
    index = {}
    for case, gt_rel in CASES:
        if only and case != only:
            continue
        off_p = BENCH / OFF_PATTERN.format(case=case)
        on_p = BENCH / ON_PATTERN.format(case=case)
        diag_p = BENCH / "work" / ("confv2_diag_%s.json" % case)
        if not (off_p.exists() and on_p.exists() and diag_p.exists()):
            print(f"[{case}] 缺批或诊断，跳过")
            continue
        off = json.loads(off_p.read_text(encoding="utf-8"))
        on = json.loads(on_p.read_text(encoding="utf-8"))
        gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
        raw_diag = json.loads(diag_p.read_text(encoding="utf-8"))
        video, original = Path(off["edited_video"]), Path(off["original_video"])

        picked = []
        n_sanity = 0
        for i, (r, hit) in enumerate(align_diag(off["results"], raw_diag)):
            if i >= len(on["results"]):
                break
            g = _owner(r, gt)
            v = _verdict(r, g)
            lv_off, lv_on = r["confidence"], on["results"][i]["confidence"]
            s = (hit or {}).get("v2", {})
            score = s.get("score")
            neg = owner_negative(r, gt)
            tags = []
            if score is not None and score < 0.6:
                tags.append("v2gate")
            if neg is not None:
                tags.append("neg_%s" % neg["id"])
            if lv_off == "HIGH" and v in ("MISS", "part"):
                tags.append("HIGHor%s" % v)
            if v == "HIT" and n_sanity < 2 and score is not None and score >= 0.6:
                tags.append("sanityHIT")
                n_sanity += 1
            if tags:
                picked.append((i, r, g, v, lv_off, lv_on, s, "-".join(tags)))
        picked.sort(key=lambda x: _prio(x[7]))
        picked = picked[:MAX_PER_CASE]

        rows_index = []
        for i, r, g, v, lv_off, lv_on, s, tag in picked:
            e0, e1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
            o0, o1 = r["original"]["candidate_start"], r["original"]["candidate_end"]
            rows = [_row(tmp, "ed", i, video, e0, e1), _row(tmp, "og", i, original, o0, o1)]
            if g is not None:
                rows.append(_row(tmp, "gt", i, original, g["original"][0], g["original"][1]))
            title = (f"{case} r{i:02d} [{tag}] ed({fmt_ts(e0)}..{fmt_ts(e1)}) "
                     f"og({fmt_ts(o0)}..{fmt_ts(o1)}) GT={v or 'n/a'} | "
                     f"off={lv_off} on={lv_on} | v2={s.get('score')} "
                     f"(L{s.get('local')} C{s.get('coarse')} K{s.get('consistency')} M{s.get('margin')}) "
                     f"nis={int(bool(r.get('not_in_source')))}")
            out = OUT / ("%s_r%02d_%s.jpg" % (case, i, tag.replace("/", "-")))
            compose_sheet(rows, out, title)
            rows_index.append({"case": case, "idx": i, "tag": tag, "gt_verdict": v,
                               "level_off": lv_off, "level_on": lv_on, "v2": s,
                               "sheet": out.name})
            print("  ->", out.name)
        index[case] = rows_index
    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
    print(f"\n共 {sum(len(v) for v in index.values())} 张 -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
