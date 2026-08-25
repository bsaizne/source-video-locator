"""engine.confidence — 工程化置信度（REWRITE/NEW，产品核心）。

``ConfidenceEngine`` 综合候选排名 + 定位结构 -> 三档置信（HIGH/MEDIUM/LOW）+
``score`` + ``reasons`` + ``hard_flags`` + ``montage_flag`` + ``alternatives``。
设计来源 CONFIDENCE_DESIGN.md；阈值/权重为**未标定占位**，禁止当模型概率。
"""
from .confidence import ConfidenceAssessment, ConfidenceEngine

__all__ = ["ConfidenceEngine", "ConfidenceAssessment"]
