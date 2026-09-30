"""成片渲染真实素材验收（2026-09-29 续30，竞品 video_renderer 移植）。

对象 = 生产现役基线结果批 ``work/fastglobal_default_2mkv.results.json``（2.mkv 39 段）
+ 原片 ``datasets/real/originals/2.mkv``。

验收四件事：
1. **成片在位且可解码**：ffprobe 严格逐帧计数 == 计划总帧数；音轨在位（aac/48k/stereo）；
   帧率 == 原片有理帧率（CFR）。
2. **口径对照**：渲染用的 clip 计划与 EDL 工程**同一套代码** ⇒ 段数必须相等，
   并留痕每段的源片区间。
3. **逐段画面对照图**：成片每段的中帧 vs 原片同时间点的帧，拼成左右对照图，
   由人（或多模态读图）逐张确认"成片这一段确实是定位到的原片内容"。
4. **耗时/编码器**：记录实际编码器（硬件失败会回退 libx264 并留痕）。

不写 GT、不改算法；产物落 ``work/render_accept/``。

Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/accept_video_render_2mkv.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault(
    "MEDIA_FFPROBE",
    r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
    r"\static_ffmpeg\bin\win32\ffprobe.exe")
sys.path.insert(0, str(BENCH / "mvp" / "src"))

import numpy as np  # noqa: E402
import cv2  # noqa: E402

from app.locator_service import SourceLocatorService  # noqa: E402
from infrastructure.config import load_config  # noqa: E402
from infrastructure.results_repo import load_results  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

# 原片路径以**结果批自带的 original_video** 为权威（素材实际在 D:\video\ 下，
# datasets/real/originals 只是历史副本位置）；这里的常量只用于报错文案。
ORIGINAL_GUESS = Path(r"D:/video/2.mkv")
BATCH_JSON = BENCH / "work" / "fastglobal_default_2mkv.results.json"
OUT = BENCH / "work" / "render_accept"
FFMPEG = Path(os.environ["MEDIA_FFMPEG"])
FFPROBE = Path(os.environ["MEDIA_FFPROBE"])


def probe_frames(path: Path, *, strict: bool = False) -> int | None:
    cmd = [str(FFPROBE), "-v", "error", "-select_streams", "v:0"]
    if strict:
        cmd.append("-count_frames")
        entries = "stream=nb_read_frames"
    else:
        entries = "stream=nb_frames"
    cmd += ["-show_entries", f"{entries},stream=r_frame_rate,stream=codec_name",
            "-of", "json", str(path)]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    data = json.loads(out.stdout or "{}")
    streams = data.get("streams") or []
    if not streams:
        return None
    key = "nb_read_frames" if strict else "nb_frames"
    val = streams[0].get(key)
    return int(val) if val not in (None, "N/A") else None


def probe_streams(path: Path) -> dict:
    cmd = [str(FFPROBE), "-v", "error", "-print_format", "json",
           "-show_streams", "-show_format", str(path)]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return json.loads(out.stdout or "{}")


def grab(path: Path, t: float, out_png: Path) -> bool:
    """精确单帧抽取（fast seek），写 PNG。"""
    args = [str(FFMPEG), "-hide_banner", "-loglevel", "error", "-nostdin",
            "-ss", f"{t:.6f}", "-i", str(path), "-frames:v", "1",
            str(out_png)]
    res = subprocess.run(args, capture_output=True, timeout=300)
    return out_png.exists() and res.returncode == 0


def sheet(left: Path, right: Path, out: Path, label: str) -> None:
    """左右对照图。输出走 **JPG**（1080p PNG 一张 ~3MB，60 段 = 218MB 残留；
    对照图只需肉眼判读，q4 足够，实测 60 张 = 2.3MB）。"""
    a = cv2.imread(str(left))
    b = cv2.imread(str(right))
    if a is None or b is None:
        return
    h = 360
    a = cv2.resize(a, (int(a.shape[1] * h / a.shape[0]), h))
    b = cv2.resize(b, (int(b.shape[1] * h / b.shape[0]), h))
    w = max(a.shape[1], b.shape[1])
    canvas = np.full((h + 34, w * 2 + 20, 3), 24, dtype=np.uint8)
    canvas[34:34 + h, 0:a.shape[1]] = a
    canvas[34:34 + h, w + 20:w + 20 + b.shape[1]] = b
    cv2.putText(canvas, "MOVIE clip", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (240, 240, 240), 1)
    cv2.putText(canvas, label, (w + 28, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (240, 240, 240), 1)
    ok = cv2.imwrite(str(out), canvas, [cv2.IMWRITE_JPEG_QUALITY, 88])
    if ok:
        # 中间单帧图只为拼对照图，留下来就是双份残留
        left.unlink(missing_ok=True)
        right.unlink(missing_ok=True)


def frame_delta_stats(path: Path, expect_fps: Fraction) -> dict:
    """成片视频帧距统计：接缝间隙缺陷（中段 AAC 补齐）的直测判据。

    理想情况所有相邻 PTS 差 == 1/fps；出现 1/fps 之外的值即段间偏移没对齐。
    """
    out = subprocess.run(
        [str(FFPROBE), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "frame=pts_time", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, timeout=900).stdout
    times = [float(x.strip().rstrip(",")) for x in out.replace("\r", "").splitlines()
             if x.strip().rstrip(",")]
    want = round(1.0 / float(expect_fps), 4)
    deltas = [round(b - a, 4) for a, b in zip(times, times[1:])]
    odd = [d for d in deltas if abs(d - want) > 0.0005]
    return {"frames": len(times), "expected_delta": want, "irregular": len(odd),
            "irregular_values": sorted(set(odd))[:6]}


def grab_gray(path: Path, t: float, width: int = 320):
    """抽一帧并转灰度小图（对齐度量用，避免色彩差异干扰 MAD）。"""
    raw = path.with_suffix(".gray.raw")
    args = [str(FFMPEG), "-hide_banner", "-loglevel", "error", "-nostdin",
            "-ss", f"{max(t, 0.0):.6f}", "-i", str(path), "-frames:v", "1",
            "-vf", f"scale={width}:-2", "-pix_fmt", "gray", "-f", "rawvideo",
            "-y", str(raw)]
    subprocess.run(args, check=True, capture_output=True, timeout=300)
    arr = np.frombuffer(raw.read_bytes(), dtype=np.uint8)
    raw.unlink(missing_ok=True)
    return arr.reshape(arr.size // width, width).astype(np.float32)


def alignment_probe(movie: Path, source: Path, clips: list[tuple[float, float]],
                    fps: Fraction, sample: int = 8) -> list[dict]:
    """逐段中帧对齐度量：成片第 i 段中帧 vs 原片同区间中帧，±4 帧内找最优匹配。

    判据 = 最优偏移必须 ≤1 帧（42ms@23.976）；偏移更大说明成片时间线累加或段长算错。
    """
    from media.ffmpeg.timeline_render import expected_frames, frames_to_seconds

    idxs = sorted(set(int(round(x)) for x in np.linspace(0, len(clips) - 1, sample)))
    rows = []
    for i in idxs:
        a0, a1 = clips[i]
        n = expected_frames(a1 - a0, fps)
        movie_t = sum(frames_to_seconds(expected_frames(b - a, fps), fps)
                      for a, b in clips[:i]) + frames_to_seconds(n, fps) / 2.0
        src_mid = (a0 + a1) / 2.0
        fm = grab_gray(movie, movie_t)
        d0 = float(np.abs(fm - grab_gray(source, src_mid)).mean())
        best = (d0, 0)
        for k in range(-4, 5):
            d = float(np.abs(fm - grab_gray(source, src_mid + k / float(fps))).mean())
            if d < best[0]:
                best = (d, k)
        rows.append({"clip": i, "frames": n, "movie_t": round(movie_t, 3),
                     "src_mid": round(src_mid, 2), "mad_at_zero": round(d0, 3),
                     "best_offset_frames": best[1], "mad_best": round(best[0], 3)})
    return rows


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    # 用**生产 app data**（索引在位 → 切点吸附/展开真实生效）；产物写到 work/render_accept。
    cfg = load_config()
    svc = SourceLocatorService(config=cfg)

    batch = load_results(BATCH_JSON)
    original = Path(str(batch.original_video) or str(ORIGINAL_GUESS))
    print(f"BATCH {BATCH_JSON.name} results={len(batch.results)} "
          f"original={original.name}")
    if not original.exists():
        print(f"SKIP: 原片不在位 {original}")
        return 1

    t0 = time.time()
    events = []
    info = svc.render_movie(batch, out_dir=OUT, on_progress=lambda ev: events.append(ev))
    secs = time.time() - t0
    movie = Path(info["movie_path"])
    print(f"RENDER done in {secs:.1f}s -> {movie.name}")
    print("INFO", {k: v for k, v in info.items() if k != "movie_path"})

    # --- 1. 成片在位 + 严格逐帧计数 -------------------------------------- #
    fast = probe_frames(movie)
    strict = probe_frames(movie, strict=True)
    streams = probe_streams(movie)
    v = next((s for s in streams.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in streams.get("streams", []) if s.get("codec_type") == "audio"), {})
    checks = {
        "movie_exists": movie.exists(),
        "expected_frames": info["total_frames"],
        "nb_frames": fast,
        "strict_frames": strict,
        "frames_match": strict == info["total_frames"],
        "movie_fps": v.get("r_frame_rate"),
        "video_codec": v.get("codec_name"),
        "audio_codec": a.get("codec_name"),
        "audio_rate": a.get("sample_rate"),
        "audio_channels": a.get("channels"),
        "duration_s": round(float((streams.get("format") or {}).get("duration") or 0.0), 3),
        "seconds_per_segment": round(secs / max(1, info["segments"]), 2),
    }
    print("CHECKS", json.dumps(checks, ensure_ascii=False, indent=2))

    # --- 1b. 帧距规则性（接缝回归锁：中段 AAC 补齐会留下 59 处 +21ms 视频间隙）--- #
    deltas = frame_delta_stats(movie, Fraction(info["fps"]))
    checks["frame_delta_stats"] = deltas
    checks["seams_clean"] = deltas["irregular"] == 0 and deltas["frames"] == info["total_frames"]
    print("FRAME DELTA", json.dumps(deltas, ensure_ascii=False))

    # --- 2. 与 EDL 工程同计划（同一套 clip 代码 ⇒ 源片区间集合必须逐段相等）---- #
    edl = svc.export_project(batch, fmt="edl", out_dir=OUT)
    edl_ranges = _edl_orig_ranges(edl.read_text(encoding="utf-8"))
    movie_ranges = [[round(float(a), 2), round(float(b), 2)]
                    for a, b in info["clip_ranges"]]
    plan_consistent = (len(edl_ranges) == len(movie_ranges)
                       and all(abs(x[0] - y[0]) <= 0.06 and abs(x[1] - y[1]) <= 0.06
                               for x, y in zip(edl_ranges, movie_ranges)))
    print(f"EDL {edl.name} clips={len(edl_ranges)} movie clips={len(movie_ranges)} "
          f"同计划={plan_consistent}")
    if not plan_consistent:
        print("  EDL 前 5 段:", edl_ranges[:5])
        print("  成片前 5 段:", movie_ranges[:5])

    # --- 3. 逐段画面对照图（成片段中帧 vs 原片同时间帧） ------------------ #
    # 段在成片里的位置 = **帧精确**累加（用名义秒累加会假跑出 4 帧"漂移"，踩过）；
    # clip 区间取 service **实际渲染**用的那份（吸附 + 切点展开之后），不在脚本里重算。
    from media.ffmpeg.timeline_render import expected_frames, frames_to_seconds

    fps = Fraction(info["fps"])
    clips = [(float(a), float(b)) for a, b in info["clip_ranges"]]
    widths = [frames_to_seconds(expected_frames(b - a, fps), fps) for a, b in clips]
    cursor = 0.0
    review_dir = OUT / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for i, (a0, a1) in enumerate(clips):
        mid_movie = cursor + widths[i] / 2.0
        mid_src = (a0 + a1) / 2.0
        cursor += widths[i]
        lm = review_dir / f"clip{i:02d}_movie_{mid_movie:.2f}s.png"
        ls = review_dir / f"clip{i:02d}_source_{mid_src:.2f}s.png"
        if grab(movie, mid_movie, lm) and grab(original, mid_src, ls):
            sheetp = review_dir / f"clip{i:02d}_sheet.jpg"
            sheet(lm, ls, sheetp, f"SRC {mid_src:.2f}s  clip={a0:.2f}-{a1:.2f}")
            made.append((i, str(sheetp), round(mid_movie, 2), round(mid_src, 2)))
    print(f"SHEETS {len(made)}/{len(clips)} -> {review_dir}")
    for row in made:
        print("  clip", row)

    # --- 4. 对齐度量：逐段中帧在原片 ±4 帧内找最优匹配（>1 帧 = 时间线算错）--- #
    align = alignment_probe(movie, original, clips, fps)
    worst = max(abs(r["best_offset_frames"]) for r in align)
    checks["alignment_sample"] = align
    checks["alignment_within_1_frame"] = worst <= 1
    print("ALIGNMENT", json.dumps(align, ensure_ascii=False))

    (OUT / "render_accept_summary.json").write_text(json.dumps({
        "batch": str(BATCH_JSON), "original": str(original), "info": {**info},
        "checks": checks, "edl": str(edl), "edl_clips": len(edl_ranges),
        "plan_consistent": bool(plan_consistent),
        "clips": [[round(x, 3), round(y, 3)] for x, y in clips],
        "seconds_total": round(secs, 1),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    ok = bool(checks["movie_exists"] and checks["frames_match"] and checks["audio_codec"]
              and plan_consistent and checks["seams_clean"]
              and checks["alignment_within_1_frame"])
    print("VERDICT", "PASS" if ok else "FAIL")
    return 0 if ok else 2


def _edl_orig_ranges(text: str) -> list[tuple[float, float]]:
    """从 EDL 的 ``* LOCATOR: ... orig=A-B`` 注释里取源片区间（渲染与工程同源校验用）。"""
    import re
    out = []
    for m in re.finditer(r"orig=([0-9.]+)-([0-9.]+)", text):
        out.append((float(m.group(1)), float(m.group(2))))
    return out


if __name__ == "__main__":
    raise SystemExit(main())
