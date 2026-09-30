# -*- coding: utf-8 -*-
"""D 段接收侧预演 (2026-09-26): 用我方 perfopt 批反向构造对方 localization.json 格式,
全链路验证 --loc 导入 → measure 四片评估, 确保 D 段产物到货即插即用。

产出: work/_loc_dryrun/localization_{case}.json (对方 schema)
      work/_loc_dryrun/proxy_{case}.results.json (我方 schema, 经 --loc 通道)
预期: 链路零崩溃; 数字 = 我方「main-span-only 口径」(导入通道只填主定位,
original_segments 为空 —— 与 D 段产物口径一致, 该差值即 D 段对照时的已知口径下限)。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
B = Path(__file__).resolve().parents[2]
OUT = B / "work" / "_loc_dryrun"
PY = sys.executable
CONF_SCORE = {"HIGH": 0.8, "MEDIUM": 0.6, "LOW": 0.3}
CASES = ["2mkv", "test1", "test2", "test3"]


def build_loc(case: str) -> int:
    src = json.loads((B / "work" / ("rerun_%s_perfopt.results.json" % case)).read_text(encoding="utf-8"))
    matches = []
    for r in src["results"]:
        es, ee = r["edited_segment"]["start"], r["edited_segment"]["end"]
        os_, oe = r["original"]["candidate_start"], r["original"]["candidate_end"]
        lvl = getattr(getattr(r, "get", lambda k: None)("confidence"), "level", None) if isinstance(r.get("confidence"), dict) else r.get("confidence")
        # results.json 已是 dict 形态
        lvl = (r.get("confidence") or {}).get("level") if isinstance(r.get("confidence"), dict) else r.get("confidence")
        nis = bool(r.get("not_in_source", False)) or (oe - os_) <= 0.01
        matches.append({
            "commentary_start_ms": int(round(es * 1000)), "commentary_end_ms": int(round(ee * 1000)),
            "source_start_ms": int(round(os_ * 1000)), "source_end_ms": int(round(oe * 1000)),
            "confidence": CONF_SCORE.get(lvl, 0.6) if not nis else None,
            "not_in_source": nis,
            "method": "dryrun-from-perfopt",
        })
    loc = {"source": src.get("original_video"), "commentary": src.get("edited_video"),
           "matches": matches}
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / ("localization_%s.json" % case)
    p.write_text(json.dumps(loc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("built %s (%d matches)" % (p.name, len(matches)))
    return 0


def main() -> int:
    for case in CASES:
        build_loc(case)
        rc = subprocess.call([PY, str(B / "mvp" / "scripts" / "import_competitor_proxy.py"),
                              "--case", case, "--loc", str(OUT / ("localization_%s.json" % case))])
        if rc:
            return rc
    print()
    subprocess.call([PY, str(B / "mvp" / "scripts" / "measure_four_results.py"),
                     "--pattern", "work/_loc_dryrun/proxy_{case}.results.json",
                     "--out", "work/_loc_dryrun/four_metrics.json"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
