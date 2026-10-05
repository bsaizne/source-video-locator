# -*- coding: utf-8 -*-
"""hwaccel 窗模式立项探针（2026-10-05 续54，路径 A 的决定性测量）。

续47 结论链：① 机制探针证明统一转换链（hw 解码 → format=<mid> → format=bgr24）与产品
软解**逐字节一致**（8-bit H.264 / 10-bit HEVC P010 全过）⇒ 像素契约可保住，续47 判负
仅因直转路径，判负不成立。② 单帧 hwaccel 3× 慢 = D3D11 设备初始化 ~0.2s/spawn 淹没。
本探针回答最后一个问题：**窗模式**（一次 spawn 解一个 ~9s 窗，isc_refine 精扫的真实形态）
下硬解净收益多少？

测量（每片 K 个窗，全部输出 rawvideo bgr24 到 NUL——只测 ffmpeg 侧，Python 读取消耗
两臂同型不计）：
  sw_total   产品软解同款命令（-copyts 全窗解 → bgr24）
  sw_decode  软解到 null（无 rawvideo 管道）⇒ 解码地板
  hw_total   -hwaccel d3d11va + 统一转换链（format=mid,format=bgr24）
  hw_decode  硬解到 null
  + 逐帧 md5：sw_total vs hw_total（验证统一链在真实 HEVC Main10 大源上逐字节一致）
  + 单帧 spawn 基线（hw 设备初始化成本）

用法: D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_hwaccel_window.py \
        [--hwaccel d3d11va|d3d12va|dxva2]
输出: work/hwaccel_probe/probe_hwaccel_window{,_后端名}.json + 控制台摘要。
（续55：d3d12va 是本机 AMD 独显上唯一未测的硬解入口，dxva2 是同族旧版。）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
OUT = BENCH / "work" / "hwaccel_probe"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VIDEOS = {
    "test1_om": (r"D:\ProjectXIXI\test1\test1-om.mkv", "yuv420p10le"),
    "2mkv": (r"D:\video\2.mkv", "yuv420p10le"),
    "test2_om": (r"D:\ProjectXIXI\test2\test2-om.mp4", "yuv420p"),
    "test3_om": (r"D:\ProjectXIXI\test3\test3-om.mp4", "yuv420p"),
}
WIN_S = 9.0          # isc_refine 精扫窗宽（±4s）
N_WINDOWS = 6
HWACCEL = "d3d11va"


def run(args, timeout=300):
    t0 = time.monotonic()
    p = subprocess.run(args, capture_output=True, timeout=timeout)
    return time.monotonic() - t0, p.returncode, p.stdout, p.stderr


def window_args(src, lo, hw, mid):
    """产品窗解码同款（-copyts 全窗解 → rawvideo bgr24），sw/hw 两臂。"""
    # ⚠️ 不可加 -copyts：copyts + -t 会在原始时间轴上裁剪 ⇒ 0 帧（产品用 copyts 时靠
    # 目标满足后 terminate，从不配 -t）。本探针纯计时/比对，无需 copyts。
    base = [str(FFMPEG), "-v", "error", "-ss", f"{lo:.6f}", "-i", src, "-t", f"{WIN_S:.3f}"]
    if hw:
        base += ["-hwaccel", HWACCEL]
        vf = f"format={mid},format=bgr24"      # 统一转换链（续47 机制探针证明逐位一致）
    else:
        vf = "format=bgr24"                     # 产品软解同款直转
    return base + ["-an", "-f", "rawvideo", "-pix_fmt", "bgr24", "-vf", vf, "-"]


def md5_stream(args):
    """边流边算 md5 + 计时 + 帧计数（帧长未知 ⇒ 按流总量与首帧尺寸推）。"""
    t0 = time.monotonic()
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    h = hashlib.md5()
    total = 0
    first = b""
    while True:
        chunk = p.stdout.read(1 << 22)
        if not chunk:
            break
        if not first:
            first = chunk[:3]
        h.update(chunk)
        total += len(chunk)
    p.wait(timeout=120)
    return time.monotonic() - t0, p.returncode, h.hexdigest(), total, first


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hwaccel", default="d3d11va",
                    choices=["d3d11va", "d3d12va", "dxva2", "vaapi", "cuda"])
    ap.add_argument("--videos", default="test1_om,2mkv",
                    help="逗号分隔的 VIDEOS 键（默认与续54 同两源，便于对照）")
    args = ap.parse_args()
    globals()["HWACCEL"] = args.hwaccel
    names = [v.strip() for v in args.videos.split(",") if v.strip() in VIDEOS]
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {}
    for name in names:
        src, mid = VIDEOS[name]
        print(f"== {name} ({mid}) hwaccel={HWACCEL}", flush=True)
        case: dict = {"src": src, "mid": mid, "hwaccel": HWACCEL, "windows": []}
        # 窗位置：中段散布
        meta = subprocess.run(
            [r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe",
             "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src],
            capture_output=True, text=True, timeout=120).stdout.strip()
        dur = float(meta)
        starts = [dur * (0.15 + 0.12 * i) for i in range(N_WINDOWS)]
        sw_md5s, hw_md5s = [], []
        for lo in starts:
            row: dict = {"lo": round(lo, 2)}
            t, rc, out, err = run(window_args(src, lo, False, mid))
            row["sw_total"] = round(t, 3); row["sw_rc"] = rc
            # sw_decode（到 null，无管道）
            args = [str(FFMPEG), "-v", "error", "-ss", f"{lo:.6f}", "-i", src,
                    "-t", f"{WIN_S:.3f}", "-an", "-f", "null", "-"]
            t, rc, _, _ = run(args)
            row["sw_decode"] = round(t, 3); row["sw_decode_rc"] = rc
            # hw_total（含逐帧 md5 流式对照）
            t, rc, digest, total, first = md5_stream(window_args(src, lo, True, mid))
            row["hw_total"] = round(t, 3); row["hw_rc"] = rc; row["hw_bytes"] = total
            hw_md5s.append(digest)
            # sw_total 的 md5（流式）
            t, rc, digest_sw, total_sw, _ = md5_stream(window_args(src, lo, False, mid))
            row["sw_total_stream"] = round(t, 3)
            sw_md5s.append(digest_sw)
            row["md5_match"] = digest == digest_sw
            row["bytes_match"] = total == total_sw
            row["hw_ok"] = bool(rc == 0 and total > 0)
            # hw_decode（到 null）
            args = [str(FFMPEG), "-v", "error", "-hwaccel", HWACCEL,
                    "-ss", f"{lo:.6f}", "-i", src, "-t", f"{WIN_S:.3f}",
                    "-an", "-f", "null", "-"]
            t, rc, _, _ = run(args)
            row["hw_decode"] = round(t, 3); row["hw_decode_rc"] = rc
            case["windows"].append(row)
            print("  lo=%.1f sw_total=%.2f sw_decode=%.2f hw_total=%.2f hw_decode=%.2f "
                  "md5_match=%s" % (lo, row["sw_total"], row["sw_decode"], row["hw_total"],
                                    row["hw_decode"], row["md5_match"]), flush=True)
        # 单帧 hw spawn 基线（设备初始化成本）
        args = [str(FFMPEG), "-v", "error", "-hwaccel", HWACCEL,
                "-ss", f"{starts[0]:.6f}", "-i", src, "-frames:v", "1",
                "-an", "-f", "null", "-"]
        t1, _, _, _ = run(args)
        t0, _, _, _ = run(args)
        case["hw_single_frame_s"] = round(t0, 3)
        case["hw_single_frame_s_cold"] = round(t1, 3)
        ok = sum(1 for w in case["windows"] if w["md5_match"] and w["bytes_match"])
        case["md5_match_windows"] = f"{ok}/{N_WINDOWS}"
        s_tot = sum(w["sw_total"] for w in case["windows"])
        h_tot = sum(w["hw_total"] for w in case["windows"])
        s_dec = sum(w["sw_decode"] for w in case["windows"])
        h_dec = sum(w["hw_decode"] for w in case["windows"])
        case["sum_sw_total"] = round(s_tot, 2)
        case["sum_hw_total"] = round(h_tot, 2)
        case["sum_sw_decode"] = round(s_dec, 2)
        case["sum_hw_decode"] = round(h_dec, 2)
        case["hw_total_speedup"] = round(s_tot / max(h_tot, 1e-9), 2)
        case["decode_speedup"] = round(s_dec / max(h_dec, 1e-9), 2)
        case["hw_windows_ok"] = "%d/%d" % (sum(1 for w in case["windows"] if w["hw_ok"]),
                                           N_WINDOWS)
        report[name] = case
        print("  汇总: sw_total=%.2fs hw_total=%.2fs (%.2fx) | 解码地板 sw=%.2f hw=%.2f (%.2fx) | "
              "md5 %s | hw 可用窗 %s"
              % (s_tot, h_tot, case["hw_total_speedup"], s_dec, h_dec,
                 case["decode_speedup"], case["md5_match_windows"],
                 case["hw_windows_ok"]), flush=True)
    suffix = "_%s" % HWACCEL        # 带后端名，绝不覆盖续54 的 d3d11va 原始留痕
    out = OUT / ("probe_hwaccel_window%s.json" % suffix)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved", out, flush=True)
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
