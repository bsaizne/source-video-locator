"""device — 统一推理后端。

H1 = :class:`CPUBackend`（无 CUDA 依赖）；H2 = :class:`DirectMLBackend`（Windows AMD GPU）。
未来 H3 `MPSBackend` / H4 `CUDABackend` 经同一 :class:`DeviceBackend` 接口加入，上层零改动。

业务代码只依赖 :class:`DeviceBackend`，用 :func:`resolve_backend` 选择后端——**不得写死
CPU/AMD/MPS/CUDA**。任何 DirectML 失败自动 CPU fallback 并明确日志（§5）。
"""
from __future__ import annotations

from infrastructure.errors import DeviceError
from infrastructure.logging import get_logger
from .base import DeviceBackend
from .cpu_backend import CPUBackend, resolve_dinov2_weights
from .directml_backend import DirectMLBackend, asset_meta, resolve_dml_model

__all__ = ["DeviceBackend", "CPUBackend", "DirectMLBackend", "DeviceError",
           "resolve_dinov2_weights", "resolve_dml_model", "asset_meta",
           "resolve_backend", "pick_best_available", "directml_available"]

_log = get_logger(__name__)


def directml_available() -> tuple[bool, str]:
    """DirectML 能力探测：onnxruntime + ``DmlExecutionProvider`` + ONNX 资产都存在。

    返回 ``(ok, reason)``。**不**创建 session（探测是廉价检查；真正的 session 失败在
    :func:`resolve_backend` 构造时捕获并 fallback CPU）。
    """
    try:
        import onnxruntime as ort
    except Exception as exc:  # pragma: no cover - import error
        return False, f"onnxruntime not installed: {exc}"
    try:
        provs = ort.get_available_providers()
    except Exception as exc:  # pragma: no cover
        return False, f"get_available_providers failed: {exc}"
    if "DmlExecutionProvider" not in provs:
        return False, "DmlExecutionProvider not available"
    try:
        resolve_dml_model()
    except DeviceError as exc:
        return False, f"onnx model asset missing: {exc}"
    return True, "ok"


def resolve_backend(preferred: str = "auto", *, config=None, **kwargs) -> DeviceBackend:
    """按 ``preferred`` 选择推理后端；任何 DirectML 失败自动 CPU fallback 并明确日志。

    - ``auto``：能力探测通过 -> DirectML，否则 CPU。
    - ``directml``：优先 DirectML；失败 -> CPU（日志 ``fallback_reason``）。
    - ``cpu``：恒 CPU。
    ``config``（可选，``AppConfig``）：``preferred=="auto"`` 时用 ``config.device.preferred``
    覆盖；并读取 ``onnx_model`` / ``dml_device_id`` / ``dml_batch_size``。
    """
    if preferred == "auto" and config is not None:
        preferred = str(getattr(getattr(config, "device", None), "preferred", "auto"))

    if preferred == "cpu":
        _log.info("backend=cpu (requested)")
        return CPUBackend()

    if preferred in ("directml", "auto"):
        ok, reason = directml_available()
        if ok:
            # 从 config 继承 DirectML 选项
            onnx_model = getattr(getattr(config, "device", None), "onnx_model", None) if config else None
            device_id = getattr(getattr(config, "device", None), "dml_device_id", 0) if config else 0
            bs = getattr(getattr(config, "device", None), "dml_batch_size", 8) if config else kwargs.get("batch_size", 8)
            try:
                dml = DirectMLBackend(model_path=onnx_model, device_id=device_id,
                                      batch_size=bs, **{k: v for k, v in kwargs.items()
                                                          if k not in ("batch_size",)})
                _log.info("backend=directml (model=%s)", dml.model_path.name)
                return dml
            except Exception as exc:  # noqa: BLE001 - 任何初始化失败都 fallback CPU
                _log.warning("backend=directml failed (%s)", exc)
                _log.warning("backend=cpu fallback_reason=%s", exc)
        else:
            _log.warning("backend=cpu (directml unavailable: %s)", reason)
    return CPUBackend()


def pick_best_available(config=None) -> DeviceBackend:
    """兼容旧入口：等价 ``resolve_backend("auto")``。"""
    return resolve_backend("auto", config=config)
