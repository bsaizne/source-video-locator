# -*- coding: utf-8 -*-
"""单元时长 x 判定 交叉表(直接从度量输出取 ed 窗 + 判定, 不解析 GT)."""
import json, re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
B = Path(r"D:\claudework\benchmark")
LINE = re.compile(r"^\[(HIT |part|MISS)\]\s+(\S+)\s+ed\s*([\d.]+)-\s*([\d.]+)")
JOBS = {"2mkv": ("proxy_qu_2mkv.results.json", "_m_pqu.txt"),
        "test1": ("proxy_qu_test1.results.json", "_m_pqu_test1.txt")}
for case, (resname, txt) in JOBS.items():
    res = json.loads((B / "work" / resname).read_text(encoding="utf-8"))["results"]
    rows = []
    for ln in (B / "work" / txt).read_text(encoding="utf-8", errors="replace").splitlines():
        m = LINE.match(ln)
        if not m:
            continue
        v, gid, e0, e1 = m.group(1).strip(), m.group(2), float(m.group(3)), float(m.group(4))
        best, bo = None, -1.0
        for r in res:
            s, t = float(r["edited_segment"]["start"]), float(r["edited_segment"]["end"])
            ov = min(t, e1) - max(s, e0)
            if ov > bo:
                best, bo = r, ov
        dur = float(best["edited_segment"]["end"]) - float(best["edited_segment"]["start"])
        rows.append((gid, round(dur, 2), v, round(bo, 2), round(e1 - e0, 2)))
    print("=== %s: %d 条 GT 正例 ===" % (case, len(rows)))
    for nm, lo, hi in (("单元<=0.5s", 0.0, 0.5), ("0.5-1.0s", 0.5, 1.0), ("1.0-2.0s", 1.0, 2.0), (">2.0s", 2.0, 1e9)):
        grp = [r for r in rows if lo < r[1] <= hi]
        if not grp:
            continue
        hit = sum(1 for r in grp if r[2] == "HIT"); part = sum(1 for r in grp if r[2] == "part");
        miss = sum(1 for r in grp if r[2] == "MISS")
        print("  %-10s n=%-3d HIT %-3d part %-3d MISS %-3d | MISS 例: %s" % (
            nm, len(grp), hit, part, miss, [r[0] for r in grp if r[2] == "MISS"][:8]))
    print("  覆盖率(单元覆盖 GT 编辑窗比例) 中位数: %.2f | 单元比 GT 窗还短的例: %s" % (
        sorted(r[3] / max(r[4], 1e-6) for r in rows)[len(rows) // 2],
        [r[0] for r in rows if r[1] < r[4] - 0.3][:10]))