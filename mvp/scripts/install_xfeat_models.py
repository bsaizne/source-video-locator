# -*- coding: utf-8 -*-
"""安装 XFeat + LighterGlue 资产到 models_root()/xfeat/。"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8")

SRC = Path(__file__).resolve().parents[2] / "work/_research/accelerated_features/weights"
FILES = {"xfeat.pt": 6247949, "xfeat-lighterglue.pt": 10820795}


def main() -> int:
    from infrastructure.paths import models_root

    destination = models_root() / "xfeat"
    destination.mkdir(parents=True, exist_ok=True)
    for name, size in FILES.items():
        source, target = SRC / name, destination / name
        if target.exists() and target.stat().st_size == size:
            print("OK    %s (already installed, %dB)" % (target, size))
            continue
        if not source.exists():
            print("MISS  %s (source not found)" % source)
            return 1
        shutil.copy2(source, target)
        assert target.stat().st_size == size, (target.stat().st_size, size)
        print("COPY  %s -> %s (%dB)" % (source.name, target, size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
