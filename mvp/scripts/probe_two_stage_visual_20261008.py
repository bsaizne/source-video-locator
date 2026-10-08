# -*- coding: utf-8 -*-
"""⑥b 两级采样探针的**逐图复核**出图（2026-10-08）。

为什么要出图：`compare.json` 的三指标与逐 ID mark 只是**代理**。B05（0.5fps 粗筛）在 test2
上 −5 的形态是 `no_evidence` 变多（1→9）与编辑侧切分合并（67 行→65 行），这两类都可能
「指标说丢了，画面上其实还在」或反过来。**判负结论必须先看过图**（项目纪律：GT/指标只是代理）。

每行 = GT_ED | GT_OG | 各臂证据格（A10 = 1.0fps 对照、B05 = 0.5fps 粗筛、
C05D = 粗筛+命中邻域密验、V10 = 10-03 现役默认批；缺臂留空格）：
  1) GT 编辑窗中帧   2) GT 原片窗中帧
  3+) 每臂一格 = 该臂「判档证据 span」中帧
证据格 = 按 `measure_shot_recall.evaluate` 的同一匹配规则（within/mid_in/cov，主子 span 都算，
按结果顺序第一个满足者）取出的那条 span，caption 标 `臂 kind 行号 区间 [档位]`。
（第一版用「与 GT 编辑窗重叠最大的行的主 span」，在 test2 这类一窗被多行重叠覆盖的区域会取错格：
 出现过画面与 GT 完全不同却判 HIT 的格，已改。）
读法：3 与 1/2 同内容而 4 不同 ⇒ 粗筛真丢画面；4 与 2 同内容却判 miss ⇒ 口径/切分假象。

零 runtime / 零 GT 改动 / 零 GPU（只 FFmpeg 精确 seek 抓帧）。

Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_two_stage_visual_20261008.py test2
  （默认 test2；片名可为 2mkv/test1/test3）
产物：work/two_stage_20261008/visual/{case}_sheet{N}.png + index.json
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", (r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
                                       r"\static_ffmpeg\bin\win32\ffprobe.exe"))
for p in (BENCH / "src", BENCH / "mvp" / "scripts", BENCH / "mvp" / "src"):
    sys.path.insert(0, str(p))

from diagnostics.contact_sheet import compose_sheet          # noqa: E402
from diagnostics.frame_sampler import ffmpeg_frame, fmt_ts   # noqa: E402
from measure_shot_recall import evaluate                      # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OUT = BENCH / "work" / "two_stage_20261008" / "visual"
GT_FILES = {
    "2mkv": "datasets/real/ground_truth_v4.json",
    "test1": "datasets/real/ground_truth_test1.json",
    "test2": "datasets/real/ground_truth_test2.json",
    "test3": "datasets/real/ground_truth_test3.json",
}
BASELINE = "V10"      # 10-03 现役默认批 work/isc_refine_arms/v2_{case}（逐字节不等但逐行 mark 已核一致）
ARMS = ("A10", "B05", "C05D", BASELINE)
N_CONTROL = 4
ROWS_PER_SHEET = 3


def _load(case: str) -> dict:
    d = {}
    for arm in ARMS:
        if arm == BASELINE:
            p = BENCH / "work" / "isc_refine_arms" / ("v2_%s.results.json" % case)
        else:
            p = (BENCH / "work" / "two_stage_20261008" / "results"
                 / ("%s_%s.results.json" % (arm, case)))
        if p.exists():
            d[arm] = json.loads(p.read_text(encoding="utf-8"))
    return d


def _marks(gt: dict, data: dict) -> dict:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = evaluate(gt, data["results"], label="")
    # 记 (严格档, 仅主span档)：2mkv 的实测形态是严格 −1 但导出实得 −6，
    # 只看严格档会漏掉「主 span 不再覆盖 GT、靠子 span 兜住」那 6 行。
    return {x["id"]: "%s|%s" % (x["mark"], "M" if x.get("main_hit") else "-")
            for x in r["per_pos"]}


def _match(gt_p: dict, res: list[dict]) -> dict:
    """**复刻 measure_shot_recall.evaluate 的匹配规则**，取出「判成这一档的那条证据」。

    第一版出图用「与 GT 编辑窗重叠最大的结果段的主 span」，在 test2 这种一个编辑窗被
    多行重叠覆盖的区域里会取错格（画面与 GT 完全不同却判 HIT 的行）——因为 HIT 可能由
    **别的行/子 span** 满足，且评估器是「按结果顺序第一个满足者」。故此处逐字复刻：
      within(a>=o0-2 且 b<=o1+2) / mid_in(GT 中点落 span 内) / cov(重叠>=0.4)，主/子 span 都算；
      场景级 = 结果中点落在 GT ±15s。
    返回 {"strict": (i,kind,a,b) | None, "main": ..., "scene": ...}
    """
    e0, e1 = float(gt_p["edited"][0]), float(gt_p["edited"][1])
    o0, o1 = float(gt_p["original"][0]), float(gt_p["original"][1])
    strict = main = scene = None
    for i, r in enumerate(res):
        re0 = float(r["edited_segment"]["start"])
        re1 = float(r["edited_segment"]["end"])
        if min(e1, re1) - max(e0, re0) <= 0:
            continue
        for kind, a, b in _spans_of(r):
            ok = (a >= o0 - 2.0 and b <= o1 + 2.0) or (a <= (o0 + o1) / 2 <= b) \
                or (_ov(o0, o1, a, b) / max(1e-6, o1 - o0) >= 0.4)
            if ok and strict is None:
                strict = (i, kind, a, b)
            if ok and kind == "main" and main is None:
                main = (i, kind, a, b)
            m = (a + b) / 2
            if scene is None and o0 - 15.0 <= m <= o1 + 15.0:
                scene = (i, kind, a, b)
    return {"strict": strict, "main": main, "scene": scene}


def _spans_of(r: dict):
    out = [("main", float(r["original"]["candidate_start"]),
            float(r["original"]["candidate_end"]))]
    for s in r.get("original_segments") or []:
        out.append(("sub", float(s["candidate_start"]), float(s["candidate_end"])))
    return [x for x in out if x[2] - x[1] > 0.01]


def _ov(o0, o1, a, b):
    return max(0.0, min(o1, b) - max(o0, a))


def _cell(video, t, cap, tag):
    if video is None or t is None:
        return None
    p = OUT / "frames" / ("%s.png" % tag)
    try:
        ffmpeg_frame(video, max(0.0, float(t)), p)
        return (str(p), [cap, fmt_ts(t)])
    except Exception as exc:                                  # noqa: BLE001
        print("  [frame fail] %s t=%s %s" % (tag, t, exc), flush=True)
        return None


def main() -> int:
    case = sys.argv[1] if len(sys.argv) > 1 else "test2"
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "frames").mkdir(parents=True, exist_ok=True)
    data = _load(case)
    if not data:
        print("无该臂结果：%s（先跑 locate 腿）" % case)
        return 2
    gt = json.loads((BENCH / GT_FILES[case]).read_text(encoding="utf-8"))
    ref = data.get("A10") or data.get("B05") or data.get(BASELINE)
    src, ed = Path(ref["original_video"]), Path(ref["edited_video"])
    marks = {a: _marks(gt, d) for a, d in data.items()}
    base_arm = next(a for a in ("A10", BASELINE, "B05") if a in marks)
    flip_ids = []
    for p in gt["positives"]:
        pid = p["id"]
        vals = {a: marks[a].get(pid) for a in data}
        if len({v for v in vals.values()}) > 1:
            flip_ids.append(pid)
    controls = [p["id"] for p in gt["positives"]
                if p["id"] not in flip_ids and str(marks[base_arm].get(p["id"])).startswith("HIT")][:N_CONTROL]
    ids = flip_ids + controls
    print("[%s] 臂=%s 翻转行=%d %s | 控制行=%d" %
          (case, list(data), len(flip_ids), flip_ids, len(controls)), flush=True)

    rows, index = [], []
    for pid in ids:
        p = next(x for x in gt["positives"] if x["id"] == pid)
        e0, e1 = float(p["edited"][0]), float(p["edited"][1])
        o0, o1 = float(p["original"][0]), float(p["original"][1])
        mid_og = (o0 + o1) / 2.0
        row = [_cell(ed, (e0 + e1) / 2.0, "GT %s ED" % pid, "%s_%s_gt_ed" % (case, pid)),
               _cell(src, mid_og, "GT %s OG %.1f-%.1f" % (pid, o0, o1),
                     "%s_%s_gt_om" % (case, pid))]
        rec = {"case": case, "id": pid, "gt_ed": [e0, e1], "gt_og": [o0, o1], "marks": {}}
        for arm in ARMS:
            if arm not in data:
                row.append(None)
                continue
            mt = _match(p, data[arm]["results"])
            pick = mt["strict"] or mt["scene"]
            rec["marks"][arm] = {"mark": marks[arm].get(pid),
                                 "evidence": None if pick is None else
                                 {"row": pick[0], "kind": pick[1], "span": [pick[2], pick[3]]},
                                 "via": "strict" if mt["strict"] else ("scene" if mt["scene"]
                                                                       else "none"),
                                 "rows": len(data[arm]["results"])}
            if pick is None:
                row.append(_cell(None, None, "%s 无证据" % arm, ""))
                continue
            i, kind, a, b = pick
            cap = "%s %s r%d %.1f-%.1f [%s]" % (arm, kind, i, a, b, marks[arm].get(pid))
            row.append(_cell(src, (a + b) / 2.0, cap, "%s_%s_%s" % (case, pid, arm)))
        rows.append(row)
        index.append(rec)

    for i in range(0, len(rows), ROWS_PER_SHEET):
        chunk = rows[i:i + ROWS_PER_SHEET]
        out = OUT / ("%s_sheet%d.png" % (case, i // ROWS_PER_SHEET + 1))
        compose_sheet(chunk, out,
                      "%s: GT_ED | GT_OG | %s" % (case,
                                                  " | ".join(a for a in ARMS if a in data)))
        print("[%s] %s (%d 行)" % (case, out.name, len(chunk)), flush=True)
    (OUT / ("%s_index.json" % case)).write_text(json.dumps(index, ensure_ascii=False, indent=1),
                                                encoding="utf-8")
    print("共 %d 行 -> %s" % (len(index), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
