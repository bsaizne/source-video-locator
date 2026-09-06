"""engine.localization.text_anchor — OCR 文字锚点重排(Phase 21 首选第二信号)。

真实案例实证(GT v3 加固 + OCR 实验):同场景内的字牌/字卡在 CLS 特征下不可分
(问句字牌 ed84.5-86 ↔ 原片 1808-1815 的 sim 0.84 仍低于错误位置 0.91;patch-token
实验亦负结果),但**文字本身**是强判别信号——rapidocr 对全部字牌/字卡读出清晰文本
(置信度 ≥0.8)。

语义:查询段帧若 OCR 出内容文字(过滤 TikTok 水印等),则对候选窗(主 span/子 span)
各抽少量帧 OCR,做字符 3-gram 相似度匹配;文字显著更优的子 span 晋级为主定位。

工程约束:
- OCR 引擎懒加载 + 依赖缺失自动降级(rapidocr 未安装 → 锚点禁用,零崩溃);
- 只在重排阶段对候选窗少量帧执行 OCR,成本可控;
- 编辑侧可能有三个文字层(原片字牌/解说字幕/TikTok 水印)——水印过滤 + 集合式容错匹配
  (字幕/解说文字在原片侧找不到属正常,只拉低分不产生错误晋级)。
"""
from __future__ import annotations

import re

_NORM_RE = re.compile(r"[^a-z0-9]+")
DEFAULT_WATERMARKS = ("tiktok", "fyprecap")


def normalize_text(s: str) -> str:
    """小写、去非字母数字、压缩——OCR 噪声容错('YOURNAME?'→'yourname')。"""
    return _NORM_RE.sub("", (s or "").lower())


def filter_watermark(lines: list[str], watermarks: tuple[str, ...] = DEFAULT_WATERMARKS) -> list[str]:
    """过滤水印/平台标识行;同时丢弃过短行(单字符 OCR 噪声)。"""
    out = []
    for ln in lines:
        n = normalize_text(ln)
        if len(n) < 3:
            continue
        if any(w in n for w in watermarks):
            continue
        out.append(ln)
    return out


def _ngrams(s: str, n: int = 3) -> set[str]:
    s = normalize_text(s)
    if len(s) < n:
        return {s} if s else set()
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def line_vs_lines(line: str, cand_lines: list[str]) -> float:
    """一行查询文字 vs 候选行集合的最佳相似度(字符 3-gram 包含率的对称平均,[0,1])。

    包含率而非 Jaccard:OCR 常把 '?' 丟掉/'YOUR NAME' 黏成 'YOURNAME',包含关系比
    严格集合交并更容错。
    """
    if not cand_lines:
        return 0.0
    q = _ngrams(line)
    if not q:
        return 0.0
    best = 0.0
    for c in cand_lines:
        cset = _ngrams(c)
        if not cset:
            continue
        inter = len(q & cset)
        cont_q = inter / len(q)           # 查询行被候选行包含
        cont_c = inter / len(cset)        # 候选行被查询行包含
        best = max(best, (cont_q + cont_c) / 2.0)
    return best


def text_similarity(q_lines: list[str], cand_lines: list[str]) -> float:
    """查询行集合 vs 候选行集合:**取最佳锚点行**的相似度(max,非均值)。

    max 而非均值的原因(实测教训):编辑侧有解说字幕等多条非原片文字行,均值会把
    唯一的强字牌锚点稀释到阈值之下;锚点语义 = 任一行强命中即为证据。
    无查询行(或全为水印)→ 0。
    """
    q = filter_watermark(q_lines)
    if not q:
        return 0.0
    c = filter_watermark(cand_lines)
    if not c:
        return 0.0
    return max(line_vs_lines(ln, c) for ln in q)


class OcrEngine:
    """rapidocr 懒加载封装;依赖缺失时 ``available=False``(锚点自动禁用)。"""

    def __init__(self):
        self._ocr = None
        self._tried = False
        self.available = False

    def _ensure(self) -> bool:
        if self._tried:
            return self.available
        self._tried = True
        try:
            from rapidocr_onnxruntime import RapidOCR  # noqa: import guard
            self._ocr = RapidOCR()
            self.available = True
        except Exception:
            self._ocr = None
            self.available = False
        return self.available

    def ensure(self) -> bool:
        """懒加载 OCR 引擎;依赖缺失返回 False(调用方禁用锚点)。"""
        return self._ensure()

    def lines(self, frames) -> list[str]:
        """对若干 BGR 帧执行 OCR,返回置信度达标的文本行。"""
        if not frames or not self._ensure():
            return []
        out: list[str] = []
        for f in frames:
            try:
                result, _ = self._ocr(f)
            except Exception:
                continue
            for item in result or []:
                try:
                    text = item[1]
                    conf = float(item[2])
                except Exception:
                    continue
                if conf >= 0.5 and text:
                    out.append(text)
        return out
