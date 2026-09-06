"""Phase 24-1 多模态交叉验证:OCR 文字独立判别(不依赖任何视觉特征)。

背景:Phase 24-1 几何/运动探针全部基于视觉特征(CLS + patch 几何)。用户追问
「拿多模态验证过了吗」——诚实补漏:对探针涉及的关键帧做 OCR 文字提取,
用**文字相似度**(text_anchor 的字符 3-gram 对称包含率)独立判断:
  查询帧(编辑片)的文字与哪个候选(真值窗/兄弟窗/干扰帧)一致?

若文字信号能独立区分真值(查询↔真值文字一致、↔兄弟不一致),则:
  a) 交叉印证探针结论(哪些失败族真值可被文字锁定,哪些连文字都混);
  b) 直接指出「文字锚点」对 p08/p08b/p26/t3-r12 是否本可救回。

对每探针:
  - 查询帧:编辑片 query_t±0.4s 3 帧
  - 候选帧:真值窗 + 兄弟窗(如有)+ CLS top-5 干扰帧
  - 每帧 OCR → 文本行 → filter_watermark → 查询 vs 候选 text_similarity(max 锚点行)
  - 判别:真值窗文字分 vs 兄弟窗/干扰文字分

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/research_phase24_1_multimodal.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "src"))

from engine.localization.text_anchor import OcrEngine, text_similarity, filter_watermark
from media.ffmpeg import FFmpegIO

FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FP = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
      / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
IDX_DIR = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index")
IDX2 = IDX_DIR / "2__4c6d4ab2.idx"
IDX_T3 = IDX_DIR / "test3-om__074e2dcc.idx"

PAIRS = {
    "2mkv":  dict(orig="D:/video/2.mkv",  edit="D:/video/1.mp4", idx=IDX2),
    "test3": dict(orig="D:/ProjectXIXI/test3/test3-om.mp4",
                  edit="D:/ProjectXIXI/test3/test3-ed.mp4", idx=IDX_T3),
}

# 与 research_phase24_1.py 同一探针集(视觉探针逐帧诊断过)
PROBES = [
    ("2mkv", "p08",  13.5, (1108, 1110), "瞭望塔+同桌机位(真值)", (1048, 1050)),
    ("2mkv", "p08b", 13.9, (1048, 1050), "士兵特写(真值)", (1108, 1110)),
    ("2mkv", "p26",  76.8, (2808, 2811), "夜读书(CLS 硬混淆)", None),
    ("2mkv", "p01",   0.8, (2417, 2428), "金属球准备(sanity 易例)", None),
    ("2mkv", "p04",   4.6, (833, 845),   "峡谷航拍(sanity 易例)", None),
    ("test3", "t3r12", 64.75, (454, 480), "精灵王重复镜头(r12 用户判错)", None),
]


def _load_cls_model():
    """加载 DINOv2(仅用于挑干扰帧的 CLS 排名,非判别信号)。"""
    sys.path.insert(0, str(BENCH / "mvp" / "src"))
    from device.dinov2_model import DinoV2Small, _imagenet_preprocess
    import torch
    mdl = DinoV2Small()
    sd = torch.load(str(BENCH / "work/dinov2_weights/dinov2_vits14_pretrain.pth"),
                    map_location="cpu", weights_only=True)
    mdl.load_state_dict(sd, strict=False)
    mdl.eval()
    return mdl, torch, _imagenet_preprocess


def main() -> int:
    import sys as _sys
    try:
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    t0 = time.time()
    ocr = OcrEngine()
    if not ocr.ensure():
        print("OCR unavailable; exit 2")
        return 2
    ff = FFmpegIO(FFMPEG, FP)
    mdl, torch, _pre = _load_cls_model()

    report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "probes": []}

    for pair, pid, qt, true_win, note, brother in PROBES:
        cfg = PAIRS[pair]

        # 查询帧 OCR(编辑片 3 帧)
        q_ts = [qt - 0.4 + 0.4 * j for j in range(3)]
        q_frames = [ff.grab_frame(cfg["edit"], t) for t in q_ts]
        q_lines = ocr.lines(q_frames)
        q_clean = filter_watermark(q_lines)

        # 候选帧:真值窗 + 兄弟窗 + CLS top-5 干扰
        feats = np.load(cfg["idx"] / "features.npy")
        times = np.load(cfg["idx"] / "times.npy")
        # 查询 CLS 用于挑干扰帧(仅挑选用,非判别信号)
        with torch.no_grad():
            qc = torch.mean(torch.stack([_pre(ff.grab_frame(cfg["edit"], t))
                                         for t in q_ts]), dim=0)
            cls, _ = mdl.forward_features(qc)
        q_cls = cls[0].numpy().astype(np.float32)
        q_cls = q_cls / max(np.linalg.norm(q_cls), 1e-8)
        sims = feats @ q_cls
        order = np.argsort(-sims)

        cand_spans = [("true", *true_win)]
        if brother:
            cand_spans.append(("brother", *brother))
        for i in order[:5]:
            t = float(times[i])
            if any(abs(t - a) < 5.0 for _, a, b in cand_spans):
                continue
            cand_spans.append(("distract", max(0.0, t - 0.5), t + 0.5))

        rows = []
        for kind, a, b in cand_spans:
            mid = (a + b) / 2.0
            c_frames = [ff.grab_frame(cfg["orig"], mid - 0.3),
                        ff.grab_frame(cfg["orig"], mid),
                        ff.grab_frame(cfg["orig"], mid + 0.3)]
            c_lines = ocr.lines(c_frames)
            c_clean = filter_watermark(c_lines)
            score = text_similarity(q_clean, c_clean)
            rows.append({"kind": kind, "span": [round(a, 1), round(b, 1)],
                         "text_sim": round(score, 4),
                         "q_lines": q_clean[:4], "c_lines": c_clean[:4]})
            print(f"  [{pid} {kind:8s}] text_sim={score:.3f} "
                  f"q_ocr={q_clean[:2]} c_ocr={c_clean[:2]}", flush=True)

        true_row = next((r for r in rows if r["kind"] == "true"), None)
        others = [r for r in rows if r["kind"] != "true"]
        margin = (true_row["text_sim"] - max((r["text_sim"] for r in others), default=0.0)
                  if true_row else None)
        report["probes"].append({
            "id": pid, "pair": pair, "note": note, "query_t": qt,
            "true_win": list(true_win), "brother": list(brother) if brother else None,
            "q_ocr_lines": q_clean, "candidates": rows,
            "text_margin_true_vs_best_other": round(margin, 4) if margin is not None else None,
        })
        print(f"[{pid}] query OCR={q_clean[:3]!r} | "
              f"text_margin(真值−最佳干扰)={margin}", flush=True)

    out = BENCH / "work" / "phase24_1_multimodal_results.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved {out}  total {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
