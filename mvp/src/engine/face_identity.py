# -*- coding: utf-8 -*-
"""SCRFD + ArcFace 边界身份旁路标注；不参与定位、置信度或镜头切分。"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

SCORE_THRESHOLD = 0.5
FRAME_OFFSETS = (0.10, 0.25, 0.40)
FRAME_WIDTH = 480
DEFAULT_COS_THRESH = 0.51
AMBIGUOUS_BAND = 0.10

_REFERENCE_ALIGNMENT = np.array([
    [38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366],
    [41.5493, 92.3655], [70.7299, 92.2041],
], dtype=np.float32)


def resolve_face_models(models_root: Path) -> tuple[Path, Path] | None:
    d = Path(models_root) / "face"
    detector = d / "det_2.5g.onnx"
    recognizer = d / "w600k_mbf.onnx"
    if detector.exists() and recognizer.exists():
        return detector, recognizer
    return None


def resolve_face_models_auto(models_root: Path, env=None) -> tuple[Path, Path] | None:
    e = os.environ if env is None else env
    root = e.get("SVL_FACE_MODELS_ROOT")
    return resolve_face_models(root if root else models_root)


def _distance2bbox(points, distance):
    x1 = points[:, 0] - distance[:, 0]
    y1 = points[:, 1] - distance[:, 1]
    x2 = points[:, 0] + distance[:, 2]
    y2 = points[:, 1] + distance[:, 3]
    return np.stack([x1, y1, x2, y2], axis=-1)


def _distance2kps(points, distance):
    preds = []
    for i in range(0, distance.shape[1], 2):
        preds.append(points[:, i % 2] + distance[:, i])
        preds.append(points[:, i % 2 + 1] + distance[:, i + 1])
    return np.stack(preds, axis=-1)


def _nms(detections, iou_threshold=0.4):
    x1, y1 = detections[:, 0], detections[:, 1]
    x2, y2 = detections[:, 2], detections[:, 3]
    scores = detections[:, 4]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        width = np.maximum(0.0, xx2 - xx1 + 1)
        height = np.maximum(0.0, yy2 - yy1 + 1)
        intersection = width * height
        overlap = intersection / (areas[i] + areas[order[1:]] - intersection)
        order = order[np.where(overlap <= iou_threshold)[0] + 1]
    return keep


class _ScrfdDetector:
    def __init__(self, model_path: Path) -> None:
        import cv2
        import onnxruntime as ort

        self.cv2 = cv2
        self.session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [output.name for output in self.session.get_outputs()]
        self.center_cache = {}

    def detect(self, image):
        height = width = 640
        image_ratio = float(image.shape[0]) / image.shape[1]
        if image_ratio > 1.0:
            new_height = height
            new_width = int(new_height / image_ratio)
        else:
            new_width = width
            new_height = int(new_width * image_ratio)
        scale = float(new_height) / image.shape[0]
        resized = self.cv2.resize(image, (new_width, new_height))
        canvas = np.zeros((height, width, 3), dtype=np.uint8)
        canvas[:new_height, :new_width, :] = resized
        blob = self.cv2.dnn.blobFromImage(canvas, 1 / 128.0, (width, height),
                                          (127.5, 127.5, 127.5), swapRB=True)
        outputs = self.session.run(self.output_names, {self.input_name: blob})
        scores_list, boxes_list, keypoints_list = [], [], []
        for index, stride in enumerate((8, 16, 32)):
            scores = outputs[index]
            box_preds = outputs[index + 3] * stride
            keypoint_preds = outputs[index + 6] * stride
            grid_height, grid_width = height // stride, width // stride
            key = (grid_height, grid_width, stride)
            centers = self.center_cache.get(key)
            if centers is None:
                centers = np.stack(np.mgrid[:grid_height, :grid_width][::-1], axis=-1).astype(np.float32)
                centers = (centers * stride).reshape((-1, 2))
                centers = np.stack([centers] * 2, axis=1).reshape((-1, 2))
                self.center_cache[key] = centers
            positions = np.where(scores >= SCORE_THRESHOLD)[0]
            scores_list.append(scores[positions])
            boxes_list.append(_distance2bbox(centers, box_preds)[positions])
            keypoints = _distance2kps(centers, keypoint_preds).reshape((centers.shape[0], -1, 2))
            keypoints_list.append(keypoints[positions])
        scores = np.vstack(scores_list).ravel()
        order = scores.argsort()[::-1]
        boxes = np.vstack(boxes_list) / scale
        keypoints = np.vstack(keypoints_list) / scale
        detections = np.hstack((boxes, scores[:, None])).astype(np.float32, copy=False)
        detections = detections[order]
        keypoints = keypoints[order]
        keep = _nms(detections)
        rows = []
        for index in keep:
            row = np.zeros(15, dtype=np.float32)
            box = detections[index]
            row[:4] = (box[0], box[1], box[2] - box[0], box[3] - box[1])
            kps = keypoints[index]
            row[4:14] = (kps[1, 0], kps[1, 1], kps[0, 0], kps[0, 1],
                         kps[2, 0], kps[2, 1], kps[4, 0], kps[4, 1],
                         kps[3, 0], kps[3, 1])
            row[14] = box[4]
            rows.append(row)
        return rows


class _ArcFaceRecognizer:
    def __init__(self, model_path: Path) -> None:
        import onnxruntime as ort

        self.session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name

    @staticmethod
    def _similarity_matrix(landmarks):
        a = np.zeros((10, 4), dtype=np.float64)
        b = np.zeros(10, dtype=np.float64)
        for i, ((x, y), (u, v)) in enumerate(zip(landmarks, _REFERENCE_ALIGNMENT)):
            a[2 * i] = (x, -y, 1, 0)
            a[2 * i + 1] = (y, x, 0, 1)
            b[2 * i:2 * i + 2] = (u, v)
        params, *_ = np.linalg.lstsq(a, b, rcond=None)
        return np.array([[params[0], -params[1], params[2]],
                         [params[1], params[0], params[3]]], dtype=np.float32)

    def embed(self, image, frow, cv2):
        landmarks = np.array([
            [frow[6], frow[7]], [frow[4], frow[5]], [frow[8], frow[9]],
            [frow[12], frow[13]], [frow[10], frow[11]],
        ], dtype=np.float32)
        aligned = cv2.warpAffine(image, self._similarity_matrix(landmarks), (112, 112), borderValue=0)
        blob = cv2.dnn.blobFromImage(aligned, 1 / 127.5, (112, 112),
                                     (127.5, 127.5, 127.5), swapRB=True)
        embedding = self.session.run(None, {self.input_name: blob})[0].flatten().astype(np.float32)
        return embedding / (np.linalg.norm(embedding) + 1e-12)


def _identity_verdict(cosine, count_left, count_right, cos_thresh):
    if count_left != 1 or count_right != 1 or abs(cosine - cos_thresh) < AMBIGUOUS_BAND:
        return "unknown"
    return "same" if cosine >= cos_thresh else "different"


class FaceIdentityAnalyzer:
    def __init__(self, models: tuple[Path, Path], io) -> None:
        self._detector_path, self._recognizer_path = (Path(models[0]), Path(models[1]))
        self._io = io
        self._det = None
        self._rec = None

    def _ensure_models(self):
        import cv2

        if self._det is None:
            self._det = _ScrfdDetector(self._detector_path)
            self._rec = _ArcFaceRecognizer(self._recognizer_path)
            self._cv2 = cv2
        return self._det, self._rec

    def measure_boundary(self, video: str | Path, t: float,
                         *, cos_thresh: float = DEFAULT_COS_THRESH) -> dict | None:
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
            embeddings, n_faces = [], -1
            for off in FRAME_OFFSETS:
                key = round(t + sign * off, 6)
                frame = None
                for candidate in (key, round(t + sign * off, 3), round(t + sign * off, 2)):
                    if candidate in frames:
                        frame = frames[candidate]
                        break
                if frame is None:
                    continue
                h0, w0 = frame.shape[:2]
                if w0 != FRAME_WIDTH:
                    frame = self._cv2.resize(
                        frame, (FRAME_WIDTH, max(2, round(h0 * FRAME_WIDTH / w0))),
                        interpolation=self._cv2.INTER_AREA)
                rows = det.detect(frame)
                n_faces = max(n_faces, len(rows))
                if not rows:
                    continue
                frow = max(rows, key=lambda f: float(f[2]) * float(f[3]))
                embedding = rec.embed(frame, frow, self._cv2)
                embeddings.append(embedding)
            if not embeddings:
                return None, n_faces
            centroid = np.mean(embeddings, axis=0)
            return centroid / (np.linalg.norm(centroid) + 1e-12), n_faces

        try:
            centroid_left, count_left = side_centroid(-1)
            centroid_right, count_right = side_centroid(+1)
        except Exception:
            log.warning("face identity inference failed at t=%.3f", t, exc_info=True)
            return None
        if centroid_left is None or centroid_right is None:
            return dict(cos=None, verdict="unknown",
                        n_faces_left=count_left, n_faces_right=count_right)
        cosine = float(centroid_left @ centroid_right)
        verdict = _identity_verdict(cosine, count_left, count_right, cos_thresh)
        return dict(cos=round(cosine, 4), verdict=verdict,
                    n_faces_left=count_left, n_faces_right=count_right)
