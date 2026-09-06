# -*- coding: utf-8 -*-
"""M4 重跑: batch=1 为什么在生产路径不管用——逐级分解 embed 吞吐(研究侧, 零 runtime)。

对照两种管线的每一级 (同一批真实帧):
  A. M4 口径: ffmpeg rawvideo 直出 518x518 + 逐帧 preprocess + 单帧 sess.run(batch=1)
  B. 生产口径: iter_frames 全分辨率解码 -> _imagenet_preprocess(逐帧) -> embed_frames 分块 forward
分解: 解码 / 预处理 / forward(batch=1/8/16) / 生产 embed_frames 端到端
输出: 每级 fps + 占比, 定位 batch 无效化的原因。
"""
import os
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("SVL_DATA_DIR", r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data")
os.environ.setdefault("MEDIA_FFMPEG", r"D:\claudework\benchmark\tools\ffmpeg.exe")
os.environ.setdefault("MEDIA_FFPROBE", r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
os.environ.setdefault("SVL_DML_MODEL", r"C:/Users/Bsaizne/AppData/Local/SourceVideoLocator/models/dinov2_cls_384/dinov2_cls_384.onnx")
BENCH = Path(r"D:\claudework\benchmark")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "mvp" / "poc" / "amdgpu_onnx"))
sys.path.insert(0, str(BENCH / "mvp" / "poc" / "amdgpu_onnx"))

import numpy as np  # noqa: E402
from app.locator_service import SourceLocatorService  # noqa: E402
from device.dinov2_model import _imagenet_preprocess  # noqa: E402
from infrastructure.config import load_config  # noqa: E402

FFMPEG = r"D:\claudework\benchmark\tools\ffmpeg.exe"
VIDEO = r"D:\ProjectXIXI\test2\test2-om.mp4"
N = 240          # 取样帧数
T0 = 300.0       # 起始时间(跳过片头)


def fps(n, t):
    return n / t if t > 0 else 0.0


def main():
    cfg = load_config()
    srv = SourceLocatorService(config=cfg)
    be = srv.backend
    W = H = 518

    print(f"=== 取样 {N} 帧 @ test2-om.mp4 ({T0}s 起) ===", flush=True)

    # 1) 生产解码: iter_frames 1fps 全分辨率
    t0 = time.perf_counter()
    frames = []
    for _, f in srv.ffmpeg.iter_frames(VIDEO, 1.0, start=T0, end=T0 + N * 1.0):
        frames.append(f)
        if len(frames) >= N:
            break
    t_decode = time.perf_counter() - t0
    h, w = frames[0].shape[:2]
    print(f"[1] 生产解码 iter_frames(全分辨率 {w}x{h}): {t_decode:.1f}s = {fps(len(frames), t_decode):.1f} fps", flush=True)

    # 2) 预处理 only(全分辨率帧 -> 518x518 tensor)
    t0 = time.perf_counter()
    pre = [_imagenet_preprocess(f).numpy()[0] for f in frames]
    t_pre = time.perf_counter() - t0
    print(f"[2] 预处理 _imagenet_preprocess 逐帧: {t_pre:.1f}s = {fps(N, t_pre):.1f} fps ({t_pre/N*1000:.1f} ms/帧)", flush=True)

    # 3) forward only (batch=1/8/16), 输入已预处理
    import onnxruntime as ort
    sess = ort.InferenceSession(os.environ["SVL_DML_MODEL"],
                                providers=[("DmlExecutionProvider", {"device_id": 0}),
                                           "CPUExecutionProvider"])
    arr = np.stack(pre, axis=0).astype(np.float32)
    # warmup
    for i in range(4):
        sess.run(["embedding"], {"input": np.ascontiguousarray(arr[i:i+1])})
    for bs in (1, 8, 16):
        t0 = time.perf_counter()
        for i in range(0, N, bs):
            sess.run(["embedding"], {"input": np.ascontiguousarray(arr[i:i+bs])})
        t = time.perf_counter() - t0
        print(f"[3] forward only batch={bs:<2}: {t:.1f}s = {fps(N, t):.1f} fps ({t/N*1000:.1f} ms/帧)", flush=True)

    # 4) 生产 embed_frames 端到端 (batch=8 / 1) —— 同一批全分辨率帧
    for bs in (8, 1):
        cfg.device.dml_batch_size = bs
        be2 = type(be)(onnx_model=os.environ["SVL_DML_MODEL"],
                       batch_size=bs) if hasattr(be, "onnx_model") else None
        t0 = time.perf_counter()
        if be2 is not None:
            be2.embed_frames(frames)
            t = time.perf_counter() - t0
            print(f"[4] 生产 embed_frames 端到端 batch={bs:<2}: {t:.1f}s = {fps(N, t):.1f} fps "
                  f"(预处理+forward, 不含解码)", flush=True)
    # 用原 backend 也跑一遍 batch=1 (直接改属性不可靠, 直接小批循环)
    t0 = time.perf_counter()
    for i in range(0, N, 1):
        be.embed_frames(frames[i:i+1], batch_size=1)
    t = time.perf_counter() - t0
    print(f"[4b] 生产 embed_frames 逐帧调用 batch=1: {t:.1f}s = {fps(N, t):.1f} fps", flush=True)

    # 5) M4 口径复刻: ffmpeg rawvideo 直出 518 + 逐帧 preprocess + 单帧 run
    t0 = time.perf_counter()
    proc = subprocess.run(
        [FFMPEG, "-y", "-v", "error", "-ss", f"{T0:.3f}", "-t", f"{N:.0f}",
         "-i", VIDEO, "-vf", "fps=1.0,scale=518:518", "-f", "rawvideo",
         "-pix_fmt", "bgr24", "-frames:v", str(N), "-"], capture_output=True)
    t_m4decode = time.perf_counter() - t0
    raw = proc.stdout
    n518 = min(len(raw) // (H * W * 3), N)
    buf = np.frombuffer(raw[:n518 * H * W * 3], dtype=np.uint8).reshape(n518, H, W, 3)
    print(f"[5] M4 口径 ffmpeg 直出 518x518: 解码+缩放 {t_m4decode:.1f}s = {fps(n518, t_m4decode):.1f} fps", flush=True)
    t0 = time.perf_counter()
    for i in range(n518):
        inp = np.stack([_imagenet_preprocess(buf[i]).numpy()[0]]).astype(np.float32)
        sess.run(["embedding"], {"input": np.ascontiguousarray(inp)})
    t = time.perf_counter() - t0
    print(f"[5b] M4 口径 518 帧 逐帧 preprocess+run: {t:.1f}s = {fps(n518, t):.1f} fps "
          f"(pre {(_imagenet_preprocess(buf[0]).numpy()[0].nbytes/1e6):.1f}MB/帧输入)", flush=True)

    print("\n结论指向: 对比 [1][2][3][4][5] —— batch 在哪一级被无效化(预处理/解码/分块开销)", flush=True)


if __name__ == "__main__":
    main()
