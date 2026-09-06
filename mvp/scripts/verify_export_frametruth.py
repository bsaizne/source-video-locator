"""verify_export_frametruth.py — 导出工程文件的自动帧比对验收（无 NLE）。

Phase 22 第 6 项「真实导出产物验收」的机器可执行部分：解析导出的 CMX3600 EDL
（或 FCP7 XML 的 clipitem），对每个事件用 ffmpeg 抽「编辑片 record in 点帧」与
「源片 source in 点帧」，用产品冻结的 DINOv2 CLS 特征算余弦相似度；并以
``+SHIFT`` 秒错位抽帧作对照。定位本身正确的前提下：
- 时间码/帧号换算正确 → 真值对相似度应显著高于错位对照；
- 换算有系统误差（fps/start_time/名义帧率拆分错）→ 真值对塌到对照水平。

用法（venv python，需 MEDIA_FFPROBE/MEDIA_FFMPEG 或默认可解析）：
  python mvp/scripts/verify_export_frametruth.py --edl <path.edl> \
      --edited <edited.mp4> --original <orig.mkv> [--shift 10.0] [--xml <path.xml>]

判定（三项分开报，全部满足才 PASS）：
1. roundtrip：TC 反解秒 vs 注释 orig= 计划值，逐事件误差 ≤ 半帧（确定性检查，
   直接验证时间码换算本身）；
2. aligned：真值对 sim>=0.60 的事件数 >= max(2, n//5)——系统性换算错误（fps/
   start_time/名义帧率拆分错）会把对齐子集打到 0，这是换算错误的判据；
3. margin：mean(true) > mean(control)。
帧相似度对「定位窗口内子镜头偏移/暗帧」天然不敏感为高（噪声估计器），单项低
sim 不判 FAIL，只在报告里展示。
退出码：0=通过，1=不通过，2=无法执行。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

_EDL_EVENT = re.compile(
    r"^\s*\d+\s+(\S+)\s+V\s+C\s+(\d\d):(\d\d):(\d\d):(\d\d)\s+(\d\d):(\d\d):(\d\d):(\d\d)"
    r"\s+(\d\d):(\d\d):(\d\d):(\d\d)\s+(\d\d):(\d\d):(\d\d):(\d\d)")
_TC_ANY = re.compile(r"(\d\d):(\d\d):(\d\d):(\d\d)")


def probe_fps(ffprobe: str, video: Path) -> float:
    """ffprobe avg_frame_rate -> float（0 视为失败）。"""
    import json
    from media.ffmpeg._runner import check_run
    out = check_run([str(ffprobe), "-show_streams", "-select_streams", "v:0",
                     "-of", "json", str(video)])
    rate = json.loads(out)["streams"][0]["avg_frame_rate"]
    num, _, den = rate.partition("/")
    f = float(num) / float(den) if den else float(num)
    return f


def tc_to_seconds(h: str, m: str, s: str, f: str, nominal: int, real_fps: float) -> float:
    """NDF timecode -> 秒（帧总数 / 实测 fps；与 timecode_ndf 的正向换算互逆）。"""
    frames = ((int(h) * 3600 + int(m) * 60 + int(s)) * nominal) + int(f)
    return frames / real_fps


def parse_edl(path: Path) -> list[dict]:
    """EDL 事件 -> [{src_in, src_out, rec_in, rec_out, note}]（秒在调用方换算）。"""
    events = []
    h = m = s = f = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        mo = _EDL_EVENT.match(raw)
        if mo:
            g = mo.groups()
            h, m, s, f = g[1:5]
            events.append({"reel": g[0], "tc": (h, m, s, f),
                           "rec_tc": g[9:13], "note": ""})
            continue
        if raw.startswith("* LOCATOR:") and events:
            events[-1]["note"] = raw
    return events


def parse_xml_clipitems(path: Path) -> list[dict]:
    """FCP7 XML clipitem -> [{in_s, out_s, start_s, end_s}]（用 file/sequence rate 反解）。"""
    import xml.etree.ElementTree as ET
    root = ET.parse(path).getroot()
    out = []
    for ci in root.findall(".//clipitem"):
        def _rate_of(el):
            tb = int(el.findtext(".//rate/timebase"))
            ntsc = el.findtext(".//rate/ntsc") == "TRUE"
            return tb / (1.001 if ntsc else 1.0)
        src_fps = _rate_of(ci.find("file"))
        seq_fps = _rate_of(ci)
        out.append({
            "in_s": int(ci.findtext("in")) / src_fps,
            "out_s": int(ci.findtext("out")) / src_fps,
            "start_s": int(ci.findtext("start")) / seq_fps,
            "end_s": int(ci.findtext("end")) / seq_fps,
            "name": ci.findtext("name") or "",
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--edl", required=True)
    ap.add_argument("--edited", required=True)
    ap.add_argument("--original", required=True)
    ap.add_argument("--ffprobe", default=None,
                    help="ffprobe 路径；缺省走 MEDIA_FFPROBE/仓库 tools/PATH 解析")
    ap.add_argument("--shift", type=float, default=10.0, help="对照组源侧错位秒数")
    ap.add_argument("--xml", default=None, help="同时校验的 FCP7 XML 路径")
    args = ap.parse_args()

    from media.ffmpeg import FFmpegIO
    from media.ffmpeg._runner import resolve_binaries
    from device import pick_best_available
    from infrastructure.config import AppConfig
    import numpy as np

    edl, edited, original = Path(args.edl), Path(args.edited), Path(args.original)
    _, ffprobe = resolve_binaries(None, args.ffprobe)
    src_fps = probe_fps(ffprobe, original)
    rec_fps = probe_fps(ffprobe, edited)
    if not src_fps or not rec_fps:
        print("FAIL: ffprobe fps unavailable")
        return 2
    nominal_src = max(1, round(src_fps))
    io = FFmpegIO()
    backend = pick_best_available(AppConfig())
    print(f"source fps={src_fps:.4f} (nominal {nominal_src})  edited fps={rec_fps:.4f}  "
          f"backend={backend.device_name()}")

    events = parse_edl(edl)
    if not events:
        print("FAIL: no EDL events parsed")
        return 2
    duration = io.metadata(original).duration

    q_frames, t_frames, c_frames = [], [], []
    for ev in events:
        h, m, s, f = ev["tc"]
        src_in = tc_to_seconds(h, m, s, f, nominal_src, src_fps)
        rh, rm, rs, rf = ev["rec_tc"]
        rec_in = tc_to_seconds(rh, rm, rs, rf, max(1, round(rec_fps)), rec_fps)
        ev["src_in"], ev["rec_in"] = src_in, rec_in
        # 注释里的计划值（orig=），供往返检查
        mo = re.search(r"orig=([\d.]+)-([\d.]+)", ev["note"])
        ev["plan_src_in"] = float(mo.group(1)) if mo else None
        q_frames.append(io.grab_frame(edited, rec_in))
        t_frames.append(io.grab_frame(original, src_in))
        c_frames.append(io.grab_frame(original, min(src_in + args.shift, max(0.0, duration - 1.0))))

    q = backend.embed_frames(q_frames)
    t = backend.embed_frames(t_frames)
    c = backend.embed_frames(c_frames)
    true_sims = (q * t).sum(axis=1)
    ctrl_sims = (q * c).sum(axis=1)

    print(f"\n{'#':>4} {'rec_in':>9} {'src_in':>9} {'plan':>9} {'true':>6} {'ctrl':>6}")
    for i, ev in enumerate(events):
        plan = f"{ev['plan_src_in']:>9.2f}" if ev["plan_src_in"] is not None else " " * 9
        print(f"{i + 1:>4} {ev['rec_in']:>9.2f} {ev['src_in']:>9.2f} {plan} "
              f"{true_sims[i]:>6.3f} {ctrl_sims[i]:>6.3f}  {ev['note'][2:60]}")
    mt, mc = float(true_sims.mean()), float(ctrl_sims.mean())
    half_frame = 0.5 / src_fps
    rt_bad = [i for i, ev in enumerate(events)
              if ev["plan_src_in"] is not None
              and abs(ev["src_in"] - ev["plan_src_in"]) > half_frame]
    aligned = int((true_sims >= 0.60).sum())
    n = len(events)
    print(f"\nroundtrip(<=半帧 {half_frame:.4f}s): {n - len(rt_bad)}/{n} "
          f"{'OK' if not rt_bad else f'BAD {rt_bad}'}")
    print(f"aligned(sim>=0.60): {aligned}/{n} (门槛 >= {max(2, n // 5)})")
    print(f"mean true={mt:.3f}  mean control(+{args.shift}s)={mc:.3f}  "
          f"margin={mt - mc:+.3f}")

    if args.xml:
        items = parse_xml_clipitems(Path(args.xml))
        if items:
            xs = np.array([it["in_s"] for it in items])
            print(f"XML clipitems={len(items)} in_s range={xs.min():.2f}-{xs.max():.2f} "
                  f"(first 3: {[round(it['in_s'], 2) for it in items[:3]]})")

    ok = (not rt_bad) and aligned >= max(2, n // 5) and mt > mc
    print("VERDICT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
