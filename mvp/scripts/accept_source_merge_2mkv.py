# -*- coding: utf-8 -*-
"""多原片合并真实素材验收（2026-09-29 video.concat 移植, 续27）。

流程（对齐生产现役基线口径, 零配置覆写 = 出厂 load_config()）：
  1) 把 D:/video/2.mkv（hevc 10bit, 7667.5s, 1.0GB）在**关键帧**处无损切成两半；
  2) SourceLocatorService.merge_originals(两半) —— 期望 mode=copy、稳定命名、
     二次调用 reused=True；
  3) DirectML 硬断言后 locate(D:/video/1.mp4, 合并片) —— 全新文件建索引 + 全链路；
  4) 用与四片验收批同一 GT(ground_truth_v4.json) evaluate，逐 ID 与基线批
     work/fastglobal_default_2mkv.results.json 对比，期望零翻转。

产物: work/merge_accept/{parts,merged_probe.json,locate_meta.json,
       source_merge_2mkv.results.json,source_merge_vs_baseline.json}

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/accept_source_merge_2mkv.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", (r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
                                        r"\static_ffmpeg\bin\win32\ffprobe.exe"))
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
sys.path.insert(0, str(BENCH / "mvp"))

FFMPEG = Path(os.environ["MEDIA_FFMPEG"])
FFPROBE = Path(os.environ["MEDIA_FFPROBE"])
BASE = Path(r"D:\video\2.mkv")
EDITED = Path(r"D:\video\1.mp4")
WORK = BENCH / "work" / "merge_accept"
BASELINE_RESULTS = BENCH / "work" / "fastglobal_default_2mkv.results.json"

from app.locator_service import SourceLocatorService  # noqa: E402
from device.directml_backend import DirectMLBackend  # noqa: E402
from infrastructure.config import load_config  # noqa: E402
from media.ffmpeg import FFmpegIO  # noqa: E402
from measure_shot_recall import evaluate  # noqa: E402
from rerun_fast_global import _Progress  # noqa: E402


def _run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, capture_output=True, check=False,
                       creationflags=0x08000000 if os.name == "nt" else 0)
    if p.returncode != 0:
        raise SystemExit(f"cmd failed rc={p.returncode}: {p.stderr.decode(errors='replace')[-800:]}")
    return p.stdout.decode("utf-8", errors="replace")


def find_keyframe(around_s: float) -> float:
    """在 around_s 附近 30s 窗口里取**第一个 >= around_s** 的关键帧 pts。"""
    out = _run([str(FFPROBE), "-v", "error", "-select_streams", "v:0",
                "-read_intervals", f"{around_s - 10}%{around_s + 20}",
                "-show_entries", "packet=pts_time,flags", "-of", "json", str(BASE)])
    pkts = json.loads(out).get("packets", [])
    for pkt in pkts:
        if "K" in (pkt.get("flags") or "") and pkt.get("pts_time"):
            t = float(pkt["pts_time"])
            if t >= around_s:
                return t
    raise SystemExit(f"{around_s}s 附近 30s 内未找到关键帧")


def probe_duration(path: Path) -> float:
    out = _run([str(FFPROBE), "-v", "error", "-show_entries", "format=duration",
                "-of", "default=nw=1:nk=1", str(path)])
    return float(out.strip())


def last_video_end(path: Path) -> float:
    """最后一个视频 packet 的结束时刻（pts+duration）= 该文件内容实际覆盖到的原片时刻。"""
    out = _run([str(FFPROBE), "-v", "error", "-select_streams", "v:0",
                "-show_entries", "packet=pts_time,duration_time", "-of", "json", str(path)])
    pkts = json.loads(out).get("packets", [])
    ends = [float(p["pts_time"]) + float(p.get("duration_time") or 0.0)
            for p in pkts if p.get("pts_time")]
    if not ends:
        raise SystemExit(f"no video packets: {path}")
    return max(ends)


def frame_png(video: Path, t: float, out: Path) -> bytes:
    _run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
          "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", str(out)])
    return out.read_bytes()


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    parts_dir = WORK / "parts"
    parts_dir.mkdir(exist_ok=True)
    p1 = parts_dir / "2mkv_part1.mkv"
    p2 = parts_dir / "2mkv_part2.mkv"

    total = probe_duration(BASE)
    key_t = find_keyframe(total / 2)
    print(f"[split] total={total:.1f}s keyframe@{key_t:.3f}s", flush=True)

    if not (p1.exists() and p2.exists()):
        _run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-i", str(BASE),
              "-to", f"{key_t:.6f}", "-map", "0:v:0", "-map", "0:a?",
              "-c", "copy", str(p1)])
        # 2026-09-30 续32 修正（交接铁律第一批补复核抓出）：旧版 part2 用 `-ss key_t` 起切，
        # 实测 copy 语义下落点比 key_t 早 ~3.4s ⇒ 与 part1 尾部**重叠**，合并片在拼接点重复该段、
        # 其后时间轴整体偏移。改为以 part1 的**实际末帧时刻**起切 part2，保证两半互斥。
        p1_end = last_video_end(p1)
        _run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
              "-ss", f"{p1_end:.6f}", "-i", str(BASE), "-map", "0:v:0", "-map", "0:a?",
              "-c", "copy", str(p2)])
    d1, d2 = probe_duration(p1), probe_duration(p2)
    print(f"[split] part1={d1:.1f}s part2={d2:.1f}s sum={d1 + d2:.1f}s", flush=True)
    # 互斥性硬断言：两半时长和必须≈原片（旧版 +3.42s 的重叠在这里就会被拦下）
    assert abs(d1 + d2 - total) <= 0.5, \
        f"切分不互斥: part1+part2={d1 + d2:.2f}s vs 原片 {total:.2f}s（差 {d1 + d2 - total:+.2f}s）"

    # -- 合并（service 口径, 产物落 appdata merged/） --
    srv = SourceLocatorService(config=load_config())
    merge_t0 = time.monotonic()
    info1 = srv.merge_originals([str(p1), str(p2)])
    info2 = srv.merge_originals([str(p1), str(p2)])
    merged = Path(info1["merged_path"])
    dm = probe_duration(merged)
    probe = json.loads(subprocess.run(
        [str(FFPROBE), "-v", "error", "-show_entries",
         "stream=codec_name,width,height,pix_fmt,avg_frame_rate:format=duration,size",
         "-of", "json", str(merged)], capture_output=True,
        creationflags=0x08000000 if os.name == "nt" else 0).stdout.decode("utf-8"))
    (WORK / "merged_probe.json").write_text(json.dumps(
        {"info_first": info1, "info_second": info2, "probe": probe,
         "original_duration": total, "merged_duration": dm,
         "merge_seconds_first": round(time.monotonic() - merge_t0, 1)},
        ensure_ascii=False, indent=1), encoding="utf-8")
    assert info1["mode"] == "copy", f"同签名两半应走 copy, 实际 {info1['mode']}"
    assert info2["reused"] is True, "二次合并必须命中稳定命名缓存"
    assert abs(dm - total) <= max(1.0, total * 0.02), "合并时长偏离 >2%"
    print(f"[merge] mode=copy reused={info2['reused']} dur={dm:.1f}s (base {total:.1f}s)",
          flush=True)

    # -- 时间轴同一性硬断言（2026-09-30 续32 新增的常驻回归锁）--
    # 旧版只抽检接缝两侧"能出图"，抓不到"拼接点重复 3.4s / 其后整体偏移"这类内容级缺陷。
    # copy-concat 在容器时间戳粒度上做不到逐帧同 t 相等，故锁的形态 = **位移恒定**：
    #   拼接点之前 δ 必须 = 0；拼接点之后 δ 必须是一个 ≤0.5s 的**常数**（不随 t 累积）。
    # δ 随 t 变化 / 超过 0.5s / 拼接点前非 0 ⇒ 有重复或缺帧，判失败。
    io = FFmpegIO(FFMPEG, FFPROBE)
    tmp = WORK / "parts"
    tmp.mkdir(exist_ok=True)
    fps = 24000.0 / 1001.0
    step = 1.0 / fps

    def shift_at(t: float, lo: float, hi: float) -> float | None:
        a = frame_png(merged, t, tmp / "tl_m.png")
        n = int(round((hi - lo) / step)) + 1
        for k in range(n):
            d = lo + k * step
            if frame_png(BASE, t - d, tmp / f"tl_o_{k}.png") == a:
                return round(d, 4)
        return None

    pre = [total * f for f in (0.1, 0.3, 0.49)]
    post = [key_t + x for x in (1.0, 60.0, 600.0, 1800.0, 3000.0)]
    deltas = {}
    for t in pre:
        deltas[round(t, 1)] = shift_at(t, 0.0, 0.0)
    for t in post:
        deltas[round(t, 1)] = shift_at(t, 0.0, 0.6)
    print("[merge] 时间轴位移 δ(t): %s" % deltas, flush=True)
    pre_bad = [t for t, d in deltas.items() if t < key_t and d != 0.0]
    post_d = [d for t, d in deltas.items() if t >= key_t]
    assert not pre_bad, f"拼接点之前出现位移: {pre_bad}"
    assert all(d is not None for d in post_d), \
        f"拼接点之后存在 0.6s 内找不到同帧的位置（=重复/缺帧）: " \
        f"{[t for t, d in deltas.items() if t >= key_t and d is None]}"
    assert max(post_d) - min(post_d) <= step * 1.5, f"拼接点后位移不恒定（有累积）: {post_d}"
    assert max(post_d) <= 0.5, f"拼接点后位移过大: {post_d}"
    (WORK / "timeline_shift.json").write_text(json.dumps(
        {"join": key_t, "deltas": deltas, "post_shift_const": min(post_d)},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[merge] 时间轴同一性 PASS（拼接点前 δ=0，拼接点后恒定 δ={min(post_d):.3f}s）",
          flush=True)

    # -- 定位（DirectML 硬断言 + 出厂默认配置） --
    assert isinstance(srv.backend, DirectMLBackend), \
        f"必须 DirectMLBackend, 实际 {type(srv.backend).__name__}"
    print("BACKEND_SELECTED type=%s (pure default fast_global=%s)" %
          (type(srv.backend).__name__, srv.config.pipeline.fast_global_enabled), flush=True)
    t0 = time.monotonic()
    batch = srv.locate(str(EDITED), str(merged), on_progress=_Progress())
    out = WORK / "source_merge_2mkv.results.json"
    out.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[locate] done {time.monotonic() - t0:.1f}s ({len(batch.results)} segments)", flush=True)

    # -- 逐 ID 对照基线 --
    gt = json.loads((BENCH / "datasets/real/ground_truth_v4.json").read_text(encoding="utf-8"))
    base_res = json.loads(BASELINE_RESULTS.read_text(encoding="utf-8"))["results"]
    new_res = json.loads(out.read_text(encoding="utf-8"))["results"]
    r_base = evaluate(gt, base_res, label="baseline_2mkv")
    r_new = evaluate(gt, new_res, label="merged_2mkv")
    marks = {}
    for r in (r_base, r_new):
        for row in r["per_pos"]:
            marks.setdefault(str(row["id"]), {})[r["label"]] = row["mark"]
    flips = [{"id": k, "baseline": v.get("baseline_2mkv"), "merged": v.get("merged_2mkv")}
             for k, v in marks.items()
             if v.get("baseline_2mkv") != v.get("merged_2mkv")]
    neg = {}
    for r in (r_base, r_new):
        for row in r["offenders"]:
            neg.setdefault(str(row["id"]), {})[r["label"]] = row["fp"]
    report = {
        "baseline": {k: r_base[k] for k in ("strict_hit", "n_pos", "scene_hit", "fp", "n_neg")},
        "merged": {k: r_new[k] for k in ("strict_hit", "n_pos", "scene_hit", "fp", "n_neg")},
        "pos_flips": flips,
        "neg_flips": [{"id": k, "baseline": v.get("baseline_2mkv"),
                       "merged": v.get("merged_2mkv")}
                      for k, v in neg.items()
                      if v.get("baseline_2mkv") != v.get("merged_2mkv")],
    }
    (WORK / "source_merge_vs_baseline.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
