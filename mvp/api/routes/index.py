"""routes.index — 原片索引。调用已有 ``SourceLocatorService.build_original_index``。

- ``device_type`` 是**纯展示层分类**：来自冻结 ``IndexMeta.backend`` 的静态标签映射，
  只写进响应 payload 供 UI 展示；桥内任何运行逻辑/分支/错误处理都不使用它
  （不据此做 fallback / 选后端 / 判错）。
- ``meta.backend`` 取自 ``IndexBundle.meta``（冻结 IndexMeta），非桥自行探测。
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from ..dependencies import AppContext, get_context
from ..schemas import IndexRequest, IndexResponse, IndexStatusResponse

router = APIRouter()

# 展示层 device_type 标签映射（纯展示，参与任何运行逻辑）
_DEVICE_TYPE_DISPLAY = {
    "cpu": "cpu",
    "directml": "amd",
    "mps": "mps",
    "cuda:0": "cuda",
}


@router.get("/api/index/status", response_model=IndexStatusResponse)
def index_status(video_path: str, ctx: AppContext = Depends(get_context)) -> IndexStatusResponse:
    """返回某源片的真实磁盘索引状态（VALID/INVALID/MISSING + 原因）。

    这是前端「索引徽章」的真实数据源：构建成功且未变 → VALID；源片不存在 → INVALID。
    解决旧版前端在 app 重启/构建失败后一律显示「缺失」的问题。
    """
    v = ctx.service.index_status(video_path)
    return IndexStatusResponse(status=v.status.value, reason=v.reason)


@router.post("/api/index", response_model=IndexResponse)
def build_index(req: IndexRequest, ctx: AppContext = Depends(get_context)) -> IndexResponse:
    bundle = ctx.service.build_original_index(req.video_path)
    ctx.current_original = Path(req.video_path)
    meta = bundle.meta
    return IndexResponse(
        status="completed",
        frames=meta.num_frames,
        backend={
            "device_name": meta.backend,
            "device_type": _DEVICE_TYPE_DISPLAY.get(meta.backend, "cpu"),
        },
    )
