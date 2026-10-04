# -*- coding: utf-8 -*-
"""方案1探针 — TN 切分 × 查询采样喂饱 = 检验「TN 效果差异是采样耦合」假设。

背景（FINDINGS_QUERY_UNIT_SWAP §3.1 / FINDINGS_TRANSNETV2_SEGMENTATION A1）：
  A1 把编辑侧切分换成 TransNetV2 但保留 2fps 查询采样 → 严格 −16。续7 分档交叉表证明
  MISS 全部落在 0.5–1.0s 细单元（>1s 单元 0 MISS）⇒ 根因是 TN 细单元在 2fps 网格下只剩
  1–2 帧查询、证据饿死，不是 TN 切不准（边界双向 recall 0.76–0.98）。

本探针固定其余变量，只变查询采样 fps，跑两臂四片：
  臂 A  edited_segment_fps=2.0（复现 A1「饿」）
  臂 B  edited_segment_fps=8.0（喂饱每个 TN 细单元）
两臂都关 shot_split / patch_refine（隔离「切分×采样」对定位层的纯效应 + 加速），
fast_global 保持默认、索引 1fps 不变、编辑缓存关闭。

判读：
  B 显著优于 A（−16 翻正/收窄）⇒ 差异确为采样耦合、可解，TN+喂饱值得进 runtime 评估；
  B ≈ A（仍负）⇒ TN 切碎本身与我方定位链「防碎片化」约束冲突，喂饱不救 ⇒ TN 无增量。

零 mvp/src 改动（monkey-patch，与 A1 同款纪律）。产物 work/tnfed_{fps}_{case}.results.json
（不覆盖 A1 的 work/tn_*.results.json）。

跑：
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/rerun_tn_fed.py
测：
  python mvp/scripts/measure_four_results.py --pattern "work/tnfed_2_{case}.results.json" --out work/_four_tnfed2.json
  python mvp/scripts/measure_four_results.py --pattern "work/tnfed_8_{case}.results.json" --out work/_four_tnfed8.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import rerun_transnet_runtime as a1  # noqa: E402  (复用 TN 切分 harness + CASES + _Progress + env)
import app.locator_service as ls  # noqa: E402
from app.locator_service import SourceLocatorService  # noqa: E402
from infrastructure.config import load_config  # noqa: E402
from infrastructure.logging import configure_logging  # noqa: E402
from device.directml_backend import DirectMLBackend  # noqa: E402

BENCH = Path(r"D:\claudework\benchmark")
import sys  # noqa: E402
FPS_ARMS = tuple(float(x) for x in sys.argv[1:]) or (2.0, 8.0)


def run_arm(fps: float, case: str, paths: dict) -> dict:
    out = BENCH / "work" / ("tnfed_%d_%s.results.json" % (int(fps), case))
    if out.exists():
        print("  %s fps=%g: skip (exists)" % (case, fps), flush=True)
        return {}
    cfg = load_config()
    cfg.pipeline.edited_segment_fps = fps
    cfg.pipeline.shot_split_enabled = False
    cfg.pipeline.patch_refine_enabled = False
    cfg.pipeline.edited_cache_enabled = False
    srv = SourceLocatorService(config=cfg)
    t0 = time.monotonic()
    batch = srv.locate(paths["edited"], paths["original"], on_progress=a1._Progress())
    out.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
    n_high = sum(1 for r in batch.results if r.confidence.level.value == "HIGH")
    unresolved = sum(1 for r in batch.results if r.failure_reason)
    print("  %s fps=%g: %d 段 HIGH=%d unresolved=%d elapsed=%.1fs -> %s"
          % (case, fps, len(batch.results), n_high, unresolved,
             time.monotonic() - t0, out.name), flush=True)
    return {"case": case, "fps": fps, "segments": len(batch.results),
            "high": n_high, "unresolved": unresolved, "elapsed": round(time.monotonic() - t0, 1)}


def main() -> int:
    configure_logging(stream=sys.stdout)
    ls.SourceLocatorService._segment_twopass_flash = a1._segment_transnet

    cfg = load_config()
    srv_probe = SourceLocatorService(config=cfg)
    assert isinstance(srv_probe.backend, DirectMLBackend), \
        "必须 DirectMLBackend, 实际 %s" % type(srv_probe.backend).__name__
    del srv_probe
    print("TN_PROVIDER=%s  arms_fps=%s  (shot_split/patch_refine OFF, index 1fps, edited_cache OFF)"
          % (a1.TN_PROVIDER, FPS_ARMS), flush=True)

    summary = []
    for fps in FPS_ARMS:
        print("\n=== 臂 fps=%g (TN 切分 + %gfps 查询) ===" % (fps, fps), flush=True)
        for case, paths in a1.CASES.items():
            r = run_arm(fps, case, paths)
            if r:
                summary.append(r)
    (BENCH / "work" / "tnfed_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nALL DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
