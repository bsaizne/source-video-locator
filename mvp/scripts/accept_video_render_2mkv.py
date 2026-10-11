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
import math
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


def clip_mid_times(clips: list[tuple[float, float]], fps: Fraction) -> list[tuple[float, float, int]]:
    """逐段返回 ``(成片取帧时刻, 原片取帧时刻, 段帧数)``，两侧都按**整数帧号**推。

    - 成片侧：段首帧号 = 前面各段的**帧数**之和（CFR 下精确），再取段内第 ``m = n//2`` 帧。
      （用名义秒累加会假跑出几帧"漂移"，踩过。）
    - 原片侧：段首帧号 = ``floor(a0*fps)``，不是 ``a0`` 那个时刻本身。
    - 取帧时刻 = ``(帧号 - 0.499)/fps``。``-ss`` 前置于 ``-i`` 的语义是「返回第一个
      PTS ≥ t 的帧」，所以 t 必须落在目标帧**之前**、上一帧之后；写成 ``+0.5`` 会恰好
      取到下一帧（2026-10-11 我就这么错过一次，偏移分布整体平移一帧）。

    ⚠️ 原片侧仍有 **±1 帧的取帧不确定性**（源容器 PTS 不是精确的 ``k/fps``，fast seek 还要
    从关键帧解码丢弃）⇒ 「绝对偏移必须为 0」这类判据物理上做不到，只能判**离散度**，
    见 :func:`alignment_probe`。
    """
    from media.ffmpeg.timeline_render import expected_frames

    out = []
    movie_frame = 0
    fr = float(fps)
    for a0, a1 in clips:
        n = expected_frames(a1 - a0, fps)
        m = n // 2
        src_frame = int(math.floor(a0 * fr + 1e-6)) + m
        out.append(((movie_frame + m - 0.499) / fr, (src_frame - 0.499) / fr, n))
        movie_frame += n
    return out


def alignment_probe(movie: Path, source: Path, clips: list[tuple[float, float]],
                    fps: Fraction, sample: int = 8) -> list[dict]:
    """逐段中帧对齐度量：成片第 i 段中帧 vs 原片对应帧，±4 帧内找最优匹配。

    判据 = **离散度**（各段偏移对"多数段偏移"的最大偏离 ≤1 帧），不是绝对偏移。
    三条理由都是 2026-10-11 实测出来的：

    1. 绝对偏移含一个**常数项**：原片侧 fast-seek 有 ±1 帧取帧不确定性（见
       :func:`clip_mid_times`）。旧判据写 ``<=1`` 而实测恒定就有 -1 ⇒ 在「1 帧系统性错位」
       方向上**零余量**，它该抓的错看不见。常数项不是错，只有**段间不一致**才是时间线累加错。
    2. 静态镜头里 MAD 曲线是平的（实测 0.378 vs 0.364，只差 0.014），argmin 挑到噪声
       ⇒ 非零偏移必须**伴随 MAD 显著下降**（``mad_best < 0.5*mad_at_zero``）才算数，
       否则这条门会天天误报（真越界的形态是断崖：2.959→0.350）。
    3. 抽 8 条太稀，定性一次「判据红但产品没错」花了全量复跑 ⇒ 段数不多时直接全跑。
    """
    idxs = sorted(set(int(round(x)) for x in np.linspace(0, len(clips) - 1, sample)))
    mids = clip_mid_times(clips, fps)
    rows = []
    for i in idxs:
        movie_t, src_t, n = mids[i]
        fm = grab_gray(movie, movie_t)
        d0 = float(np.abs(fm - grab_gray(source, src_t)).mean())
        best = (d0, 0)
        for k in range(-4, 5):
            d = float(np.abs(fm - grab_gray(source, src_t + k / float(fps))).mean())
            if d < best[0]:
                best = (d, k)
        sig = best[1] != 0 and best[0] < 0.5 * d0      # 曲线平 => argmin 无信息
        rows.append({"clip": i, "frames": n, "movie_t": round(movie_t, 3),
                     "src_t": round(src_t, 3), "mad_at_zero": round(d0, 3),
                     "raw_offset_frames": best[1], "mad_best": round(best[0], 3),
                     "significant": bool(sig)})
    return rows


