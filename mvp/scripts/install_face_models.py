# -*- coding: utf-8 -*-
"""安装人脸身份标注资产（候选 B）到 ``models_root()/face/``。

源 = 本仓研究探针目录 ``work/face_probe_20261024/models/``（YuNet 2023mar 232,589B +
SFace 2021dec 38,696,353B；SFace 2023mar 官方 404，见 FINDINGS_GT_PATCH_PROBES §3 权重注记）。
目标缺失才复制（幂等）；逐文件校验字节数。资产不在 git / 不进包 ⇒ 首跑缺失时
face_identity 整层降级不标注（engine/face_identity.py resolve_face_models → None）。

  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/install_face_models.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8")

SRC = Path(__file__).resolve().parents[2] / "work/face_probe_20261024/models"
FILES = {"face_detection_yunet_2023mar.onnx": 232589,
         "face_recognition_sface_2021dec.onnx": 38696353}


def main() -> int:
    from infrastructure.paths import models_root
    dst = models_root() / "face"
    dst.mkdir(parents=True, exist_ok=True)
    for name, size in FILES.items():
        s, t = SRC / name, dst / name
        if t.exists() and t.stat().st_size == size:
            print("OK    %s (already installed, %dB)" % (t, size))
            continue
        if not s.exists():
            print("MISS  %s (source not found)" % s)
            return 1
        shutil.copy2(s, t)
        assert t.stat().st_size == size, (t.stat().st_size, size)
        print("COPY  %s -> %s (%dB)" % (s.name, t, size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
