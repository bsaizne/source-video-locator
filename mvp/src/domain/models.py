"""domain.models — 定位结果与候选的纯数据模型。

字段严格对齐冻结设计文档：
- ``Candidate`` / ``Confidence`` / ``Result`` / ``Alternative`` <-> MVP_PRODUCT_SPEC §5、MVP_ARCHITECTURE §3。
- ``Confidence`` 只来自检索/定位层真实信号；**不使用** start_err/end_err/IoU（运行时无 GT）。

纯数据：不 import numpy / torch / media / infrastructure，不执行任何 IO。
序列化由 ``to_dict()`` 输出产品契约 JSON（持久化不在此层）。
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field

from .enums import ConfidenceLevel, ResultSource


@dataclass(frozen=True)
class TimeSpan:
    """一个时间区间（秒）。用于 edited 段 / original 候选区间。"""

    start: float
    end: float

    @property
    def width(self) -> float:
        return self.end - self.start

    def to_dict(self) -> dict:
        return {"start": self.start, "end": self.end}


@dataclass
class Candidate:
    """检索层原始候选（内部结构）。这些字段是工程化 Confidence 的输入信号。"""

    start: float
    end: float
    width: float
    peak_sim: float
    mean_sim: float
    consistency: float
    hit_count: int
    n_reps: int
    qcov: float
    sim_std: float
    rank_score: float
    best_cover: float = 0.0
    scene_div: int = 0   # candidate 内部 orig 时间 gap>BASE_GAP_S 的段数（montage 指示，Confidence 用）

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Confidence:
    """工程化置信度。``score`` 不是模型概率，禁止展示为百分比概率。"""

    level: ConfidenceLevel
    score: float
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "confidence": self.level.value,
            "confidence_score": self.score,
            "reasons": list(self.reasons),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Confidence":
        """对称还原 to_dict()（供 ResultBatch 持久化加载）。"""
        return cls(
            level=ConfidenceLevel(d.get("confidence", "LOW")),
            score=float(d.get("confidence_score", 0.0)),
            reasons=tuple(d.get("reasons", ())),
        )


@dataclass(frozen=True)
class Alternative:
    """一个备选原片区间（用于人工/UI 展示竞争候选）。"""

    interval: TimeSpan
    confidence_level: ConfidenceLevel
    score: float

    def to_dict(self) -> dict:
        return {
            "candidate_start": self.interval.start,
            "candidate_end": self.interval.end,
            "confidence": self.confidence_level.value,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Alternative":
        """对称还原 to_dict()（供 ResultBatch 持久化加载）。"""
        return cls(
            interval=TimeSpan(float(d.get("candidate_start", 0.0)),
                              float(d.get("candidate_end", 0.0))),
            confidence_level=ConfidenceLevel(d.get("confidence", "LOW")),
            score=float(d.get("score", 0.0)),
        )


@dataclass(frozen=True)
class IndexProgress:
    """建索引进度（engine 向 UI 汇报）。``total`` 为 0 表示未知。

    ``stage`` 取值示例：``probing`` / ``extracting_frames`` / ``embedding`` /
    ``writing``。
    """

    stage: str
    done: int = 0
    total: int = 0

    @property
    def ratio(self) -> float | None:
        return (self.done / self.total) if self.total else None

    def to_dict(self) -> dict:
        return {"stage": self.stage, "done": self.done, "total": self.total}


@dataclass
class Result:
    """一条最终结果（含 auto/manual 双轨，不因手动覆盖丢失自动结果）。

    ``original`` 是当前授权区间（auto 或 manual）。手动修正时保留
    ``auto_result``（原自动结果副本）与 ``manual_timestamp``。
    """

    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    edited: TimeSpan = field(default_factory=lambda: TimeSpan(0.0, 0.0))
    original: TimeSpan = field(default_factory=lambda: TimeSpan(0.0, 0.0))
    confidence: Confidence = field(default_factory=lambda: Confidence(ConfidenceLevel.LOW, 0.0))
    candidate_rank: int = 1
    alternatives: list[Alternative] = field(default_factory=list)
    source: ResultSource = ResultSource.AUTO
    manual_override: bool = False
    montage_flag: bool = False
    extracted_path: str | None = None
    failure_reason: str | None = None   # 段级失败隔离时记录（无候选/段异常），正常为 None
    auto_result: "Result | None" = field(default=None, repr=False, compare=False)
    manual_timestamp: str | None = None

    def to_dict(self) -> dict:
        """产品契约 JSON（MVP_PRODUCT_SPEC §5 / §27）。"""
        d = {
            "result_id": self.result_id,
            "edited_segment": self.edited.to_dict(),
            "original": {
                "candidate_start": self.original.start,
                "candidate_end": self.original.end,
            },
            "confidence": self.confidence.level.value,
            "confidence_score": self.confidence.score,
            "reasons": list(self.confidence.reasons),
            "candidate_rank": self.candidate_rank,
            "alternatives": [a.to_dict() for a in self.alternatives],
            "source": self.source.value,
            "manual_override": self.manual_override,
            "montage_flag": self.montage_flag,
            "extracted_path": self.extracted_path,
            "failure_reason": self.failure_reason,
        }
        if self.manual_override:
            d["manual_timestamp"] = self.manual_timestamp
            d["auto_result"] = self.auto_result.to_dict() if self.auto_result else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Result":
        """对称还原 to_dict()（含 auto/manual 双轨，供 ResultBatch 持久化加载）。"""
        manual = bool(d.get("manual_override", False))
        ed = d.get("edited_segment") or {}
        orig = d.get("original") or {}
        return cls(
            result_id=d.get("result_id") or str(uuid.uuid4()),
            edited=TimeSpan(float(ed.get("start", 0.0)), float(ed.get("end", 0.0))),
            original=TimeSpan(float(orig.get("candidate_start", 0.0)),
                              float(orig.get("candidate_end", 0.0))),
            confidence=Confidence.from_dict(d),
            candidate_rank=int(d.get("candidate_rank", 1)),
            alternatives=[Alternative.from_dict(a) for a in d.get("alternatives", ())],
            source=ResultSource(d.get("source", "auto")),
            manual_override=manual,
            montage_flag=bool(d.get("montage_flag", False)),
            extracted_path=d.get("extracted_path"),
            failure_reason=d.get("failure_reason"),
            manual_timestamp=d.get("manual_timestamp"),
            auto_result=cls.from_dict(d["auto_result"]) if manual and d.get("auto_result") else None,
        )


@dataclass
class ResultBatch:
    """一次分析任务的批量结果信封（持久化格式，``schema_version`` 兼容演进）。

    ``results`` 按 edited 时间升序，每条 Result 对应一个 edited segment。
    """

    schema_version: int = 1
    original_video: str | None = None
    edited_video: str | None = None
    results: list[Result] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "original_video": self.original_video,
            "edited_video": self.edited_video,
            "results": [r.to_dict() for r in self.results],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ResultBatch":
        """对称还原 to_dict()（供持久化加载）。"""
        return cls(
            schema_version=int(d.get("schema_version", 1)),
            original_video=d.get("original_video"),
            edited_video=d.get("edited_video"),
            results=[Result.from_dict(r) for r in d.get("results", ())],
        )