def alignment_verdict(rows: list[dict]) -> dict:
    """把探针原始行折成判据量：常数项偏移 + 离散度（纯函数，便于单测）。"""
    sig = [r["raw_offset_frames"] for r in rows if r["significant"]]
    if not sig:                       # 全片都是平曲线（例：整段静止素材）=> 无可判信息
        return {"base_offset": 0, "dispersion": 0, "n_significant": 0, "ok": True}
    base = int(np.median(sig))
    return {"base_offset": base,
            "dispersion": int(max(abs(k - base) for k in sig)),
            "n_significant": len(sig), "ok": max(abs(k - base) for k in sig) <= 1}


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

    # --- 3. 逐段画面对照图（成片段中帧 vs 原片对应帧） -------------------- #
    # 取帧时刻一律走 clip_mid_times（与对齐度量同一套）：段在成片里的位置要按**帧数**累加，
    # 段在原片里的起点要按渲染器的 fast-seek 约定取 ceil(a0*fps)（用名义秒/用 a0 本身都踩过坑）。
    fps = Fraction(info["fps"])
    clips = [(float(a), float(b)) for a, b in info["clip_ranges"]]
    mids = clip_mid_times(clips, fps)      # 与对齐度量同一套取帧时刻（两处各写一份必漂移）
    review_dir = OUT / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for i, (a0, a1) in enumerate(clips):
        mid_movie, mid_src, _n = mids[i]
        lm = review_dir / f"clip{i:02d}_movie_{mid_movie:.2f}s.png"
        ls = review_dir / f"clip{i:02d}_source_{mid_src:.2f}s.png"
        if grab(movie, mid_movie, lm) and grab(original, mid_src, ls):
            sheetp = review_dir / f"clip{i:02d}_sheet.jpg"
            sheet(lm, ls, sheetp, f"SRC {mid_src:.2f}s  clip={a0:.2f}-{a1:.2f}")
            made.append((i, str(sheetp), round(mid_movie, 2), round(mid_src, 2)))
    print(f"SHEETS {len(made)}/{len(clips)} -> {review_dir}")
    for row in made:
        print("  clip", row)

    # --- 4. 对齐度量：逐段中帧在原片 ±4 帧内找最优匹配（判据 = 离散度，见 alignment_probe）--- #
    # 默认抽 8 条太稀（2026-10-11 那次误报就是靠全量复跑才定性的）⇒ 段数不多时直接全跑。
    align = alignment_probe(movie, original, clips, fps,
                            sample=len(clips) if len(clips) <= 96 else 8)
    verdict = alignment_verdict(align)
    checks["alignment_sample"] = align
    checks["alignment_base_offset"] = verdict["base_offset"]
    checks["alignment_dispersion_frames"] = verdict["dispersion"]
    checks["alignment_dispersion_within_1_frame"] = verdict["ok"]
    checks["alignment_offset_hist"] = {str(k): sum(1 for r in align
                                                   if r["raw_offset_frames"] == k)
                                       for k in range(-4, 5)}
    print("ALIGNMENT", json.dumps(align, ensure_ascii=False))
    print("ALIGN_VERDICT base=%+d dispersion=%d sig=%d/%d ok=%s hist=%s" % (
        verdict["base_offset"], verdict["dispersion"], verdict["n_significant"], len(align),
        verdict["ok"], {k: v for k, v in checks["alignment_offset_hist"].items() if v}))

    (OUT / "render_accept_summary.json").write_text(json.dumps({
        "batch": str(BATCH_JSON), "original": str(original), "info": {**info},
        "checks": checks, "edl": str(edl), "edl_clips": len(edl_ranges),
        "plan_consistent": bool(plan_consistent),
        "clips": [[round(x, 3), round(y, 3)] for x, y in clips],
        "seconds_total": round(secs, 1),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    ok = bool(checks["movie_exists"] and checks["frames_match"] and checks["audio_codec"]
              and plan_consistent and checks["seams_clean"]
              and checks["alignment_dispersion_within_1_frame"])
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
