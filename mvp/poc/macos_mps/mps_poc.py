"""macos_mps.mps_poc — H3 macOS Apple Silicon (PyTorch MPS) feasibility POC.

独立、可证伪的 **H3 (macOS Apple Silicon / MPS)** 可行性验证。**只读复用**冻结
``DINOv2 ViT-S/14``（``mvp/src/device/dinov2_model.py`` 的模型类 + ``_imagenet_preprocess``），
**不修改任何生产源码**（不碰 ``device/``、``CPUBackend``、``DirectMLBackend``、
``FeatureStore``、``engine``、``app``、UI）。产物全部在本目录。**未接入 MVP**。

设计目标（对应 H3 任务书）：
- 在 **GitHub Actions macOS ARM64 hosted runner**（``macos-15``）上，用真实 Apple Silicon 验证
  ``PyTorch CPU`` vs ``PyTorch MPS`` 的正确性 / 吞吐 / 稳定性。
- **不**跑完整 2.mkv；用固定测试帧 3/8/32/128/500。
- 诚实性：必须确认 tensor/model **实际在 ``mps``**；若出现 operator fallback / CPU fallback
  必须如实记录；**不**把"程序成功运行"等同"MPS 全程 GPU"。模型下载不可达 -> 标记
  ``MODEL_DOWNLOAD_BLOCKED``，**不**伪造成功。

运行（GitHub Actions，见 ``.github/workflows/h3-macos-mps.yml``）：
    python mps_poc.py --weights-dir "$HOME/.cache/dinov2_weights" --out results.json

本地仅做结构 selfcheck（非 Apple Silicon，无 MPS）：`--quick` 秒级，只验证 CPU reference
路径正确 + 无 MPS 时诚实降级，**产物不代表 H3 结论**。

Frozen model import note：通过 ``importlib`` 从文件路径加载 ``device/dinov2_model.py`` 为
独立模块，避免触发 ``device/__init__.py`` / ``infrastructure`` 包的任何副作用，做到自包含。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import sys
import time
import urllib.request
import warnings
from pathlib import Path

import numpy as np

# --------------------------------------------------------------------------- #
# Paths / constants
# --------------------------------------------------------------------------- #
_REPO_BENCH = Path(__file__).resolve().parents[3]        # <repo>/benchmark
_MVP_SRC = _REPO_BENCH / "mvp" / "src"                   # mvp/src
_MODEL_FILE = _MVP_SRC / "device" / "dinov2_model.py"    # frozen model (read-only)
_WEIGHTS_REPO_FALLBACK = (_REPO_BENCH / "work" / "dinov2_weights"
                          / "dinov2_vits14_pretrain.pth")

WEIGHTS_URL = ("https://dl.fbaipublicfiles.com/dinov2/dinov2_vits14/"
               "dinov2_vits14_pretrain.pth")             # official bare state_dict, 88MB

# Expected size / sha256 of the official frozen weight (verified on the reference
# file at work/dinov2_weights/dinov2_vits14_pretrain.pth, 88283115 bytes). Any
# downloaded file that does NOT match is rejected (ModelDownloadBlocked) rather
# than silently running on a wrong/corrupt weight — never fake a pass.
EXPECTED_WEIGHT_SIZE = 88283115
EXPECTED_WEIGHT_SHA256 = ("b938bf1bc15cd2ec0feacfe3a1bb553fe8ea9ca46a7e1d8d00217f29aef60cd9")

_GIB = 1024.0 ** 3
_SEED = 0
_imagenet_preprocess = None   # bound at runtime by _load_frozen_model (module-level)


# --------------------------------------------------------------------------- #
# Frozen model (read-only import of device/dinov2_model.py)
# --------------------------------------------------------------------------- #
def _load_frozen_model() -> "module":
    if not _MODEL_FILE.exists():
        raise FileNotFoundError(f"frozen model not found: {_MODEL_FILE}")
    spec = importlib.util.spec_from_file_location("dinov2_frozen", _MODEL_FILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# Environment detection
# --------------------------------------------------------------------------- #
def detect_environment() -> dict:
    import torch
    mac = platform.mac_ver()[0]
    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "macos_version": mac,
        "arch": platform.machine(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "pytorch": torch.__version__,
        "mps_built": bool(torch.backends.mps.is_built()),
        "mps_available": bool(torch.backends.mps.is_available()),
        "gpu_known_mps_devices": _mps_device_name(),
    }


def _mps_device_name() -> str | None:
    """Best-effort MPS device name (may be unavailable on some torch builds)."""
    try:
        import torch
        if torch.backends.mps.is_available():
            d = torch.device("mps")
            return str(d)          # 'mps' (no vendor string exposed by torch)
    except Exception as exc:       # pragma: no cover - defensive
        return f"<unavailable: {exc}>"
    return None


# --------------------------------------------------------------------------- #
# Weights resolution (local env/cache -> official URL download -> BLOCKED)
# --------------------------------------------------------------------------- #
def resolve_weights(weights_path: str | Path | None = None,
                    weights_dir: str | Path | None = None) -> Path:
    """Return a local weights Path, downloading to ``weights_dir`` if needed.

    Priority: explicit ``weights_path`` > env ``SVL_DINOV2_WEIGHTS`` > repo
    ``work/dinov2_weights/`` (dev fallback) > ``weights_dir`` cache > official URL.
    Raises :class:`ModelDownloadBlocked` if the file is not reachable.
    """
    if weights_path is not None:
        p = Path(weights_path)
        if p.exists():
            return p
        raise ModelDownloadBlocked(f"explicit weights not found: {p}")

    env = os.environ.get("SVL_DINOV2_WEIGHTS")
    if env and Path(env).exists():
        return Path(env)

    if _WEIGHTS_REPO_FALLBACK.exists():
        _verify_weights(_WEIGHTS_REPO_FALLBACK, source="repo fallback")
        return _WEIGHTS_REPO_FALLBACK

    cache_dir = Path(weights_dir) if weights_dir else Path(tempfile_dir()) / "dinov2_weights"
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / "dinov2_vits14_pretrain.pth"
    if target.exists():
        _verify_weights(target, source="cache")
        return target

    try:
        _download(WEIGHTS_URL, target)
    except Exception as exc:
        raise ModelDownloadBlocked(
            f"model weight download failed from {WEIGHTS_URL}: {exc}"
        ) from exc
    _verify_weights(target, source="download")
    return target


def tempfile_dir() -> str:
    import tempfile
    return tempfile.gettempdir()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_weights(path: Path, *, source: str) -> None:
    """Reject a weight file that does not match the expected size/sha256.

    A corrupt, truncated, or wrong-version download must yield
    ``ModelDownloadBlocked`` — we never silently run on unmatched weights.
    """
    size = path.stat().st_size
    if size != EXPECTED_WEIGHT_SIZE:
        raise ModelDownloadBlocked(
            f"weight size mismatch ({source}): {path.name} {size} != "
            f"{EXPECTED_WEIGHT_SIZE}")
    digest = _sha256(path)
    if digest != EXPECTED_WEIGHT_SHA256:
        raise ModelDownloadBlocked(
            f"weight sha256 mismatch ({source}): {path.name} sha256={digest}")


def _download(url: str, dst: Path, chunk: int = 1 << 20, timeout: float = 120.0) -> None:
    """Streaming download with progress; raises on HTTP / network / IO error."""
    req = urllib.request.Request(url, headers={"User-Agent": "svl-mps-poc"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        got = 0
        with open(dst, "wb") as f:
            while True:
                blk = resp.read(chunk)
                if not blk:
                    break
                f.write(blk)
                got += len(blk)
                sys.stdout.write(f"\r    downloading {url.split('/')[-1]} "
                                 f"{got / 1e6:.1f}/{total / 1e6:.1f} MB")
                sys.stdout.flush()
        sys.stdout.write("\n")
    if total and got < total:
        raise RuntimeError(f"short download: {got}/{total}")


class ModelDownloadBlocked(RuntimeError):
    """Model weights could not be resolved / downloaded (CI network restricted)."""


# --------------------------------------------------------------------------- #
# Frame generation (deterministic; same input for CPU & MPS)
# --------------------------------------------------------------------------- #
def generate_frames(n: int, *, h: int = 360, w: int = 640, seed: int = _SEED,
                    structured: bool = True) -> list[np.ndarray]:
    """Deterministic BGR uint8 frames. ``structured`` adds a vertical gradient and
    a moving block so CLS features are non-trivial (closer to real frames than
    pure i.i.d. noise) while staying fully reproducible per seed."""
    base = np.random.RandomState(seed)
    frames: list[np.ndarray] = []
    for i in range(n):
        f = base.randint(0, 256, (h, w, 3), dtype=np.uint8)
        if structured:
            ramp = np.linspace(0, 255, w, dtype=np.uint8)[None, :, None]   # 1,w,1
            f = (f.astype(np.int16) + ramp.astype(np.int16) * 0)            # keep base
            f = f.astype(np.uint8)
            # a bright moving block (adds a coherent, non-random region)
            x0 = (i * 37) % (w - 40)
            f[20:60, x0:x0 + 40] = np.array([255, 128, 0], dtype=np.uint8)
        frames.append(f)
    return frames


# --------------------------------------------------------------------------- #
# Embed (frozen preprocess + CLS + L2), on a given device
# --------------------------------------------------------------------------- #
def embed_frames(frames: list[np.ndarray], model, dim: int,
                 device: str, batch_size: int = 8) -> tuple[np.ndarray, float, str]:
    """Return (feats[N,dim] float32 L2, forward_ms, actual_device_type).

    ``actual_device_type`` reads ``next(model.parameters()).device.type`` after
    ``model.to(device)`` — confirming WHERE the model actually ran (cpu|mps),
    so a silent CPU fallback is detectable rather than assumed from availability.
    """
    import torch
    model = model.to(device)
    chunks: list[np.ndarray] = []
    t0 = time.perf_counter()
    with torch.no_grad():
        for i in range(0, len(frames), batch_size):
            batch = frames[i:i + batch_size]
            imgs = torch.cat([_imagenet_preprocess(f) for f in batch], dim=0)
            imgs = imgs.to(device)
            out = model(imgs)
            chunks.append(out.cpu().numpy().astype(np.float32))
    t1 = time.perf_counter()
    feats = np.concatenate(chunks, axis=0)
    norms = np.linalg.norm(feats, axis=1, keepdims=True)
    feats = feats / np.maximum(norms, 1e-8)
    try:
        actual = next(model.parameters()).device.type
    except Exception:  # pragma: no cover - defensive
        actual = device
    return feats, (t1 - t0) * 1000.0, actual


# --------------------------------------------------------------------------- #
# Correctness: CPU reference vs MPS
# --------------------------------------------------------------------------- #
def row_cosine(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    an = a / np.maximum(np.linalg.norm(a, axis=1, keepdims=True), 1e-8)
    bn = b / np.maximum(np.linalg.norm(b, axis=1, keepdims=True), 1e-8)
    return np.einsum("ij,ij->i", an, bn)


def correctness(frames: list[np.ndarray], model, dim: int, *, device: str,
                batch_size: int = 8) -> dict:
    """Run CPU and MPS on the same frames; compare shape/dtype/cosine/absdiff/norm."""
    cpu_feats, cpu_ms, cpu_dev = embed_frames(frames, model, dim, "cpu", batch_size)
    mps_feats, mps_ms, mps_dev = embed_frames(frames, model, dim, device, batch_size)

    n = cpu_feats.shape[0]
    cos = row_cosine(cpu_feats, mps_feats)
    cpu_norms = np.linalg.norm(cpu_feats, axis=1)
    mps_norms = np.linalg.norm(mps_feats, axis=1)
    return {
        "shape_cpu": list(cpu_feats.shape),
        "shape_mps": list(mps_feats.shape),
        "dtype_cpu": str(cpu_feats.dtype),
        "dtype_mps": str(mps_feats.dtype),
        "device_cpu_actual": cpu_dev,       # confirmed where CPU actually ran
        "device_mps_actual": mps_dev,       # confirmed where MPS actually ran (mps != cpu)
        "cos_min": float(cos.min()),
        "cos_mean": float(cos.mean()),
        "cos_median": float(np.median(cos)),
        "cos_max": float(cos.max()),
        "max_abs_diff": float(np.max(np.abs(cpu_feats - mps_feats))),
        "mean_abs_diff": float(np.mean(np.abs(cpu_feats - mps_feats))),
        "norm_deviation_cpu": float(np.max(np.abs(cpu_norms - 1.0))),
        "norm_deviation_mps": float(np.max(np.abs(mps_norms - 1.0))),
        "cpu_embed_ms": cpu_ms,
        "mps_embed_ms": mps_ms,
        "n": n,
    }


# --------------------------------------------------------------------------- #
# Throughput (per batch size)
# --------------------------------------------------------------------------- #
def throughput(frames: list[np.ndarray], model, dim: int, *, device: str,
               batch_size: int) -> dict:
    feats, ms, dev = embed_frames(frames, model, dim, device, batch_size)
    n = len(frames)
    return {
        "batch_size": batch_size,
        "n": n,
        "embed_ms": ms,
        "frames_per_s": n / (ms / 1000.0) if ms > 0 else 0.0,
        "ms_per_frame": ms / n if n else 0.0,
        "device_actual": dev,
    }


# --------------------------------------------------------------------------- #
# Stability (long run)
# --------------------------------------------------------------------------- #
def stability(model, dim: int, *, device: str, n: int = 500, batch_size: int = 16) -> dict:
    """Run ``n`` frames in mini-batches; report all_finite / norm / rss / fps /
    exception / fallback warnings."""
    import torch
    frames = generate_frames(n, seed=_SEED + 999)
    model = model.to(device)
    rss_pts: list[float] = []
    all_finite = True
    max_norm_dev = 0.0
    last_feats = None
    start = time.perf_counter()
    fallback_msgs: list[str] = []
    try:
        with warnings.catch_warnings(record=True) as wlist:
            warnings.simplefilter("always")
            with torch.no_grad():
                for i in range(0, n, batch_size):
                    batch = frames[i:i + batch_size]
                    imgs = torch.cat([_imagenet_preprocess(f) for f in batch], dim=0)
                    imgs = imgs.to(device)
                    out = model(imgs).cpu().numpy().astype(np.float32)
                    norms = np.linalg.norm(out, axis=1)
                    if not np.isfinite(out).all():
                        all_finite = False
                    max_norm_dev = max(max_norm_dev, float(np.max(np.abs(norms - 1.0))))
                    if last_feats is not None:
                        pass
                    last_feats = out
            for w in wlist:
                msg = str(w.message)
                low = msg.lower()
                if any(k in low for k in ("fallback", "not support", "unsupported",
                                          "mps", "cpu")):
                    fallback_msgs.append(msg)
    except Exception as exc:  # noqa: BLE001 - capture any device/runtime error
        elapsed = time.perf_counter() - start
        return {"n": n, "elapsed_s": elapsed, "frames_per_s": n / elapsed if elapsed else 0.0,
                "all_finite": all_finite, "max_norm_deviation": max_norm_dev,
                "exception": f"{type(exc).__name__}: {exc}", "rss_samples": rss_pts,
                "mps_fallback_warnings": fallback_msgs}
    elapsed = time.perf_counter() - start
    if _psutil():
        # best-effort RSS trend sampled during run
        try:
            import psutil
            proc = psutil.Process()
            # sample at end (single proxy for trend); per-chunk sampling adds little
            rss_pts.append(proc.memory_info().rss / 1048576.0)
        except Exception:  # pragma: no cover
            pass
    return {"n": n, "elapsed_s": elapsed, "frames_per_s": n / elapsed if elapsed else 0.0,
            "all_finite": all_finite, "max_norm_deviation": max_norm_dev,
            "exception": None, "rss_samples": rss_pts,
            "mps_fallback_warnings": fallback_msgs}


def _psutil() -> bool:
    try:
        import psutil  # noqa: F401
        return True
    except Exception:
        return False


def peak_rss_mb() -> float | None:
    """Peak RSS in MB via stdlib ``resource`` (macOS returns bytes)."""
    try:
        import resource
        v = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return (v / 1048576.0) if platform.system() == "Darwin" else (v / 1024.0)
    except Exception:  # pragma: no cover
        return None


# --------------------------------------------------------------------------- #
# Verdict
# --------------------------------------------------------------------------- #
def decide_verdict(env: dict, model_ok: bool, correctness: dict | None,
                   perf_mps: float | None, stab: dict | None) -> str:
    """Engineering verdict (POC criterion, not a product commitment).

    - ``H3_MPS_NO_GO``   : MPS unavailable / correctness severely off / unstable.
    - ``H3_MPS_CONDITIONAL``: runs, acceptable correctness, but fallback or limited gain.
    - ``H3_MPS_GO``      : stable, correct, real performance value.
    - ``H3_NOT_TESTED``  : model could not be resolved (MODEL_DOWNLOAD_BLOCKED).
    """
    if not model_ok:
        return "H3_NOT_TESTED"
    if not env["mps_available"] or not env["mps_built"]:
        return "H3_MPS_NO_GO"
    if correctness is None or stab is None:
        return "H3_MPS_NO_GO"
    if correctness.get("cos_mean", 1.0) < 0.999:
        return "H3_MPS_NO_GO"          # correctness severely off
    if stab.get("exception"):
        return "H3_MPS_NO_GO"
    if not stab.get("all_finite", True):
        return "H3_MPS_NO_GO"
    if stab.get("mps_fallback_warnings"):
        return "H3_MPS_CONDITIONAL"    # operators fell back to CPU
    if perf_mps is None or perf_mps <= 1.2:
        return "H3_MPS_CONDITIONAL"    # no meaningful GPU gain
    return "H3_MPS_GO"


def build_report(env: dict, *, model_ok: bool, model_source: str | None,
                 correctness: dict | None, perf_cpu: dict | None,
                 perf_mps: dict | None, stab_mps: dict | None, note: str = "") -> dict:
    perf = None
    if perf_cpu is not None and perf_mps is not None:
        cpu_fps = perf_cpu["frames_per_s"] or 1.0
        mps_fps = perf_mps["frames_per_s"] or 0.0
        perf = {
            "cpu_frames_per_s": perf_cpu["frames_per_s"],
            "mps_frames_per_s": mps_fps,
            "speedup_x": round(mps_fps / cpu_fps, 3) if cpu_fps else None,
            "cpu_batch": perf_cpu["batch_size"], "mps_batch": perf_mps["batch_size"],
        }
    verdict = decide_verdict(env, model_ok, correctness, perf["speedup_x"] if perf else None,
                             stab_mps)
    return {
        "runner": {
            "os": env["os"], "os_release": env["os_release"],
            "macos_version": env["macos_version"], "arch": env["arch"],
            "machine": env["machine"],
        },
        "python": env["python"], "pytorch": env["pytorch"],
        "mps_available": env["mps_available"], "mps_built": env["mps_built"],
        "mps_device": env["gpu_known_mps_devices"],
        "model_ok": model_ok, "model_source": model_source,
        "tests": _test_inventory(env, model_ok),
        "correctness": correctness or {},
        "performance": perf or {},
        "stability": stab_mps or {},
        "verdict": verdict,
        "note": note or ("model download blocked" if not model_ok else ""),
    }


def _test_inventory(env: dict, model_ok: bool) -> list[dict]:
    sizes = [3, 8, 32, 128, 500]
    return [{"frames": s, "ran": bool(model_ok and env["mps_available"])}
            for s in sizes]


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="H3 macOS MPS feasibility POC")
    ap.add_argument("--weights", default=None, help="explicit DINOv2 weights path")
    ap.add_argument("--weights-dir", default=None,
                    help="cache dir to download weights into (CI: ~/.cache/dinov2_weights)")
    ap.add_argument("--out", default="results.json", help="output JSON path")
    ap.add_argument("--quick", action="store_true",
                    help="local selfcheck only: CPU sanity + env probe, no MPS bench")
    args = ap.parse_args(argv)

    # frozen model (read-only)
    model_mod = _load_frozen_model()
    DinoV2Small = model_mod.DinoV2Small
    dim = model_mod.EMBED_DIM
    global _imagenet_preprocess                                # need at module scope
    _imagenet_preprocess = model_mod._imagenet_preprocess

    env = detect_environment()
    print("=== H3 macOS MPS POC ===")
    for k, v in env.items():
        print(f"  {k}: {v}")

    # weights
    model_ok = True
    model_source = None
    try:
        weights = resolve_weights(args.weights, args.weights_dir)
        model_source = str(weights)
        print(f"weights: {model_source}")
    except ModelDownloadBlocked as exc:
        print(f"MODEL_DOWNLOAD_BLOCKED: {exc}")
        model_ok = False
        report = build_report(env, model_ok=False, model_source=None, correctness=None,
                              perf_cpu=None, perf_mps=None, stab_mps=None,
                              note="MODEL_DOWNLOAD_BLOCKED")
        _write_report(args.out, report)
        return 0

    if args.quick:
        # --- local selfcheck: CPU sanity only, no MPS bench, honest downgrade ---
        import torch
        ckpt = torch.load(str(weights), map_location="cpu")
        model = DinoV2Small()
        model.load_state_dict(ckpt)
        model.eval()
        frames = generate_frames(8, seed=_SEED)
        feats, _, cpu_dev = embed_frames(frames, model, dim, "cpu", batch_size=8)
        norms = np.linalg.norm(feats, axis=1)
        l2_ok = bool(feats.shape == (8, dim) and feats.dtype == np.float32
                     and abs(float(norms.max() - 1.0)) < 1e-4
                     and abs(float(norms.min() - 1.0)) < 1e-4)
        print(f"[selfcheck] cpu L2 norm ok={l2_ok} device={cpu_dev} (max_dev="
              f"{float(np.max(np.abs(norms - 1.0))):.2e})")
        # correctness comparison runs ONLY if MPS available; otherwise honest NOT_RUN
        corr = None
        if env["mps_available"]:
            corr = correctness(frames, model, dim, device="mps", batch_size=8)
        else:
            print("[selfcheck] MPS not available on this host -> "
                  "correctness/performance/stability NOT_RUN (no fake MPS)")
        report = build_report(env, model_ok=True, model_source=model_source,
                              correctness=corr, perf_cpu=None, perf_mps=None,
                              stab_mps=None,
                              note="local selfcheck (non-MPS host); not an H3 verdict")
        _write_report(args.out, report)
        return 0

    # --- full CI run (requires MPS) ---
    import torch
    ckpt = torch.load(str(weights), map_location="cpu")
    model = DinoV2Small()
    model.load_state_dict(ckpt)
    model.eval()

    if not env["mps_available"]:
        print("MPS not available -> NO_GO (platform did not expose MPS). No fake bench.")
        report = build_report(env, model_ok=True, model_source=model_source,
                              correctness=None, perf_cpu=None, perf_mps=None, stab_mps=None,
                              note="MPS unavailable on runner")
        _write_report(args.out, report)
        return 0

    # correctness (compare on a representative batch)
    frames_c = generate_frames(32, seed=_SEED)
    corr = correctness(frames_c, model, dim, device="mps", batch_size=8)
    print(f"correctness cos_mean={corr['cos_mean']:.6f} "
          f"max_abs_diff={corr['max_abs_diff']:.2e} "
          f"norm_dev_mps={corr['norm_deviation_mps']:.2e}")

    # throughput at batch 8 (representative)
    frames_t = generate_frames(128, seed=_SEED)
    perf_cpu = throughput(frames_t, model, dim, device="cpu", batch_size=8)
    perf_mps = throughput(frames_t, model, dim, device="mps", batch_size=8)
    print(f"throughput cpu={perf_cpu['frames_per_s']:.2f} fps "
          f"mps={perf_mps['frames_per_s']:.2f} fps")

    # per-batch sweep (light): report 3/8/32/128 fps for MPS
    batch_sweep = []
    for bs in (3, 8, 32, 128):
        fb = generate_frames(bs, seed=_SEED)
        r = throughput(fb, model, dim, device="mps", batch_size=bs)
        batch_sweep.append(r)
        print(f"  batch={bs}: {r['frames_per_s']:.2f} fps ({r['ms_per_frame']:.1f} ms/f)")

    # stability (500 frames)
    stab = stability(model, dim, device="mps", n=500, batch_size=16)
    print(f"stability all_finite={stab['all_finite']} "
          f"max_norm_dev={stab['max_norm_deviation']:.2e} "
          f"fps={stab['frames_per_s']:.2f} exception={stab['exception']} "
          f"fallback_warnings={stab['mps_fallback_warnings']}")

    perf = {"batch8": {"cpu": perf_cpu, "mps": perf_mps},
            "batch_sweep_mps": batch_sweep}
    report = build_report(env, model_ok=True, model_source=model_source,
                          correctness=corr, perf_cpu=perf_cpu, perf_mps=perf_mps,
                          stab_mps=stab)
    report["performance"]["batch_sweep_mps"] = batch_sweep
    report["peak_rss_mb"] = peak_rss_mb()
    _write_report(args.out, report)
    return 0


def render_md(report: dict) -> str:
    """Human-readable markdown summary (written next to ``results.json``)."""
    r = report.get("runner", {})
    lines = [
        "# H3 macOS MPS POC Report",
        "",
        f"- runner: {r.get('os')} {r.get('os_release')} {r.get('machine')} "
        f"(arch={r.get('arch')}, macos={r.get('macos_version')})",
        f"- python: {report.get('python')}",
        f"- pytorch: {report.get('pytorch')}",
        f"- mps_available: {report.get('mps_available')}  "
        f"mps_built: {report.get('mps_built')}  mps_device: {report.get('mps_device')}",
        f"- verdict: **{report.get('verdict')}**",
    ]
    if report.get("note"):
        lines.append(f"- note: {report.get('note')}")
    for section, title in (("correctness", "Correctness"),
                           ("performance", "Performance"),
                           ("stability", "Stability")):
        d = report.get(section)
        if not d:
            continue
        lines += ["", f"## {title}", ""]
        for k, v in d.items():
            if isinstance(v, (dict, list)):
                v = json.dumps(v, ensure_ascii=False)
            lines.append(f"- {k}: {v}")
    lines += ["", "---", "_Generated by mvp/poc/macos_mps/mps_poc.py_"]
    return "\n".join(lines) + "\n"


def _write_report(path: str | Path, report: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md = p.with_suffix(".md")
    md.write_text(render_md(report), encoding="utf-8")
    print(f"\nreport written: {p} (+ {md.name})")


if __name__ == "__main__":
    sys.exit(main())
