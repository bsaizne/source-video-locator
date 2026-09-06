# -*- coding: utf-8 -*-
"""编辑侧分析持久缓存（A4 性能优化, 2026-09-05）。

缓存内容（全部为确定性派生物, 键 = 文件身份 + 特征口径 + 管线配置指纹）:
  - shots: 两级切分产物（span/card_ratio/card_run_ratio + 2fps 特征/时间）
  - dense: 每段 8fps 密帧特征（seq_align/finloc 输入, 首跑最大头之一）

失效: 路径/size/mtime/feature_version/设备口径(类型+batch)/PipelineConfig 任一变化 → 新键,
旧文件自然过期（不删除）。写入原子化（临时文件 + rename）。零语义: 命中与未命中产出逐字节一致
（float32 原样存取, 不做量化）。
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np

_SCHEMA = "edited_cache_v1"


def fingerprint(edited: Path, feature_version: str, pipeline_dict: dict, device_tag: str) -> str:
    """缓存键: 文件身份 + 特征口径 + 管线配置 + 设备口径 的 sha1。"""
    st = edited.stat()
    payload = json.dumps({
        "schema": _SCHEMA,
        "path": str(edited).lower(),
        "size": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "fv": feature_version,
        "device": device_tag,
        "cfg": json.dumps(pipeline_dict, sort_keys=True, ensure_ascii=False),
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


class EditedCache:
    """单文件单 npz 的编辑侧缓存（shots.npz + dense.npz）。损坏/缺 schema 视为未命中。"""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # ---- shots ----
    def _shots_path(self, key: str) -> Path:
        return self.root / f"shots_{key}.npz"

    def load_shots(self, key: str):
        """返回 (shots_dicts, ) 或 None。shots_dicts 元素:
        {start,end,card_ratio,card_run_ratio,feats,times}（float32/float64 原样）。"""
        p = self._shots_path(key)
        if not p.exists():
            return None
        try:
            with np.load(p, allow_pickle=False) as z:
                if str(z["schema"]) != _SCHEMA:
                    return None
                n = int(z["n_shots"])
                shots = []
                for i in range(n):
                    shots.append({
                        "start": float(z[f"s{i}_start"]), "end": float(z[f"s{i}_end"]),
                        "card_ratio": float(z[f"s{i}_card"]), "card_run_ratio": float(z[f"s{i}_cardrun"]),
                        "feats": np.asarray(z[f"s{i}_feats"], dtype=np.float32),
                        "times": np.asarray(z[f"s{i}_times"], dtype=np.float64),
                    })
                return shots
        except Exception:
            return None

    def save_shots(self, key: str, shots: list[dict]) -> None:
        out = {"schema": np.array(_SCHEMA), "n_shots": np.array(len(shots))}
        for i, s in enumerate(shots):
            out[f"s{i}_start"] = np.float64(s["start"])
            out[f"s{i}_end"] = np.float64(s["end"])
            out[f"s{i}_card"] = np.float64(s["card_ratio"])
            out[f"s{i}_cardrun"] = np.float64(s["card_run_ratio"])
            out[f"s{i}_feats"] = np.asarray(s["feats"], dtype=np.float32)
            out[f"s{i}_times"] = np.asarray(s["times"], dtype=np.float64)
        self._atomic_save(self._shots_path(key), out)

    # ---- dense ----
    def _dense_path(self, key: str) -> Path:
        return self.root / f"dense_{key}.npz"

    @staticmethod
    def dense_key(span_start: float, span_end: float) -> str:
        return f"{round(span_start, 2):.2f}_{round(span_end, 2):.2f}"

    def load_dense(self, key: str, dkey: str):
        p = self._dense_path(key)
        if not p.exists():
            return None
        try:
            with np.load(p, allow_pickle=False) as z:
                if f"d{dkey}_f" not in z.files:
                    return None
                return (np.asarray(z[f"d{dkey}_f"], dtype=np.float32),
                        np.asarray(z[f"d{dkey}_t"], dtype=np.float64))
        except Exception:
            return None

    def save_dense(self, key: str, dkey: str, feats: np.ndarray, times: np.ndarray) -> None:
        p = self._dense_path(key)
        out = {}
        if p.exists():
            try:
                with np.load(p, allow_pickle=False) as z:
                    out = {k: z[k] for k in z.files}
            except Exception:
                out = {}
        out["schema"] = np.array(_SCHEMA)
        out[f"d{dkey}_f"] = np.asarray(feats, dtype=np.float32)
        out[f"d{dkey}_t"] = np.asarray(times, dtype=np.float64)
        self._atomic_save(p, out)

    @staticmethod
    def _atomic_save(path: Path, arrays: dict) -> None:
        tmp = path.with_suffix(f".tmp{os.getpid()}")
        try:
            with open(tmp, "wb") as f:
                np.savez(f, **arrays)
            os.replace(tmp, path)
        except Exception:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
