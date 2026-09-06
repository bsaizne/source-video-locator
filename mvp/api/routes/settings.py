"""routes.settings — 设备后端切换（唯一真正控制推理后端的通道）。

- ``GET  /api/settings/device``：返回当前偏好 + 实际生效后端 + 可用设备列表。
- ``POST /api/settings/device``：设置偏好（``auto`` / ``cpu`` / ``directml``），
  重建 backend，返回新状态；非法偏好 -> 400。

``preferred`` 是唯一能改变运行时推理后端的用户设置；其余前端设置项为展示/占位。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from infrastructure.settings_repo import VALID_DEVICE_PREFS

from ..dependencies import AppContext, get_context
from ..schemas import DeviceSettingsRequest, DeviceSettingsResponse

router = APIRouter()


@router.get("/api/settings/device", response_model=DeviceSettingsResponse)
def get_device_settings(ctx: AppContext = Depends(get_context)) -> DeviceSettingsResponse:
    return DeviceSettingsResponse(**ctx.service.device_settings())


@router.post("/api/settings/device", response_model=DeviceSettingsResponse)
def set_device_settings(
    req: DeviceSettingsRequest,
    ctx: AppContext = Depends(get_context),
) -> DeviceSettingsResponse:
    if req.preferred not in VALID_DEVICE_PREFS:
        raise HTTPException(status_code=400, detail=f"invalid preferred: {req.preferred}")
    ctx.service.set_device_preference(req.preferred)
    return DeviceSettingsResponse(**ctx.service.device_settings())
