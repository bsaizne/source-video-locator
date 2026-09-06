"""engine.localization.patch_rerank — patch 最大匹配二阶段重排(Phase 21 E21 验证)。

E21 实验(6 verified 探针):CLS 全局特征对"同场景兄弟机位"无分辨率(p08b 全局排名 32),
patch 级最大匹配把它拉回第 2。聚合 = 每查询 patch 对候选帧 patch 的最大余弦,top-100 均值。

运行时形态:仅对**歧义段**(CLS 弱/蒙太奇/多簇)触发;查询侧 3 帧 + 每候选窗 1 帧。
特征提取(2026-09-05 性能优化):优先 DML ONNX 双输出图(518×518 → CLS[384]+patches[1369,384],
M5 验证与 torch 数值一致 cos=1.0, 18fps vs CPU torch 1.4fps ≈ 13×);资产缺失/DML 不可用
回退 CPU torch forward_features。依赖缺失/权重缺失自动禁用。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

_PATCH_GRID = 37          # 518/14
_TOPK_AGG = 100           # 每查询 patch 最大余弦的 top-K 均值(E21 验证口径)


def _l2(x: np.ndarray) -> np.ndarray:
    return x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-8)


class PatchReranker:
    """懒加载 DINOv2 patch 特征:DML ONNX 优先, 回退 CPU torch;都不可用则 disabled。"""

    def __init__(self, weights_path: str | Path | None,
                 onnx_model: str | Path | None = None, dml_device_id: int = 0):
        self._weights = weights_path
        self._onnx_model = onnx_model
        self._dml_device_id = dml_device_id
        self._model = None
        self._session = None
        self._tried = False
        self.available = False
        self.device = "none"        # "dml" | "cpu"(torch) | "none"

    def _ensure(self) -> bool:
        if self._tried:
            return self.available
        self._tried = True
        if self._try_onnx():
            return True
        return self._try_torch()

    def _try_onnx(self) -> bool:
        if not self._onnx_model or not Path(self._onnx_model).exists():
            return False
        try:
            import onnxruntime as ort  # noqa: import guard

            sess = ort.InferenceSession(
                str(self._onnx_model),
                providers=[("DmlExecutionProvider", {"device_id": self._dml_device_id}),
                           "CPUExecutionProvider"])
            if "DmlExecutionProvider" not in sess.get_providers():
                return False  # DML 不可用不走 CPU ONNX(与 torch 同量级), 留给 torch 回退
            self._session = sess
            self.available = True
            self.device = "dml"
            return True
        except Exception:
            self._session = None
            self.available = False
            return False

    def _try_torch(self) -> bool:
        try:
            import torch  # noqa: import guard

            if not self._weights or not Path(self._weights).exists():
                return False
            from device.dinov2_model import DinoV2Small

            model = DinoV2Small()
            sd = torch.load(str(self._weights), map_location="cpu", weights_only=True)
            model.load_state_dict(sd, strict=False)
            model.eval()
            self._model = (torch, model)
            self.available = True
            self.device = "cpu"
        except Exception:
            self._model = None
            self.available = False
        return self.available

    def ensure(self) -> bool:
        """懒加载 patch 特征提取器(DML ONNX 优先/torch 回退);不可用返回 False(禁用重排)。"""
        return self._ensure()

    def frame_patches(self, frame_bgr) -> np.ndarray:
        """BGR 帧 → (1369,384) L2 patch 特征。"""
        if self.device == "dml":
            return self._frame_patches_dml(frame_bgr)
        torch, model = self._model
        with torch.no_grad():
            _, pt = model.forward_features(_pre(frame_bgr, torch))
        pt = pt[0].numpy().astype(np.float32)
        return _l2(pt)

    def _frame_patches_dml(self, frame_bgr) -> np.ndarray:
        from device.dinov2_model import _imagenet_preprocess

        inp = _imagenet_preprocess(frame_bgr).numpy()[0][None].astype(np.float32)
        _, op = self._session.run(["embedding", "patches"],
                                  {"input": np.ascontiguousarray(inp)})
        return _l2(op[0].astype(np.float32))


def _pre(frame_bgr, torch):
    from device.dinov2_model import _imagenet_preprocess

    return _imagenet_preprocess(frame_bgr)


def patch_score(q_patches: np.ndarray, cand_patch: np.ndarray,
                *, agg_topk: int = _TOPK_AGG) -> float:
    """每查询 patch 对候选帧 patch 的最大余弦,top-agg 均值([0,1] 近似)。"""
    m = (q_patches @ cand_patch.T).max(axis=1)
    k = min(agg_topk, len(m))
    return float(np.sort(m)[-k:].mean())


def resolve_weights(explicit: str | Path | None, data_dir: str | Path | None = None) -> str | None:
    """权重解析:显式 → env → repo work 目录（本文件在 src/engine/localization/,
    parents[4] = benchmark 根; 打包安全——打包时经 env ``SVL_DINOV2_WEIGHTS`` 注入）。"""
    import os

    if explicit and Path(explicit).exists():
        return str(explicit)
    env = os.environ.get("SVL_DINOV2_WEIGHTS")
    if env and Path(env).exists():
        return env
    cand = Path(__file__).resolve().parents[4] / "work" / "dinov2_weights" / "dinov2_vits14_pretrain.pth"
    if cand.exists():
        return str(cand)
    return None


def resolve_patch_onnx(explicit: str | Path | None = None) -> str | None:
    """DML 双输出 ONNX 解析:显式 → env ``SVL_PATCH_ONNX`` → repo work 目录（parents[4],
    注意比 device 层深一级; ``.onnx.data`` 必须同目录）。

    找不到返回 None（调用方回退 CPU torch），不视为错误。
    """
    import os

    if explicit and Path(explicit).exists():
        return str(explicit)
    env = os.environ.get("SVL_PATCH_ONNX")
    if env and Path(env).exists():
        return env
    cand = Path(__file__).resolve().parents[4] / "work" / "_patch_onnx_tmp" / "dinov2_cls_patch.onnx"
    if cand.exists():
        return str(cand)
    return None
