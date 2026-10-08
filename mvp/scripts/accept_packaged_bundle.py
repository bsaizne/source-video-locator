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
ISC_DIR = RES / "models" / "isc_ft_v107"
# 合成素材冒烟：venv 直跑约 20s；CPU torch 回退实测 78.5s。阈值取中间，判「有没有回退」。
# 2026-10-03 续44 ISC 翻默认：冒烟额外跑 ISC 重扫（EffNetV2-M@512），阈值放宽到 75s。
SMOKE_WALL_S = 75.0
# 腿边界埋点的 12 条腿，**按执行顺序**（2026-10-08 续63 补九 ①）。
# 与 `mvp/tests/test_locator_service.py::LocateLegLoggingTest.LEGS` 同源，两处必须同改
# （改了不改另一处 = 要么包侧锁假绿，要么单测抓不到顺序回归）。
EXPECT_LEGS = ("global_anchor", "dense_recheck", "text_anchor", "seq_rerank",
               "temporal_repair", "conflict_rerank", "temporal_ambiguity",
               "consecutive_resolve", "degradation_gate",
               "shot_split", "patch_refine", "isc_refine")


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

    # ISC 第二意见资产（2026-10-03 续44 翻默认；缺 = isc_refine 整体跳过，精度回退到续44 前）
    isc_manifest = ISC_DIR / "asset.json"
    check("ISC 资产清单在位", isc_manifest.exists(), str(isc_manifest))
    isc_graph = ISC_DIR / "isc_ft_v107.onnx"
    isc_data = ISC_DIR / "isc_ft_v107.onnx.data"
    check("ISC 图在位", isc_graph.exists(),
          "%s bytes" % (isc_graph.stat().st_size if isc_graph.exists() else "-"))
    check("ISC 外部权重在位", isc_data.exists(),
          "%s bytes" % (isc_data.stat().st_size if isc_data.exists() else "-"))
    if isc_manifest.exists() and isc_graph.exists() and isc_data.exists():
        isc_want = json.loads(isc_manifest.read_text(encoding="utf-8")).get("sha256", {})
        for fname, digest in isc_want.items():
            f = ISC_DIR / fname
            check("sha256 %s" % fname, f.exists() and sha256(f) == digest,
                  "" if f.exists() else "文件缺失")

    # 用与 Electron 主进程相同的接法起包内后端，跑合成素材冒烟
    env = {**os.environ, "SVL_PATCH_ONNX": str(graph), "SVL_ISC_ONNX": str(isc_graph)}
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
        check("ISC 第二意见在 GPU", "isc refine device=dml" in text,
              "出现 device=cpu 即 ISC 降级" if "isc refine device=cpu" in text else "")
        check("冒烟耗时在阈值内", summary.get("wall_s", 1e9) <= SMOKE_WALL_S,
              "%.1fs <= %.1fs" % (summary.get("wall_s", 1e9), SMOKE_WALL_S))
        check("定位出结果", summary.get("segments", 0) > 0, "segments=%s" % summary.get("segments"))
        # 打包态任务级进程隔离（六项立项 ④，2026-10-07 续62 补六；r14 及以前没有此项 ⇒ 红）：
        # PyInstaller 下 spawn 子进程必须起得来（入口 freeze_support 已接），
        # 证据 = 包内后端 stdout 的隔离启动行。起不来会静默回落线程内执行，
        # 那正是本项要防的「一崩全崩」形态，所以回落也算失败。
        check("打包态任务隔离子进程在跑（spawn）",
              "isolated child started pid=" in text,
              "缺启动行=未隔离或 spawn 回落线程（r14 无此项属预期红）")
        # 子进程不走 ASGI lifespan ⇒ 必须自己 configure_logging()。漏了它，root logger
        # 无 handler，INFO 被 lastResort 丢弃：包内 stdout 与支持档 video_locator.log
        # 一起失去分析过程记录（2026-10-07 r15 accept 首跑实测，靠下面这条硬断言抓到）。
        check("隔离子进程日志进得到包内（INFO 未被吞）",
              "isolated child booted pid=" in text,
              "缺此行=子进程没配日志，售后档会缺整段分析记录")
        # 收割状态只作信息打印，不做硬断言：正常终态路径父进程会先等子进程自然退出
        # （CHILD_GRACE_S），而本冒烟在任务 completed 后立刻收后端 ⇒ 这行常常来不及打。
        # 真正要守的是「任务成功 + 子进程日志齐」，已由上面三条覆盖。
        reaped = [ln for ln in text.splitlines() if "isolated child reaped" in ln]
        print("[info] 隔离子进程收割：%s" % (reaped[-1].split(" - ")[-1] if reaped
                                            else "未打印（冒烟先收了后端，正常）"), flush=True)
        check("隔离子进程未被误判为硬崩",
              "isolated child DIED without envelope" not in text,
              "出现即子进程崩了没留信封")

        # ---- 包侧观测面锁（2026-10-08 续63 补九 ①，r17 起）------------------ #
        # 进度事件此前**完全不落日志** ⇒ 售后拿到支持档看不出「进度卡在哪条腿」。
        # 现每次 locate 落 12 行 `locate leg=<名> elapsed=… units=a->b/48 chain=…` + 链首一行
        # `locate refine start legs=<12 个开关>`。这三条断言 = 该修复**真的进了包**并且
        # **在包内落盘到支持档文件**（不是只在 stdout；stdout 与文件走同一 logger 但
        # 只有文件是售后能拿到的东西，续63 补二/补八 就是被这个区分坑过两次）。
        # 读**最后一次 locate 的窗口**：该档是追加式，历次冒烟会累积 ⇒ 全文计数会假绿。
        support = BENCH / "work" / "pkg_attr" / "logs" / "video_locator.log"
        if support.exists():
            import re as _re
            st = support.read_text(encoding="utf-8", errors="replace")
            cut = st.rfind("locate started")
            win = st[cut:] if cut != -1 else ""
            legs = [_re.search(r"locate leg=(\w+)", l) for l in win.splitlines()]
            legs = [m.group(1) for m in legs if m]
            check("腿边界埋点进包并落支持档（一次 locate 12 行）",
                  legs == list(EXPECT_LEGS),
                  "实得 %d 行 %s（r16 及以前=0 行，属预期红）" % (len(legs), legs))
            units = [int(m.group(1)) for m in
                     (_re.search(r"units=\d+->(\d+)/48", l) for l in win.splitlines()
                      if "locate leg=" in l) if m]
            check("腿刻度只增不减（48 单位口径自洽）", units == sorted(units), "实得 %s" % units)
            check("链首开关行在位（legs=…，售后可判某腿跑没跑）",
                  "locate refine start" in win,
                  "" if "locate refine start" in win else "缺此行=只落了腿行没落开关行")
        else:
            check("支持档存在（腿边界埋点判据依赖它）", False, str(support))

    else:
        check("冒烟产物可读", False, str(summary_path))

    print("FAILED=%d" % len(fails), flush=True)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
