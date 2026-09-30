# -*- coding: utf-8 -*-
"""conf_v2（竞品四项加权置信）四片生产回归（2026-09-28 护栏豁免后的移植验收）。

走生产 ``SourceLocatorService.locate`` 全链路，与现役 119/139 基线批同配置
（vote_prior ON / dense OFF），只额外打开 ``confidence.conf_v2_enabled=True``。

  OFF 基线 = work/voteprior_{case}.results.json（2026-09-27 续11, 已存在, 不重跑）
  ON  本批 = work/confv2_{case}.results.json

同时旁路记录逐段 v2 诊断（``work/confv2_diag_{case}.json``）：每次 assess_evidence
用同一 evidence 各跑一遍「关/开」，落盘降档前后档位 + 四项信号值。纯研究侧 monkey-patch，
零 ``mvp/src`` 改动。

置信不参与定位，故三指标（严格/场景/负例）应逐位不变——本脚本实测留证，
并回答真正的问题：**clean 单证据簇型误配（n01/n02 型）是否真被降到 0.6 以下**。

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/rerun_conf_v2.py [case]
评估:
  ... mvp/scripts/measure_four_results.py --pattern "work/confv2_{case}.results.json" \
        --out work/confv2_four_metrics.json
"""
from __future__ import annotations

import copy
import json
import os
import sys
import time
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", (r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
                                        r"\static_ffmpeg\bin\win32\ffprobe.exe"))

sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))

from app.locator_service import SourceLocatorService  # noqa: E402
from engine.confidence import ConfidenceEngine  # noqa: E402
from infrastructure.config import load_config  # noqa: E402

CASES = {
    "2mkv":  {"edited": r"D:\video\1.mp4", "original": r"D:\video\2.mkv"},
    "test1": {"edited": r"D:\ProjectXIXI\test1\test1-ed.mp4",
              "original": r"D:\ProjectXIXI\test1\test1-om.mkv"},
    "test2": {"edited": r"D:\ProjectXIXI\test2\tset2-ed.mp4",
              "original": r"D:\ProjectXIXI\test2\test2-om.mp4"},
    "test3": {"edited": r"D:\ProjectXIXI\test3\test3-ed.mp4",
              "original": r"D:\ProjectXIXI\test3\test3-om.mp4"},
}

_diag: list[dict] = []
_orig_assess = ConfidenceEngine.assess_evidence


def _assess_with_diag(self, evidence):
    """同一 evidence 各跑一遍关/开，记录降档前后（返回开启态结果给生产链路）。"""
    on = _orig_assess(self, evidence)
    off_cfg = copy.deepcopy(self.cfg)
    off_cfg.conf_v2_enabled = False
    off = _orig_assess(ConfidenceEngine(off_cfg), evidence)
    prim = evidence.primary
    _diag.append({
        "edited_interval": list(prim.edited_interval) if prim else None,
        "original_span": list(prim.original_span) if prim else None,
        "level_off": off.confidence.level.value,
        "level_on": on.confidence.level.value,
        "score_off": off.confidence.score,
        "score_on": on.confidence.score,
        "v2": on.confidence_v2,
        "new_reasons": [r for r in on.confidence.reasons if r not in off.confidence.reasons],
    })
    return on


ConfidenceEngine.assess_evidence = _assess_with_diag


class _Progress:
    def __init__(self):
        self.t_last = 0.0
        self.stage = None

    def __call__(self, ev):
        now = time.monotonic()
        stage = getattr(getattr(ev, "stage", None), "value", "?")
        if stage != self.stage or now - self.t_last > 15:
            self.stage = stage
            self.t_last = now
            print("    [%s] %s %s/%s" % (stage, getattr(ev, "message", ""),
                                         getattr(ev, "current", 0),
                                         getattr(ev, "total", 0) or "?"), flush=True)


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    cfg = load_config()
    cfg.pipeline.vote_prior_enabled = True     # 与 119/139 基线批同配置
    cfg.pipeline.dense_recheck_enabled = False
    c = cfg.pipeline.confidence
    c.conf_v2_enabled = True
    print("cfg: conf_v2=ON local=%.2f coarse=%.2f consistency=%.2f margin=%.2f min=%.2f "
          "(gate %s/%s/%s/%s) vote_prior=%s dense=%s"
          % (c.conf_v2_local_weight, c.conf_v2_coarse_weight, c.conf_v2_consistency_weight,
             c.conf_v2_margin_weight, c.conf_v2_min_score, c.conf_v2_min_valid_samples,
             c.conf_v2_min_support_ratio, c.conf_v2_min_local_score,
             c.conf_v2_min_candidate_margin, cfg.pipeline.vote_prior_enabled,
             cfg.pipeline.dense_recheck_enabled), flush=True)
    print("cfg: data_dir=%s index_fps=%s" % (cfg.data_dir, cfg.pipeline.index_sampling_fps),
          flush=True)

    srv = SourceLocatorService(config=cfg)
    b = srv.backend
    print("BACKEND_SELECTED type=%s device=%s dtype=%s"
          % (type(b).__name__, getattr(b, "device_name", lambda: "?")(),
             getattr(b, "device_type", lambda: "?")()), flush=True)

    for name, paths in CASES.items():
        if only and name != only:
            continue
        out = BENCH / "work" / ("confv2_%s.results.json" % name)
        if out.exists() and not os.environ.get("SVL_FORCE_RERUN"):
            print("[skip] %s exists" % out.name, flush=True)
            continue
        del _diag[:]
        t0 = time.monotonic()
        print("[case %s] locate start (confv2 ON)" % name, flush=True)
        try:
            batch = srv.locate(paths["edited"], paths["original"], on_progress=_Progress())
            out.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1),
                           encoding="utf-8")
            (BENCH / "work" / ("confv2_diag_%s.json" % name)).write_text(
                json.dumps(_diag, ensure_ascii=False, indent=1), encoding="utf-8")
            moved = sum(1 for d in _diag if d["level_off"] != d["level_on"])
            print("[case %s] done %.1fs -> %s (%d segments, %d 降档)"
                  % (name, time.monotonic() - t0, out.name, len(batch.results), moved),
                  flush=True)
        except Exception as exc:
            import traceback
            print("[case %s] FAILED: %s: %s" % (name, type(exc).__name__, exc), flush=True)
            traceback.print_exc()
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
