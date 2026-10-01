# -*- coding: utf-8 -*-
"""attr_lab_arm_timestamped — 打包态归因第二步的「实验室对照臂」：给 venv 直跑加时间戳。

为什么需要：现有两个总数（venv 1396.7s / 打包 E2E 3756.7s）都没有**阶段级**分解，
无法判断环境罚落在哪一段。打包 E2E 的阶段边界可以从包内后端日志的逐分钟行数复原
（切分 121.5s / 逐段主循环 ~19min / 后处理精修 ~42min），但 venv 侧 `rerun_split_patch_arms.py`
的进度打印不带时刻。本脚本不复制任何测量逻辑，只把该脚本的 stdout 逐行加上 elapsed 秒，
得到同口径的阶段分解；同时把既有产物改名留痕（rerun 脚本在 SVL_FORCE_RERUN=1 下会覆盖同名文件）。

前置（硬断言，不满足直接退出）：
- 不得有打包后端/UI 在跑（backend.exe / Video Locator.exe）——否则两臂互相污染；
- DirectML 生效由被包跑的 rerun 脚本自己断言。

Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/attr_lab_arm_timestamped.py [case]
产物：work/pkg_attr/armA2_lab.<console.log,armB_prev.results.json>
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
PY = Path(r"D:\claudework\video-dedup-tool\.venv\Scripts\python.exe")
OUT = BENCH / "work" / "pkg_attr"
ARMS_DIR = BENCH / "work" / "spl_patch_arms"


def named_images() -> list[str]:
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace", check=False).stdout
    except OSError:
        return []
    return [ln.split(",")[0].strip('"') for ln in out.splitlines() if ln.strip()]


def main() -> int:
    case = sys.argv[1] if len(sys.argv) > 1 else "test2"
    imgs = named_images()
    clash = [n for n in ("backend.exe", "Video Locator.exe") if n in imgs]
    assert not clash, "实验室对照臂要求打包态未在跑，发现 %s" % clash

    OUT.mkdir(parents=True, exist_ok=True)
    console = OUT / "armA2_lab.console.log"
    prev = ARMS_DIR / ("on_%s.results.json" % case)
    kept = OUT / ("armA2_prev_%s.results.json" % case)
    if prev.exists() and not kept.exists():
        kept.write_bytes(prev.read_bytes())  # 留痕：rerun 会覆盖同名产物
        print("[backup] %s -> %s" % (prev.name, kept.name), flush=True)

    env = {**os.environ, "SVL_FORCE_RERUN": "1", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.Popen([str(PY), str(BENCH / "mvp" / "scripts" / "rerun_split_patch_arms.py"),
                             "on", case], cwd=str(BENCH), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", bufsize=1)
    t0 = time.monotonic()
    with console.open("w", encoding="utf-8") as f:
        for line in proc.stdout:
            stamped = "[+%7.1fs] %s" % (time.monotonic() - t0, line.rstrip("\n"))
            print(stamped, flush=True)
            f.write(stamped + "\n")
            f.flush()
    rc = proc.wait()
    print("[exit] rc=%s total=%.1fs -> %s" % (rc, time.monotonic() - t0, console.name), flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
