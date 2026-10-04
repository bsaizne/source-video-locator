#!/usr/bin/env python
"""硬解抓帧像素差异机制探针（2026-10-03 续47，缺陷3专用）。

上一轮现象：单帧硬解 16/16 md5 与软解不同（连 8-bit H.264 也如此），机制未知。
本探针假设：硬解码器回传的系统内存帧是 NV12（8-bit）/ P010（10-bit），而软解是
yuv420p / yuv420p10le；两者 YUV 数据相同但 swscale 转换到 bgr24 走的插值路径不同，
差异在【色彩转换层】而非【解码层】。

验证设计（每片取 2 个时间点，全部输出 rawvideo 比 md5）：
  A. 解码层对照：sw 臂 `-pix_fmt <mid>` vs hw 臂 `-hwaccel d3d11va -pix_fmt <mid>`
     （mid = yuv420p / yuv420p10le；硬解先解码到 NV12/P010，再由 swscale 无损重排
     为 planar mid）。若 md5 相同 ⇒ 解码层一致，差异只在转换层。
  B. 统一转换链对照：hw 臂加 `-vf format=<mid>,format=bgr24`（强制 NV12→mid→bgr24
     两步，其中 mid 步为无损重排），与现役软解命令 `-pix_fmt bgr24`（yuv420p→bgr24
     直转）比。若 md5 相同 ⇒ 两臂可用统一 format 路径做到逐位一致。
  C. 控制组：sw 臂同款 `-vf format=<mid>,format=bgr24`，验证统一链本身不扰动软解结果。
  D. 手工字节级佐证：d3d11va 输出 NV12/P010 原始字节，在 Python 里手工重排为
     planar mid（NV12: U=uv[0::2],V=uv[1::2]；P010: 16bit 词 + 尝试 >>6 / >>0 两种
     对齐），与 sw mid 输出逐字节比，直接证明重排无损/确定对齐。

只测机制，不做耗时结论（耗时见 probe_hwaccel_grab.py）。零 mvp/src 接线。

用法：
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_hwaccel_mech.py
输出：work/hwaccel_probe/probe_hwaccel_mech.json + 控制台摘要。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

BENCH = Path(r"D:\claudework\benchmark")
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = Path(r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
               r"\static_ffmpeg\bin\win32\ffprobe.exe")
OUT = BENCH / "work" / "hwaccel_probe"
HW = "d3d11va"  # 机制验证固定用 d3d11va（主探针已覆盖另两个）

# 代表片：8-bit H.264 + 两档 10-bit HEVC（不需要全部 5 片，机制同 codec/pix_fmt 即同）
VIDEOS = [
    ("test1_ed_8bit_h264", r"D:\ProjectXIXI\test1\test1-ed.mp4"),
    ("2mkv_10bit_hevc",    r"D:\video\2.mkv"),
    ("test1_om_10bit_hevc", r"D:\ProjectXIXI\test1\test1-om.mkv"),
]
BASE = ["-hide_banner", "-loglevel", "error", "-nostdin"]


def ffprobe_meta(path: str) -> dict:
    out = subprocess.run(
        [str(FFPROBE), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,profile,pix_fmt,width,height",
         "-show_entries", "format=duration", "-of", "json", path],
        capture_output=True, timeout=60, creationflags=0x08000000)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.decode(errors="replace"))
    js = json.loads(out.stdout.decode("utf-8", "replace"))
    st = js["streams"][0]
    return {"codec": st["codec_name"], "pix_fmt": st["pix_fmt"],
            "w": st["width"], "h": st["height"],
            "duration": float(js["format"]["duration"])}


def run(args: list[str]) -> tuple[bytes, float]:
    t0 = time.perf_counter()
    proc = subprocess.run(args, capture_output=True, timeout=600,
                          creationflags=0x08000000)
    dt = time.perf_counter() - t0
    if proc.returncode != 0:
        raise RuntimeError(
            f"rc={proc.returncode}: {proc.stderr.decode(errors='replace')[-500:]}")
    return proc.stdout, dt


def md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def mid_fmt(pix_fmt: str) -> str:
    return "yuv420p10le" if "10le" in pix_fmt else "yuv420p"


def native_fmt(pix_fmt: str) -> str:
    return "p010" if "10le" in pix_fmt else "nv12"


def manual_repack(native: bytes, sw_mid: bytes, w: int, h: int, pix_fmt: str) -> dict:
    """Python 手工把 NV12/P010 重排为 planar，与 sw mid 输出逐字节比。"""
    w2, h2 = w // 2, h // 2
    if pix_fmt.endswith("420p10le"):
        # P010: Y 平面 w*h*2B + UV 交错平面（U16,V16 对）
        y = np.frombuffer(native[:w * h * 2], dtype="<u2")
        uv = np.frombuffer(native[w * h * 2:], dtype="<u2")
        u, v = uv[0::2], uv[1::2]
        planar = np.concatenate([y, u, v]).astype("<u2")
        sw = np.frombuffer(sw_mid, dtype="<u2")
        res = {"n_native_bytes": len(native), "n_sw_bytes": len(sw_mid)}
        for shift in (6, 0):
            cand = (planar >> shift) if shift else planar
            res[f"match_shift{shift}"] = bool(np.array_equal(cand, sw))
        return res
    # NV12: Y 平面 w*h + UV 交错平面（U8,V8 对）
    y = native[:w * h]
    uv = native[w * h:]
    cand = y + uv[0::2] + uv[1::2]
    return {"n_native_bytes": len(native), "n_sw_bytes": len(sw_mid),
            "match": cand == sw_mid}


def probe_video(name: str, path: str) -> dict:
    meta = ffprobe_meta(path)
    w, h, pix = meta["w"], meta["h"], meta["pix_fmt"]
    mid, nat = mid_fmt(pix), native_fmt(pix)
    dur = meta["duration"]
    ts = [round(dur * 0.25, 3), round(dur * 0.65, 3)]
    print(f"[{name}] {meta['codec']} {pix} {w}x{h} dur={dur:.1f} "
          f"mid={mid} native={nat} ts={ts}", flush=True)

    res: dict = {"meta": meta, "mid_fmt": mid, "native_fmt": nat, "points": []}
    for t in ts:
        p: dict = {"t": t}
        try:
            sw_mid_b, _ = run([str(FFMPEG), *BASE, "-ss", f"{t:.6f}", "-i", path,
                               "-frames:v", "1", "-an", "-f", "rawvideo",
                               "-pix_fmt", mid, "-"])
            p["sw_mid_md5"] = md5(sw_mid_b)

            hw_mid_b, _ = run([str(FFMPEG), *BASE, "-hwaccel", HW,
                               "-ss", f"{t:.6f}", "-i", path,
                               "-frames:v", "1", "-an", "-f", "rawvideo",
                               "-pix_fmt", mid, "-"])
            p["hw_mid_md5"] = md5(hw_mid_b)
            p["decode_layer_identical"] = p["sw_mid_md5"] == p["hw_mid_md5"]

            sw_bgr_b, _ = run([str(FFMPEG), *BASE, "-ss", f"{t:.6f}", "-i", path,
                               "-frames:v", "1", "-an", "-f", "rawvideo",
                               "-pix_fmt", "bgr24", "-"])
            p["sw_bgr_md5"] = md5(sw_bgr_b)

            hw_bgr_b, _ = run([str(FFMPEG), *BASE, "-hwaccel", HW,
                               "-ss", f"{t:.6f}", "-i", path,
                               "-frames:v", "1", "-an", "-f", "rawvideo",
                               "-pix_fmt", "bgr24", "-"])
            p["hw_bgr_md5"] = md5(hw_bgr_b)
            p["bgr_direct_differs"] = p["sw_bgr_md5"] != p["hw_bgr_md5"]

            unified = ["-vf", f"format={mid},format=bgr24"]
            hw_uni_b, _ = run([str(FFMPEG), *BASE, "-hwaccel", HW,
                               "-ss", f"{t:.6f}", "-i", path,
                               "-frames:v", "1", "-an", *unified,
                               "-f", "rawvideo", "-"])
            p["hw_unified_md5"] = md5(hw_uni_b)
            p["unified_matches_product_sw"] = p["hw_unified_md5"] == p["sw_bgr_md5"]

            sw_uni_b, _ = run([str(FFMPEG), *BASE, "-ss", f"{t:.6f}", "-i", path,
                               "-frames:v", "1", "-an", *unified,
                               "-f", "rawvideo", "-"])
            p["sw_unified_md5"] = md5(sw_uni_b)
            p["control_sw_unified_matches_product_sw"] = \
                p["sw_unified_md5"] == p["sw_bgr_md5"]

            nat_b, _ = run([str(FFMPEG), *BASE, "-hwaccel", HW,
                            "-ss", f"{t:.6f}", "-i", path,
                            "-frames:v", "1", "-an", "-f", "rawvideo",
                            "-pix_fmt", nat, "-"])
            p["manual_repack"] = manual_repack(nat_b, sw_mid_b, w, h, pix)
        except RuntimeError as e:
            p["error"] = str(e)[:300]
        res["points"].append(p)
        keep = {k: v for k, v in p.items() if not k.endswith("_md5")}
        print(f"    t={t}: {json.dumps(keep, ensure_ascii=False)}", flush=True)
    return res


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    for name, path in VIDEOS:
        if not Path(path).exists():
            print(f"[{name}] MISSING: {path}", flush=True)
            report[name] = {"error": "missing"}
            continue
        try:
            report[name] = probe_video(name, path)
        except Exception as e:  # noqa: BLE001
            print(f"[{name}] PROBE ERROR: {e}", flush=True)
            report[name] = {"error": str(e)[:300]}

    out_json = OUT / "probe_hwaccel_mech.json"
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"\nsaved -> {out_json}", flush=True)

    print("\n===== 机制摘要 =====")
    for name, r in report.items():
        if "error" in r and "points" not in r:
            print(f"{name}: {r['error']}")
            continue
        for p in r["points"]:
            if "error" in p:
                print(f"{name} t={p['t']}: ERROR {p['error'][:120]}")
                continue
            print(f"{name} t={p['t']}: 解码层一致={p['decode_layer_identical']} "
                  f"直转bgr不同={p['bgr_direct_differs']} "
                  f"统一链==现役sw={p['unified_matches_product_sw']} "
                  f"控制组ok={p['control_sw_unified_matches_product_sw']} "
                  f"手工重排={p['manual_repack']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
