# -*- coding: utf-8 -*-
"""verify_model_asset_shas — 按 asset.json 的 sha256 锁逐个校验模型资产。

用途两处：
- 本地/CI 在把资产放进 `mvp/ui/resources/models/` 之后跑一遍 ⇒ 传错包不了（构建前就红）；
- mac 打包链尤其需要：patch/ISC 的 `.data` 外部权重不入库（ISC 209MB 超 GitHub 单文件硬限），
  由 CI 从 `model-assets` release 下载 ⇒ 下载完整性必须有独立判据，不能只看 curl 退出码。

用法: python mvp/scripts/verify_model_asset_shas.py <dir> [<dir> ...]
      dir = 含 asset.json 的模型目录（如 mvp/ui/resources/models/isc_ft_v107）
退出码 0 = 全过；1 = 有缺项或摘要不符（最后一行 FAILED=<n>）。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    dirs = [Path(a) for a in sys.argv[1:]]
    if not dirs:
        print("用法: verify_model_asset_shas.py <dir> [<dir> ...]")
        return 2
    fails = 0
    for d in dirs:
        man = d / "asset.json"
        if not man.is_file():
            print("[FAIL] 缺清单 %s" % man)
            fails += 1
            continue
        want = json.loads(man.read_text(encoding="utf-8")).get("sha256", {})
        if not want:
            print("[FAIL] %s 里没有 sha256 段" % man)
            fails += 1
            continue
        for name, digest in want.items():
            p = d / name
            if not p.is_file():
                print("[FAIL] 缺文件 %s" % p)
                fails += 1
                continue
            got = sha256_of(p)
            if got != digest:
                print("[FAIL] 摘要不符 %s got=%s want=%s" % (p, got[:16], digest[:16]))
                fails += 1
            else:
                print("[PASS] %s (%d B)" % (p, p.stat().st_size))
    print("FAILED=%d" % fails)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
