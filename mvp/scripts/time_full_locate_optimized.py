# -*- coding: utf-8 -*-
"""整条 locate() 优化后墙钟 + 全生产路径逐位一致验证（续34 收尾）。

动机：probe_split_patch_timing.py 的 1.90× 是「旋钮段墙钟」（off批→两旋钮），不是用户
实际体验的整条 locate。本脚本跑**完整 srv.locate()**（双旋钮开、优化后代码），一次拿两样：
  1) 真实用户侧墙钟（测量，替代 FINDINGS 里推导的 2.4~3× 估值）；
  2) 整条 locate 输出 vs 续33 原始串行产物 on_{case}.results.json **逐位一致**
     => 把零语义验证从「旋钮段微探针」升级到「完整生产路径」（最强证明）。

pre-knob 管线与旋钮无关（常量 P）：opt_full = P + 旋钮段(665)，serial_full = P + 旋钮段(1262)，
故 full-locate 提速 = (P+1262)/(P+665)，并与档案 ON 臂 ~31min 交叉核对。

不覆盖 work/spl_patch_arms/on_{case}.results.json（续33 参照物）；产物落 work/spl_patch_timing/。

Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/time_full_locate_optimized.py [case]
"""
from __future__ import annotations

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
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

from app.locator_service import SourceLocatorService  # noqa: E402
from device.directml_backend import DirectMLBackend  # noqa: E402
from domain.models import ResultBatch  # noqa: E402
from infrastructure.config import load_config  # noqa: E402
from rerun_fast_global import CASES, _Progress  # noqa: E402

OUT = BENCH / "work" / "spl_patch_timing"


def span_of(r) -> dict:
    """与 probe_split_patch_timing.py 同规格（排除 shot_split uuid result_id）。"""
    return {
        "ed": [round(r.edited.start, 3), round(r.edited.end, 3)],
        "og": [round(r.original.start, 3), round(r.original.end, 3)],
        "segs": sorted([[round(s.start, 3), round(s.end, 3)] for s in r.original_segments]),
        "conf": r.confidence.level.value,
        "nis": bool(r.not_in_source),
    }


def main() -> int:
    case = sys.argv[1] if len(sys.argv) > 1 else "test1"
    paths = CASES[case]
    srv = SourceLocatorService(config=load_config())
    assert isinstance(srv.backend, DirectMLBackend), \
        "必须 DirectMLBackend, 实际 %s" % type(srv.backend).__name__
    cfg = srv.config.pipeline
    assert cfg.fast_global_enabled is True, "基线要求 fast_global_enabled=True（现役默认）"
    cfg.shot_split_enabled = True
    cfg.patch_refine_enabled = True
    print("BACKEND_SELECTED type=%s | shot_split=%s patch_refine=%s (优化后代码, 整条 locate)"
          % (type(srv.backend).__name__, cfg.shot_split_enabled, cfg.patch_refine_enabled),
          flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    batch = srv.locate(paths["edited"], paths["original"], on_progress=_Progress())
    wall = time.monotonic() - t0
    fp = OUT / ("fulllocate_on_%s.results.json" % case)
    fp.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n[full locate | %s] 墙钟 %.1fs = %.2f min  (%d 段) -> %s"
          % (case, wall, wall / 60, len(batch.results), fp.name), flush=True)

    # 逐位一致：整条 locate 输出 vs 续33 原始串行产物
    ref_fp = BENCH / "work" / "spl_patch_arms" / ("on_%s.results.json" % case)
    if ref_fp.exists():
        ref = ResultBatch.from_dict(json.loads(ref_fp.read_text(encoding="utf-8")))
        so = [span_of(r) for r in batch.results]
        sr = [span_of(r) for r in ref.results]
        ident = (so == sr)
        print("[identity] opt_full_locate(%d spans) == on_%s.results.json(%d spans, 原始串行) : %s"
              % (len(so), case, len(sr), ident), flush=True)
        if not ident:
            nd = 0
            for i, (x, y) in enumerate(zip(so, sr)):
                if x != y:
                    nd += 1
                    if nd <= 10:
                        print("  idx", i, "\n   opt", json.dumps(x, ensure_ascii=False),
                              "\n   ref", json.dumps(y, ensure_ascii=False), flush=True)
            print("  differing idx:", nd, " len equal:", len(so) == len(sr), flush=True)
        print(">>> FULL-LOCATE BIT-IDENTICAL:", ident, flush=True)
    else:
        print("[identity] 参照 %s 不存在, 跳过比对" % ref_fp.name, flush=True)

    # 常量 P 反推 + 与档案交叉核对（ASCII 箭头, 避免 GBK 控制台 UnicodeEncodeError）
    print("\n== 常量 P 反推（pre-knob 管线, 与旋钮无关）==", flush=True)
    print("  opt_full_locate 墙钟       = %.1fs" % wall, flush=True)
    print("  优化旋钮段(probe 实测)     = 664.9s  => P ~= %.1fs" % (wall - 664.9), flush=True)
    print("  串行旋钮段(probe 实测)     = 1262.3s => serial_full ~= P+1262.3 = %.1fs = %.1f min"
          % (wall - 664.9 + 1262.3, (wall - 664.9 + 1262.3) / 60), flush=True)
    print("  full-locate 提速(推导)     = %.2fx" % ((wall - 664.9 + 1262.3) / wall), flush=True)
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
