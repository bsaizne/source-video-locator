# -*- coding: utf-8 -*-
"""XFeat + LighterGlue 局部起点精修；只在现役窗内移动，失败保留原起点。"""
from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np

TOP_K = 1024
FPS = 10
MIN_MATCHES = 12
MIN_INLIERS = 8
MIN_INLIER_RATIO = 0.20
MIN_GAIN = 4


def resolve_xfeat_models(models_root: Path) -> tuple[Path, Path] | None:
    root = Path(models_root) / "xfeat"
    weights = root / "xfeat.pt"
    lighterglue = root / "xfeat-lighterglue.pt"
    if weights.exists() and lighterglue.exists():
        return weights, lighterglue
    return None


def resolve_xfeat_models_auto(models_root: Path, env=None) -> tuple[Path, Path] | None:
    e = os.environ if env is None else env
    root = e.get("SVL_XFEAT_MODELS_ROOT")
    return resolve_xfeat_models(root if root else models_root)


class XFeatStartRefiner:
    def __init__(self, models: tuple[Path, Path], io) -> None:
        self._weights, self._lighterglue_weights = models
        self._io = io
        self._xfeat = None

    def _ensure_model(self):
        if self._xfeat is None:
            from engine.xfeat_vendor.xfeat import XFeat

            self._xfeat = XFeat(weights=str(self._weights),
                                lighterglue_weights=str(self._lighterglue_weights), top_k=TOP_K)
        return self._xfeat

    @staticmethod
    def _geometry(points0, points1):
        if len(points0) < 4:
            return {"matches": len(points0), "inliers": 0, "ratio": 0.0}
        _, mask = cv2.findHomography(points0, points1, cv2.RANSAC, 3.0,
                                     maxIters=2000, confidence=0.995)
        inliers = int(mask.sum()) if mask is not None else 0
        return {"matches": len(points0), "inliers": inliers,
                "ratio": inliers / len(points0) if len(points0) else 0.0}

    def _extract(self, bgr):
        xfeat = self._ensure_model()
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        output = xfeat.detectAndCompute(xfeat.parse_input(rgb), top_k=TOP_K)[0]
        output["image_size"] = (rgb.shape[1], rgb.shape[0])
        return output

    def _mnn(self, query, source):
        xfeat = self._ensure_model()
        if not len(query["descriptors"]) or not len(source["descriptors"]):
            return {"matches": 0, "inliers": 0, "ratio": 0.0}
        i0, i1 = xfeat.match(query["descriptors"], source["descriptors"], min_cossim=0.82)
        return self._geometry(query["keypoints"][i0].cpu().numpy(),
                              source["keypoints"][i1].cpu().numpy())

    def _lighterglue(self, query, source):
        xfeat = self._ensure_model()
        if not len(query["descriptors"]) or not len(source["descriptors"]):
            return {"matches": 0, "inliers": 0, "ratio": 0.0}
        points0, points1, _ = xfeat.match_lighterglue(query, source, min_conf=0.1)
        return self._geometry(points0, points1)

    def refine(self, edited_video, source_video, edited_start, edited_end,
               current_start, *, margin_s=4.0):
        duration = max(0.0, edited_end - edited_start)
        anchor_offset = min(0.25, duration * 0.1)
        query_time = edited_start + anchor_offset
        query = self._extract(self._io.grab_frame(str(edited_video), query_time, scale=(640, 360)))
        decode_start = max(0.0, current_start - margin_s)
        decode_end = current_start + margin_s + anchor_offset + 1 / FPS
        candidates = []
        for source_time, image in self._io.iter_frames(
                str(source_video), fps=FPS, start=decode_start, end=decode_end, scale=(640, 360)):
            candidate_start = source_time - anchor_offset
            if abs(candidate_start - current_start) > margin_s + 0.051:
                continue
            source = self._extract(image)
            candidates.append({"candidate": candidate_start, "source": source,
                               "mnn": self._mnn(query, source)})
        if not candidates:
            return None
        current = min(candidates, key=lambda c: abs(c["candidate"] - current_start))
        ranked = sorted(candidates,
                        key=lambda c: (-c["mnn"]["inliers"], -c["mnn"]["matches"],
                                       abs(c["candidate"] - current_start)))
        finalists = ranked[:5] + [current]
        seen = set()
        for candidate in finalists:
            key = round(candidate["candidate"], 6)
            if key in seen:
                continue
            seen.add(key)
            candidate["lg"] = self._lighterglue(query, candidate["source"])
        finalists = [c for c in finalists if "lg" in c]
        best = sorted(finalists,
                      key=lambda c: (-c["lg"]["inliers"], -c["lg"]["matches"],
                                     abs(c["candidate"] - current_start)))[0]
        score = best["lg"]
        current_score = current["lg"]
        significant = (score["matches"] >= MIN_MATCHES
                       and score["inliers"] >= max(MIN_INLIERS, current_score["inliers"] + MIN_GAIN)
                       and score["ratio"] >= MIN_INLIER_RATIO)
        if not significant or abs(best["candidate"] - current_start) < 0.005:
            return None
        return {"start": round(best["candidate"], 2),
                "current_inliers": current_score["inliers"], "best_inliers": score["inliers"],
                "matches": score["matches"], "ratio": round(score["ratio"], 4),
                "anchor_time": query_time}
