# -*- coding: utf-8 -*-
"""安装 SCRFD + ArcFace 人脸身份资产到 ``models_root()/face/``。

目标缺失才复制（幂等）；逐文件校验字节数。资产不在 git / 不进包 ⇒ 首跑缺失时
face_identity 整层降级不标注（engine/face_identity.py resolve_face_models → None）。

  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/install_face_models.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8")

SRC = Path(__file__).resolve().parents[2] / "work/_research/face-reidentification/weights"
FILES = {"det_2.5g.onnx": 3292009,
         "w600k_mbf.onnx": 13616099}


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
