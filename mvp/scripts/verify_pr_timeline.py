"""verify_pr_timeline.py — PR CEP 通道自动比对(交接固化版)。

读 PR 面板导出的时间轴 JSON(`work/svl_pr_timeline.json`,由
`%APPDATA%/Adobe/CEP/extensions/com.svl.timelineexport` 面板按钮生成),
与我们的 FCP7 XML 声明值逐项四元组(start/end/in/out)比对。

用法:
  python verify_pr_timeline.py [--xml <fcp7.xml>] [--json <pr_timeline.json>] [--tol 0.02]
默认:
  --xml  mvp/benchmark/user_case/export_smoke/test1-ed.loc.xml
  --json work/svl_pr_timeline.json
退出码:0=全部匹配;1=存在超差/缺失。
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]


def parse_fcp7(xml_path: Path) -> tuple[float, list[dict]]:
    root = ET.parse(xml_path).getroot()
    fps = float(root.find(".//sequence/rate/timebase").text)
    clips = []
    for track_i, track in enumerate(root.findall(".//video/track")):
        for ci in track.findall("clipitem"):
            def f(tag: str):
                e = ci.find(tag)
                return None if e is None else float(e.text) / fps
            clips.append({"track": track_i, "name": ci.find("name").text,
                          "start_s": f("start"), "end_s": f("end"),
                          "in_s": f("in"), "out_s": f("out")})
    return fps, clips


def parse_pr(json_path: Path) -> tuple[float, list[dict]]:
    d = json.loads(json_path.read_text(encoding="utf-8"))
    clips = []
    for t in d["tracks"]:
        for c in t["clips"]:
            clips.append({"track": t["index"], "name": c["name"],
                          "start_s": c["start_s"], "end_s": c["end_s"],
                          "in_s": c["in_s"], "out_s": c["out_s"]})
    return float(d["fps"]), clips


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xml", default=str(BENCH / "mvp/benchmark/user_case/export_smoke/test1-ed.loc.xml"))
    ap.add_argument("--json", default=str(BENCH / "work/svl_pr_timeline.json"))
    ap.add_argument("--tol", type=float, default=0.02)
    args = ap.parse_args()

    xml_fps, xml_clips = parse_fcp7(Path(args.xml))
    pr_fps, pr_clips = parse_pr(Path(args.json))
    print(f"XML: {len(xml_clips)} clipitem @ {xml_fps}fps | PR: {len(pr_clips)} clips @ {pr_fps}fps")

    pr_map: dict[tuple[int, str], list[dict]] = {}
    for c in pr_clips:
        pr_map.setdefault((c["track"], c["name"]), []).append(c)

    matched = mismatched = missing = 0
    worst = 0.0
    fields = ("start_s", "end_s", "in_s", "out_s")
    for xc in xml_clips:
        cands = pr_map.get((xc["track"], xc["name"]))
        if not cands:
            missing += 1
            print(f"  MISSING V{xc['track']} {xc['name']}")
            continue
        pc = cands.pop(0)
        diffs = [abs(xc[k] - pc[k]) for k in fields
                 if xc[k] is not None and pc[k] is not None]
        md = max(diffs) if diffs else 0.0
        worst = max(worst, md)
        if md <= args.tol:
            matched += 1
        else:
            mismatched += 1
            print(f"  MISMATCH V{xc['track']} {xc['name']}: "
                  f"xml={[round(xc[k], 3) for k in fields]} pr={[round(pc[k], 3) for k in fields]} maxdiff={md:.4f}")

    print(f"结果: 匹配={matched} 超差(>{args.tol}s)={mismatched} 缺失={missing} 最大偏差={worst:.4f}s")
    return 0 if (mismatched == 0 and missing == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
