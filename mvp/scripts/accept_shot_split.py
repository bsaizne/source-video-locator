# -*- coding: utf-8 -*-
"""段级拆分（形态4 runtime 化）真实验收（2026-09-30，test2 最小片冒烟）。

对照口径：同一 pipeline、`pipeline.shot_split_enabled` 关/开各跑一次完整定位，
导出 EDL 对比（+ 结果批 JSON 对比）。验证点：
  1. 关侧结果批与生产现役一致（fastglobal_default_test2 对照主 span 逐段一致）
  2. 开侧结果数 ≥ 关侧（多镜段拆出子段），严格口径结构性零回退
     （关/开两侧各自对 GT 跑 measure：严格 ≥ 关侧、负例不增）
  3. EDL 开侧含新增 clip（+8 型收益的 runtime 体现）
产物参数化 -> `work/shot_split_accept/`。
Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/accept_shot_split.py
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
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

sys.stdout.reconfigure(encoding="utf-8")

from app.locator_service import SourceLocatorService  # noqa: E402
from device.directml_backend import DirectMLBackend   # noqa: E402
from infrastructure.config import load_config          # noqa: E402

OUT = BENCH / "work" / "shot_split_accept"
CASE_ORIG = json.loads((BENCH / "work/fastglobal_default_test2.results.json")
                       .read_text(encoding="utf-8"))
GT_REL = BENCH / "datasets/real/ground_truth_test2.json"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    orig = CASE_ORIG["original_video"]
    edited = CASE_ORIG["edited_video"]
    batches = {}
    for flag in (False, True):
        svc = SourceLocatorService(config=load_config())
        assert isinstance(svc.backend, DirectMLBackend), \
            f"必须 DirectMLBackend, 实际 {type(svc.backend).__name__}"
        svc.config.pipeline.shot_split_enabled = flag
        print("shot_split_enabled=%s locate..." % flag, flush=True)
        batch = svc.locate(edited, orig)
        tag = "off" if not flag else "on"
        (OUT / f"test2_{tag}.results.json").write_text(
            json.dumps(batch.to_dict(), ensure_ascii=False, indent=1),
            encoding="utf-8")
        edl = svc.export_project(batch, fmt="edl",
                                 filename=f"test2_{tag}.edl", out_dir=OUT)
        batches[flag] = batch
        print("  results=%d edl=%s" % (len(batch.results), Path(edl).name), flush=True)
    # 1) 关侧与生产现役逐段一致（主 span）
    prod = json.loads((BENCH / "work/fastglobal_default_test2.results.json")
                      .read_text(encoding="utf-8"))["results"]
    off = [r.to_dict() for r in batches[False].results]
    same = len(prod) == len(off) and all(
        abs(p["original"]["candidate_start"] - q["original"]["candidate_start"]) < 0.01
        and abs(p["original"]["candidate_end"] - q["original"]["candidate_end"]) < 0.01
        for p, q in zip(prod, off))
    print("关侧与生产现役主 span 逐段一致: %s (%d 段)" % (same, len(prod)))
    # 2) 严格口径零回退（GT measure）
    sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
    from measure_shot_recall import evaluate  # noqa: E402
    gt = json.loads(GT_REL.read_text(encoding="utf-8"))
    with contextlib.redirect_stdout(io.StringIO()):
        m_off = evaluate(gt, [r.to_dict() for r in batches[False].results])
        m_on = evaluate(gt, [r.to_dict() for r in batches[True].results])
    print("严格: %d→%d (门 ≥%d) | 导出实得: %d→%d | FP: %d→%d" % (
        m_off["strict_hit"], m_on["strict_hit"], m_off["strict_hit"],
        m_off["main_hit"], m_on["main_hit"], m_off["fp"], m_on["fp"]))
    ok = (same and m_on["strict_hit"] >= m_off["strict_hit"]
          and m_on["fp"] <= m_off["fp"] and len(batches[True].results) >= len(batches[False].results))
    print("验收: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
