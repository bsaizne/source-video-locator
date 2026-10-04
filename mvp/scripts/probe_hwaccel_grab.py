#!/usr/bin/env python
"""硬解抓帧探针（2026-10-03 续47）— ffmpeg 解码侧下一杠杆的立项证据。

背景（续46）：窗批量抓帧解码翻默认开（test1 全片 1.34×，逐位一致）。续46 留痕
「硬解（-hwaccel）留作下一杠杆」。本探针只做研究级对照，零 mvp/src 接线、零默认值变更。

要回答的两个问题：
  1. 逐位一致性：hwaccel 解码输出与现役软解（FFmpegIO.grab_frame 同款命令）是否
     逐字节相同？（下游特征/索引/三指标逐位一致的前提；HEVC Main10 10-bit→BGR24
     的 swscale 转换是否在硬解链路上保持同一结果，是最大风险点。）
  2. 耗时：单帧 grab 与 40s 窗批量解码各提速多少？硬解帧回传（download to RAM）
     是否吃掉收益？

方法：
  - 单帧：对每片取 N 个散布时间点，分别用软解 / hwaccel 跑产品同款
    ``-ss t -i ... -frames:v 1 -f rawvideo -pix_fmt bgr24``，md5 对比 + 计时。
  - 窗批量：中段取 40s 窗，软解 / hwaccel 各一次 spawn 全解（-copyts 对齐续46 口径），
    逐帧 md5 对比 + 计时 + 帧数核对。
  - hwaccel 候选：d3d11va / dxva2 / d3d12va（ffmpeg 7.1 gyan essentials 构建在位；
    cuda=qsv 需 NVIDIA/Intel，本机 AMD 不测）。初始化失败即记 unavailable，不重试。

用法：
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_hwaccel_grab.py
输出：work/hwaccel_probe/probe_hwaccel.json + 控制台摘要。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = Path(r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
               r"\static_ffmpeg\bin\win32\ffprobe.exe")
OUT = BENCH / "work" / "hwaccel_probe"

# 与 rerun_fast_global.CASES 同源（test3 原 .mkv 路径笔误，实际 .mp4）
VIDEOS = {
    "2mkv_om":   r"D:\video\2.mkv",                                # HEVC Main10 1280x688
    "test1_om":  r"D:\ProjectXIXI\test1\test1-om.mkv",             # HEVC Main10 1920x960
    "test2_om":  r"D:\ProjectXIXI\test2\test2-om.mp4",             # HEVC Main10 1920x1036
    "test3_om":  r"D:\ProjectXIXI\test3\test3-om.mp4",             # H.264 High 8-bit 1920x800
    "test1_ed":  r"D:\ProjectXIXI\test1\test1-ed.mp4",             # H.264 8-bit 768x576（剪辑片代表）
}
HWACCELS = ["d3d11va", "dxva2", "d3d12va"]
N_SEEKS = 16          # 单帧对照时间点数
WINDOW_S = 40.0       # 窗批量解码跨度（续46 max_span_s 上限口径）
BASE = ["-hide_banner", "-loglevel", "error", "-nostdin"]


def ffprobe_meta(path: str) -> dict:
    """只取容器级元数据（2026-10-03 修订：删 -count_frames，长片不再全片解码）。"""
    out = subprocess.run(
        [str(FFPROBE), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,profile,pix_fmt,width,height,avg_frame_rate",
         "-show_entries", "format=duration",
         "-of", "json", path],
        capture_output=True, timeout=60, creationflags=0x08000000)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.decode(errors="replace"))
    js = json.loads(out.stdout.decode("utf-8", "replace"))
    st = js["streams"][0]
    return {
        "codec": st["codec_name"], "profile": st.get("profile", ""),
        "pix_fmt": st["pix_fmt"], "w": st["width"], "h": st["height"],
        "fps": st.get("avg_frame_rate", ""),
        "duration": float(js["format"]["duration"]),
    }


def run_decode(args: list[str]) -> tuple[bytes, float]:
    """跑一次 ffmpeg 抓帧命令，返回 (stdout, wall_seconds)。"""
    t0 = time.perf_counter()
    proc = subprocess.run(args, capture_output=True, timeout=600,
                          creationflags=0x08000000)
    dt = time.perf_counter() - t0
    if proc.returncode != 0:
        raise RuntimeError(
            f"rc={proc.returncode}: {proc.stderr.decode(errors='replace')[-600:]}")
    return proc.stdout, dt


def grab_args(path: str, t: float, hw: str | None, frame_bytes: int) -> list[str]:
    args = [str(FFMPEG), *BASE]
    if hw:
        args += ["-hwaccel", hw]
    args += ["-ss", f"{t:.6f}", "-i", path, "-frames:v", "1",
             "-an", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    return args


def window_args(path: str, lo: float, span: float, hw: str | None) -> list[str]:
    """2026-10-03 修订：-t 移到输入侧、去掉 -copyts。

    旧版 `-copyts` + 输出侧 `-t` 组合下输出时间戳是绝对值（seek 后可达数百秒），
    超出 recording_time 检查导致 0 帧输出。改为 `-ss lo -t span -i ...` 输入侧
    截断，且两臂命令除 -hwaccel 外逐字相同 ⇒ 逐位置帧对比即可。
    """
    args = [str(FFMPEG), *BASE]
    if hw:
        args += ["-hwaccel", hw]
    args += ["-ss", f"{lo:.6f}", "-t", f"{span:.6f}", "-i", path,
             "-an", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    return args


def md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def probe_video(name: str, path: str) -> dict:
    meta = ffprobe_meta(path)
    w, h = meta["w"], meta["h"]
    frame_bytes = w * h * 3
    dur = meta["duration"]
    # 散布时间点：避开首尾 5s
    ts = [5.0 + (dur - 10.0) * (i + 0.5) / N_SEEKS for i in range(N_SEEKS)]
    lo = dur * 0.5
    print(f"[{name}] {meta['codec']} {meta['profile']} {meta['pix_fmt']} "
          f"{w}x{h} dur={dur:.1f}s", flush=True)

    res: dict = {"meta": meta, "seeks": {}, "window": {}}

    # ---------- 单帧对照 ----------
    for hw in [None] + HWACCELS:
        key = hw or "sw"
        rows = []
        t_total = 0.0
        fail = None
        for t in ts:
            try:
                buf, dt = run_decode(grab_args(path, t, hw, frame_bytes))
                if len(buf) < frame_bytes:
                    raise RuntimeError(f"short output {len(buf)}")
                rows.append({"t": round(t, 3), "md5": md5(buf[:frame_bytes]),
                             "s": round(dt, 4)})
                t_total += dt
            except RuntimeError as e:
                fail = str(e)[:300]
                break
        res["seeks"][key] = {
            "frames_ok": len(rows), "mean_s": round(t_total / max(len(rows), 1), 4),
            "total_s": round(t_total, 3), "error": fail, "rows": rows,
        }
        status = f"ok x{len(rows)} mean={res['seeks'][key]['mean_s']}s" if not fail \
            else f"FAILED: {fail[:120]}"
        print(f"    seek [{key:8s}] {status}", flush=True)

    # ---------- 窗批量对照 ----------
    for hw in [None] + HWACCELS:
        key = hw or "sw"
        try:
            buf, dt = run_decode(window_args(path, lo, WINDOW_S, hw))
            n = len(buf) // frame_bytes
            hashes = [md5(buf[i * frame_bytes:(i + 1) * frame_bytes]) for i in range(n)]
            res["window"][key] = {"frames": n, "s": round(dt, 3),
                                  "fps": round(n / dt, 2), "md5s": hashes, "error": None}
            print(f"    win  [{key:8s}] {n} frames {dt:.2f}s = {n/dt:.1f} fps", flush=True)
        except RuntimeError as e:
            res["window"][key] = {"error": str(e)[:300]}
            print(f"    win  [{key:8s}] FAILED: {str(e)[:120]}", flush=True)

    # ---------- 一致性判定 ----------
    sw_seeks = res["seeks"].get("sw", {})
    sw_win = res["window"].get("sw", {})
    verdict = {}
    for hw in HWACCELS:
        hw_seeks = res["seeks"].get(hw, {})
        identical_seek = bool(
            sw_seeks.get("rows") and hw_seeks.get("rows")
            and len(sw_seeks["rows"]) == len(hw_seeks["rows"])
            and all(a["md5"] == b["md5"] for a, b in zip(sw_seeks["rows"], hw_seeks["rows"])))
        hw_win = res["window"].get(hw, {})
        identical_win = bool(
            sw_win.get("md5s") and hw_win.get("md5s")
            and sw_win["md5s"] == hw_win["md5s"])
        verdict[hw] = {
            "seek_identical": identical_seek,
            "window_identical": identical_win,
            # 提速比只要求两臂都跑完且帧数相同（不要求逐位一致），供立项评估用
            "seek_speedup": round(sw_seeks["mean_s"] / hw_seeks["mean_s"], 2)
            if sw_seeks.get("mean_s") and hw_seeks.get("mean_s")
            and sw_seeks.get("frames_ok") == hw_seeks.get("frames_ok") else None,
            "window_speedup": round(sw_win["s"] / hw_win["s"], 2)
            if sw_win.get("s") and hw_win.get("s")
            and sw_win.get("frames") == hw_win.get("frames") else None,
        }
        print(f"    ==>  {hw}: seek_id={identical_seek} win_id={identical_win} "
              f"seek_x{verdict[hw]['seek_speedup']} win_x{verdict[hw]['window_speedup']}",
              flush=True)
    res["verdict"] = verdict
    return res


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    for name, path in VIDEOS.items():
        if not Path(path).exists():
            print(f"[{name}] MISSING: {path}", flush=True)
            report[name] = {"error": "missing"}
            continue
        try:
            report[name] = probe_video(name, path)
        except Exception as e:  # noqa: BLE001
            print(f"[{name}] PROBE ERROR: {e}", flush=True)
            report[name] = {"error": str(e)[:300]}

    out_json = OUT / "probe_hwaccel.json"
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"\nsaved -> {out_json}", flush=True)

    print("\n===== 摘要 =====")
    for name, r in report.items():
        if "error" in r and "meta" not in r:
            print(f"{name}: {r['error']}")
            continue
        line = [name]
        for hw in HWACCELS:
            v = r.get("verdict", {}).get(hw, {})
            if v.get("seek_identical") or v.get("window_identical"):
                line.append(f"{hw}: id(s){v['seek_identical']}/id(w){v['window_identical']} "
                            f"x{v['seek_speedup']}/x{v['window_speedup']}")
            elif "unavailable" in str(v).lower() or r["seeks"].get(hw, {}).get("error"):
                line.append(f"{hw}: unavailable")
            else:
                line.append(f"{hw}: DIFFERS")
        print(" | ".join(line))
    return 0


if __name__ == "__main__":
    sys.exit(main())
