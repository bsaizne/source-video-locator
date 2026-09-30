"""engine.confidence — 工程化置信度（REWRITE/NEW，产品核心）。

``ConfidenceEngine`` 综合候选排名 + 定位结构 -> 三档置信（HIGH/MEDIUM/LOW）+
``score`` + ``reasons`` + ``hard_flags`` + ``montage_flag`` + ``alternatives``。
设计来源 CONFIDENCE_DESIGN.md；阈值/权重为**未标定占位**，禁止当模型概率。
``confidence_v2`` 是竞品四项加权置信公式的并行通道（默认关，只降不升）。
"""
from .confidence import ConfidenceAssessment, ConfidenceEngine
from .confidence_v2 import confidence_v2

__all__ = ["ConfidenceEngine", "ConfidenceAssessment", "confidence_v2"]
