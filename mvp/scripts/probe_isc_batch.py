# -*- coding: utf-8 -*-
"""probe_isc_batch — ISC@512 批量推理微探针（2026-10-03 性能侧①，纯计时零语义风险）。

背景：v2 宽扫翻默认后 ~150 embeds/歧义段、每帧一次 DML Run 是宽扫成本大头
（四片 +88min）。DINOv2@518 实测 batch=1 最佳（续6），但 ISC 的 EffNetV2-M@512 小得多
⇒ batch>1 可能有效，未测过。本探针定论：batch ∈ {1,4,8,16} 吞吐（fps）与逐帧延迟，
并验证批量输出与逐帧单 Run 数值一致（max|d|）。

方法：真实帧 64 张（2.mkv 窗批量抓帧），导出动态 batch ONNX（torch.onnx.export
dynamic_axes），DML session 各 batch 档预热 3 次计时 10 次；对照单帧 Run。
产物：stdout 表 + `work/probe_isc_batch.json`。

Run: D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_isc_batch.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(BENCH / "engines" / "isc21"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import os  # noqa: E402

os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", (r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
                                        r"\static_ffmpeg\bin\win32\ffprobe.exe"))

import numpy as np  # noqa: E402

OUT_JSON = BENCH / "work" / "probe_isc_batch.json"
WEIGHTS = BENCH / "work" / "isc21_weights_ortho_probe" / "isc_ft_v107.pth.tar"
DYN_ONNX = BENCH / "work" / "isc21_weights_ortho_probe" / "isc_ft_v107_dynbatch.onnx"
SRC = r"D:\video\2.mkv"
N_FRAMES = 64


def build_dynamic_onnx() -> None:
    import torch
    import torch.nn.functional as F
    import timm
    from isc_feature_extractor.model import ISCNet

    ckpt = torch.load(str(WEIGHTS), map_location="cpu", weights_only=False)
    bb = timm.create_model("timm/tf_efficientnetv2_m.in21k_ft_in1k", features_only=True)
    net = ISCNet(backbone=bb, fc_dim=256, p=1.0, eval_p=1.0)
    sd = {s.replace("module.", ""): v for s, v in ckpt["state_dict"].items()}
    net.load_state_dict(sd)
    net.eval()

    class Wrap(torch.nn.Module):
        def __init__(self, n):
            super().__init__()
            self.n = n

        def forward(self, x):
            f = self.n.backbone(x)[-1]
            return F.normalize(self.n.bn(self.n.fc(f.mean(dim=(2, 3)))))

    ex = torch.randn(2, 3, 512, 512)  # 演示 batch 维可变
    torch.onnx.export(
        Wrap(net), ex, str(DYN_ONNX), opset_version=17,
        input_names=["input"], output_names=["emb"],
        dynamic_axes={"input": {0: "batch"}, "emb": {0: "batch"}})
    print(f"[export] 动态 batch ONNX -> {DYN_ONNX.name}", flush=True)


def preprocess(frame_bgr: np.ndarray) -> np.ndarray:
    import cv2
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(rgb, (512, 512), interpolation=cv2.INTER_CUBIC)
    x = rgb.astype(np.float32) / 255.0
    x = (x - 0.5) / 0.5
    return np.ascontiguousarray(x.transpose(2, 0, 1))


def main() -> int:
    import onnxruntime as ort

    from media.ffmpeg import FFmpegIO

    if not DYN_ONNX.exists():
        build_dynamic_onnx()
    sess = ort.InferenceSession(str(DYN_ONNX), providers=[
        ("DmlExecutionProvider", {"device_id": 0}), "CPUExecutionProvider"])
    prov = sess.get_providers()
    print(f"providers={prov}", flush=True)
    assert prov[0] == "DmlExecutionProvider", "必须 DML（GPU-first）"

    io = FFmpegIO()
    dur = io.metadata(SRC).duration
    rng = np.random.RandomState(11)
    times = sorted(round(float(t), 3) for t in rng.uniform(60, dur - 60, N_FRAMES))
    frames = list(io.grab_frames(SRC, times).values())
    batch_in = np.stack([preprocess(f) for f in frames])
    print(f"frames={len(frames)} input={batch_in.shape}", flush=True)

    # 正确性：batch=64 一次 Run vs 逐帧单 Run
    singles = np.stack([sess.run(["emb"], {"input": batch_in[i:i + 1]})[0][0]
                        for i in range(len(batch_in))])
    bulk = sess.run(["emb"], {"input": batch_in})[0]
    maxd = float(np.abs(bulk - singles).max())
    print(f"正确性 batch64 vs 单帧: max|d|={maxd:.2e}", flush=True)

    results = {"providers": prov, "max_diff_batch_vs_single": maxd, "throughput": {}}
    for bs in (1, 4, 8, 16):
        # 预热 3 次
        for _ in range(3):
            for i in range(0, len(batch_in), bs):
                sess.run(["emb"], {"input": np.ascontiguousarray(batch_in[i:i + bs])})
        n_runs = 0
        t0 = time.perf_counter()
        for rep in range(10):
            for i in range(0, len(batch_in), bs):
                sess.run(["emb"], {"input": np.ascontiguousarray(batch_in[i:i + bs])})
                n_runs += 1
        el = time.perf_counter() - t0
        fps = len(batch_in) * 10 / el
        results["throughput"][str(bs)] = {
            "fps": round(fps, 2), "per_frame_ms": round(el * 1000 / (len(batch_in) * 10), 2),
            "runs": n_runs}
        print(f"batch={bs:2d}: {fps:7.2f} fps  ({el*1000/(len(batch_in)*10):6.2f} ms/帧)", flush=True)

    OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"PROBE_DONE -> {OUT_JSON}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
