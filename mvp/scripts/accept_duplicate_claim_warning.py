"""重复认领告警（LOC-2002）真实素材冒烟 + 出图复核（2026-09-29 续31）。

对象 = 生产现役基线结果批（``work/fastglobal_default_{case}.results.json``），走**真实导出链路**
``locator_service.export_project``（门槛 → 吸附 → 切点展开 → 告警），验证四件事：

1. 默认开启时 LOC-2002 真的产出（不是只有合成夹具）；
2. ``duplicate_claim_warn=False`` 时该码零出现（开关真的接线）；
3. 告警不动数据：开/关两侧的 EDL **逐字节一致**（只提示不删答案，这是与拒识形态的根本区别）；
4. 每条告警点名的段出**对照图**（左=编辑片该段中帧，右=原片该 clip 中帧），
   由逐张读图确认「确实是同一原片内容被多段指到」—— 指标与文案只是代理，画面才算数。

出图一律走 ``tools/ffmpeg.exe`` 精确 seek（项目护栏：FFmpeg seek），不用 OpenCV 抓帧。
零算法/零 GT 改动。

Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/accept_duplicate_claim_warning.py
  # 只跑指定片: --cases test3,2mkv    不出图: --no-frames    调阈值: --min-ratio 0.9
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault(
    "MEDIA_FFPROBE",
    r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
    r"\static_ffmpeg\bin\win32\ffprobe.exe")
FFMPEG = Path(os.environ["MEDIA_FFMPEG"])
sys.path.insert(0, str(BENCH / "mvp" / "src"))

from app.locator_service import SourceLocatorService  # noqa: E402
from infrastructure.config import load_config  # noqa: E402
from infrastructure.results_repo import load_results  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OUT = BENCH / "work" / "dupwarn_accept"
SEG_RE = re.compile(r"第 ([0-9、]+) 段都指向原片同一区间 ([0-9.]+)-([0-9.]+)s")


def grab_frame(video: Path, t: float, out_png: Path) -> bool:
    """ffmpeg 精确 seek 取一帧（缩放高 360）。"""
    cmd = [str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
           "-ss", f"{max(0.0, t):.3f}", "-i", str(video),
           "-frames:v", "1", "-vf", "scale=-2:360", str(out_png)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    return out_png.exists() and r.returncode == 0


def hstack(left: Path, right: Path, out: Path) -> None:
    cmd = [str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
           "-i", str(left), "-i", str(right), "-filter_complex",
           "[0:v][1:v]hstack=inputs=2,pad=iw+8:ih:8:0:white[s]", "-map", "[s]",
           "-frames:v", "1", str(out)]
    subprocess.run(cmd, capture_output=True, text=True, timeout=180)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="2mkv,test2,test3")
    ap.add_argument("--no-frames", action="store_true")
    ap.add_argument("--min-ratio", type=float, default=None)
    args = ap.parse_args()

    review = OUT / "review"
    OUT.mkdir(parents=True, exist_ok=True)
    review.mkdir(exist_ok=True)
    summary = {"min_ratio": args.min_ratio, "cases": []}

    for case in [c.strip() for c in args.cases.split(",") if c.strip()]:
        batch_path = BENCH / "work" / f"fastglobal_default_{case}.results.json"
        if not batch_path.exists():
            print("MISSING batch: %s" % batch_path)
            continue
        batch = load_results(batch_path)
        src, ed = Path(batch.original_video), Path(batch.edited_video)
        if not src.exists() or not ed.exists():
            print("[%s] 素材不存在, 跳过: %s / %s" % (case, src, ed))
            continue

        cfg = load_config()
        if args.min_ratio is not None:
            cfg.export.duplicate_claim_min_ratio = args.min_ratio
        svc_on = SourceLocatorService(config=cfg, export_root=OUT / case)
        path_on = svc_on.export_project(batch, fmt="edl", filename=f"{case}.loc.edl")
        warns_on = list(svc_on.last_export_warnings)

        cfg2 = load_config()
        if args.min_ratio is not None:
            cfg2.export.duplicate_claim_min_ratio = args.min_ratio
        cfg2.export.duplicate_claim_warn = False
        svc_off = SourceLocatorService(config=cfg2, export_root=OUT / f"{case}_off")
        path_off = svc_off.export_project(batch, fmt="edl", filename=f"{case}.loc.edl")
        warns_off = list(svc_off.last_export_warnings)

        dup_on = [w for w in warns_on if "LOC-2002" in w]
        dup_off = [w for w in warns_off if "LOC-2002" in w]
        identical = Path(path_on).read_bytes() == Path(path_off).read_bytes()
        row = {"case": case, "batch": str(batch_path), "edl": str(path_on),
               "n_dup_warnings": len(dup_on), "n_dup_warnings_when_off": len(dup_off),
               "edl_byte_identical": identical,
               "warnings": warns_on, "frames": []}
        summary["cases"].append(row)

        print("\n===== %s (%d 段) =====" % (case, len(batch.results)))
        print("  LOC-2002 组数=%d | 开关置 False 时=%d | EDL 逐字节一致=%s" % (
            len(dup_on), len(dup_off), identical))
        for w in dup_on:
            print("   ", w)

        if not args.no_frames:
            for wi, w in enumerate(dup_on):
                m = SEG_RE.search(w)
                if not m:
                    print("    [出图跳过] 文案未解析: %s" % w)
                    continue
                segs = [int(x) for x in m.group(1).split("、")]
                for n in segs:                      # 文案是 1-based
                    r = batch.results[n - 1]
                    et = (r.edited.start + r.edited.end) / 2.0
                    ot = (r.original.start + r.original.end) / 2.0
                    ep, op = review / f"{case}_w{wi}_s{n}_ed.png", review / f"{case}_w{wi}_s{n}_om.png"
                    sheet = review / f"{case}_w{wi}_s{n}_pair.png"
                    ok_e, ok_o = grab_frame(ed, et, ep), grab_frame(src, ot, op)
                    if ok_e and ok_o:
                        hstack(ep, op, sheet)
                        row["frames"].append({
                            "warning": wi, "seg": n, "sheet": sheet.name,
                            "edited": [r.edited.start, r.edited.end],
                            "original": [r.original.start, r.original.end],
                            "conf": str(r.confidence.level),
                            "source_span_in_warning": [float(m.group(2)), float(m.group(3))]})
                        print("    组%d 段%d 出图 %s (ed%.1f-%.1f src%.1f-%.1f %s)" % (
                            wi, n, sheet.name, r.edited.start, r.edited.end,
                            r.original.start, r.original.end, r.confidence.level))

    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
    print("\n产物: %s" % (OUT / "summary.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
