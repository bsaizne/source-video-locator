# -*- coding: utf-8 -*-
"""attr_env_phase_table — 打包态性能归因：把各臂产物折成同一张「阶段耗时表」。

参与对照（同素材 test2、同优化代码、同索引复用，唯一变量是运行形态）：
  E2E 打包整包（UI+CdU 观察在场）——从包内后端日志 `%APPDATA%/Video Locator AI/logs/
    video_locator.log` 的逐分钟时间戳复原阶段边界（该轮 r3 包，2026-10-01 02:45 起）
  打包 headless（backend.exe，无 UI/无预览/无观察）——`work/pkg_attr/headless_test2.events.csv`
  源码树 + HTTP（run_backend.py，同 env/同数据目录）——`work/pkg_attr/venvhttp_test2.events.csv`
  源码树直跑（venv，无 HTTP）——`work/pkg_attr/armA2_lab.console.log`（带 elapsed 秒）

用法:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/attr_env_phase_table.py
缺哪个臂就少列哪一行，不编数。
"""
from __future__ import annotations

import csv
import datetime as dt
import re
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
OUT = BENCH / "work" / "pkg_attr"
PKG_LOG = (Path.home() / "AppData" / "Roaming" / "Video Locator AI"
           / "logs" / "video_locator.log")
LAB_CONSOLE = OUT / "armA2_lab.console.log"

# 阶段名 -> 识别关键词（消息文案来自 locator_service / shot_split / patch_refine）
SPLIT_MSG = "多镜头段切镜拆分"
REFINE_MSG = "patch 局部精排"


def _secs(ts: dt.datetime) -> float:
    return ts.timestamp()


def e2e_rows() -> list[tuple[float, str]]:
    """从打包日志复原 E2E 那一轮的阶段边界（毫秒时间戳）。"""
    rows: list[tuple[float, str]] = []
    if not PKG_LOG.exists():
        return rows
    submit = None
    seg_done = None
    last_near = None
    done = None
    for line in PKG_LOG.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("2026-10-01 0"):
            continue
        ts = dt.datetime.strptime(line[:23], "%Y-%m-%d %H:%M:%S,%f")
        if "POST /api/tasks/analyze" in line:
            submit = ts if submit is None or ts < submit else submit
        elif "twopass+flash final segments" in line:
            seg_done = ts
        elif "patch v2 nearfield" in line:
            last_near = ts
        elif (submit and seg_done and last_near and done is None
              and "/api/tasks/" not in line
              and ("POST /api/preview" in line or "GET /api/results" in line)
              and ts > last_near):
            done = ts
    if not (submit and seg_done and last_near and done):
        return rows
    t0 = _secs(submit)
    rows.append((0.0, "submit"))
    rows.append((_secs(seg_done) - t0, "segmentation done (54 segs)"))
    rows.append((_secs(last_near) - t0, "per-segment loop done"))
    rows.append((_secs(done) - t0, "locate finished (first post-done request)"))
    return rows


def events_rows(path: Path) -> list[tuple[float, str]]:
    """harness 的 (t_s, message) 阶段变化序列 -> 同样的边界行。"""
    rows: list[tuple[float, str]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        first_retr = None
        last_conf = None
        split_t = None
        refine_done = None
        final_t = None
        prev = None
        for r in rdr:
            t = float(r["t_s"])
            msg = (r["message"] or "").strip()
            st = r["status"]
            if "segment 1/" in msg and "retrieval" in msg and first_retr is None:
                first_retr = t
            if "confidence" in msg:
                last_conf = t
            if SPLIT_MSG in msg and split_t is None:
                split_t = t
            if REFINE_MSG in msg:
                refine_done = t
            if st in ("completed", "failed", "cancelled") and prev not in (st,):
                final_t = t
                break
            prev = st
        if first_retr is not None:
            rows.append((first_retr, "segmentation done -> per-segment loop"))
        if last_conf is not None:
            rows.append((last_conf, "per-segment loop done"))
        if split_t is not None:
            rows.append((split_t, "shot_split start"))
        if refine_done is not None and refine_done != split_t:
            rows.append((refine_done, "patch_refine last report"))
        if final_t is not None:
            rows.append((final_t, "locate finished (%s)" % (st or "?")))
    return rows


def lab_rows() -> list[tuple[float, str]]:
    """venv 直跑（带 elapsed 秒的 stdout）里的阶段边界。"""
    rows: list[tuple[float, str]] = []
    if not LAB_CONSOLE.exists():
        return rows
    text = LAB_CONSOLE.read_text(encoding="utf-8", errors="replace")
    def find(pat):
        hits = re.findall(r"\[\+\s*([\d.]+)s\].*%s" % pat, text)
        return hits
    retr = find(r"segment 1/\d+: retrieval")
    conf = find(r"segment \d+/\d+: confidence")
    split = find(re.escape(SPLIT_MSG))
    refine = find(r"patch 局部精排 \d+/\d+")
    done = find(r"\] done ")
    if retr:
        rows.append((float(retr[0]), "segmentation done -> per-segment loop"))
    if conf:
        rows.append((float(conf[-1]), "per-segment loop done"))
    if split:
        rows.append((float(split[0]), "shot_split start"))
    if refine:
        rows.append((float(refine[-1]), "patch_refine last report"))
    if done:
        rows.append((float(done[-1]), "locate finished"))
    return rows


def main() -> int:
    arms = [
        ("E2E 打包整包(UI/预览/CUA 在场)", e2e_rows()),
        ("打包 headless", events_rows(OUT / "headless_test2.events.csv")),
        ("源码树+HTTP", events_rows(OUT / "venvhttp_test2.events.csv")),
        ("源码树直跑(venv)", lab_rows()),
    ]
    arms = [(name, rows) for name, rows in arms if rows]
    if not arms:
        print("没有任何臂的产物可读——先跑 attr_packaged_headless.py / attr_lab_arm_timestamped.py")
        return 1

    keys = ["切分+检索/定位/置信 主循环", "shot_split", "patch_refine", "总计"]
    print("阶段耗时（秒）\n")
    for name, rows in arms:
        marks = {label: t for t, label in rows}
        total = next((sec for sec, label in rows if label.startswith("locate finished")), None)
        loop_end = marks.get("per-segment loop done")
        split = marks.get("shot_split start")
        refine = marks.get("patch_refine last report")
        parts = {}
        if loop_end is not None:
            parts["切分+检索/定位/置信 主循环"] = loop_end
        if split is not None and refine is not None:
            parts["shot_split"] = refine - split
        if refine is not None and total is not None:
            parts["patch_refine"] = total - refine
        if total is not None:
            parts["总计"] = total
        print("  ".join([name.ljust(28)] +
                        ["%s=%s" % (k, "-" if parts.get(k) is None else "%.0f" % parts[k])
                         for k in keys]))
    print("\n注：E2E 臂无 shot_split/patch_refine 的独立日志行，两者合并在「主循环之后」的静默段——"
          "该行用 总计-主循环 反算，不拆细。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
