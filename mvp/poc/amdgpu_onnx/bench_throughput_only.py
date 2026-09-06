"""DML 吞吐上限实测 —— 回答「能否 30fps 全片解析」。
纯本地, 不改任何生产源码; 只测 ONNX DirectML 前向吞吐(合成帧)。
"""
from __future__ import annotations
import sys, time, os
from pathlib import Path

POC = Path(__file__).resolve().parent
sys.path.insert(0, str(POC))
sys.path.insert(0, str(POC.parents[1] / "src"))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from common import MODEL_PATH, gen_frames, preprocess_np, l2norm  # noqa
import numpy as np  # noqa

import onnxruntime as ort  # noqa

print("=== DML 吞吐上限实测 (RX 6750 GRE + DINOv2 ViT-S/14 CLS-384) ===", flush=True)
print(f"model: {MODEL_PATH}", flush=True)

def build_session(extra=None):
    prov = [("DmlExecutionProvider", {"device_id": 0}), "CPUExecutionProvider"]
    return ort.InferenceSession(str(MODEL_PATH), providers=prov, sess_options=extra)

def bench(sess, inputs, batch, reps=5):
    # warmup
    for _ in range(2):
        for i in range(0, len(inputs), batch):
            sess.run(["embedding"], {"input": np.ascontiguousarray(inputs[i:i+batch])})
    t0 = time.perf_counter()
    n = 0
    for _ in range(reps):
        for i in range(0, len(inputs), batch):
            sess.run(["embedding"], {"input": np.ascontiguousarray(inputs[i:i+batch])})
            n += len(inputs[i:i+batch])
    dt = time.perf_counter() - t0
    return n / dt

# 预生成帧: 960x540 随机帧(模拟真实源), 统一 preprocess
N = 512
frames = gen_frames(N, size=(960, 540))
inputs = preprocess_np(frames)  # [N,3,518,518]
print(f"preprocessed: {inputs.shape} dtype={inputs.dtype}", flush=True)

sess = build_session()
print(f"providers: {sess.get_providers()}", flush=True)

print("\n--- batch 扫描 (fp32) ---", flush=True)
results = {}
for b in [1, 4, 8, 16, 32]:
    try:
        fps = bench(sess, inputs, b)
        results[f"b{b}"] = round(fps, 1)
        print(f"batch={b:2d}  {fps:7.1f} fps  ({1000.0/fps:6.2f} ms/帧)", flush=True)
    except Exception as e:
        print(f"batch={b:2d}  FAILED: {type(e).__name__}: {str(e)[:100]}", flush=True)

# fp16 测试
print("\n--- fp16 测试 (ORT graph_optimization + fp16 enable) ---", flush=True)
try:
    so = ort.SessionOptions()
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    # 通过优化级别本身观察差异
    sess_opt = build_session(extra=so)
    for b in [8, 16]:
        fps = bench(sess_opt, inputs, b)
        print(f"batch={b:2d} (opt_all)  {fps:7.1f} fps", flush=True)
except Exception as e:
    print(f"fp16/opt test FAILED: {type(e).__name__}: {str(e)[:120]}", flush=True)

print("\n=== 摘要 ===", flush=True)
print(json_dump := {"fps_by_batch": results}, flush=True)
out = Path(__file__).resolve().parents[2] / "work" / "dml_throughput.json"
import json
out.write_text(json.dumps({"dml_fps_by_batch": results}, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"saved {out}", flush=True)
