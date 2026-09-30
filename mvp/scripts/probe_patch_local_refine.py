# -*- coding: utf-8 -*-
"""(E) 形态6：场景局部窗口 patch 精排（local_refiner 形态）探针（2026-09-30）。

依据：机制诊断实锤 p20/p34/t3r02c（t2r06c 半盲）= CLS 全局指纹盲区；竞品赢在
`fast_timeline.local_refiner`「局部窗口移动候选起点 + 多帧全局/Patch 证据精排」形态。
我方已证伪的是「全局融合打分」与「AKAZE 几何」两个**别的形态**——本探针首次测
局部窗口形态。参数 GT 无关，取竞品字节确证值：global 0.45 / patch 0.55、
query_count=5、局部窗 ±10s。

方法（每行）：ED 窗 5 查询帧 → 源片锚 ±10s @2fps 稠密网格 → 逐源帧
score = 0.45·CLS 余弦均值 + 0.55·patch top-100 均值（查询帧平均）→ 峰值位；
精修提案 = 以峰为中心、编辑窗等长。对照行（现役 HIT）验证稳定性（峰不乱动）。
**评估自带全量读图**（用户令：不再纯数据定案）。

产物 `work/patch_local_refine/`。零 runtime / 零 GT 改动。
Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_patch_local_refine.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
sys.path.insert(0, str(BENCH / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "src"))

import numpy as np  # noqa: E402

from diagnostics.contact_sheet import compose_sheet   # noqa: E402
from diagnostics.frame_sampler import ffmpeg_frame, fmt_ts  # noqa: E402
from research_patch_recall_v4 import Embedder, patch_score  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OUT = BENCH / "work" / "patch_local_refine"
GT_OF_CASE = {"2mkv": "datasets/real/ground_truth_v4.json",
              "test1": "datasets/real/ground_truth_test1.json",
              "test2": "datasets/real/ground_truth_test2.json",
              "test3": "datasets/real/ground_truth_test3.json"}
SRC_OF = {"2mkv": "work/fastglobal_default_2mkv.results.json",
          "test1": "work/fastglobal_default_test1.results.json",
          "test2": "work/fastglobal_default_test2.results.json",
          "test3": "work/fastglobal_default_test3.results.json"}
# 盲区行（诊断）+ 对照行（现役 HIT, 稳定性哨兵）
ROWS = [("2mkv", "p20", "blind"), ("2mkv", "p34", "blind"),
        ("test2", "t2r06c", "blind"), ("test3", "t3r02c", "blind"),
        ("2mkv", "p30", "blind"),
        ("2mkv", "p01", "ctrl"), ("2mkv", "p06", "ctrl"),
        ("test1", "t1r01", "ctrl"), ("test3", "t3r07", "ctrl")]
W_GLOBAL, W_PATCH = 0.45, 0.55
N_Q, LOCAL_WIN, SRC_FPS = 5, 10.0, 2.0


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "frames").mkdir(parents=True, exist_ok=True)
    emb = Embedder()
    print("patch backend DML=%s" % emb._use_dml, flush=True)
    gts = {c: json.loads((BENCH / g).read_text(encoding="utf-8"))
           for c, g in GT_OF_CASE.items()}
    src_cache = {}

    def srcp(case):
        if case not in src_cache:
            raw = json.loads((BENCH / SRC_OF[case]).read_text(encoding="utf-8"))
            src_cache[case] = (Path(raw["original_video"]), Path(raw["edited_video"]))
        return src_cache[case]

    index, rows = [], []
    for case, pid, kind in ROWS:
        p = next(x for x in gts[case]["positives"] if x["id"] == pid)
        e0, e1 = p["edited"][0], p["edited"][1]
        o0, o1 = p["original"][0], p["original"][1]
        w = e1 - e0
        mid_anchor = (o0 + o1) / 2
        src, ed = srcp(case)
        # 查询帧（ED 窗 5 帧）
        q_ets = [e0 + w * (i + 0.5) / N_Q for i in range(N_Q)]
        q_cls, q_patch = [], []
        for t in q_ets:
            c, pp = emb.embed(str(ed), float(t))
            q_cls.append(c)
            q_patch.append(pp)
        # 源片局部网格
        s0, s1 = max(0.0, mid_anchor - LOCAL_WIN), mid_anchor + LOCAL_WIN
        n = max(20, int((s1 - s0) * SRC_FPS))
        grid = [s0 + (s1 - s0) * (i + 0.5) / n for i in range(n)]
        sc = []
        for t in grid:
            c, pp = emb.embed(str(src), float(t))
            g = W_GLOBAL * float(np.mean([float(c @ q) for q in q_cls]))
            pt = W_PATCH * float(np.mean([patch_score(qp, pp) for qp in q_patch]))
            sc.append(g + pt)
        k = int(np.argmax(sc))
        peak = float(grid[k])
        anchor_score = sc[int(np.argmin(np.abs(np.array(grid) - mid_anchor)))]
        margin = float(sc[k] - anchor_score)
        prop0, prop1 = peak - w / 2, peak + w / 2
        moved = abs(peak - mid_anchor)
        row = {"case": case, "id": pid, "kind": kind,
               "gt_ed": [e0, e1], "gt_og": [o0, o1],
               "anchor_mid": round(mid_anchor, 2), "peak_mid": round(peak, 2),
               "moved_s": round(moved, 2), "margin": round(margin, 4),
               "score_peak": round(float(sc[k]), 4),
               "proposed": [round(prop0, 2), round(prop1, 2)],
               "peak_in_gt": o0 - 2 <= peak <= o1 + 2}
        index.append(row)
        tag = f"{case}_{pid}"
        cells = []
        for vid, t, cap in ((ed, (e0 + e1) / 2, "GT ED"),
                            (src, mid_anchor, "ANCHOR"),
                            (src, peak, "PEAK"),
                            (src, (o0 + o1) / 2, "GT OG")):
            pp = OUT / "frames" / f"{tag}_{cap.split()[0]}.png"
            try:
                ffmpeg_frame(vid, max(0.0, float(t)), pp)
                cells.append((str(pp), [cap, fmt_ts(t)]))
            except Exception:
                cells.append(None)
        rows.append(cells)
        print("[%-5s %-7s %-5s] 锚=%.1f 峰=%.1f 移动=%.1fs margin=%.3f 峰在GT窗=%s" % (
            case, pid, kind, mid_anchor, peak, moved, margin, row["peak_in_gt"]),
            flush=True)
    for i in range(0, len(rows), 3):
        compose_sheet(rows[i:i + 3], OUT / f"refine_{i // 3 + 1:02d}.png",
                      "patch local refine %d-%d: GT_ED | ANCHOR | PEAK | GT_OG"
                      % (i + 1, i + 3))
    (OUT / "proposals.json").write_text(json.dumps(index, ensure_ascii=False, indent=1),
                                        encoding="utf-8")
    blind = [x for x in index if x["kind"] == "blind"]
    ctrl = [x for x in index if x["kind"] == "ctrl"]
    print("\n盲区行峰在 GT 窗: %d/%d | 对照行峰移动 ≤2s: %d/%d" % (
        sum(1 for x in blind if x["peak_in_gt"]), len(blind),
        sum(1 for x in ctrl if x["moved_s"] <= 2.0), len(ctrl)))
    print("产物: %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
