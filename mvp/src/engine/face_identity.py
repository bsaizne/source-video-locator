# -*- coding: utf-8 -*-
"""人脸身份一致性标注（2026-10-25 候选 B，PLAN_EXISTENCE_SIGNAL §2）。

**只标注，不参与任何判据**：不改定位、不改 confidence（公式冻结）、不自动改 scenes.npy
（采纳层无自动信号是档案死结，FINDINGS_SUBSHOT_QUERY 续78）。

判据（FINDINGS_GT_PATCH_PROBES_20261024 §3，双样本互证）：
- 两侧各 3 帧（±0.10/0.25/0.40s）YuNet 检出（score>=0.7）→ 每帧取**最大脸** SFace 128d 嵌入
  （L2 归一）→ 每侧质心 = 3 帧嵌入均值再 L2 → 质心余弦。
- **仅当两侧每帧都恰好一张脸**才给 same/different 二判（阈 0.57）；多脸（max 脸会换人）、
  无脸、抓帧失败一律 unknown——裸判据对多脸侧双带重叠，是已实测的失败模式。
- 资产缺失/加载失败/推理异常 → 整条标注 None（宁可丢也不修，同 scene_strength sidecar 惯例）。
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

# 与探针同口径（work/face_probe_20261024/probe.py）：
SCORE_THRESHOLD = 0.7
FRAME_OFFSETS = (0.10, 0.25, 0.40)
FRAME_WIDTH = 480

DEFAULT_COS_THRESH = 0.57


def resolve_face_models(models_root: Path) -> tuple[Path, Path] | None:
    """定位 ``models/face/`` 下的 YuNet/SFace ONNX；任一缺失返回 None（调用方降级跳过）。"""
    d = Path(models_root) / "face"
    yunet = d / "face_detection_yunet_2023mar.onnx"
    sface = d / "face_recognition_sface_2021dec.onnx"
    if yunet.exists() and sface.exists():
        return yunet, sface
    return None


class FaceIdentityAnalyzer:
    """YuNet 检测 + SFace 嵌入的边界身份测量器。模型懒加载（首次调用才建）。"""

    def __init__(self, models: tuple[Path, Path], io) -> None:
        self._yunet_path, self._sface_path = (Path(models[0]), Path(models[1]))
        self._io = io
        self._det = None
        self._rec = None

    def _ensure_models(self):
        import cv2  # 产品依赖已含（device/dinov2_model 顶层 import cv2）

        if self._det is None:
            self._det = cv2.FaceDetectorYN.create(str(self._yunet_path), "",
                                                  (FRAME_WIDTH, 270),
                                                  score_threshold=SCORE_THRESHOLD)
            self._rec = cv2.FaceRecognizerSF.create(str(self._sface_path), "")
            self._cv2 = cv2
        return self._det, self._rec

    def measure_boundary(self, video: str | Path, t: float,
                         *, cos_thresh: float = DEFAULT_COS_THRESH) -> dict | None:
        """测 ``t`` 两侧身份。返回 {cos, verdict, n_faces_left, n_faces_right} 或 None。

        verdict: "same" | "different" | "unknown"（两侧均单脸才给前两者）。
        任何一步失败（抓帧/检测/嵌入）返回 None——不落半截数据。
        """
        try:
            det, rec = self._ensure_models()
        except Exception:
            log.warning("face identity models failed to load; annotation disabled", exc_info=True)
            return None
        times = [t - off for off in FRAME_OFFSETS] + [t + off for off in FRAME_OFFSETS]
        try:
            frames = self._io.grab_frames(str(video), times)
        except Exception:
            log.warning("face identity grab_frames failed at t=%.3f", t, exc_info=True)
            return None
        if not frames:
            return None

        def side_centroid(sign: int):
            embs, n_faces = [], -1
            for off in FRAME_OFFSETS:
                key = round(t + sign * off, 6)
                frame = None
                for cand in (key, round(t + sign * off, 3), round(t + sign * off, 2)):
                    if cand in frames:
                        frame = frames[cand]
                        break
                if frame is None:
                    continue
                # 探针口径 = 480 宽（work/face_probe_20261024）：全分辨率下 YuNet 会多检出
                # 边缘小脸（实测 nf 1→2、max 脸选择漂移、cos 0.015→0.128）。判据阈值只在
                # 480 宽口径上标定过，换口径必须重标——这里对齐探针而不是重标。
                h0, w0 = frame.shape[:2]
                if w0 != FRAME_WIDTH:
                    frame = self._cv2.resize(
                        frame, (FRAME_WIDTH, max(2, round(h0 * FRAME_WIDTH / w0))),
                        interpolation=self._cv2.INTER_AREA)
                h, w = frame.shape[:2]
                det.setInputSize((w, h))
                _, faces = det.detect(frame)
                rows = [] if faces is None else [f for f in faces if float(f[14]) >= SCORE_THRESHOLD]
                n_faces = max(n_faces, len(rows))
                if not rows:
                    continue
                frow = max(rows, key=lambda f: float(f[2]) * float(f[3]))
                emb = rec.feature(rec.alignCrop(frame, frow)).flatten().astype(np.float32)
                embs.append(emb / (np.linalg.norm(emb) + 1e-9))
            if not embs:
                return None, n_faces
            c = np.mean(embs, axis=0)
            return c / (np.linalg.norm(c) + 1e-9), n_faces

        try:
            c_l, nf_l = side_centroid(-1)
            c_r, nf_r = side_centroid(+1)
        except Exception:
            log.warning("face identity inference failed at t=%.3f", t, exc_info=True)
            return None
        if c_l is None or c_r is None:
            return dict(cos=None, verdict="unknown", n_faces_left=nf_l, n_faces_right=nf_r)
        cos = float(c_l @ c_r)
        single = (nf_l == 1 and nf_r == 1)
        verdict = ("same" if cos >= cos_thresh else "different") if single else "unknown"
        return dict(cos=round(cos, 4), verdict=verdict,
                    n_faces_left=nf_l, n_faces_right=nf_r)
