"""common — POC 共享工具：session 构建、帧生成、preprocess、metric、进程内存采样。

只读复用 ``device.dinov2_model.DinoV2Small`` / ``_imagenet_preprocess``；不改任何生产源码。
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path

import numpy as np

POC_DIR = Path(__file__).resolve().parent
SRC = POC_DIR.parents[1] / "src"
if str(SRC) not in os.sys.path:
    os.sys.path.insert(0, str(SRC))

import cv2  # noqa: E402

# 冻结模型/预处理/后端（只读）
from device import CPUBackend, resolve_dinov2_weights  # noqa: E402
from device.dinov2_model import DinoV2Small, _imagenet_preprocess  # noqa: E402

MODEL_PATH = POC_DIR / "export_model" / "dinov2_cls_384.onnx"


# --------------------------------------------------------------------------- #
# 引擎 / 会话
# --------------------------------------------------------------------------- #
def make_session(model_path: Path = MODEL_PATH, providers=None):
    import onnxruntime as ort

    if providers is None:
        providers = ["CPUExecutionProvider"]
    return ort.InferenceSession(str(model_path), providers=providers)


def torch_model() -> DinoV2Small:
    t = DinoV2Small()
    t.load_state_dict(torch_load_statedict())
    t.eval()
    return t


def torch_load_statedict():
    import torch

    return torch.load(str(resolve_dinov2_weights()), map_location="cpu")


# --------------------------------------------------------------------------- #
# 帧 / 输入
# --------------------------------------------------------------------------- #
def gen_frames(n: int, size: tuple[int, int] = (960, 540), rng_seed: int = 0) -> list[np.ndarray]:
    """生成 ``n`` 个随机 BGR uint8 帧（真实预处理会再缩到 518x518）。"""
    rng = np.random.RandomState(rng_seed)
    h, w = size[1], size[0]
    return [rng.randint(0, 256, (h, w, 3), dtype=np.uint8) for _ in range(n)]


def preprocess_np(frames: list[np.ndarray]) -> np.ndarray:
    """复用冻结 ``_imagenet_preprocess``（逐帧）-> [N,3,518,518] float32 NCHW。"""
    return np.stack([_imagenet_preprocess(f).numpy()[0] for f in frames], axis=0).astype(np.float32)


def l2norm(x: np.ndarray) -> np.ndarray:
    """与 ``embed_frames`` 相同的 numpy L2（norm 1e-8 floor）。"""
    n = np.linalg.norm(x, axis=1, keepdims=True)
    return x / np.maximum(n, 1e-8)


# --------------------------------------------------------------------------- #
# 推理 drivers（对 preprocessed 输入跑 forward，返回 raw CLS [N,384]）
# --------------------------------------------------------------------------- #
def run_torch_forward(model, inputs: np.ndarray, batch: int) -> np.ndarray:
    import torch

    outs = []
    with torch.no_grad():
        for i in range(0, len(inputs), batch):
            b = torch.from_numpy(inputs[i:i + batch])
            outs.append(model(b).detach().cpu().numpy())
    return np.concatenate(outs, axis=0) if outs else np.zeros((0, 384), np.float32)


def run_onnx_forward(sess, inputs: np.ndarray, batch: int) -> np.ndarray:
    outs = []
    for i in range(0, len(inputs), batch):
        b = np.ascontiguousarray(inputs[i:i + batch])
        outs.append(sess.run(["embedding"], {"input": b})[0])
    return np.concatenate(outs, axis=0) if outs else np.zeros((0, 384), np.float32)


# --------------------------------------------------------------------------- #
# metric
# --------------------------------------------------------------------------- #
def cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    return float(np.sum(a * b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))


def cosine_rowwise(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    an = a / np.maximum(np.linalg.norm(a, axis=1, keepdims=True), 1e-12)
    bn = b / np.maximum(np.linalg.norm(b, axis=1, keepdims=True), 1e-12)
    return np.sum(an * bn, axis=1)


def max_abs_diff(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.max(np.abs(a - b)))


def mean_abs_diff(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.mean(np.abs(a - b)))


def l2_norms(x: np.ndarray) -> np.ndarray:
    return np.linalg.norm(x, axis=1)


# --------------------------------------------------------------------------- #
# 进程内存（psutil 未装 -> ctypes GetProcessMemoryInfo）
# --------------------------------------------------------------------------- #
def proc_mem_mb() -> float | None:
    try:
        import ctypes.wintypes as wt

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

        psapi = ctypes.windll.psapi
        kern = ctypes.windll.kernel32
        c = PMC()
        c.cb = ctypes.sizeof(PMC)
        kern.GetCurrentProcess.restype = ctypes.c_void_p
        h = kern.GetCurrentProcess()
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PMC), wt.DWORD]
        psapi.GetProcessMemoryInfo.restype = ctypes.c_bool
        if psapi.GetProcessMemoryInfo(h, ctypes.byref(c), c.cb):
            return float(c.WorkingSetSize) / 1048576.0
        return None
    except Exception:
        return None


def list_gpu_names() -> list[str]:
    """只读列出 Windows 显示适配器名（确认 AMD RX 6750 GRE 在场）。"""
    try:
        r = __import__("subprocess").run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
            capture_output=True, text=True, timeout=45, creationflags=0x08000000)
        names = [ln.strip() for ln in r.stdout.splitlines() if ln.strip() and not ln.startswith("Name")]
        return names if names else [r.stdout.strip()] if r.stdout.strip() else []
    except Exception as exc:
        return [f"<gpu query failed: {exc}>"]


# convenience re-export for bench
DmlExecutionProvider = "DmlExecutionProvider"
CPUExecutionProvider = "CPUExecutionProvider"
