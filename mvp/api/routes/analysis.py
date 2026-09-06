"""routes.analysis — 编辑侧 shot 切分。调用已有 ``SourceLocatorService.analyze_edited_video``。

把 ``ShotSegment[]`` 映射为 ``{id,label,span,nq}``（numpy ``feats``/``times`` 留在后端不出 JSON）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..dependencies import AppContext, get_context
from ..schemas import AnalyzeRequest

router = APIRouter()


@router.post("/api/analyze")
def analyze(req: AnalyzeRequest, ctx: AppContext = Depends(get_context)) -> dict:
    shots = ctx.service.analyze_edited_video(req.edited_path)
    segments = [
        {
            "id": f"seg-{i:03d}",
            "label": f"Clip {i + 1:02d}",
            "span": shot.span.to_dict(),
            "nq": shot.nq,
        }
        for i, shot in enumerate(shots)
    ]
    return {"segments": segments}
