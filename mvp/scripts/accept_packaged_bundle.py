# -*- coding: utf-8 -*-
"""accept_packaged_bundle — 分发包装配验收（打包后必跑，缺项即失败）。

为什么要这个脚本：2026-10-01 的打包态归因发现，分发包里**没有** DML patch 双输出 ONNX，
`resolve_patch_onnx()` 找不到就静默回退 CPU torch，整条定位慢 2.6~3.9x（包内日志
`patch reranker device=cpu` vs 源码树 `device=dml`），而当时的打包验收只看「起得来、
跑得完」，瞒了两周。验收口径因此加两条硬断言：资产在位且摘要对得上、跑起来精排在 GPU。

用法（venv python 绝对路径）:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/accept_packaged_bundle.py
退出码 0 = 全部通过；非 0 = 有失败项（最后一行汇总 FAILED 计数）。
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
VENV_PY = Path(r"D:\claudework\video-dedup-tool\.venv\Scripts\python.exe")
RES = BENCH / "mvp" / "ui" / "release" / "win-unpacked" / "resources"
PATCH_DIR = RES / "models" / "dinov2_cls_patch"
# 合成素材冒烟：venv 直跑约 20s；CPU torch 回退实测 78.5s。阈值取中间，判「有没有回退」。
SMOKE_WALL_S = 45.0

fails: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print("[%s] %s %s" % ("PASS" if ok else "FAIL", name, detail), flush=True)
    if not ok:
        fails.append(name)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    exe = RES / "backend" / "backend.exe"
    check("包内后端存在", exe.exists(), str(exe))
    if not exe.exists():
        print("FAILED=1")
        return 1

    manifest = PATCH_DIR / "asset.json"
    check("patch 资产清单在位", manifest.exists(), str(manifest))
    graph = PATCH_DIR / "dinov2_cls_patch.onnx"
    data = PATCH_DIR / "dinov2_cls_patch.onnx.data"
    check("patch 图在位", graph.exists(), "%s bytes" % (graph.stat().st_size if graph.exists() else "-"))
    check("patch 外部权重在位", data.exists(),
          "%s bytes" % (data.stat().st_size if data.exists() else "-"))
    if manifest.exists() and graph.exists() and data.exists():
        want = json.loads(manifest.read_text(encoding="utf-8")).get("sha256", {})
        for fname, digest in want.items():
            f = PATCH_DIR / fname
            check("sha256 %s" % fname, f.exists() and sha256(f) == digest,
                  "" if f.exists() else "文件缺失")

    # 用与 Electron 主进程相同的接法起包内后端，跑合成素材冒烟
    env = {**os.environ, "SVL_PATCH_ONNX": str(graph)}
    tmp_data = BENCH / "work" / "pkg_attr" / "accept_data"
    cmd = [str(VENV_PY), str(BENCH / "mvp" / "scripts" / "attr_packaged_headless.py"),
           "syn", "1.0", str(tmp_data), "packaged"]
    print("[run] attr_packaged_headless.py syn（包内 backend.exe + SVL_PATCH_ONNX）...", flush=True)
    rc = subprocess.run(cmd, cwd=str(BENCH), env=env, capture_output=True,
                        text=True, encoding="utf-8", errors="replace").returncode
    check("冒烟退出码 0", rc == 0, "rc=%s" % rc)

    summary_path = BENCH / "work" / "pkg_attr" / "headless_syn.summary.json"
    stdout_log = BENCH / "work" / "pkg_attr" / "headless_syn.backend_stdout.log"
    if summary_path.exists() and stdout_log.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        text = stdout_log.read_text(encoding="utf-8", errors="replace")
        check("DirectML 生效", "backend selected=directml" in text,
              "wall=%.1fs" % summary.get("wall_s", -1))
        check("精排在 GPU（未回退 CPU torch）", "patch reranker device=dml" in text,
              "出现 device=cpu 即为静默降级" if "patch reranker device=cpu" in text else "")
        check("冒烟耗时在阈值内", summary.get("wall_s", 1e9) <= SMOKE_WALL_S,
              "%.1fs <= %.1fs" % (summary.get("wall_s", 1e9), SMOKE_WALL_S))
        check("定位出结果", summary.get("segments", 0) > 0, "segments=%s" % summary.get("segments"))
    else:
        check("冒烟产物可读", False, str(summary_path))

    print("FAILED=%d" % len(fails), flush=True)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
