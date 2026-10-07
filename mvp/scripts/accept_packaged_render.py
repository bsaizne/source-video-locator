# -*- coding: utf-8 -*-
"""accept_packaged_render — 包内**成片通道**验收（出包后必跑，缺项即失败）。

为什么单独有这条：成片渲染是四个产物出口里最贵的一个，r14/r15 的 accept 主脚本用
`syn` 合成素材冒烟（只出 1 段），**构造不出多段拼接形态** ⇒ 成片通道从来没在包里被
真跑过。2026-10-07 续63 把三处计划序列收口成 `prepare_channel_plan`（`render_movie`
是调用方之一），收口本身没改语义要靠包内实测才算闭合——顺带正是这一趟抓到
`submit_render` 漏传 `isolated`（渲染从未进隔离子进程，而档案写的是"analyze/render 都隔离"）。

判据（默认门槛，与产品一致）：
  R1 渲染任务 completed；
  R2 **渲染确实走隔离子进程**（包内日志有 `isolated child started`，且无 spawn 回落留痕）；
  R3 无 `DIED without envelope`（没被误判硬崩）；
  R4 成片时长 ≈ Σ 实际渲染 clip 宽度（±0.8s）——拼接没多也没少；
  R5 成片顺序里**紧邻段无源区间交叠**（重复画面会在成片里播两遍，这条是产物级守门）；
  R6 编码器为硬件 AMF（降档/回退不该把成片拉回 CPU 编码）。

前置：本机有 2.mkv/1.mpv 真素材与已建索引（缺则 skip 并退 0，登记为"未实测"）。
Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/accept_packaged_render.py
"""
from __future__ import annotations

import json
import os
import queue
import secrets
import subprocess
import sys
import time
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from attr_packaged_headless import (EXE_DIR, RES_DIR, appdata_dir, http,  # noqa: E402
                                    spawn_stdout_drain, wait_backendListen)

OUT = BENCH / "work" / "pkg_render_accept"
RESULTS = BENCH / "work" / "stable_sort_regress" / "2mkv.results.json"
fails: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print("[%s] %s %s" % ("PASS" if ok else "FAIL", name, detail), flush=True)
    if not ok:
        fails.append(name)


def main() -> int:
    raw = json.loads(RESULTS.read_text(encoding="utf-8"))
    ed, om = Path(raw["original_video"]), Path(raw["edited_video"])
    if not (ed.exists() and om.exists()):
        print(f"[skip] 真素材不在位（{ed} / {om}）⇒ 成片包体实测**未闭合**，请登记")
        return 0
    exe = EXE_DIR / "backend.exe"
    assert exe.exists(), f"包内后端不存在: {exe}"

    out_dir = OUT / "movie"
    if out_dir.exists():
        subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", str(out_dir)], check=False)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir = OUT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(24)
    env = {
        **os.environ,
        "MEDIA_FFMPEG": str(EXE_DIR / "ffmpeg.exe"),
        "MEDIA_FFPROBE": str(EXE_DIR / "ffprobe.exe"),
        "SVL_DATA_DIR": str(appdata_dir()),
        "SVL_LOG_DIR": str(log_dir),
        "SVL_SESSION_TOKEN": token,
        "SVL_BUILD_CHANNEL": "release",
        "SVL_BACKEND_PORT": "0",
        "SVL_DML_MODEL": str(RES_DIR / "models" / "dinov2_cls_384" / "dinov2_cls_384.onnx"),
        "SVL_PATCH_ONNX": str(RES_DIR / "models" / "dinov2_cls_patch" / "dinov2_cls_patch.onnx"),
        "SVL_ISC_ONNX": str(RES_DIR / "models" / "isc_ft_v107" / "isc_ft_v107.onnx"),
    }
    stdout_log = OUT / "backend_stdout.log"
    proc = subprocess.Popen([str(exe)], cwd=str(EXE_DIR), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", bufsize=1)
    listen_q: "queue.Queue" = queue.Queue()
    report: dict = {}
    try:
        with stdout_log.open("w", encoding="utf-8") as logf:
            spawn_stdout_drain(proc, logf, listen_q)
            host, port = wait_backendListen(proc, listen_q, timeout=180.0)
            base = "http://%s:%d" % (host, port)
            d = http(base, token, "GET", "/api/settings/device")
            check("DirectML 生效", d.get("actual_device_name") == "directml"
                  and not d.get("fallback"), str(d.get("actual_device_name")))
            http(base, token, "POST", "/api/results/load", {"path": str(RESULTS)})
            t0 = time.monotonic()
            task = http(base, token, "POST", "/api/tasks/render", {"output_dir": str(out_dir)})
            tid = task["task_id"]
            while True:
                st = http(base, token, "GET", f"/api/tasks/{tid}", timeout=300.0)
                if st.get("status") in ("completed", "failed", "cancelled"):
                    break
                if proc.poll() is not None:
                    raise RuntimeError("backend 渲染中途退出")
                time.sleep(3.0)
            wall = time.monotonic() - t0
            info = st.get("result") or {}
            check("R1 渲染任务完成", st.get("status") == "completed",
                  f"status={st.get('status')} wall={wall:.0f}s err={st.get('error')}")

            ranges = [[float(a), float(b)] for a, b in (info.get("clip_ranges") or [])]
            check("R5a 成片紧邻段无源区间交叠",
                  all(min(a[1], b[1]) - max(a[0], b[0]) <= 0 for a, b in zip(ranges, ranges[1:])),
                  f"{len(ranges)} 段")
            total = round(sum(b - a for a, b in ranges), 3)
            dur = 0.0
            if info.get("movie_path"):
                r = subprocess.run([str(EXE_DIR / "ffprobe.exe"), "-v", "error",
                                    "-show_entries", "format=duration",
                                    "-of", "default=nw=1:nk=1", str(info["movie_path"])],
                                   capture_output=True, text=True)
                dur = float((r.stdout or "0").strip() or 0.0)
            check("R4 成片时长 ≈ Σ clip 宽度", abs(dur - total) <= 0.8,
                  f"{dur:.3f}s vs {total}s（±0.8s）")
            check("R6 硬件编码器在位", "amf" in str(info.get("actual_encoder", "")).lower(),
                  f"encoder={info.get('actual_encoder')} mode={info.get('mode')}")
            report = {"segments": info.get("segments"), "clips": len(ranges),
                      "sum_width_s": total, "probed_duration_s": round(dur, 3),
                      "encoder": info.get("actual_encoder"), "wall_s": round(wall, 1),
                      "movie_path": info.get("movie_path")}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except Exception:
            proc.kill()

    text = stdout_log.read_text(encoding="utf-8", errors="replace")
    check("R2 渲染走了隔离子进程（submit_render 传了 isolated）",
          "isolated child started pid=" in text,
          "缺启动行=渲染仍在线程内跑（崩溃会拖垮后端）")
    check("R2b 未静默回落线程内", "spawn unavailable" not in text,
          "出现=spawn 起不来，隔离性等于没有")
    check("R3 子进程未被误判硬崩", "isolated child DIED without envelope" not in text)
    (OUT / "report.json").write_text(json.dumps({"report": report, "fails": fails},
                                                ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    print(f"\n留证 = {OUT / 'report.json'}")
    print(f"FAILED={len(fails)} {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    sys.exit(main())
